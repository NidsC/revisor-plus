#!/usr/bin/env python3
"""
Builds elevenplus_data/contrib_prash_vr_18.json — 16 Scenario Deduction questions.

    python3 elevenplus_data/generate_scenario_deduction.py [OUTPUT.json]

The RNG is seeded, so re-running reproduces the committed pack byte for byte.
Check what comes out with its companion, `check_scenario_deduction.py`, which
re-solves every puzzle from the printed clues by brute force — every ordering
of the named people, tested against every clue — without importing this file or
the generator.

BAND 5 IS DELIBERATELY ABSENT
------------------------------
`catalog/generators/verbal.py`'s `LogicOrdering` maps difficulty to the number
of people, `n = {1: 3, 2: 4, 3: 4, 4: 5, 5: 5}`, and adds exactly one merged
distance clue at band 3 and above. **Bands 4 and 5 are therefore the same
puzzle population**: five people, one merge, the same three merge positions and
the same five askable places — 30 distinct structures each, and the same 30.
Measured by drawing them, band 4 and band 5 produce identical structure sets;
only the label differs.

Two labels on one population is a mislabelled difficulty, and the adaptive
engine reads difficulty as its only signal, so it would be told a pupil had
moved up a band when nothing about the question changed. This pack uses band 4
and leaves band 5 out — the lower of the two labels, because claiming the
harder one for a puzzle that is not harder is the error that costs a pupil
something. Making band 5 genuinely harder (six people, or two merges, or an
anchor at neither end) is a change to the generator, not to a pack.

The ceilings, counting a name permutation as cosmetic — a pupil meeting the
same puzzle with Leo and Zara swapped has met the same puzzle — are 6 / 8 / 16 /
30 for bands 1-4. This pack ships 3 / 4 / 5 / 4, so no band is drawn thin.

WHAT COUNTS AS A DISTINCT PUZZLE
---------------------------------
(framing, number of people, which pair of steps is merged, which place is
asked). Names are not part of it: the eight names are drawn per build, so two
items differing only by name are one puzzle wearing two coats. Sizing to the
name-blind count is why this pack is 16 rather than an arbitrarily larger
number that would repeat itself.

WHY THE PUZZLES ARE ALWAYS SOLVABLE
------------------------------------
The clues are generated FROM a known ordering and only ever restate it, never
hand-written, so an under-constrained puzzle with two valid solutions cannot be
written by accident — the classic failure of a hand-authored logic item. At
band 3 and above exactly one pair of adjacent clue-steps is merged into a
distance clue ("X finishes 2 places ahead of Y"), which leaves exactly one
person unmentioned; that person's place is recoverable only by elimination,
since every other place is pinned and there are as many people as slots. Never
two merges in a row and never two unmentioned people: with two people and two
free slots, nothing would say which goes where.

The checker does not take any of that on trust. It brute-forces every ordering
against the printed clues and requires exactly one to survive.
"""
import collections
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from catalog.generators.verbal import LogicOrdering   # noqa: E402

rng = random.Random(20260915)

# Band -> how many questions. Band 5 is excluded — see the module docstring.
TAKE = {1: 3, 2: 4, 3: 5, 4: 4}
# Distinct name-blind structures each band can build, for the record.
BAND_CEILING = {1: 6, 2: 8, 3: 16, 4: 30}

GROUPS = [
    {
        "group_ref": "G-SD-ORDER",
        "instruction": (
            "Each question describes several people in one order — finishing a race, or "
            "sitting in a numbered row of seats. Put the clues together to work out the "
            "whole order, then answer the question asked. Every question has exactly one "
            "possible order."
        ),
        "example": (
            "3 friends run a race. Sam finishes last. Ava finishes ahead of Sam. Tom "
            "finishes ahead of Ava. Who finishes first? Tom is ahead of Ava, who is "
            "ahead of Sam, so the order is Tom, Ava, Sam and Tom finishes first."
        ),
    },
]


def structure(item):
    """What makes two of these the same puzzle for a pupil: everything but names."""
    p = item.params
    return (p["variant"], len(p["order"]), p["merge_at"], p["place"])


def draw(band, count):
    """`count` distinct name-blind structures at this band."""
    gen, seen = LogicOrdering(), {}
    for _ in range(200000):
        if len(seen) == count:
            break
        item = gen.build(rng, band)
        seen.setdefault(structure(item), item)
    if len(seen) != count:
        raise SystemExit(f"band {band}: drew {len(seen)} of {count}")
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
        os.path.dirname(os.path.abspath(__file__)), "contrib_prash_vr_18.json")

    questions = []
    for band in sorted(TAKE):
        for item in draw(band, TAKE[band]):
            key = next(text for text, correct in item.options if correct)
            questions.append({
                "subtopic": "Scenario Deduction",
                "question_type": item.question_type,
                "group_ref": "G-SD-ORDER",
                "stem": item.stem,
                "difficulty": band,
                "explanation": item.explanation,
                "kind": "mcq",
                "_key": key,
                "_wrong": [text for text, correct in item.options if not correct],
            })

    rng.shuffle(questions)

    for q, pos in zip(questions, key_positions(len(questions))):
        # Every distractor is another person named in the same stem. No
        # misconception slug fits: picking the wrong person is a failed
        # deduction, not one of taxonomy.json's named slips, and CLAUDE.md
        # prefers an empty field to a forced one.
        opts = [{"text": t, "correct": False} for t in q.pop("_wrong")]
        opts.insert(min(pos, len(opts)), {"text": q.pop("_key"), "correct": True})
        q["options"] = opts

    for i, q in enumerate(questions, start=1):
        ordered = {"number": str(i), "ref": f"PRASH-VR-{1291 + i:04d}"}
        ordered.update(q)
        questions[i - 1] = ordered

    pack = {
        "section": {
            "code": "VR",
            "name": "Verbal Reasoning",
            "source": "CONTRIB-PRASH-18",
            "is_placeholder": False,
        },
        "groups": GROUPS,
        "questions": questions,
    }
    with open(out_path, "w") as fh:
        json.dump(pack, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    spread = collections.Counter(q["difficulty"] for q in questions)
    print(f"wrote {out_path}: {len(questions)} questions ({dict(sorted(spread.items()))})")
    for band in sorted(spread):
        print(f"  band {band}: {spread[band]} of {BAND_CEILING[band]} distinct structures")


if __name__ == "__main__":
    main()
