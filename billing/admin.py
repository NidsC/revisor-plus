from django.contrib import admin

from .models import StripeEvent, Subscription


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
