from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user with a role. Email is the login identifier."""

    class Role(models.TextChoices):
        STUDENT = "student", "Student"
        TUTOR = "tutor", "Tutor"
        ADMIN = "admin", "Admin"
        PARENT = "parent", "Parent"

    email = models.EmailField("email address", unique=True, null=True, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)
    full_name = models.CharField(max_length=150, blank=True)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="children",
        limit_choices_to={"role": "parent"},
    )
    # Set on parents only, once Phase C creates a Stripe Customer for them.
    stripe_customer_id = models.CharField(max_length=120, blank=True, db_index=True)
    # Set when a parent or tutor ticks the Terms agreement (sign-up, or family:accept_terms
    # for accounts from before the Terms were published). Pupils never agree: the parent does.
    terms_accepted_at = models.DateTimeField(null=True, blank=True)
    terms_version = models.CharField(max_length=20, blank=True)
    # Offer funnel (billing/funnel.py): set when the funnel creates the account before payment,
    # cleared when the paid Stripe session logs the parent in. purge_pending_signups removes
    # accounts still pending after OFFER_PENDING_HOURS.
    offer_pending_since = models.DateTimeField(null=True, blank=True)
    offer_code = models.CharField(max_length=40, blank=True)

    def __str__(self):
        return self.full_name or self.email or self.username

    @property
    def is_student(self):
        return self.role == self.Role.STUDENT

    @property
    def is_tutor(self):
        return self.role == self.Role.TUTOR

    @property
    def is_parent(self):
        return self.role == self.Role.PARENT
