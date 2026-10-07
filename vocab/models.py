"""
The vocabulary trainer: words, which pack they are in, and each pupil's progress.

Deliberately separate from the question bank. Nothing here has a foreign key
into catalog: import_pack, import_paper and generate_bank all hard-delete
questions, and anything hanging off a Question or Subtopic by CASCADE would go
with them. Words come from vocab/data/*.json through `load_vocab`, which never
deletes a word either — see that command for why.

What is deleted, and by what:
  * A pupil's progress, profile and rounds CASCADE from the pupil, the same as
    their practice attempts. Deleting a parent deletes their children
    (accounts.User.parent is CASCADE), and so this too.
  * A Word is never deleted while anything points at it: WordProgress and
    RoundItem hold it with PROTECT. A word dropped from the packs is set
    inactive instead, and a pupil's history with it stays.
  * A WordPack is held with PROTECT by Round for the same reason.
"""
from django.conf import settings
from django.db import models


class WordPack(models.Model):
    """One file in vocab/data/. `slug` is the file name: "gl", "general"."""

    slug = models.SlugField(max_length=40, unique=True)
    title = models.CharField(max_length=100)

    class Meta:
        ordering = ["slug"]

    def __str__(self):
        return self.title


class Word(models.Model):
    """One headword, stored once however many packs it is in.

    Stored once so that a pupil whose pack changes (they pick a target school,
    or change it) keeps their progress on every word the two packs share.
    The fields mirror the pack format checked by vocab/validate_words.py.
    """

    class Pos(models.TextChoices):
        NOUN = "noun", "Noun"
        VERB = "verb", "Verb"
        ADJECTIVE = "adjective", "Adjective"
        ADVERB = "adverb", "Adverb"

    headword = models.CharField(max_length=40, unique=True)
    pos = models.CharField(max_length=10, choices=Pos.choices)
    year = models.PositiveSmallIntegerField()  # 5-8
    definition = models.TextField()
    synonyms = models.JSONField(default=list)
    # Entries close enough in meaning that they are never wrong options for
    # each other. See validate_words.py's header.
    group = models.SlugField(max_length=60)
    example = models.TextField()
    gap_frame = models.TextField()
    gap_distractors = models.JSONField(default=list)

    packs = models.ManyToManyField(WordPack, related_name="words", blank=True)
    # False once a word is no longer in any pack file. Kept, not deleted, because
    # pupils' progress and past rounds point at it.
    active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["headword"]

    def __str__(self):
        return self.headword


class VocabProfile(models.Model):
    """A pupil's running totals. One row per pupil, created on first play.

    The level is not stored: it is worked out from `xp`, so changing the level
    thresholds later needs no data migration.
    """

    pupil = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="vocab_profile"
    )
    xp = models.PositiveIntegerField(default=0)
    current_streak = models.PositiveIntegerField(default=0)
    best_streak = models.PositiveIntegerField(default=0)
    # A date from timezone.localdate(), so the day turns over at UK midnight
    # (settings.TIME_ZONE), BST included. Null until the first finished round.
    last_played_on = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.pupil}: {self.xp} XP, streak {self.current_streak}"


class WordProgress(models.Model):
    """Where one word sits in one pupil's spaced-repetition schedule.

    No row means the pupil has not met the word yet. `box` runs from 1 (just
    met, or just got wrong) upwards; each box has a longer gap before the word
    is due again. The intervals live in vocab/services.py, not here.
    """

    pupil = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="vocab_progress"
    )
    word = models.ForeignKey(Word, on_delete=models.PROTECT, related_name="progress")
    box = models.PositiveSmallIntegerField(default=1)
    due_on = models.DateField()  # timezone.localdate() based, like the streak
    times_seen = models.PositiveIntegerField(default=0)
    times_correct = models.PositiveIntegerField(default=0)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["pupil", "word"], name="vocab_progress_once_per_word"),
        ]
        indexes = [models.Index(fields=["pupil", "due_on"])]

    def __str__(self):
        return f"{self.pupil} / {self.word}: box {self.box}, due {self.due_on}"


class Round(models.Model):
    """One round of ten items. Built and marked on the server.

    Every item's options and answer are fixed when the round is built, so a
    refresh shows the same question and the answer never reaches the browser
    before the pupil commits to one.
    """

    class Kind(models.TextChoices):
        MIXED = "mixed", "Mixed"
        SYNONYM = "synonym", "Synonym match"
        ODD_ONE_OUT = "odd_one_out", "Odd one out"
        GAP = "gap", "Fill the gap"

    pupil = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="vocab_rounds"
    )
    pack = models.ForeignKey(WordPack, on_delete=models.PROTECT, related_name="rounds")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    xp_awarded = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-started_at"]
        indexes = [models.Index(fields=["pupil", "-started_at"])]

    def __str__(self):
        return f"{self.pupil}: {self.get_kind_display()} ({self.started_at:%Y-%m-%d})"


# What a single item can be. "mixed" describes a round, never an item.
ITEM_KINDS = [(k, label) for k, label in Round.Kind.choices if k != Round.Kind.MIXED]


class RoundItem(models.Model):
    """One question in a round.

    `kind` is per item, not only per round, so a mixed round needs no
    migration later. `chosen_index` is null until answered, and an item is
    answered once: marking only ever updates a row whose chosen_index is
    still null, so a double submit cannot score twice.
    """

    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name="items")
    position = models.PositiveSmallIntegerField()  # 0-9
    word = models.ForeignKey(Word, on_delete=models.PROTECT, related_name="round_items")
    kind = models.CharField(max_length=20, choices=ITEM_KINDS)
    options = models.JSONField()  # the four options, in the order shown
    answer_index = models.PositiveSmallIntegerField()
    chosen_index = models.PositiveSmallIntegerField(null=True, blank=True)
    correct = models.BooleanField(null=True, blank=True)
    answered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["round", "position"]
        constraints = [
            models.UniqueConstraint(fields=["round", "position"], name="vocab_item_position_once"),
        ]

    def __str__(self):
        return f"{self.round_id}#{self.position}: {self.word}"
