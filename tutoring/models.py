from django.conf import settings
from django.db import models


class TutorStudent(models.Model):
    """The authorization/tenancy spine: which students a tutor may access."""

    tutor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="students_link"
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tutors_link"
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("tutor", "student")

    def __str__(self):
        return f"{self.tutor} -> {self.student}"
