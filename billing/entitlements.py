"""Answers two questions: is this pupil Premium, and how many free answers are
left for this paper? Views consult this module rather than reading
`Subscription` directly, so the entitlement rules live in exactly one place.
"""
from django.conf import settings
from django.utils import timezone

from .models import Subscription

# Lifetime free-answer cap, per paper (Section). See free_questions_used's
# docstring for why this is lifetime rather than reset on lapse.
FREE_QUESTIONS_PER_PAPER = 100


def _subscription(pupil):
    """The pupil's Subscription row, or None. A missing row means the free
    tier, never an exception — see the Edge Cases note in the plan: "Pupil
    with no Subscription row (should not happen after accounts.views.
    add_child, but:) treated as free tier, never a 500."."""
    return Subscription.objects.filter(user=pupil).first()


def is_premium(pupil) -> bool:
    """Whether `pupil` currently has Premium access.

    `PREMIUM_GATES_ENABLED` is a kill switch: while it is off (the default
    until Phase C is live), everyone is Premium and nothing is gated. Once
    on, Premium follows Stripe's subscription status: `active` and
    `past_due` (kept during Stripe's Smart Retry window) count; a `canceled`
    subscription still counts until its `current_period_end`, so cancelling
    keeps access until the period actually ends.
    """
    if not settings.PREMIUM_GATES_ENABLED:
        return True
    sub = _subscription(pupil)
    if sub is None:
        return False
    if sub.status in (Subscription.Status.ACTIVE, Subscription.Status.PAST_DUE):
        return True
    if sub.status == Subscription.Status.CANCELED:
        return bool(sub.current_period_end and sub.current_period_end > timezone.now())
    return False


def free_questions_used(pupil, section) -> int:
    """Lifetime count of practice answers a pupil has given in this paper.

    Deliberately NOT filtered by Attempt.tier: the cap is lifetime, so
    answers given while Premium still count against it after a lapse — a
    pupil who answered 100 questions during a subscribed month and then
    lapses does not get another 100 free ones. Mock papers never count here:
    a free pupil cannot sit one (billing/entitlements gates mocks
    separately), and timed practice (`?mode=test`) does count, matching the
    plan's "counts toward the cap" note.
    """
    from practice.models import Attempt, TestSession

    return Attempt.objects.filter(
        student=pupil, subtopic__section=section,
    ).exclude(session__mode=TestSession.Mode.MOCK).count()


def free_questions_left(pupil, section) -> int:
    return max(0, FREE_QUESTIONS_PER_PAPER - free_questions_used(pupil, section))


def practice_allowed(pupil, section) -> bool:
    return is_premium(pupil) or free_questions_left(pupil, section) > 0
