from django.conf import settings
from django.db import models


class School(models.Model):
    """A searchable school imported from the DfE GIAS establishment download."""

    urn = models.CharField(max_length=16, unique=True, db_index=True)
    name = models.CharField(max_length=255, db_index=True)
    postcode = models.CharField(max_length=12, blank=True, db_index=True)
    town = models.CharField(max_length=120, blank=True, db_index=True)
    county = models.CharField(max_length=120, blank=True)
    establishment_type = models.CharField(max_length=160, blank=True)
    admissions_policy = models.CharField(max_length=120, blank=True)
    gender = models.CharField(max_length=80, blank=True)
    phase = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=100, blank=True)
    statutory_low_age = models.PositiveSmallIntegerField(null=True, blank=True)
    statutory_high_age = models.PositiveSmallIntegerField(null=True, blank=True)

    # GIAS provides British National Grid coordinates. These are ideal for
    # postcode-distance ranking because Postcodes.io also returns eastings/northings.
    easting = models.IntegerField(null=True, blank=True, db_index=True)
    northing = models.IntegerField(null=True, blank=True, db_index=True)

    # Lat/lng are cached lazily from the school's postcode when it appears in results.
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["status", "phase"]),
            models.Index(fields=["easting", "northing"]),
        ]

    def __str__(self):
        return self.name


class StudentTargetSchool(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="school_onboarding_targets",
    )
    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name="student_targets",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "school"],
                name="unique_student_target_school",
            )
        ]
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.user} → {self.school}"


class SchoolOnboardingState(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="school_onboarding_state",
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    skipped_at = models.DateTimeField(null=True, blank=True)
    last_postcode = models.CharField(max_length=12, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_finished(self):
        return bool(self.completed_at or self.skipped_at)

    def __str__(self):
        return f"School onboarding: {self.user}"
