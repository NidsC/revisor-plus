"""Turns a pupil's Subscription row into the label a parent sees, on
`family:home` and `family:child`. One place so the wording can't drift
between the two pages (step 29)."""
from django.conf import settings
from django.utils import timezone


def stripe_ready():
    """Whether Checkout can actually run — read from both `billing.views`
    and `accounts.views` so the two never disagree on when to show a
    subscribe button."""
    return bool(settings.STRIPE_SECRET_KEY and settings.STRIPE_PRICE_ID)


def plan_status(sub):
    """Return (label, kind). kind is one of "ok", "warn", "free" — the
    template pairs "warn" with the portal button when stripe_ready."""
    if sub is None or not sub.status or sub.status == sub.Status.INACTIVE:
        return "Free", "free"
    if sub.status == sub.Status.PAST_DUE:
        return "Payment problem, update your card", "warn"
    if sub.status == sub.Status.ACTIVE:
        if sub.cancel_at_period_end and sub.current_period_end:
            return f"Premium until {sub.current_period_end:%-d %b}", "ok"
        return "Premium", "ok"
    if sub.status == sub.Status.CANCELED:
        if sub.current_period_end and sub.current_period_end > timezone.now():
            return f"Premium until {sub.current_period_end:%-d %b}", "ok"
        return "Free", "free"
    return "Free", "free"
