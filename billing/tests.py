import json
import time
from datetime import timedelta
from io import StringIO
from unittest import mock

from django.conf import settings
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User

from .emails import maybe_send_purchase_confirmation
from .models import Subscription
from .views import format_price_gbp

LOCMEM_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
PW = "a-long-test-password-1234"


@override_settings(
    EMAIL_BACKEND=LOCMEM_BACKEND,
    STRIPE_WEBHOOK_SECRET="whsec_test",
    STRIPE_SECRET_KEY="sk_test_x",
    STRIPE_PRICE_ID="price_x",
    STRIPE_PRICE_GBP="2999",
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
        self.assertEqual(
            message.subject, "[RevisorPlus] Your RevisorPlus Premium subscription for Kid Example"
        )
        renewal = timezone.localtime(self.period_end).strftime("%-d %B %Y")
        for expected in (
            f"RevisorPlus Premium for Kid Example, {format_price_gbp('2999')}/month",
            "Next renewal: " + renewal,
            "Premium started as soon as you paid, because you asked us to start it straight away.",
            "14 days from the day you subscribed",
            "we refund that payment in full",
            "I hereby give notice that I cancel my contract",
            "Manage billing",
            "https://www.revisorplus.co.uk/terms/",
            "https://www.revisorplus.co.uk/privacy/",
            "Stripe will send you a separate receipt.",
        ):
            self.assertIn(expected, message.body)
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
        self.assertNotIn("Next renewal", mail.outbox[0].body)

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
