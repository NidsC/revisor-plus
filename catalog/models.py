from django.db import models

# The label an error-span question gives its "no mistake" answer. Real papers
# print N beside it, and a pupil who thinks the sentence is already correct has
# to have somewhere to say so.
NO_ERROR_LABEL = "N"
NO_ERROR_TEXT = "No mistake"

# The letters a paper prints beside its choices, in order.
OPTION_LABELS = ("A", "B", "C", "D", "E", "F", "G", "H")


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
        # The pupil picks a stretch of the text in front of them rather than an
        # answer written underneath it. Mechanically these mark like multiple
        # choice — the options are the stretches — but they are not multiple
        # choice to look at, and rendering them as a list of answers is not what
        # a child meets in the exam.
        ERROR_SPAN = "error_span", "Spot the error"
        SELECT_WORD = "select_word", "Click the word"
        CLOZE_GAP = "cloze_gap", "Cloze gap"
        # "Money is to (coins, bank, shopping) as tea is to (sandwich, cup,
        # caddy)" — the pupil picks one word from EACH bracket and the answer is
        # the pair. GL verbal reasoning prints these for analogies, similars and
        # opposites, which is a large part of the paper.
        #
        # Not expressible as `mcq`: that takes one flat option list with exactly
        # one key, and flattening two brackets into nine combined options is not
        # what the child is shown. Not two questions either — a paper gives one
        # mark for the pair, and splitting them would deal the halves into
        # separate practice decks.
        GROUPED_OPTIONS = "grouped_options", "One from each bracket"

    #: Kinds whose options are consecutive pieces of the stem, not answers.
    SELECTION_KINDS = frozenset({"error_span", "select_word"})
    #: Kinds whose options are divided into brackets, one pick from each.
    GROUPED_KINDS = frozenset({"grouped_options"})

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
    # A passage's title, and where the text came from. They live on the container
    # row that owns the passage, and its questions read them through
    # `context_passage_title` / `context_passage_source`.
    #
    # The source note is not decoration: it is what separates a public-domain
    # extract from someone else's copyright. A bank that cannot say which is
    # which cannot safely be published, so it is carried rather than dropped.
    passage_title = models.CharField(max_length=200, blank=True)
    passage_source = models.CharField(max_length=300, blank=True)
    # The line or range of the passage this question is about, e.g. "12" or
    # "20-21". Comprehension questions cite a line constantly — "another way of
    # saying 'lulled' (line 1)" — and before this the reference had to be
    # written into the stem, where it could not be rendered distinctly or
    # checked against anything. Passage lines are numbered by wrapping at
    # PASSAGE_LINE_WIDTH, so the number means the same thing to the author and
    # to the pupil.
    line_ref = models.CharField(max_length=16, blank=True)
    # Which gap of its passage a cloze question fills. A cloze section is one
    # passage with ten numbered gaps, not ten questions each repeating the
    # passage, and this is what lets the two be told apart when rendering.
    gap_number = models.PositiveSmallIntegerField(null=True, blank=True)
    # The instruction and worked example a paper prints ONCE above a block of
    # items, carried on every question in the block.
    #
    # For much of verbal reasoning the instruction is not framing, it is the
    # rule: "mal ( ) ens / har ( ) wig" is not a hard question without it, it is
    # not a question at all. The worked example is load-bearing for the same
    # reason — it is where the pupil learns what the brackets mean.
    #
    # Denormalised rather than held on a container row like `passage`, for two
    # reasons. A question routinely needs a passage AND an instruction, or a code
    # table AND an instruction, and `parent` is a single ForeignKey — the
    # collaborator's VR pack has both combinations. And a practice deck is dealt
    # across subtopics, so a question is served alone, out of its block; it has
    # to carry its own instruction or arrive unanswerable. Copying two short
    # strings costs nothing, unlike a 400-word passage.
    instruction = models.TextField(blank=True)
    worked_example = models.TextField(blank=True)
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
    def is_selection(self):
        """True when the options are pieces of the stem rather than answers."""
        return self.kind in self.SELECTION_KINDS

    @property
    def is_grouped(self):
        """True when the options are divided into brackets, one pick from each."""
        return self.kind in self.GROUPED_KINDS

    @property
    def option_groups(self):
        """[(group number, [options])] in reading order, for a grouped question.

        The brackets are numbered from 1, so a question is rendered — and marked
        — bracket by bracket rather than as one long list of words that happens
        to have two right answers in it.
        """
        if not self.is_grouped:
            return []
        groups = {}
        for opt in self.options.all():
            groups.setdefault(opt.group, []).append(opt)
        return sorted(groups.items())

    @property
    def selection_spans(self):
        """The options that are stretches of the stem, in reading order.

        Excludes the "no mistake" choice, which is an answer rather than a span
        and so is rendered apart from the sentence.
        """
        if not self.is_selection:
            return []
        return [o for o in self.options.all() if o.label != NO_ERROR_LABEL]

    @property
    def no_error_option(self):
        """The "no mistake" choice, when this question offers one."""
        if not self.is_selection:
            return None
        return next((o for o in self.options.all() if o.label == NO_ERROR_LABEL), None)

    @property
    def context_passage(self):
        return self.passage or (self.parent.passage if self.parent_id else "")

    @property
    def context_passage_title(self):
        return self.passage_title or (self.parent.passage_title if self.parent_id else "")

    @property
    def context_passage_source(self):
        return self.passage_source or (self.parent.passage_source if self.parent_id else "")

    @property
    def context_image(self):
        return self.image or (self.parent.image if self.parent_id else "")

    @property
    def context_figure(self):
        return self.figure or (self.parent.figure if self.parent_id else None)

    @property
    def has_figure_options(self):
        """True when the answers are pictures rather than words.

        A non-verbal question's options are panels the pupil compares against
        the stem. They used to be drawn *inside* the stem figure, with the
        options themselves holding the bare letters "A".."D" — so the picture
        and the row that marked the answer were kept in step only by list
        position. They are now the same object: each option owns its panel.
        """
        return any(o.figure for o in self.options.all())


class AnswerOption(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="options")
    text = models.CharField(max_length=400)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    # The letter a paper prints beside this choice: "A".."E", or "N" for the
    # "no mistake" answer an error-span question offers. Derivable from `order`
    # for an ordinary question, but not for that sentinel — and a spot-the-error
    # question is unreadable if its segments and its escape hatch cannot be told
    # apart. Blank for questions that were never lettered.
    label = models.CharField(max_length=2, blank=True)
    # This option's picture, for a non-verbal question whose answers are panels
    # rather than words: {"kind": "nvr_panel"|"nvr_net", "data": {...}}, drawn by
    # catalog/figures. Null for every ordinary option.
    #
    # `text` stays required and carries the panel in words ("shaded triangle,
    # one dot"). That is not belt-and-braces: the authoring contract's rule is
    # that anything needed to answer a question must also be in the text, so a
    # pupil on a screen reader, or looking at a diagram that failed to draw, can
    # still answer. It is also what the marking and review screens print.
    figure = models.JSONField(null=True, blank=True)
    # Which bracket of a `grouped_options` question this word belongs to,
    # numbered from 1. Zero means "not in a bracket", which is every option of
    # every other kind — so existing rows are already correct and no data
    # migration is needed.
    group = models.PositiveSmallIntegerField(default=0)
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
