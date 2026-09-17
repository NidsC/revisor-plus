from django.contrib import admin

from .models import Subscription


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "user", "plan", "status", "payer", "current_period_end",
        "cancel_at_period_end", "updated_at",
    )
    list_filter = ("status",)
