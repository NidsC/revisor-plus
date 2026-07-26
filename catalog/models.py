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
    """A question, or one answerable part of one.

    Multi-part questions (a Maths item with parts a/b/c) are modelled as a parent
    row carrying the shared stem and figure, plus one child row per part. Only
    leaves — rows with no children — are answerable and go into practice decks;
    the parent exists to supply context.
    """

    class Kind(models.TextChoices):
        MCQ = "mcq", "Multiple choice"
        NUMERIC = "numeric", "Numeric entry"
        SHORT_TEXT = "short_text", "Short text"
        EXTENDED_TEXT = "extended_text", "Extended writing"

    class Marking(models.TextChoices):
        AUTO = "auto", "Auto-marked"          # exact / numeric-with-tolerance
        KEYWORD = "keyword", "Keyword-matched"  # short text, accept/reject lists
        RUBRIC = "rubric", "Rubric — needs a marker"

    subtopic = models.ForeignKey(Subtopic, on_delete=models.CASCADE, related_name="questions")
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.MCQ)
    passage = models.TextField(blank=True)
    stem = models.TextField()
    explanation = models.TextField(blank=True)
    difficulty = models.PositiveSmallIntegerField(default=2)  # 1-5
    active = models.BooleanField(default=True)
    # Static-relative path to a chart/diagram, e.g. "questions/paper_mat_01_q21.svg"
    image = models.CharField(max_length=200, blank=True)
    is_placeholder = models.BooleanField(default=False)  # disposable demo content, not owned IP
    source = models.CharField(max_length=50, blank=True)  # e.g. "CONTRIB-ALEX-01", "seed"
    # Stable identity for generated questions: sha1(generator|template|params).
    # generate_bank matches on this and update_or_creates, so re-running keeps the
    # same row ids. That matters because deleting a Question CASCADES to every
    # Attempt against it — a regenerate that recreated rows would silently wipe
    # pupils' history and every ability estimate derived from it.
    gen_key = models.CharField(max_length=40, blank=True, db_index=True)

    # --- multi-part -------------------------------------------------------
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="parts"
    )
    label = models.CharField(max_length=4, blank=True)  # "a", "b", "c"
    order = models.PositiveIntegerField(default=0)

    # --- marking ----------------------------------------------------------
    marks = models.PositiveSmallIntegerField(default=1)
    marking = models.CharField(max_length=10, choices=Marking.choices, default=Marking.AUTO)
    # Canonical answer for non-MCQ kinds. Stored as text so numeric and short
    # text share one field; the marking engine parses it per kind.
    answer_text = models.CharField(max_length=200, blank=True)
    tolerance = models.FloatField(default=0)  # numeric only, absolute
    accepted_alternatives = models.JSONField(default=list, blank=True)
    reject_keywords = models.JSONField(default=list, blank=True)  # keyword marking
    unit = models.CharField(max_length=16, blank=True)  # "cm", "°" — shown, not typed
    rubric = models.JSONField(null=True, blank=True)  # {"max": n, "bands": [...]}
    model_answer = models.TextField(blank=True)
    working_note = models.TextField(blank=True)  # method, shown with the explanation
    # Non-image figures rendered as HTML: {"kind": "table"|"number_box", "data": ...}
    figure = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["order", "id"]
        indexes = [
            # Deck building is the hot path: filter by subtopic, active, and
            # (once the adaptive engine lands) difficulty band.
            models.Index(fields=["subtopic", "active", "difficulty"],
                         name="question_subtopic_active_d"),
        ]

    def __str__(self):
        return f"[{self.subtopic.section.code}] {self.display_stem[:60]}"

    def correct_option(self):
        return self.options.filter(is_correct=True).first()

    @property
    def is_container(self):
        """True when this row only supplies context for its parts."""
        return self.parts.exists()

    @property
    def display_stem(self):
        """A part's own stem, prefixed with its parent's shared stem."""
        if self.parent_id and self.parent.stem and self.parent.stem != self.stem:
            return f"{self.parent.stem} {self.stem}".strip()
        return self.stem

    @property
    def context_passage(self):
        return self.passage or (self.parent.passage if self.parent_id else "")

    @property
    def context_image(self):
        return self.image or (self.parent.image if self.parent_id else "")

    @property
    def context_figure(self):
        return self.figure or (self.parent.figure if self.parent_id else None)


class AnswerOption(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="options")
    text = models.CharField(max_length=400)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.text
