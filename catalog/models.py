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
    # The topic this subtopic belongs to, e.g. "Geometry". A label validated
    # against elevenplus_data/taxonomy.json and written by `sync_taxonomy`, not
    # a ForeignKey: a Topic table would put a cascade path into Attempt every
    # time the taxonomy is revised, and revision against real papers is the
    # plan. Same reasoning as Question.question_type.
    #
    # STRUCTURAL ONLY. The seven-paper audit of 250 questions found that no real
    # 11+ paper groups its questions by topic — where papers have sections they
    # are named by answer format or shared stimulus, and several are
    # deliberately topic-shuffled. This exists so a pupil's weakness report can
    # clear the eight-attempt evidence floor in analytics sooner (8 topics
    # rather than 17 subtopics), and so the practice picker can group. It is not
    # a claim about how exams are built.
    topic = models.CharField(max_length=80, blank=True)
    topic_order = models.PositiveSmallIntegerField(default=0)

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
    # Which syllabus question type this item is, e.g. "roman-numerals". The
    # third level of the taxonomy: Section -> Subtopic -> question type. Slugs
    # are scoped BY SUBTOPIC (elevenplus_data/taxonomy.json is the canonical
    # list), so the same slug may legitimately appear under two subtopics and
    # this field is only meaningful alongside subtopic_id.
    #
    # Deliberately not a ForeignKey: it carries no data of its own, and a table
    # would mean a cascade path into Question every time the syllabus is
    # revised. Revising the taxonomy against real papers is the stated plan, so
    # a plain slug keeps that a data edit rather than a destructive migration.
    #
    # Blank for sections whose taxonomy has not been rebuilt yet (ENG/VR/NVR)
    # and for the pre-rebuild generated bank.
    question_type = models.CharField(max_length=60, blank=True, db_index=True)
    # Other (subtopic, question_type) pairs a question genuinely requires, as
    # [{"subtopic": "...", "question_type": "..."}]. The audit of 250 real
    # questions found 38% need more than one subtopic, and the single filed type
    # names the last or hardest step rather than the question. Without this a
    # subtopic can be load-bearing across a whole paper and still register zero
    # — Collins GL 10-11 showed exactly that for Measurement — which distorts
    # both the weakness diagnosis and the frequency data targets are set from.
    #
    # Secondary by definition: `subtopic` and `question_type` remain where the
    # question is filed and what practice decks are built from. Nothing reads
    # this yet; it is recorded now so the data exists when analytics wants it.
    also_tests = models.JSONField(default=list, blank=True)
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.MCQ)
    passage = models.TextField(blank=True)
    # The line or range of the passage this question is about, e.g. "12" or
    # "20-21". Comprehension questions cite a line constantly — "another way of
    # saying 'lulled' (line 1)" — and before this the reference had to be
    # written into the stem, where it could not be rendered distinctly or
    # checked against anything. Passage lines are numbered by wrapping at
    # PASSAGE_LINE_WIDTH, so the number means the same thing to the author and
    # to the pupil.
    line_ref = models.CharField(max_length=16, blank=True)
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
    # WHY this wrong answer is tempting, as a slug: "used-the-wrong-percentage",
    # "confused-area-with-perimeter". The generators build distractors from an
    # error model rather than picking plausible-looking numbers, so each one
    # already knows the mistake it represents — this is where that knowledge is
    # kept so feedback can name the slip instead of only saying "not quite".
    misconception = models.CharField(max_length=60, blank=True)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.text

    @property
    def misconception_text(self):
        """The slug as a readable phrase, for showing to a pupil."""
        return self.misconception.replace("-", " ") if self.misconception else ""
