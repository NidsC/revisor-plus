"""
Question generators.

Procedural generation rather than authored content, for three reasons beyond cost:

1. Difficulty is a PARAMETER, not a judgement. "35% of 240" is a d2 because it
   decomposes into 30%+5%; "17.5% of 3,480" is a d4 because it does not. That is
   reproducible, whereas a model or a human self-rating difficulty drifts between
   sessions — and the adaptive engine reads difficulty as its only signal, so
   drift there is drift in what every pupil gets served.
2. Distractors come from an error model. The wrong options for 35% of 240 are the
   mistakes pupils actually make: 96 (used 40%), 74 (arithmetic slip), 8.4
   (decimal place). Those feed per-misconception feedback later; random plausible
   numbers cannot.
3. No licensing question. Nothing here derives from a copyrighted paper.

Adding a generator: subclass Generator, set slug/section/subtopic, implement
build(rng, difficulty) -> Item or None, and register it. `slug` is part of every
gen_key, so RENAMING A SLUG ORPHANS THAT GENERATOR'S QUESTIONS — they will be
retired and a fresh set created. Rename only deliberately.
"""
import hashlib
import json
from dataclasses import dataclass, field

REGISTRY = []


@dataclass
class Item:
    """One generated question, before it becomes a Question row."""

    stem: str
    options: list                      # [(text, is_correct), ...] — exactly one True
    difficulty: int                    # 1-5, DERIVED from params, never random
    params: dict                       # identity input for gen_key
    explanation: str = ""
    passage: str = ""
    figure: dict = None
    # Maps a distractor's text to the misconception it represents, so feedback can
    # say why that answer is tempting rather than just "wrong".
    misconceptions: dict = field(default_factory=dict)

    def key(self, generator_slug, template_id):
        """Stable identity. Same generator + template + params -> same row."""
        blob = json.dumps(
            {"g": generator_slug, "t": template_id, "p": self.params},
            sort_keys=True, separators=(",", ":"), default=str,
        )
        return hashlib.sha1(blob.encode()).hexdigest()


class Generator:
    slug = ""
    section = ""      # ENG / MAT / VR / NVR
    subtopic = ""     # must match a canonical subtopic name exactly
    template_id = "0"
    # Which difficulties this generator can actually produce. Asking for one it
    # cannot make returns None rather than a mislabelled question.
    difficulties = (1, 2, 3, 4, 5)

    def build(self, rng, difficulty):
        raise NotImplementedError

    def __repr__(self):
        return f"<{self.slug} {self.section}/{self.subtopic}>"


def register(cls):
    REGISTRY.append(cls())
    return cls


def shuffled_options(rng, correct, distractors, keep=3):
    """Options in random order with exactly one correct.

    Distractors are de-duplicated and any colliding with the correct answer are
    dropped: an error model can legitimately land on the right answer (1/2 of a
    number is the same whether you stop after dividing or not), and two identical
    options make a question unanswerable rather than hard. Pass MORE distractors
    than you need and let `keep` trim — that way a collision costs a spare rather
    than the question.
    """
    seen = {str(correct)}
    clean = []
    for d in distractors:
        text = str(d)
        if text not in seen:
            seen.add(text)
            clean.append(text)
    options = [(str(correct), True)] + [(d, False) for d in clean[:keep]]
    rng.shuffle(options)
    return options


def load_all():
    """Import the generator modules so their registrations run."""
    from . import english, maths, nonverbal, verbal  # noqa: F401

    return REGISTRY
