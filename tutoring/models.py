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


class TutorMessage(models.Model):
    """A message in the private conversation between a tutor and a pupil's parent.

    The current demo uses the pupil account to expose the parent dashboard, so
    the student side of the TutorStudent link represents the parent/family side
    of the conversation. Keeping messages attached to the TutorStudent link
    prevents a tutor from accidentally reading or writing another pupil's
    thread.
    """

    link = models.ForeignKey(
        TutorStudent,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tutor_messages_sent",
    )
    body = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("created_at", "id")

    def __str__(self):
        return f"Message {self.pk} on {self.link}"
