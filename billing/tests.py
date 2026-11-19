import json
import re
import time
from datetime import date, datetime, timedelta
from io import StringIO
from unittest import mock
from zoneinfo import ZoneInfo

import stripe
from allauth.account.models import EmailAddress
from django.conf import settings
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.contrib.messages import get_messages
from django.core.management.base import CommandError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.consent import CURRENT_TERMS_VERSION, record_acceptance
from accounts.models import User
from accounts.views import create_placeholder_pupil

from .emails import maybe_send_purchase_confirmation
from .funnel import _one_month_on
from .models import Subscription
from .offers import lookup_promotion_code
from .views import format_price_gbp

LOCMEM_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
PW = "a-long-test-password-1234"


@override_settings(
    EMAIL_BACKEND=LOCMEM_BACKEND,
    STRIPE_WEBHOOK_SECRET="whsec_test",
    STRIPE_SECRET_KEY="sk_test_x",
    STRIPE_PRICE_ID="price_x",
    STRIPE_PRICE_GBP="1499",
    SITE_URL="https://www.revisorplus.co.uk",
)
class PurchaseEmailTests(TestCase):
    def setUp(self):
        self.parent = User.objects.create_user(
            username="payer", email="payer@example.test", password=PW, role=User.Role.PARENT
        )
        self.pupil = User(
            username="kid", email=None, full_name="Kid Example",
            role=User.Role.STUDENT, parent=self.parent,
        )
        self.pupil.set_password(PW)
        self.pupil.save()
        self.period_end = timezone.now() + timedelta(days=30)
        self.sub = Subscription.objects.create(
            user=self.pupil,
            payer=self.parent,
            status=Subscription.Status.ACTIVE,
            stripe_subscription_id="sub_test_1",
            current_period_end=self.period_end,
        )

    def test_active_subscription_sends_one_confirmation_with_the_required_content(self):
        self.assertTrue(maybe_send_purchase_confirmation(self.sub))
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["payer@example.test"])
        self.assertEqual(message.from_email, settings.DEFAULT_FROM_EMAIL)
        self.assertEqual(message.subject, "You're all set — RevisorPlus Premium for Kid Example")
        self.assertNotIn("[RevisorPlus]", message.subject)
        renewal = timezone.localtime(self.period_end).strftime("%-d %B %Y")
        started = timezone.localdate().strftime("%-d %B %Y")
        for expected in (
            "Kid Example now has full access to RevisorPlus Premium.",
            f"Plan:           RevisorPlus Premium, {format_price_gbp('1499')} a month",
            "Started:        " + started + " (straight away, as you asked at checkout)",
            "Next payment:   " + renewal,
            "Receipt:        sent separately by Stripe",
            "You have 14 days to cancel for a full refund",
            "Manage billing",
            "Have a great day,\nRevisorPlus",
        ):
            self.assertIn(expected, message.body)
        self.assertIn(
            "Started:        " + started + " (straight away, as you asked at checkout)\n"
            "Next payment:   " + renewal + "\n"
            "Receipt:        sent separately by Stripe",
            message.body,
        )
        for absent in ("/terms/", "/privacy/", "I hereby give notice", "Happy", "[RevisorPlus]"):
            self.assertNotIn(absent, message.body)
        self.assertNotIn("{{", message.body)
        self.assertNotIn("{%", message.body)
        self.sub.refresh_from_db()
        self.assertIsNotNone(self.sub.confirmation_sent_at)
        self.assertLess(timezone.now() - self.sub.confirmation_sent_at, timedelta(minutes=1))

    def test_no_renewal_line_without_a_period_end(self):
        other_parent = User.objects.create_user(
            username="payer2", email="payer2@example.test", password=PW, role=User.Role.PARENT
        )
        other_pupil = User(
            username="kid2", email=None, full_name="Other Kid",
            role=User.Role.STUDENT, parent=other_parent,
        )
        other_pupil.set_password(PW)
        other_pupil.save()
        sub = Subscription.objects.create(
            user=other_pupil,
            payer=other_parent,
            status=Subscription.Status.ACTIVE,
            stripe_subscription_id="sub_test_2",
            current_period_end=None,
        )
        self.assertTrue(maybe_send_purchase_confirmation(sub))
        self.assertNotIn("Next payment", mail.outbox[0].body)
        self.assertIn(
            "(straight away, as you asked at checkout)\nReceipt:        sent separately by Stripe",
            mail.outbox[0].body,
        )

    def test_second_call_sends_nothing(self):
        self.assertTrue(maybe_send_purchase_confirmation(self.sub))
        self.sub.refresh_from_db()
        first = self.sub.confirmation_sent_at
        self.assertFalse(maybe_send_purchase_confirmation(self.sub))
        self.assertEqual(len(mail.outbox), 1)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.confirmation_sent_at, first)

    def test_failed_send_releases_the_claim_and_logs(self):
        with override_settings(EMAIL_BACKEND="config.mail.UnconfiguredEmailBackend"), \
                self.assertLogs("billing.emails", level="WARNING") as logs:
            self.assertFalse(maybe_send_purchase_confirmation(self.sub))
        self.sub.refresh_from_db()
        self.assertIsNone(self.sub.confirmation_sent_at)
        for line in logs.output:
            self.assertNotIn("payer@example.test", line)

    def test_not_sent_when_not_active_or_no_payer_email_or_no_stripe_id(self):
        cases = {
            "past_due": {"status": Subscription.Status.PAST_DUE},
            "no_payer": {"payer": None},
            "no_stripe_id": {"stripe_subscription_id": ""},
        }
        for name, changes in cases.items():
            with self.subTest(name):
                Subscription.objects.filter(pk=self.sub.pk).update(**changes)
                self.sub.refresh_from_db()
                self.assertFalse(maybe_send_purchase_confirmation(self.sub))
                self.assertEqual(mail.outbox, [])
                self.sub.refresh_from_db()
                self.assertIsNone(self.sub.confirmation_sent_at)
                Subscription.objects.filter(pk=self.sub.pk).update(
                    status=Subscription.Status.ACTIVE,
                    payer=self.parent,
                    stripe_subscription_id="sub_test_1",
                )

    def test_webhook_sends_once_and_a_retried_event_does_not_resend(self):
        Subscription.objects.filter(pk=self.sub.pk).update(
            status=Subscription.Status.INACTIVE, stripe_subscription_id=""
        )
        event = {
            "id": "evt_c2_1",
            "object": "event",
            "type": "checkout.session.completed",
            "created": int(time.time()),
            "data": {"object": {"subscription": "sub_test_1"}},
        }
        fixture = {
            "id": "sub_test_1",
            "status": "active",
            "cancel_at_period_end": False,
            "metadata": {"pupil_id": str(self.pupil.id), "parent_id": str(self.parent.id)},
            "items": {"data": [{"current_period_end": int(self.period_end.timestamp())}]},
        }
        with mock.patch("billing.views.stripe.Webhook.construct_event", return_value=event), \
                mock.patch("billing.views.stripe.Subscription.retrieve", return_value=fixture):
            for _ in range(2):
                response = self.client.post(
                    reverse("billing:webhook"),
                    data=json.dumps(event),
                    content_type="application/json",
                    HTTP_STRIPE_SIGNATURE="t=1,v1=test",
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(mail.outbox), 1)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, Subscription.Status.ACTIVE)
        self.assertIsNotNone(self.sub.confirmation_sent_at)


def _make_pupil(username, parent, full_name):
    pupil = User(username=username, email=None, full_name=full_name,
                 role=User.Role.STUDENT, parent=parent)
    pupil.set_password(PW)
    pupil.save()
    return pupil


class LiveCutoverTests(TestCase):
    def setUp(self):
        self.parent = User.objects.create_user(
            username="cutover_parent", email="cutover@example.test", password=PW,
            role=User.Role.PARENT, stripe_customer_id="cus_test_1",
        )
        self.other_parent = User.objects.create_user(
            username="cutover_other", email="other@example.test", password=PW,
            role=User.Role.PARENT,
        )
        self.pupil_a = _make_pupil("cutover_a", self.parent, "Pupil A")
        self.pupil_b = _make_pupil("cutover_b", self.other_parent, "Pupil B")
        self.pupil_c = _make_pupil("cutover_c", self.other_parent, "Pupil C")
        now = timezone.now()
        self.sub_a = Subscription.objects.create(
            user=self.pupil_a, payer=self.parent, status=Subscription.Status.ACTIVE,
            stripe_subscription_id="sub_test_a", stripe_ref="ref_a",
            last_event_created=now, current_period_end=now + timedelta(days=30),
            confirmation_sent_at=now,
        )
        self.sub_b = Subscription.objects.create(
            user=self.pupil_b, payer=None, status=Subscription.Status.ACTIVE,
        )
        self.sub_c = Subscription.objects.create(
            user=self.pupil_c, status=Subscription.Status.CANCELED,
            stripe_subscription_id="sub_test_c",
        )

    def _run(self, *args):
        out = StringIO()
        call_command("stripe_live_cutover", *args, stdout=out)
        return out.getvalue()

    @override_settings(STRIPE_SECRET_KEY="sk_live_x")
    def test_dry_run_changes_nothing_and_lists_the_rows(self):
        before = {s.pk: Subscription.objects.values().get(pk=s.pk)
                  for s in (self.sub_a, self.sub_b, self.sub_c)}
        out = self._run()
        self.assertIn("cutover_a @example.test", out)
        self.assertIn("cutover_c", out)
        self.assertNotIn("cutover_b", out)
        self.assertNotIn("cutover@example.test", out)
        self.assertEqual(out.count("REVIEW: active with a cleared Stripe id"), 1)
        review_line = [ln for ln in out.splitlines() if "REVIEW" in ln][0]
        self.assertIn("cutover_a", review_line)
        self.assertIn("dry run: nothing changed", out)
        self.assertIn("1 customer ids, 2 subscriptions would be cleared", out)
        for pk, row in before.items():
            self.assertEqual(Subscription.objects.values().get(pk=pk), row)
        self.parent.refresh_from_db()
        self.assertEqual(self.parent.stripe_customer_id, "cus_test_1")

    @override_settings(STRIPE_SECRET_KEY="sk_live_x")
    def test_apply_clears_ids_and_keeps_statuses(self):
        b_before = Subscription.objects.values().get(pk=self.sub_b.pk)
        a_before = Subscription.objects.get(pk=self.sub_a.pk)
        out = self._run("--apply")
        self.parent.refresh_from_db()
        self.other_parent.refresh_from_db()
        self.assertEqual(self.parent.stripe_customer_id, "")
        self.assertEqual(self.other_parent.stripe_customer_id, "")
        for sub in (self.sub_a, self.sub_c):
            sub.refresh_from_db()
            self.assertEqual(sub.stripe_subscription_id, "")
            self.assertEqual(sub.stripe_ref, "")
            self.assertIsNone(sub.last_event_created)
        self.assertEqual(self.sub_a.status, Subscription.Status.ACTIVE)
        self.assertEqual(self.sub_a.payer, self.parent)
        self.assertEqual(self.sub_a.current_period_end, a_before.current_period_end)
        self.assertEqual(self.sub_a.confirmation_sent_at, a_before.confirmation_sent_at)
        self.assertEqual(self.sub_c.status, Subscription.Status.CANCELED)
        self.assertEqual(Subscription.objects.values().get(pk=self.sub_b.pk), b_before)
        self.assertTrue(out.strip().endswith("1 customer ids, 2 subscriptions cleared"))

    @override_settings(STRIPE_SECRET_KEY="sk_test_x")
    def test_apply_refuses_under_a_test_key(self):
        with self.assertRaises(CommandError):
            self._run("--apply")
        self.parent.refresh_from_db()
        self.sub_a.refresh_from_db()
        self.assertEqual(self.parent.stripe_customer_id, "cus_test_1")
        self.assertEqual(self.sub_a.stripe_subscription_id, "sub_test_a")
        self.assertIn("dry run: nothing changed", self._run())

    def test_pricing_shows_the_test_card_note_only_under_a_test_key(self):
        pricing_parent = User.objects.create_user(
            username="pricing_parent", email="pricing@example.test", password=PW,
            role=User.Role.PARENT,
        )
        pupil = _make_pupil("pricing_pupil", pricing_parent, "Pricing Pupil")
        Subscription.objects.create(user=pupil, payer=pricing_parent,
                                    status=Subscription.Status.INACTIVE)
        self.client.force_login(pricing_parent)
        url = reverse("billing:pricing")
        with override_settings(STRIPE_SECRET_KEY="sk_test_x", STRIPE_PRICE_ID="price_x"):
            body = self.client.get(url).content.decode()
        self.assertIn("Stripe test mode", body)
        self.assertIn("Subscribe for", body)
        with override_settings(STRIPE_SECRET_KEY="sk_live_x", STRIPE_PRICE_ID="price_x"):
            body = self.client.get(url).content.decode()
        self.assertNotIn("Stripe test mode", body)
        self.assertNotIn("Payments are not configured", body)
        self.assertIn("Subscribe for", body)
        with override_settings(STRIPE_SECRET_KEY="", STRIPE_PRICE_ID="price_x"):
            body = self.client.get(url).content.decode()
        self.assertIn("Payments are not configured", body)
        self.assertNotIn("Subscribe for", body)


PROMO = {
    "id": "promo_x", "code": "FIRSTMONTH499", "restrictions": {"first_time_transaction": True},
    "promotion": {
        "type": "coupon",
        "coupon": {"amount_off": 1000, "currency": "gbp", "duration": "once", "redeem_by": None},
    },
}
SESSION_URL = "https://checkout.stripe.com/pay/cs_test_1"


@override_settings(
    EMAIL_BACKEND=LOCMEM_BACKEND,
    STRIPE_SECRET_KEY="sk_test_x",
    STRIPE_PRICE_ID="price_x",
    STRIPE_PRICE_GBP="1499",
    SITE_URL="https://www.revisorplus.co.uk",
    OFFER_PENDING_HOURS=48,
)
class OfferFunnelTests(TestCase):
    EMAIL = "mum@example.test"

    def setUp(self):
        cache.clear()
        self.promo_list = self._patch("billing.offers.stripe.PromotionCode.list", return_value={"data": [PROMO]})
        self.create = self._patch(
            "billing.checkout.stripe.checkout.Session.create",
            return_value={"id": "cs_test_1", "url": SESSION_URL},
        )
        self.retrieve = self._patch("billing.funnel.stripe.checkout.Session.retrieve")
        self._patch("billing.stripe_sync.stripe.Customer.create", return_value={"id": "cus_x"})

    def _patch(self, target, **kwargs):
        patcher = mock.patch(target, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def _start(self, email=None, tick=True, code="FIRSTMONTH499", client=None):
        data = {"email": email or self.EMAIL}
        if tick:
            data["accept_terms"] = "on"
        return (client or self.client).post(reverse("offer_start", args=[code]), data)

    def _paid_session(self, pupil, **overrides):
        session = {
            "id": "cs_test_1", "payment_status": "paid", "client_reference_id": str(pupil.id),
            "customer": "cus_new_1", "customer_details": {"email": pupil.parent.email},
            "subscription": {
                "id": "sub_f_1", "status": "active", "cancel_at_period_end": False,
                "metadata": {"pupil_id": str(pupil.id), "parent_id": str(pupil.parent_id)},
                "items": {"data": [{"current_period_end": int((timezone.now() + timedelta(days=30)).timestamp())}]},
            },
        }
        session.update(overrides)
        self.retrieve.return_value = session
        return session

    def _started(self, email=None):
        self._start(email)
        parent = User.objects.get(email=email or self.EMAIL)
        return parent, User.objects.get(parent=parent)

    def _success(self, client=None):
        return (client or self.client).get(reverse("offer_success"), {"session_id": "cs_test_1"})

    # 1
    def test_landing_shows_the_offer_the_terms_box_and_the_cooling_off_line(self):
        response = self.client.get(reverse("offer_landing", args=["FIRSTMONTH499"]))
        self.assertContains(response, "£4.99")
        self.assertContains(response, "£14.99")
        self.assertContains(response, 'name="accept_terms"')
        self.assertContains(response, _one_month_on(timezone.localdate()).strftime("%-d %B %Y"))

    def test_landing_for_an_unknown_code_says_the_offer_has_ended(self):
        self.promo_list.return_value = {"data": []}
        response = self.client.get(reverse("offer_landing", args=["NOPE"]))
        self.assertContains(response, "This offer has ended")

    def test_landing_redirects_a_signed_in_parent_to_pricing(self):
        parent = User.objects.create_user(username="in", email="in@example.test", password=PW, role=User.Role.PARENT)
        self.client.force_login(parent)
        response = self.client.get(reverse("offer_landing", args=["FIRSTMONTH499"]))
        self.assertRedirects(response, reverse("billing:pricing"), fetch_redirect_response=False)

    def test_one_month_on_clamps_to_the_last_day(self):
        self.assertEqual(_one_month_on(date(2027, 1, 31)), date(2027, 2, 28))
        self.assertEqual(_one_month_on(date(2027, 12, 15)), date(2028, 1, 15))

    # 2
    def test_start_without_the_tick_creates_nothing(self):
        response = self._start(tick=False)
        self.assertContains(response, "Please tick the box")
        self.assertFalse(User.objects.filter(email=self.EMAIL).exists())

    def test_start_with_an_existing_email_creates_nothing(self):
        User.objects.create_user(username="old", email=self.EMAIL, password=PW, role=User.Role.PARENT)
        response = self._start()
        self.assertContains(response, "You already have an account")
        self.assertContains(response, reverse("account_login"))
        self.assertEqual(User.objects.count(), 1)

    def test_start_creates_a_pending_parent_and_placeholder_and_redirects_to_stripe(self):
        response = self._start()
        self.assertRedirects(response, SESSION_URL, fetch_redirect_response=False)
        parent = User.objects.get(email=self.EMAIL)
        self.assertFalse(parent.has_usable_password())
        self.assertIsNotNone(parent.offer_pending_since)
        self.assertEqual(parent.offer_code, "FIRSTMONTH499")
        self.assertEqual(parent.terms_version, CURRENT_TERMS_VERSION)
        self.assertTrue(EmailAddress.objects.filter(user=parent, email=self.EMAIL, primary=True, verified=False).exists())
        pupil = User.objects.get(parent=parent)
        self.assertEqual(pupil.username, f"child-{parent.pk}")
        self.assertEqual(pupil.full_name, "Your child")
        self.assertFalse(pupil.has_usable_password())
        self.assertTrue(Subscription.objects.filter(user=pupil).exists())
        self.create.assert_called_once()
        kwargs = self.create.call_args.kwargs
        self.assertEqual(kwargs["discounts"], [{"promotion_code": "promo_x"}])
        self.assertEqual(kwargs["customer_email"], self.EMAIL)
        self.assertEqual(kwargs["client_reference_id"], str(pupil.id))
        self.assertNotIn("customer", kwargs)
        self.assertNotIn("allow_promotion_codes", kwargs)

    # 3
    def test_start_when_stripe_refuses_leaves_no_rows(self):
        self.create.side_effect = stripe.error.StripeError("boom")
        response = self._start()
        self.assertContains(response, "We couldn&#x27;t start the payment")
        self.assertEqual(User.objects.count(), 0)
        self.assertFalse(EmailAddress.objects.filter(email=self.EMAIL).exists())

    def test_start_rate_limit_keys_on_the_forwarded_address(self):
        url = reverse("offer_start", args=["FIRSTMONTH499"])
        first = {"HTTP_X_FORWARDED_FOR": "1.1.1.1, 10.0.0.5"}
        statuses = [self.client.post(url, {"email": self.EMAIL}, **first).status_code for _ in range(11)]
        self.assertEqual(statuses[-1], 429)
        self.assertNotIn(429, statuses[:-1])
        headers = ["2.2.2.2, 10.0.0.6", "3.3.3.3, 10.0.0.7"]
        for i in range(11):
            response = self.client.post(url, {"email": self.EMAIL}, HTTP_X_FORWARDED_FOR=headers[i % 2])
            self.assertNotEqual(response.status_code, 429)

    # U1: the approved look of the four funnel pages
    def test_landing_renders_the_approved_offer_page(self):
        response = self.client.get(reverse("offer_landing", args=["FIRSTMONTH499"]))
        for text in ("See exactly which 11+ topics your child is losing marks on.", "Continue to payment",
                     "Start your first month", "Full refund, no questions", "Questions parents ask",
                     'name="email"', 'name="accept_terms"', "pages/offer.css?v=1"):
            self.assertContains(response, text)
        for text in ("data-live", "landing.css", "Parent quote goes here", "exam board", "Ends "):
            self.assertNotContains(response, text)

    def test_landing_shows_the_deadline_only_when_the_coupon_has_one(self):
        deadline = int(datetime(2026, 12, 31, 23, 59, 59, tzinfo=ZoneInfo("Europe/London")).timestamp())
        self.promo_list.return_value = {"data": [{**PROMO, "promotion": {**PROMO["promotion"], "coupon": {**PROMO["promotion"]["coupon"], "redeem_by": deadline}}}]}
        response = self.client.get(reverse("offer_landing", args=["FIRSTMONTH499"]))
        self.assertContains(response, "Ends 31 December 2026")

    def test_a_start_error_renders_inside_the_error_element(self):
        response = self._start(tick=False)
        self.assertContains(response, 'class="rp-offer__error"')
        self.assertRegex(response.content.decode(), r'class="rp-offer__error"[^>]*>[^<]*Please tick the box')

    def test_cancelled_landing_says_no_payment_was_taken(self):
        response = self.client.get(reverse("offer_landing", args=["FIRSTMONTH499"]), {"cancelled": "1"})
        self.assertContains(response, "No payment was taken.")

    def test_the_ended_page_shows_the_standard_price_and_the_free_allowance(self):
        self.promo_list.return_value = {"data": []}
        response = self.client.get(reverse("offer_landing", args=["NOPE"]))
        for text in ("£14.99", "answer up to 50 questions", "Create an account", "pages/funnel.css?v=1"):
            self.assertContains(response, text)
        self.assertNotContains(response, "data-live")

    def test_setup_child_page_and_its_error_render(self):
        parent = User.objects.create_user(username="sp", email="sp@example.test", password=PW, role=User.Role.PARENT)
        placeholder = create_placeholder_pupil(parent)
        self.client.force_login(parent)
        url = reverse("family:setup_child", args=[placeholder.id])
        response = self.client.get(url)
        for text in ("Set up your child's login", "Save and continue", 'name="full_name"', 'name="username"',
                     'name="password"', "pages/funnel.css?v=1"):
            self.assertContains(response, text)
        self.assertNotContains(response, "data-live")
        response = self.client.post(url, {"full_name": "Kai", "username": "", "password": PW})
        self.assertContains(response, 'class="rp-setup__errors"')
        self.assertContains(response, "Choose a username.")

    def test_setup_child_done_page(self):
        parent = User.objects.create_user(username="sp", email="sp@example.test", password=PW, role=User.Role.PARENT)
        placeholder = create_placeholder_pupil(parent)
        self.client.force_login(parent)
        response = self.client.post(reverse("family:setup_child", args=[placeholder.id]),
                                    {"full_name": "Kai", "username": "kai.reads", "password": PW})
        for text in ("Kai can log in now", "kai.reads", "Set up on your child's device",
                     "Go to your family page", "Add another child", "#add-child"):
            self.assertContains(response, text)
        self.assertNotContains(response, "data-live")

    def test_success_flash_points_to_the_receipt_email(self):
        parent, pupil = self._started()
        self._paid_session(pupil)
        response = self._success()
        self.assertEqual([str(m) for m in get_messages(response.wsgi_request)],
                         ["Payment received. Your receipt is on its way by email."])

    # 4
    def test_success_logs_the_parent_in_applies_the_subscription_and_sends_both_emails(self):
        parent, pupil = self._started()
        self._paid_session(pupil)
        response = self._success()
        self.assertRedirects(response, reverse("family:setup_child", args=[pupil.id]), fetch_redirect_response=False)
        self.assertEqual(int(self.client.session["_auth_user_id"]), parent.pk)
        parent.refresh_from_db()
        self.assertIsNone(parent.offer_pending_since)
        self.assertEqual(parent.stripe_customer_id, "cus_new_1")
        self.assertTrue(EmailAddress.objects.get(user=parent, primary=True).verified)
        sub = Subscription.objects.get(user=pupil)
        self.assertEqual(sub.status, Subscription.Status.ACTIVE)
        self.assertEqual(sub.payer, parent)
        self.assertEqual([m.subject for m in mail.outbox],
                         ["You're all set — RevisorPlus Premium for Your child", "Welcome to RevisorPlus"])
        self.assertIn("https://www.revisorplus.co.uk/family/", mail.outbox[1].body)

    def test_success_refuses_an_unpaid_session(self):
        parent, pupil = self._started()
        self._paid_session(pupil, payment_status="unpaid")
        self.assertEqual(self._success().status_code, 404)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_success_replay_does_not_log_in_or_email_again(self):
        parent, pupil = self._started()
        self._paid_session(pupil)
        self._success()
        self.assertEqual(len(mail.outbox), 2)
        response = self._success(client=Client())
        self.assertRedirects(response, reverse("account_login"), fetch_redirect_response=False)
        response = self._success()
        self.assertRedirects(response, reverse("family:home"), fetch_redirect_response=False)
        self.assertEqual(len(mail.outbox), 2)

    def test_success_for_a_settled_parent_or_unknown_pupil(self):
        parent = User.objects.create_user(username="set", email="set@example.test", password=PW, role=User.Role.PARENT)
        pupil = _make_pupil("setpupil", parent, "Set Pupil")
        self._paid_session(pupil)
        self.assertRedirects(self._success(), reverse("account_login"), fetch_redirect_response=False)
        self._paid_session(pupil, client_reference_id="999999")
        self.assertEqual(self._success().status_code, 404)
        self._paid_session(pupil, client_reference_id="not-a-number")
        self.assertEqual(self._success().status_code, 404)
        self.assertEqual(self.client.get(reverse("offer_success")).status_code, 404)

    # 5
    def test_success_adopts_the_stripe_email_when_it_is_free(self):
        parent, pupil = self._started()
        self._paid_session(pupil, customer_details={"email": "Other@Example.test"})
        self._success()
        parent.refresh_from_db()
        self.assertEqual(parent.email, "other@example.test")
        self.assertEqual(EmailAddress.objects.get(user=parent, primary=True).email, "other@example.test")

    def test_success_keeps_the_account_email_when_the_stripe_email_is_taken(self):
        User.objects.create_user(username="held", email="held@example.test", password=PW, role=User.Role.PARENT)
        parent, pupil = self._started()
        self._paid_session(pupil, customer_details={"email": "held@example.test"})
        with self.assertLogs("billing.funnel", "INFO") as logs:
            self._success()
        self.assertTrue(any("kept the account email" in line for line in logs.output))
        parent.refresh_from_db()
        self.assertEqual(parent.email, self.EMAIL)

    # 6
    def test_setup_child_completes_the_placeholder(self):
        parent, pupil = self._started()
        self.client.force_login(parent)
        url = reverse("family:setup_child", args=[pupil.id])
        response = self.client.get(url)
        for field in ("full_name", "username", "password"):
            self.assertContains(response, f'name="{field}"')
        response = self.client.post(url, {"full_name": "Kai", "username": "kai2026", "password": "Kestrel7!x"})
        self.assertContains(response, "kai2026")
        self.assertNotContains(response, "Kestrel7!x")
        pupil.refresh_from_db()
        self.assertEqual(pupil.full_name, "Kai")
        self.assertTrue(pupil.has_usable_password())
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_setup_child_refuses_a_taken_username_and_another_parents_pupil(self):
        parent, pupil = self._started()
        other = User.objects.create_user(username="o", email="o@example.test", password=PW, role=User.Role.PARENT)
        _make_pupil("taken_name", other, "Taken")
        self.client.force_login(parent)
        url = reverse("family:setup_child", args=[pupil.id])
        response = self.client.post(url, {"full_name": "Kai", "username": "taken_name", "password": "Kestrel7!x"})
        self.assertContains(response, "already taken")
        pupil.refresh_from_db()
        self.assertFalse(pupil.has_usable_password())
        self.client.force_login(other)
        self.assertEqual(self.client.get(url).status_code, 403)

    # 7
    def test_family_home_offers_finish_setting_up_for_a_placeholder_only(self):
        parent, placeholder = self._started()
        done = _make_pupil("done_pupil", parent, "Done Pupil")
        self.client.force_login(parent)
        response = self.client.get(reverse("family:home"))
        self.assertContains(response, "Finish setting up")
        self.assertNotContains(response, f'href="{reverse("family:child", args=[placeholder.pk])}"')
        self.assertContains(response, f'href="{reverse("family:child", args=[done.pk])}"')

    # 8
    def test_the_family_page_checkout_allows_promotion_codes(self):
        parent = User.objects.create_user(username="buyer", email="buyer@example.test", password=PW, role=User.Role.PARENT)
        record_acceptance(parent)
        pupil = _make_pupil("buyer_pupil", parent, "Buyer Pupil")
        self.create.return_value = mock.Mock(url=SESSION_URL)
        self.client.force_login(parent)
        self.client.post(reverse("billing:checkout"), {"pupil_id": pupil.id})
        kwargs = self.create.call_args.kwargs
        self.assertIs(kwargs["allow_promotion_codes"], True)
        self.assertEqual(kwargs["customer"], "cus_x")
        self.assertNotIn("customer_email", kwargs)
        self.assertNotIn("discounts", kwargs)

    # 10
    def test_a_funnel_parent_can_sign_in_with_an_emailed_code(self):
        parent, _ = self._started()
        login_page = self.client.get(reverse("account_login"))
        self.assertContains(login_page, reverse("account_request_login_code"))
        response = self.client.post(reverse("account_request_login_code"), {"email": parent.email})
        self.assertRedirects(response, reverse("account_confirm_login_code"), fetch_redirect_response=False)
        # allauth's codes look like "WXHW-CRZC" (hyphenated), so the pattern allows a hyphen.
        login_mails = [m for m in mail.outbox if m.subject == "[RevisorPlus] Your sign-in code"]
        self.assertEqual(len(login_mails), 1)
        code = re.search(r"^\s*([A-Za-z0-9-]{4,16})\s*$", login_mails[0].body, re.M).group(1)
        response = self.client.post(reverse("account_confirm_login_code"), {"code": code})
        self.assertEqual(response.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)
        self.assertTrue(EmailAddress.objects.get(user=parent, primary=True).verified)


@override_settings(STRIPE_SECRET_KEY="sk_test_x", STRIPE_PRICE_ID="price_x", STRIPE_PRICE_GBP="1499")
class OfferLookupTests(TestCase):
    COUPON = {"amount_off": 1000, "currency": "gbp", "duration": "once", "redeem_by": None}

    def setUp(self):
        cache.clear()
        patcher = mock.patch("billing.offers.stripe.PromotionCode.list")
        self.promo_list = patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch("billing.offers.stripe.Coupon.retrieve")
        self.coupon_retrieve = patcher.start()
        self.addCleanup(patcher.stop)

    def test_reads_the_expanded_promotion_coupon_and_asks_stripe_to_expand_it(self):
        self.promo_list.return_value = {"data": [PROMO]}
        offer = lookup_promotion_code("FIRSTMONTH499")
        self.assertEqual(offer["amount_off_pence"], 1000)
        self.assertEqual(offer["first_month_price_pence"], 499)
        self.assertEqual(self.promo_list.call_args.kwargs["expand"], ["data.promotion.coupon"])
        self.coupon_retrieve.assert_not_called()

    def test_a_coupon_id_is_retrieved_and_its_fields_used(self):
        promo = {"id": "promo_x", "code": "FIRSTMONTH499", "promotion": {"type": "coupon", "coupon": "cpn_x"}}
        self.promo_list.return_value = {"data": [promo]}
        self.coupon_retrieve.return_value = dict(self.COUPON)
        offer = lookup_promotion_code("FIRSTMONTH499")
        self.coupon_retrieve.assert_called_once_with("cpn_x")
        self.assertEqual(offer["first_month_price_pence"], 499)

    def test_a_failed_coupon_retrieve_returns_none(self):
        promo = {"id": "promo_x", "code": "FIRSTMONTH499", "promotion": {"type": "coupon", "coupon": "cpn_x"}}
        self.promo_list.return_value = {"data": [promo]}
        self.coupon_retrieve.side_effect = stripe.error.StripeError("boom")
        self.assertIsNone(lookup_promotion_code("FIRSTMONTH499"))

    def test_the_older_top_level_coupon_shape_still_resolves(self):
        promo = {"id": "promo_x", "code": "FIRSTMONTH499", "coupon": dict(self.COUPON)}
        self.promo_list.return_value = {"data": [promo]}
        offer = lookup_promotion_code("FIRSTMONTH499")
        self.assertEqual(offer["id"], "promo_x")
        self.assertEqual(offer["first_month_price_pence"], 499)

    def test_a_promotion_without_a_coupon_is_ignored_and_not_cached_as_valid(self):
        promo = {"id": "promo_x", "code": "FIRSTMONTH499", "promotion": {"type": "coupon"}}
        self.promo_list.return_value = {"data": [promo]}
        self.assertIsNone(lookup_promotion_code("FIRSTMONTH499"))
        self.assertFalse(cache.get("offer:FIRSTMONTH499"))
