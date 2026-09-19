from django.conf import settings
from django.db import models


class Subscription(models.Model):
    class Status(models.TextChoices):
        INACTIVE = "inactive", "Inactive"
        ACTIVE = "active", "Active"
        PAST_DUE = "past_due", "Past due"
        CANCELED = "canceled", "Canceled"
        UNPAID = "unpaid", "Unpaid"
        INCOMPLETE = "incomplete", "Incomplete"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscription"
    )
    # The parent who pays, once Stripe is wired up in Phase C. Nullable because
    # every pupil gets a Subscription row at creation (accounts.views.add_child,
    # seed_demo) before any parent has ever paid.
    payer = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="paid_subscriptions",
    )
    plan = models.CharField(max_length=50, default="RevisorPlus Premium")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.INACTIVE)
    stripe_ref = models.CharField(max_length=120, blank=True)
    stripe_subscription_id = models.CharField(max_length=120, blank=True, db_index=True)
    cancel_at_period_end = models.BooleanField(default=False)
    current_period_end = models.DateTimeField(null=True, blank=True)
    # The Stripe event timestamp of the last change applied to this row —
    # Phase C's ordering guard reads this so an out-of-order webhook delivery
    # can never overwrite a newer state with an older one.
    last_event_created = models.DateTimeField(null=True, blank=True)
    # Set when a non-premium pupil is turned away from a mock paper — the
    # demand signal a parent sees on their home page (Phase C, step 29).
    last_mock_blocked_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} · {self.status}"

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE


class StripeEvent(models.Model):
    """One row per processed Stripe webhook event id, so a retried delivery
    is a no-op instead of re-applying a change (see billing/views.py webhook
    and stripe_sync.apply_subscription). `processed_at` is written only after
    the event's apply_subscription call succeeds and inside the same atomic
    block, so a row with `processed_at` null (after a delivery Stripe shows
    as sent) means the handler raised — never mark one processed by hand.
    """
    event_id = models.CharField(max_length=255, unique=True)
    type = models.CharField(max_length=120)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.event_id} · {self.type}"
