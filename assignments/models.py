from django.conf import settings
from django.db import models


class Assignment(models.Model):
    class Status(models.TextChoices):
        ASSIGNED = "assigned", "Assigned"
        COMPLETED = "completed", "Completed"

    tutor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="assignments_set"
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="assignments_received"
    )
    subtopic = models.ForeignKey("catalog.Subtopic", on_delete=models.CASCADE, related_name="assignments")
    target_count = models.PositiveIntegerField(default=5)
    due_date = models.DateField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ASSIGNED)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["due_date"]

    def __str__(self):
        return f"{self.student} · {self.subtopic} · {self.status}"

    def progress_count(self):
        """Attempts by this student on this subtopic since the assignment was set."""
        from practice.models import Attempt

        return Attempt.objects.filter(
            student=self.student, subtopic=self.subtopic, created_at__gte=self.created_at
        ).count()

    def refresh_status(self):
        """Auto-complete when the student has done enough attempts (derived, not self-reported)."""
        if self.status != self.Status.COMPLETED and self.progress_count() >= self.target_count:
            self.status = self.Status.COMPLETED
            self.save(update_fields=["status"])
        return self.status
