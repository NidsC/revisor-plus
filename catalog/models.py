from django.db import models


class Section(models.Model):
    """An 11+ paper, e.g. English."""

    code = models.CharField(max_length=10, unique=True)  # ENG, MAT, VR, NVR
    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.code} — {self.name}"


class Subtopic(models.Model):
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="subtopics")
    name = models.CharField(max_length=150)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["section__order", "order"]

    def __str__(self):
        return f"{self.section.code} · {self.name}"


class Question(models.Model):
    class Kind(models.TextChoices):
        MCQ = "mcq", "Multiple choice"

    subtopic = models.ForeignKey(Subtopic, on_delete=models.CASCADE, related_name="questions")
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.MCQ)
    passage = models.TextField(blank=True)
    stem = models.TextField()
    explanation = models.TextField(blank=True)
    difficulty = models.PositiveSmallIntegerField(default=2)  # 1-3
    active = models.BooleanField(default=True)
    # Static-relative path to a chart/table/diagram image, e.g. "questions/dm_q3.png"
    image = models.CharField(max_length=200, blank=True)
    is_placeholder = models.BooleanField(default=False)  # disposable demo content, not owned IP
    source = models.CharField(max_length=50, blank=True)  # e.g. "CONTRIB-ALEX-01", "seed"

    def __str__(self):
        return f"[{self.subtopic.section.code}] {self.stem[:60]}"

    def correct_option(self):
        return self.options.filter(is_correct=True).first()


class AnswerOption(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="options")
    text = models.CharField(max_length=400)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.text
