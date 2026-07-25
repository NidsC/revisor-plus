from django.conf import settings
from django.db import models
from django.utils import timezone


class TestSession(models.Model):
    class Mode(models.TextChoices):
        PRACTICE = "practice", "Practice"
        TEST = "test", "Timed test"
        HOMEWORK = "homework", "Homework"

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sessions")
    subtopic = models.ForeignKey(
        "catalog.Subtopic", null=True, blank=True, on_delete=models.SET_NULL, related_name="sessions"
    )
    mode = models.CharField(max_length=12, choices=Mode.choices, default=Mode.PRACTICE)
    time_limit_seconds = models.PositiveIntegerField(default=0)  # 0 = untimed
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    deck_state = models.JSONField(null=True, blank=True)  # parked deck while paused

    def __str__(self):
        return f"{self.student} · {self.mode} · {self.started_at:%Y-%m-%d}"


class Attempt(models.Model):
    """One row per answered question — the analytics spine."""

    class Source(models.TextChoices):
        PRACTICE = "practice", "Practice"
        TEST = "test", "Test"
        HOMEWORK = "homework", "Homework"

    session = models.ForeignKey(TestSession, on_delete=models.CASCADE, related_name="attempts")
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="attempts")
    question = models.ForeignKey("catalog.Question", on_delete=models.CASCADE, related_name="attempts")
    subtopic = models.ForeignKey("catalog.Subtopic", on_delete=models.CASCADE, related_name="attempts")
    selected_option = models.ForeignKey(
        "catalog.AnswerOption", null=True, blank=True, on_delete=models.SET_NULL
    )
    is_correct = models.BooleanField(default=False)
    time_taken_ms = models.PositiveIntegerField(default=0)
    source = models.CharField(max_length=12, choices=Source.choices, default=Source.PRACTICE)
    created_at = models.DateTimeField(default=timezone.now)  # settable so seed can backdate

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        mark = "correct" if self.is_correct else "wrong"
        return f"{self.student} · Q{self.question_id} · {mark}"
