#!/usr/bin/env python3
"""
Builds elevenplus_data/contrib_prash_vr_14.json — 25 Letter Moves questions.

    python3 elevenplus_data/generate_letter_moves.py [OUTPUT.json]

The RNG is seeded, so re-running reproduces the committed pack byte for byte.
Check what comes out with its companion, `check_letter_moves.py`, which
re-derives every answer from the rendered stem — including an exhaustive sweep
of every legal move — without importing this file or the generator.

WHY 25 AND NOT 28 — THREE ENTRIES HAVE A SECOND VALID MOVE
-----------------------------------------------------------
This pack is sized to the measured ceiling of `catalog/generators/verbal.py`'s
`LetterMove`. Its pool is 28 word pairs (10 + 9 + 9 across bands 3-5), and the
class docstring records that each was checked by exhaustive search: "EVERY
possible single-letter move -- any letter, either direction, inserted at any
position in the other word -- is tried against a real-word dictionary, and an
entry is kept only if the intended move is the ONLY one that turns both words
real."

Re-running that sweep found **three entries where a second move also works**:

    band 3  SPEAK -> AID   intended PEAK / SAID, but PEAK / AIDS also works
    band 4  BEAST -> OWL   intended EAST / BOWL, but BEAT / OWLS also works
    band 5  STONE -> PET   intended TONE / PEST, but TONE / PETS also works

All three rivals are the same move — take the S and put it on the END of the
second word — and all three are plurals. That is the whole explanation: the
sweep was run against `/usr/share/dict/web2`, which lists lemmas, so `aids`,
`owls` and `pets` are simply not in it. `HiddenWord`'s pool has eleven
sentences with the same root cause; see `generate_hidden_words.py`.

An 11-year-old offering PEAK / AIDS has done exactly what the question asked.
The three pairs are dropped here rather than reworded, because rewording a
curated pool entry from a pack generator leaves the generator still serving the
ambiguous version to every pupil the adaptive engine reaches. Fixing the pool
is a deliberate edit to `verbal.py`; this pack ships the 25 that are clean.

DRIVEN, NOT REIMPLEMENTED
-------------------------
This script drives the real `LetterMove.build()` with a seeded RNG and keeps
the first item drawn for each surviving pair, so the pack is what the adaptive
engine serves — distractors, misconception slugs and all. `EXPECTED_POOL`
asserts the pool sizes this file was built against, so an upstream edit fails
the run rather than quietly reshaping a committed pack.

WHY EVERY QUESTION IS MULTIPLE CHOICE
--------------------------------------
The generator's own note says the natural format here is `short_text`, "the
pupil writes the two new words". That is true of the paper and false of the
marking engine: `short_text` is a case-insensitive match against one string, so
a two-word answer would hinge on the pupil typing `EAST, BOWL` with that comma
and that order — marking punctuation rather than reasoning. Until the answer
kinds can hold an unordered pair, `mcq` is the honest format, and it is also
what carries the two named slips below.
"""
import collections
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from catalog.generators.verbal import (LETTERMOVE_D3, LETTERMOVE_D4,   # noqa: E402
                                       LETTERMOVE_D5, LetterMove)

rng = random.Random(20260911)

POOLS = {3: LETTERMOVE_D3, 4: LETTERMOVE_D4, 5: LETTERMOVE_D5}
EXPECTED_POOL = {3: 10, 4: 9, 5: 9}

# (word_a, word_b) pairs with a second valid move — see the module docstring.
# Each is annotated with the rival move a pupil could legitimately give.
EXCLUDED = {
    ("SPEAK", "AID"),      # PEAK / AIDS
    ("BEAST", "OWL"),      # BEAT / OWLS
    ("STONE", "PET"),      # TONE / PETS
}

GROUPS = [
    {
        "group_ref": "G-LM-MOVE",
        "instruction": (
            "In each question, move ONE letter out of the first word and into the second "
            "word, so that both words become different real words. The letters that stay "
            "behind keep their order, and so do the letters of the second word — the "
            "moved letter can go anywhere in it. Choose the pair that results, in the "
            "order the two words are printed."
        ),
        "example": (
            "Move one letter from PLANT to OWN: taking the T out of PLANT leaves PLAN, "
            "and putting it into OWN makes TOWN, so the pair is PLAN, TOWN."
        ),
    },
]


def draw(band):
    """Every distinct pair the generator builds at this band, minus the excluded."""
    gen, seen = LetterMove(), {}
    wanted = {(a, b) for a, b, *_ in POOLS[band]} - EXCLUDED
    for _ in range(200000):
        if len(seen) == len(wanted):
            break
        item = gen.build(rng, band)
        pair = (item.params["word_a"], item.params["word_b"])
        if pair in wanted:
            seen.setdefault(pair, item)
    if len(seen) != len(wanted):
        raise SystemExit(f"band {band}: drew {len(seen)} of {len(wanted)} pairs")
    return list(seen.values())


def key_positions(n):
    """An even spread of key positions with no long run and no cycle."""
    base = [0, 1, 2, 3] * (n // 4) + list(range(n % 4))
    while True:
        rng.shuffle(base)
        if all(base[i] != base[i + 1] or base[i + 1] != base[i + 2]
               for i in range(len(base) - 2)):
            return base


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "contrib_prash_vr_14.json")

    sizes = {b: len(p) for b, p in POOLS.items()}
    if sizes != EXPECTED_POOL:
        raise SystemExit(f"LetterMove pool is now {sizes}, not {EXPECTED_POOL}; "
                         f"re-read the pack sizing before regenerating")

    questions = []
    for band in sorted(EXPECTED_POOL):
        for item in draw(band):
            p = item.params
            questions.append({
                "subtopic": "Letter Moves",
                "question_type": item.question_type,
                "group_ref": "G-LM-MOVE",
                # The rule lives in the group block; the stem is the move.
                "stem": f"Move one letter from {p['word_a']} to {p['word_b']}.",
                "difficulty": band,
                "explanation": item.explanation,
                "kind": "mcq",
                "_key": f"{p['new_a']}, {p['new_b']}",
                "_wrong": [(text, item.misconceptions.get(text))
                           for text, correct in item.options if not correct],
            })

    rng.shuffle(questions)

    for q, pos in zip(questions, key_positions(len(questions))):
        opts = [{"text": t, "correct": False, **({"misconception": s} if s else {})}
                for t, s in q.pop("_wrong")]
        opts.insert(pos, {"text": q.pop("_key"), "correct": True})
        q["options"] = opts

    for i, q in enumerate(questions, start=1):
        ordered = {"number": str(i), "ref": f"PRASH-VR-{1166 + i:04d}"}
        ordered.update(q)
        questions[i - 1] = ordered

    pack = {
        "section": {
            "code": "VR",
            "name": "Verbal Reasoning",
            "source": "CONTRIB-PRASH-14",
            "is_placeholder": False,
        },
        "groups": GROUPS,
        "questions": questions,
    }
    with open(out_path, "w") as fh:
        json.dump(pack, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"wrote {out_path}: {len(questions)} questions "
          f"({dict(sorted(collections.Counter(q['difficulty'] for q in questions).items()))})")


if __name__ == "__main__":
    main()
