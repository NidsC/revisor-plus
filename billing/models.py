from django.conf import settings
from django.db import models


class Subscription(models.Model):
    class Status(models.TextChoices):
        INACTIVE = "inactive", "Inactive"
        ACTIVE = "active", "Active"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscription"
    )
    plan = models.CharField(max_length=50, default="Med-revisor Premium")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.INACTIVE)
    stripe_ref = models.CharField(max_length=120, blank=True)
    current_period_end = models.DateField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} · {self.status}"

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE
