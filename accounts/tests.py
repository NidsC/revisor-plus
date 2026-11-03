"""Regression coverage for the parent dashboard's child-scoped progress links."""
from django.conf import settings
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

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
