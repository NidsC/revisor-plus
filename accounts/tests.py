"""Regression coverage for the parent dashboard's child-scoped progress links."""
import re
from io import StringIO
from types import SimpleNamespace
from unittest import mock

from allauth.account.models import EmailAddress
from allauth.core import context as allauth_context
from allauth.socialaccount.adapter import get_adapter as get_social_adapter
from allauth.socialaccount.helpers import complete_social_login
from allauth.socialaccount.models import SocialAccount, SocialLogin
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from accounts.consent import CURRENT_TERMS_VERSION, needs_acceptance, record_acceptance
from accounts.models import User
from assignments.models import Assignment
from billing.models import Subscription
from catalog.models import Section, Subtopic, Question, AnswerOption
from practice.models import Attempt, TestSession
from tutoring.models import TutorStudent, TutorMessage

from config.mail import MailNotConfigured, UnconfiguredEmailBackend, backend_for


@override_settings(PREMIUM_GATES_ENABLED=False)
class FamilyDashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.parent = User.objects.create_user(username="parent", email="parent@example.test", role="parent")
        cls.other_parent = User.objects.create_user(username="other", email="other@example.test", role="parent")
        cls.pupil = User.objects.create(username="ben", full_name="Ben", parent=cls.parent, role="student")
        cls.sibling = User.objects.create(username="sibling", full_name="Maya", parent=cls.parent, role="student")
        cls.unrelated = User.objects.create(username="other-child", parent=cls.other_parent, role="student")
        cls.tutor = User.objects.create_user(username="tutor", email="tutor@example.test", full_name="Sam", role="tutor")
        for i, (code, name) in enumerate([("MAT", "Maths"), ("ENG", "English"), ("VR", "Verbal Reasoning"), ("NVR", "Non-Verbal Reasoning")]):
            Section.objects.create(code=code, name=name, order=i)
        cls.section = Section.objects.get(code="MAT")
        cls.topic = Subtopic.objects.create(section=cls.section, name="Fractions", topic="Number")
        cls.question = Question.objects.create(subtopic=cls.topic, stem="What is half of 8?")
        AnswerOption.objects.create(question=cls.question, text="4", is_correct=True)
        session = TestSession.objects.create(student=cls.pupil, subtopic=cls.topic)
        for _ in range(3):
            Attempt.objects.create(student=cls.pupil, session=session, question=cls.question,
                                   subtopic=cls.topic, is_correct=True, marks_earned=1)
        cls.link = TutorStudent.objects.create(student=cls.pupil, tutor=cls.tutor)

    def setUp(self):
        self.client.force_login(self.parent)
        self.child_url = reverse("family:child", args=[self.pupil.pk])
        self.subjects_url = reverse("family:child_subjects", args=[self.pupil.pk])
        self.homework_url = reverse("family:child_homework", args=[self.pupil.pk])
        self.messages_url = reverse("family:child_messages", args=[self.pupil.pk])
        self.subject_url = reverse("family:child_subject", args=[self.pupil.pk, "MAT"])

    def test_child_links_use_selected_child(self):
        response = self.client.get(self.subjects_url)
        self.assertEqual(response.status_code, 200)
        for code in ["MAT", "ENG", "VR", "NVR"]:
            self.assertContains(response, reverse("family:child_subject", args=[self.pupil.pk, code]))
        self.assertNotContains(response, 'href="/practice/subject/')

    def test_parent_sees_child_data_and_cannot_start_from_read_only_view(self):
        response = self.client.get(self.subject_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["pupil"], self.pupil)
        topic = response.context["subtopics"][0]
        self.assertEqual((topic["attempted"], topic["accuracy"]), (3, 100))
        self.assertContains(response, "Ben's subject progress")
        self.assertNotContains(response, 'id="practiceModal"')
        self.assertNotContains(response, 'href="/practice/start/')
        self.assertContains(response, f'href="{self.subjects_url}"')

    def test_siblings_have_separate_results(self):
        response = self.client.get(reverse("family:child_subject", args=[self.sibling.pk, "MAT"]))
        self.assertEqual(response.context["subtopics"][0]["attempted"], 0)
        self.assertIsNone(response.context["subtopics"][0]["accuracy"])

    def test_other_parents_cannot_open_child_or_subject(self):
        self.client.force_login(self.other_parent)
        self.assertEqual(self.client.get(self.child_url).status_code, 403)
        self.assertEqual(self.client.get(self.subject_url).status_code, 403)

    def test_pupil_and_tutor_cannot_open_parent_routes(self):
        for user in [self.pupil, self.tutor]:
            self.client.force_login(user)
            self.assertEqual(self.client.get(self.child_url).status_code, 403)
            self.assertEqual(self.client.get(self.subjects_url).status_code, 403)
            self.assertEqual(self.client.get(self.homework_url).status_code, 403)
            self.assertEqual(self.client.get(self.messages_url).status_code, 403)
            self.assertEqual(self.client.get(self.subject_url).status_code, 403)

    def test_unauthenticated_visitors_are_redirected(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.subject_url).status_code, 302)

    def test_missing_child_or_subject_returns_404(self):
        self.assertEqual(self.client.get(reverse("family:child_subject", args=[9999, "MAT"])).status_code, 404)
        self.assertEqual(self.client.get(reverse("family:child_subject", args=[self.pupil.pk, "UNKNOWN"])).status_code, 404)

    @override_settings(PREMIUM_GATES_ENABLED=True)
    def test_parent_detail_keeps_premium_gate(self):
        self.assertRedirects(self.client.get(self.subject_url), self.child_url)

    def test_zero_attempts_have_empty_state_not_zero_accuracy(self):
        response = self.client.get(reverse("family:child_subjects", args=[self.sibling.pk]))
        self.assertContains(response, "A fresh start in maths.")
        self.assertRegex(response.content.decode(), r"<strong\b[^>]*>\s*—\s*</strong>")
        self.assertNotContains(response, "0% current accuracy")

    def test_homework_can_be_created_and_removed(self):
        self.client.post(self.homework_url, {"action": "add_homework", "subtopic": self.topic.pk,
                         "target_count": "8", "due_date": (timezone.localdate() + timedelta(days=7)).isoformat()})
        assignment = Assignment.objects.get(student=self.pupil)
        self.assertEqual(assignment.target_count, 8)
        self.assertEqual(assignment.tutor, self.parent)
        self.client.post(self.homework_url, {"action": "delete_homework", "assignment_id": assignment.pk})
        self.assertFalse(Assignment.objects.filter(pk=assignment.pk).exists())

    def test_parent_cannot_remove_tutor_homework(self):
        assignment = Assignment.objects.create(student=self.pupil, tutor=self.tutor, subtopic=self.topic,
                                               due_date=timezone.localdate())
        self.assertEqual(self.client.post(self.homework_url, {"action": "delete_homework", "assignment_id": assignment.pk}).status_code, 404)
        self.assertTrue(Assignment.objects.filter(pk=assignment.pk).exists())

    def test_tutor_message_stays_with_selected_child(self):
        self.client.post(self.messages_url, {"action": "send_tutor_message", "message": "Could we review fractions?"})
        message = TutorMessage.objects.get()
        self.assertEqual(message.link, self.link)
        self.assertEqual(message.sender, self.parent)
        self.assertContains(self.client.get(self.messages_url), "Could we review fractions?")

    def test_child_dashboard_is_split_into_clear_pages(self):
        overview = self.client.get(self.child_url)
        self.assertContains(overview, "Parent summary")
        self.assertNotContains(overview, "Set work for Ben")
        self.assertNotContains(overview, "Chat with Ben's tutor")

        subjects = self.client.get(self.subjects_url)
        self.assertContains(subjects, "What to work on")
        self.assertContains(subjects, "Word Wizard")

        homework = self.client.get(self.homework_url)
        self.assertContains(homework, "Set work for Ben")
        self.assertNotContains(homework, "Chat with Ben's tutor")

        messages_page = self.client.get(self.messages_url)
        self.assertContains(messages_page, "Chat with Ben's tutor")
        self.assertNotContains(messages_page, "Set work for Ben")

    def test_parent_nav_has_family_instead_of_student_tools(self):
        response = self.client.get(reverse("family:home"))
        self.assertContains(response, "My family")
        self.assertNotContains(response, 'href="/practice/"')
        self.assertNotContains(response, 'href="/mocks/"')

    def test_family_home_uses_the_shared_page_header(self):
        html = self.client.get(reverse("family:home")).content.decode()
        self.assertIn('class="rp-page-head"', html)
        self.assertNotIn("rp-family__head", html)

    def test_child_page_uses_the_shared_page_header(self):
        html = self.client.get(self.child_url).content.decode()
        self.assertIn('class="rp-page-head"', html)
        self.assertNotIn("rp-parent__page-head", html)

    @override_settings(PREMIUM_GATES_ENABLED=True, STRIPE_SECRET_KEY="sk_test_x", STRIPE_PRICE_ID="price_x")
    def test_family_subscribe_button_is_full_size_while_pricing_keeps_the_small_one(self):
        # A demand line is what puts the subscribe button on a family card.
        Subscription.objects.create(user=self.pupil, last_mock_blocked_at=timezone.now())
        home = self.client.get(reverse("family:home")).content.decode()
        self.assertIn("Subscribe for Ben", home)
        self.assertIn('class="btn btn-outline-secondary" type="submit">Subscribe for Ben', home)
        self.assertNotIn("btn-brand btn-sm", home)
        pricing = self.client.get(reverse("billing:pricing")).content.decode()
        self.assertIn('class="btn btn-brand btn-sm" type="submit">Subscribe for Ben', pricing)
        child = self.client.get(self.child_url).content.decode()
        self.assertIn('class="btn btn-brand" type="submit">Subscribe for Ben', child)
        self.assertNotIn("btn-brand btn-sm", child)


LOCMEM_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
UNCONFIGURED_BACKEND = "config.mail.UnconfiguredEmailBackend"
MAIL_WARNING = "We couldn&#x27;t send that email just now."


class MailTests(TestCase):
    """Password reset sends through whatever backend is configured and never 500s."""

    @classmethod
    def setUpTestData(cls):
        cls.parent = User.objects.create_user(
            username="mailparent", email="mailparent@example.test", role="parent",
            password="reset-me-please-1234",
        )
        cls.url = reverse("account_reset_password")

    def setUp(self):
        cache.clear()  # allauth rate-limits reset requests per address and per IP

    def _request_reset(self, email):
        return self.client.post(self.url, {"email": email}, follow=True)

    @override_settings(EMAIL_BACKEND=LOCMEM_BACKEND)
    def test_reset_email_is_sent_with_the_project_wording(self):
        response = self._request_reset(self.parent.email)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.request["PATH_INFO"], reverse("account_reset_password_done"))
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertTrue(message.subject.startswith("[RevisorPlus]"), message.subject)
        self.assertIn("Reset your RevisorPlus password", message.subject)
        self.assertIn("/accounts/password/reset/key/", message.body)
        self.assertNotIn("example.com", message.body)
        self.assertEqual(message.from_email, settings.DEFAULT_FROM_EMAIL)
        self.assertEqual(message.to, [self.parent.email])

    @override_settings(EMAIL_BACKEND=UNCONFIGURED_BACKEND)
    def test_unconfigured_mail_shows_a_warning_instead_of_a_500(self):
        response = self._request_reset(self.parent.email)
        self.assertLess(response.status_code, 500)
        self.assertContains(response, MAIL_WARNING)
        self.assertEqual(len(mail.outbox), 0)

    def test_unknown_email_never_500s(self):
        for backend in (LOCMEM_BACKEND, UNCONFIGURED_BACKEND):
            with self.subTest(backend=backend), override_settings(EMAIL_BACKEND=backend):
                cache.clear()
                response = self._request_reset("nobody@example.test")
                self.assertLess(response.status_code, 500)

    def test_unconfigured_backend_raises_unless_asked_to_fail_silently(self):
        message = mail.EmailMessage("s", "b", "from@example.test", ["to@example.test"])
        with self.assertRaises(MailNotConfigured):
            UnconfiguredEmailBackend().send_messages([message])
        self.assertEqual(UnconfiguredEmailBackend(fail_silently=True).send_messages([message]), 0)

    def test_backend_choice_follows_the_environment(self):
        self.assertEqual(backend_for("", False), UNCONFIGURED_BACKEND)
        self.assertEqual(backend_for("", True), "django.core.mail.backends.console.EmailBackend")
        self.assertEqual(backend_for("smtp.gmail.com", False), "django.core.mail.backends.smtp.EmailBackend")
        self.assertEqual(backend_for("smtp.gmail.com", True), "django.core.mail.backends.smtp.EmailBackend")


DUMMY_PROVIDERS = {
    "google": {
        "APPS": [{"client_id": "dummy-client-id", "secret": "dummy-secret", "key": ""}],
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
    },
}
PW = "a-long-test-password-1234"


@override_settings(EMAIL_BACKEND=LOCMEM_BACKEND, ACCOUNT_EMAIL_VERIFICATION="mandatory")
class VerificationTests(TestCase):
    """Parents and tutors confirm their email; pupils and Google sign-ins never are asked."""

    def setUp(self):
        cache.clear()  # allauth rate-limits per key in the process cache

    def _signup(self, email, account_type="parent"):
        return self.client.post(reverse("account_signup"), {
            "email": email, "password1": PW, "password2": PW, "account_type": account_type, "accept_terms": "on",
        })

    def _login(self, login, password):
        return self.client.post(reverse("account_login"), {"login": login, "password": password})

    def _authenticated(self):
        return "_auth_user_id" in self.client.session

    def _pupil(self, parent, username, password):
        # Exactly as accounts.views.add_child builds one: no email (None, not "").
        pupil = User(username=username, email=None, full_name="Pupil", role=User.Role.STUDENT, parent=parent)
        pupil.set_password(password)
        pupil.save()
        return pupil

    def test_password_signup_is_held_until_the_email_is_confirmed(self):
        response = self._signup("new.parent@example.test")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("account_email_verification_sent"))
        self.assertEqual(self.client.get(response.url).status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertTrue(message.subject.startswith("[RevisorPlus]"), message.subject)
        self.assertIn("Confirm your RevisorPlus email", message.subject)
        self.assertIn("/accounts/confirm-email/", message.body)
        self.assertNotIn("example.com", message.body)
        self.assertEqual(User.objects.get(email="new.parent@example.test").role, User.Role.PARENT)
        self.assertFalse(self._authenticated())

    def test_confirming_the_email_then_logging_in_works(self):
        self._signup("confirm.me@example.test")
        key = re.search(r"/accounts/confirm-email/([^/\s]+)/", mail.outbox[0].body).group(1)
        url = reverse("account_confirm_email", args=[key])
        page = self.client.get(url)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "<form")
        self.assertEqual(self.client.post(url).status_code, 302)
        user = User.objects.get(email="confirm.me@example.test")
        self.assertTrue(EmailAddress.objects.get(user=user).verified)
        cache.clear()
        response = self._login("confirm.me@example.test", PW)
        self.assertTrue(self._authenticated())
        self.assertRedirects(response, settings.LOGIN_REDIRECT_URL, fetch_redirect_response=False)

    def test_pupil_login_by_username_is_unaffected(self):
        parent = User.objects.create_user(username="pp", email="pp@example.test", role="parent", password=PW)
        self._pupil(parent, "kid-one", "pupil-password-1234")
        response = self._login("kid-one", "pupil-password-1234")
        self.assertRedirects(response, settings.LOGIN_REDIRECT_URL, fetch_redirect_response=False)
        self.assertNotEqual(response.url, reverse("account_email_verification_sent"))
        self.assertTrue(self._authenticated())
        self.assertEqual(mail.outbox, [])

    @override_settings(SOCIALACCOUNT_PROVIDERS=DUMMY_PROVIDERS)
    def test_verified_google_login_is_not_asked_again(self):
        parent = User.objects.create_user(username="gp", email="gp@example.test", role="parent", password=PW)
        account = SocialAccount.objects.create(user=parent, provider="google", uid="v1-uid", extra_data={})
        EmailAddress.objects.create(user=parent, email=parent.email, verified=True, primary=True)
        request = RequestFactory().get("/accounts/login/")
        SessionMiddleware(lambda r: None).process_request(request)
        request.session.save()
        MessageMiddleware(lambda r: None).process_request(request)
        request.user = AnonymousUser()
        request.allauth = SimpleNamespace()
        with allauth_context.request_context(request):
            sociallogin = SocialLogin(
                account=SocialAccount(provider="google", uid=account.uid),
                email_addresses=[EmailAddress(email=parent.email, verified=True, primary=True)],
                provider=get_social_adapter().get_provider(request, "google"),
            )
            response = complete_social_login(request, sociallogin)
        self.assertEqual(response.status_code, 302)
        self.assertNotEqual(response.url, reverse("account_email_verification_sent"))
        self.assertEqual(request.session["_auth_user_id"], str(parent.pk))
        self.assertEqual(mail.outbox, [])

    def test_existing_unverified_parent_is_held_until_the_command_runs(self):
        User.objects.create_user(username="old", email="old@example.test", role="parent", password=PW)
        response = self._login("old@example.test", PW)
        self.assertEqual(response.url, reverse("account_email_verification_sent"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertFalse(self._authenticated())
        tomorrow = (timezone.localdate() + timedelta(days=1)).isoformat()
        with self.assertRaises(CommandError):  # the real cutoff must be in the past...
            call_command("verify_existing_emails", "--before", tomorrow, "--apply", stdout=StringIO())
        User.objects.filter(username="old").update(date_joined=timezone.now() - timedelta(days=30))
        yesterday = (timezone.localdate() - timedelta(days=1)).isoformat()
        call_command("verify_existing_emails", "--before", yesterday, "--apply", stdout=StringIO())
        cache.clear()
        self._login("old@example.test", PW)
        self.assertTrue(self._authenticated())
        self.assertEqual(len(mail.outbox), 1)

    def test_switch_off_restores_instant_login(self):
        with override_settings(ACCOUNT_EMAIL_VERIFICATION="none"):
            response = self._signup("instant@example.test")
        self.assertRedirects(response, settings.LOGIN_REDIRECT_URL, fetch_redirect_response=False)
        self.assertTrue(self._authenticated())
        self.assertEqual(mail.outbox, [])

    def test_verify_existing_emails_command(self):
        old = timezone.now() - timedelta(days=30)
        parent = User.objects.create_user(username="op", email="op@example.test", role="parent", password=PW)
        tutor = User.objects.create_user(username="ot", email="ot@example.test", role="tutor", password=PW)
        recent = User.objects.create_user(username="rp", email="rp@example.test", role="parent", password=PW)
        pupil = self._pupil(parent, "old-kid", PW)
        User.objects.filter(pk__in=[parent.pk, tutor.pk, pupil.pk]).update(date_joined=old)
        yesterday = (timezone.localdate() - timedelta(days=1)).isoformat()

        def run(*args):
            out = StringIO()
            call_command("verify_existing_emails", "--before", yesterday, *args, stdout=out)
            return out.getvalue()

        output = run()
        self.assertIn("dry run", output)
        self.assertEqual(EmailAddress.objects.count(), 0)

        output = run("--apply")
        self.assertIn("@example.test", output)
        for address in ("op@", "ot@", "rp@"):
            self.assertNotIn(address, output)
        self.assertIn("2 selected, 2 verified", output)
        for user in (parent, tutor):
            row = EmailAddress.objects.get(user=user)
            self.assertTrue(row.verified and row.primary)
        self.assertFalse(EmailAddress.objects.filter(user__in=[recent, pupil]).exists())

        output = run("--apply")
        self.assertIn("2 selected, 0 verified", output)
        self.assertEqual(EmailAddress.objects.count(), 2)

        with self.assertRaises(CommandError):
            call_command("verify_existing_emails", "--before", timezone.localdate().isoformat(), stdout=StringIO())


@override_settings(EMAIL_BACKEND=LOCMEM_BACKEND, ACCOUNT_EMAIL_VERIFICATION="mandatory")
class ConsentTests(TestCase):
    """Parents and tutors agree to the Terms at sign-up, or once before subscribing if older."""

    def setUp(self):
        cache.clear()

    def _signup(self, email, **extra):
        payload = {"email": email, "password1": PW, "password2": PW, "account_type": "parent", **extra}
        return self.client.post(reverse("account_signup"), payload)

    def _pupil(self, parent, username="kid"):
        pupil = User(username=username, email=None, full_name="Pupil", role=User.Role.STUDENT, parent=parent)
        pupil.set_password(PW)
        pupil.save()
        return pupil

    def _unagreed_parent(self, username="p"):
        return User.objects.create_user(username=username, email=f"{username}@example.test", password=PW, role=User.Role.PARENT)

    def test_signup_without_the_agreement_creates_no_user(self):
        response = self._signup("noterms@example.test")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="noterms@example.test").exists())
        self.assertContains(response, "Please tick the box to agree to the Terms of Service.")
        self.assertEqual(mail.outbox, [])

    def test_signup_with_the_agreement_records_it_then_verification_runs(self):
        response = self._signup("terms@example.test", accept_terms="on")
        self.assertRedirects(response, reverse("account_email_verification_sent"), fetch_redirect_response=False)
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn("_auth_user_id", self.client.session)
        user = User.objects.get(email="terms@example.test")
        self.assertEqual(user.terms_version, CURRENT_TERMS_VERSION)
        self.assertGreater(user.terms_accepted_at, timezone.now() - timedelta(minutes=1))

    def test_signup_with_the_agreement_logs_in_when_verification_is_off(self):
        with self.settings(ACCOUNT_EMAIL_VERIFICATION="none"):
            response = self._signup("noverify@example.test", accept_terms="on")
        self.assertRedirects(response, reverse("after_login"), fetch_redirect_response=False)

    def test_social_signup_form_requires_the_agreement_and_google_is_not_auto_signed_up(self):
        from allauth.socialaccount.forms import SignupForm

        self.assertIn("accept_terms", SignupForm.base_fields)
        self.assertIs(settings.SOCIALACCOUNT_AUTO_SIGNUP, False)

    def test_checkout_sends_an_unagreed_parent_to_accept_terms_before_stripe(self):
        parent = self._unagreed_parent()
        pupil = self._pupil(parent)
        self.client.force_login(parent)
        with mock.patch("billing.views.stripe.checkout.Session.create") as create:
            response = self.client.post(reverse("billing:checkout"), {"pupil_id": pupil.id})
        self.assertRedirects(
            response, f"{reverse('family:accept_terms')}?next={reverse('billing:pricing')}", fetch_redirect_response=False
        )
        create.assert_not_called()

    def test_accept_terms_page(self):
        parent = self._unagreed_parent()
        self.client.force_login(parent)
        self.assertContains(self.client.get(reverse("family:accept_terms")), 'name="accept_terms"')
        response = self.client.post(reverse("family:accept_terms"), {"accept_terms": "on", "next": "/billing/"})
        self.assertRedirects(response, "/billing/", fetch_redirect_response=False)
        parent.refresh_from_db()
        self.assertEqual(parent.terms_version, CURRENT_TERMS_VERSION)
        self.assertIsNotNone(parent.terms_accepted_at)

        other = self._unagreed_parent("p2")
        self.client.force_login(other)
        response = self.client.post(reverse("family:accept_terms"), {})
        self.assertContains(response, "Please tick the box to agree to the Terms of Service.")

        pupil = self._pupil(parent)
        self.client.force_login(pupil)
        self.assertRedirects(
            self.client.get(reverse("family:accept_terms")), reverse("practice:dashboard"), fetch_redirect_response=False
        )

    def test_checkout_passes_the_consent_guard_after_acceptance(self):
        parent = self._unagreed_parent()
        pupil = self._pupil(parent)
        record_acceptance(parent)
        self.client.force_login(parent)
        response = self.client.post(reverse("billing:checkout"), {"pupil_id": pupil.id})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("family:child", args=[pupil.id]))

    def test_pupil_login_is_unaffected(self):
        pupil = self._pupil(self._unagreed_parent())
        response = self.client.post(reverse("account_login"), {"login": pupil.username, "password": PW})
        self.assertRedirects(response, reverse("after_login"), fetch_redirect_response=False)
        self.assertIs(needs_acceptance(pupil), False)


class PurgeGuardTests(TestCase):
    def setUp(self):
        self.parent = User.objects.create_user(
            username="purge_parent", email="purge.parent@example.test", password=PW, role=User.Role.PARENT)

    def _inactive_pupil(self, name):
        pupil = User(username=name, email=None, full_name=name, role=User.Role.STUDENT, parent=self.parent)
        pupil.set_password(PW)
        pupil.save()
        old = timezone.now() - timedelta(days=400)
        User.objects.filter(pk=pupil.pk).update(date_joined=old, last_login=old)
        Subscription.objects.get_or_create(user=pupil)
        return pupil

    def _pupils(self, n):
        return [self._inactive_pupil(f"purge_pupil_{i}") for i in range(n)]

    def _run(self, out=None, **kwargs):
        out = out if out is not None else StringIO()
        call_command("purge_inactive_pupils", days=365, stdout=out, **kwargs)
        return out.getvalue()

    def _alive(self, pupils):
        return User.objects.filter(pk__in=[p.pk for p in pupils]).count()

    def test_live_run_over_the_cap_refuses_and_deletes_nothing(self):
        pupils = self._pupils(6)
        out = StringIO()
        with self.assertRaises(CommandError) as cm:
            self._run(out=out)
        self.assertIn("6 pupils selected exceeds --max-deletions 5", str(cm.exception))
        self.assertEqual(self._alive(pupils), 6)
        for pupil in pupils:
            self.assertIn(pupil.username, out.getvalue())

    def test_allow_mass_deletes_all_six(self):
        pupils = self._pupils(6)
        out = self._run(allow_mass=True)
        self.assertEqual(self._alive(pupils), 0)
        self.assertTrue(out.strip().endswith("6 selected, 6 deleted"))

    def test_raising_the_cap_deletes_all_six(self):
        pupils = self._pupils(6)
        self._run(max_deletions=6)
        self.assertEqual(self._alive(pupils), 0)

    def test_dry_run_over_the_cap_warns_and_exits_normally(self):
        pupils = self._pupils(6)
        out = self._run(dry_run=True)
        self.assertIn("WARNING: 6 selected exceeds --max-deletions 5; a live run would refuse", out)
        self.assertEqual(out.strip().splitlines()[-1], "purge_inactive_pupils: 6 selected, 0 deleted")
        self.assertEqual(self._alive(pupils), 6)

    def test_five_inactive_pupils_are_deleted_without_the_flag(self):
        pupils = self._pupils(5)
        out = self._run()
        self.assertTrue(out.strip().endswith("5 selected, 5 deleted"))
        self.assertEqual(self._alive(pupils), 0)

    def test_negative_cap_is_refused(self):
        pupils = self._pupils(2)
        with self.assertRaises(CommandError):
            self._run(max_deletions=-1)
        self.assertEqual(self._alive(pupils), 2)
