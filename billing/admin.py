import stripe
from django.contrib import admin, messages
from django.db import transaction
from django.db.models import Count, Q

from . import referrals
from .models import Referral, ReferralReward, StripeEvent, Subscription
from .stripe_sync import _configure


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "user", "plan", "status", "payer", "current_period_end",
        "cancel_at_period_end", "updated_at",
    )
    list_filter = ("status",)


@admin.register(StripeEvent)
class StripeEventAdmin(admin.ModelAdmin):
    list_display = ("event_id", "type", "received_at", "processed_at")
    list_filter = ("type",)


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = ("referrer", "code", "active", "created_at", "granted_count")
    search_fields = ("code", "referrer__email")
    actions = ("deactivate_code",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            granted_count=Count("rewards", filter=Q(rewards__status=ReferralReward.Status.GRANTED)),
        )

    @admin.display(description="Credits granted", ordering="granted_count")
    def granted_count(self, obj):
        return obj.granted_count

    @admin.action(description="Deactivate code")
    def deactivate_code(self, request, queryset):
        _configure()
        done = 0
        for ref in queryset:
            try:
                if ref.stripe_promotion_code_id:
                    stripe.PromotionCode.modify(ref.stripe_promotion_code_id, active=False)
            except stripe.error.StripeError as exc:
                self.message_user(request, f"Stripe refused for {ref.code}: {type(exc).__name__}",
                                  level=messages.ERROR)
                continue
            ref.active = False
            ref.save(update_fields=["active"])
            done += 1
        self.message_user(request, f"{done} code(s) deactivated.")


@admin.register(ReferralReward)
class ReferralRewardAdmin(admin.ModelAdmin):
    list_display = (
        "created_at", "referral", "referred_parent", "status", "reason",
        "amount_pence", "stripe_subscription_id",
    )
    list_filter = ("status",)
    search_fields = ("referral__code", "referred_parent__email", "stripe_subscription_id")
    readonly_fields = (
        "stripe_subscription_id", "stripe_balance_txn_id", "stripe_reversal_txn_id",
        "created_at", "reversed_at",
    )
    actions = ("reverse_credit", "retry_credit")

    @admin.action(description="Reverse credit")
    def reverse_credit(self, request, queryset):
        done = 0
        for reward in queryset.filter(status=ReferralReward.Status.GRANTED):
            with transaction.atomic():
                if referrals.reverse_reward(reward) is not None:
                    done += 1
        self.message_user(request, f"{done} credit(s) reversed.")

    @admin.action(description="Retry credit")
    def retry_credit(self, request, queryset):
        done = 0
        for reward in queryset.filter(status=ReferralReward.Status.FAILED):
            if referrals.retry_failed(reward).status == ReferralReward.Status.GRANTED:
                done += 1
        self.message_user(request, f"{done} credit(s) granted.")
