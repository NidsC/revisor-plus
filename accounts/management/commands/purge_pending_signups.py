"""
Delete offer-funnel parent accounts that were created before payment and never completed.

The offer funnel (billing/funnel.py) creates a parent with an unusable password, a placeholder
pupil and a Subscription row before sending the parent to Stripe. offer_success clears
`offer_pending_since` and logs the parent in when the paid session returns. A parent who closes
the tab leaves the pending account behind; this command removes it.

Selected: a parent (role=parent) whose `offer_pending_since` is older than
`settings.OFFER_PENDING_HOURS` (48), who has never logged in (`last_login` is empty), still has
an unusable password, and is the payer of no Subscription that is anything other than INACTIVE.

The Stripe check: for each selected parent that has a `stripe_customer_id`, Stripe is asked for
that customer's subscriptions. Any subscription at all (or a Stripe error) drops the parent from
the list with a "skip" line, so a parent who paid but whose success page or webhook has not been
processed yet is never deleted. A parent with no customer id has never reached Stripe's payment.

Deleting a parent cascades the placeholder pupil and its Subscription row.

Dry run by default: lists what it would delete. Pass --apply to delete. A live run refuses to
delete more than --max-deletions parents (default 50) unless --allow-mass is passed. Every
selected parent is printed first, so the log names them; a dry run prints a WARNING instead and
exits normally. build.sh never passes --allow-mass.

Run:  python main.py purge_pending_signups
      python main.py purge_pending_signups --apply
      python main.py purge_pending_signups --apply --max-deletions 200 --allow-mass
"""
from datetime import timedelta

import stripe
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from billing.models import Subscription
from billing.stripe_sync import _configure, as_dict


def _domain(user):
    return (user.email or "").rpartition("@")[2] or "-"


class Command(BaseCommand):
    help = "Delete funnel parents still pending after OFFER_PENDING_HOURS with no login and no subscription (dry run unless --apply)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="delete; without it the command only lists")
        parser.add_argument("--max-deletions", type=int, default=50, help="refuse a live run that would delete more parents than this (default 50)")
        parser.add_argument("--allow-mass", action="store_true", help="override --max-deletions for one run; build.sh never passes this")

    def _select(self):
        cutoff = timezone.now() - timedelta(hours=settings.OFFER_PENDING_HOURS)
        candidates = User.objects.filter(
            role=User.Role.PARENT, offer_pending_since__lt=cutoff, last_login__isnull=True,
        ).order_by("pk")
        return [
            u for u in candidates
            if not u.has_usable_password()
            and not Subscription.objects.filter(payer=u).exclude(status=Subscription.Status.INACTIVE).exists()
        ]

    def _stripe_has_subscription(self, user):
        """True when Stripe knows a subscription for this customer, or cannot be asked."""
        _configure()
        try:
            found = as_dict(stripe.Subscription.list(customer=user.stripe_customer_id, limit=1))
        except stripe.error.StripeError as exc:
            self.stdout.write(f"skip {user.username} @{_domain(user)}: could not ask Stripe ({type(exc).__name__})")
            return True
        if found.get("data"):
            self.stdout.write(f"skip {user.username} @{_domain(user)}: Stripe has a subscription for this customer")
            return True
        return False

    def handle(self, *args, **opts):
        dry = not opts["apply"]
        max_deletions, allow_mass = opts["max_deletions"], opts["allow_mass"]
        if max_deletions < 0:
            raise CommandError("--max-deletions must be 0 or more")
        plan = [u for u in self._select() if not (u.stripe_customer_id and self._stripe_has_subscription(u))]
        for u in plan:
            self.stdout.write(
                f"{u.username} @{_domain(u)} pending since {u.offer_pending_since:%Y-%m-%d %H:%M}: "
                f"{'would delete' if dry else 'deleting'}"
            )
        over_cap = len(plan) > max_deletions and not allow_mass
        if over_cap and dry:
            self.stdout.write(f"WARNING: {len(plan)} selected exceeds --max-deletions {max_deletions}; a live run would refuse")
        if over_cap and not dry:
            raise CommandError(
                f"{len(plan)} parents selected exceeds --max-deletions {max_deletions}; nothing deleted "
                "(pass --allow-mass to override after reading the list above)"
            )
        deleted = 0
        if not dry:
            with transaction.atomic():
                for u in plan:
                    u.delete()
                    deleted += 1
        self.stdout.write(f"purge_pending_signups: {len(plan)} selected, {deleted} deleted")
