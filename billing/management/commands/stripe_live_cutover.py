"""One-off: clear the test-mode Stripe ids before the first live checkout.

Every Stripe id stored so far was created with the TEST key. After the Render
dashboard switches to the live key those ids do not exist in live mode:
`ensure_customer` would send a dead customer id to Checkout, and the webhook
would match nothing. This command clears them once.

What it clears: `User.stripe_customer_id` on every user that has one; on every
`Subscription` with a non-empty `stripe_subscription_id` or `stripe_ref`, both
fields and `last_event_created`.

What it never touches: `status`, `payer`, `current_period_end`,
`cancel_at_period_end`, `confirmation_sent_at`. Rows the owner set Active by
hand for the beta families must survive; rows left Active by old test
checkouts are printed with `REVIEW` so the owner sets them Inactive in the
admin.

Dry run unless `--apply`. `--apply` refuses while `STRIPE_SECRET_KEY` starts
with `sk_test_`: the live key must already be in the environment. Run once,
after the key switch, before anyone checks out.

Run:  python main.py stripe_live_cutover
      python main.py stripe_live_cutover --apply
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from accounts.models import User
from billing.models import Subscription


def _domain(user):
    if user is None or not user.email:
        return "-"
    return "@" + user.email.rsplit("@", 1)[-1]


class Command(BaseCommand):
    help = "Clear test-mode Stripe ids before the first live checkout (dry run unless --apply)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true",
                            help="Write the changes. Without it nothing is changed.")

    def handle(self, *args, apply, **options):
        if apply and settings.STRIPE_SECRET_KEY.startswith("sk_test_"):
            raise CommandError("STRIPE_SECRET_KEY is a test key; switch the dashboard to the live key first.")
        customers = list(User.objects.exclude(stripe_customer_id="").order_by("pk"))
        subs = list(
            Subscription.objects.filter(Q(stripe_subscription_id__gt="") | Q(stripe_ref__gt=""))
            .select_related("user", "payer").order_by("pk")
        )
        verb = "cleared" if apply else "would clear"
        with transaction.atomic():
            for user in customers:
                self.stdout.write(f"customer {user.role} {_domain(user)}: {verb} stripe_customer_id")
            for sub in subs:
                line = f"subscription {sub.user.username} {_domain(sub.payer)} {sub.status}: {verb} Stripe id"
                if sub.status == Subscription.Status.ACTIVE:
                    line += "  REVIEW: active with a cleared Stripe id"
                self.stdout.write(line)
            if apply:
                User.objects.filter(pk__in=[u.pk for u in customers]).update(stripe_customer_id="")
                Subscription.objects.filter(pk__in=[s.pk for s in subs]).update(
                    stripe_subscription_id="", stripe_ref="", last_event_created=None,
                )
        if not apply:
            self.stdout.write("dry run: nothing changed")
        self.stdout.write(
            f"stripe_live_cutover: {len(customers)} customer ids, {len(subs)} subscriptions "
            f"{'cleared' if apply else 'would be cleared'}"
        )
