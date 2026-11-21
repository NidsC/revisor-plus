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
    # When the purchase confirmation email (billing/emails.py) was sent to the payer. Set
    # before the send as a claim so the webhook and the success page cannot both send;
    # cleared again if the send fails so the next Stripe event retries.
    confirmation_sent_at = models.DateTimeField(null=True, blank=True)
    # Claims for the Meta Conversions API events (billing/meta.py): set inside the same atomic
    # block as the webhook/success write, before the send, so each event goes at most once.
    meta_purchase_sent_at = models.DateTimeField(null=True, blank=True)
    meta_subscribe_sent_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} · {self.status}"

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE


class StripeEvent(models.Model):
    """One row per processed Stripe webhook event id, so a retried delivery
    is a no-op instead of re-applying a change (see billing/views.py webhook
    and stripe_sync.apply_subscription). The webhook creates this row FIRST,
    under a row lock (select_for_update), so a concurrent duplicate delivery
    of the same event id blocks until the first finishes and then sees it
    processed. `processed_at` is set LAST, after the event has been applied,
    all inside one atomic block: a handler failure rolls the whole block back,
    marker row included, so Stripe's retry starts clean. A committed row
    always has `processed_at` set — never mark one processed by hand.
    """
    event_id = models.CharField(max_length=255, unique=True)
    type = models.CharField(max_length=120)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.event_id} · {self.type}"


class Referral(models.Model):
    """A parent's personal refer-a-friend code. One per referrer. The Stripe
    promotion code (on the shared referral coupon) is what the friend types or
    arrives with; `active` is the admin switch, and the Stripe code is
    deactivated alongside it. See billing/referrals.py.
    """
    referrer = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="referral"
    )
    code = models.CharField(max_length=20, unique=True)  # "RP-K7M2QX"
    stripe_promotion_code_id = models.CharField(max_length=120, blank=True, db_index=True)
    active = models.BooleanField(default=True)  # admin switch; the Stripe code is deactivated too
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.code


class ReferralReward(models.Model):
    """The decision taken for one referred subscription. The unique
    `stripe_subscription_id` is the claim: the webhook and the success page
    can race on the same purchase, and whichever writes this row first (under
    the Referral row lock) decides; the other sees it and does nothing. A
    committed row is never re-decided, except FAILED rows by the admin retry.
    """

    class Status(models.TextChoices):
        GRANTED = "granted", "Granted"
        CAPPED = "capped", "Capped"
        REJECTED = "rejected", "Rejected"
        FAILED = "failed", "Failed"
        REVERSED = "reversed", "Reversed"

    referral = models.ForeignKey(Referral, on_delete=models.CASCADE, related_name="rewards")
    referred_parent = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    stripe_subscription_id = models.CharField(max_length=120, unique=True)  # the friend's subscription: one reward per it
    status = models.CharField(max_length=10, choices=Status.choices)
    reason = models.CharField(max_length=120, blank=True)  # why CAPPED / REJECTED / FAILED
    amount_pence = models.PositiveIntegerField(default=0)
    stripe_balance_txn_id = models.CharField(max_length=120, blank=True)
    stripe_reversal_txn_id = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reversed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.status} · {self.stripe_subscription_id}"
