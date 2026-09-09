#!/usr/bin/env python3
"""
Builds elevenplus_data/contrib_prash_vr_19.json — 16 Must Be True questions.

    python3 elevenplus_data/generate_must_be_true.py [OUTPUT.json]

The RNG is seeded, so re-running reproduces the committed pack byte for byte.
Check what comes out with its companion, `check_must_be_true.py`, which parses
the printed rules back into a day-by-day table with its own solver and
re-evaluates all five statements — never importing this file, the generator, or
the generator's solver.

SIZE, AND WHY THE CEILING IS NOT THE CONSTRAINT
------------------------------------------------
`catalog/generators/verbal.py`'s `MustBeTrue` is computational, not curated.
Counting distinct rule-sets — the scenario a pupil actually reasons about,
with venue and person names treated as cosmetic — it can build 21 / 65 / 312 /
2,170 / 17,413 across bands 1-5. Counting whole items (rule-set plus which five
(entity, day) statements are offered and which is keyed) the numbers run into
the tens of thousands from band 1 up.

So 16 is a size choice, not a limit. The bands are 2 / 3 / 4 / 4 / 3. Band 1's
21 rule-sets is the only figure worth watching: it is one entity opening on an
enumerated pair of days, so there are exactly C(7,2) = 21 worlds to describe,
and a pack of 20+ band-1 items would start repeating the world even while the
five statements varied.

WHAT THE BANDS ACTUALLY VARY
-----------------------------
Not the question, which is always "which one of these must be true?" (or
cannot be), but the scenario's shape: band 1 is one entity on an enumerated
pair of days; band 2 is one entity under a negation or a weekday/weekend rule;
band 3 adds a person whose days depend on the entity's; band 4 adds an
exception day to that dependency; band 5 chains a third entity off the second,
with an exception somewhere in the chain. Every link is a total function of an
already-known row, so the table stays fully determined however long the chain.

THE FAILURE MODE THIS SUBTOPIC EXISTS TO AVOID
-----------------------------------------------
An under-determined world. If the stated rules leave any day open to judgement,
the "true" conclusion is only true in the world the author imagined, and a
pupil who imagines a different one is not wrong. The generator closes this by
construction: every rule is one of three exhaustive closed forms for the first
entity, and every other entity is a total function of an already-known one, so
each rule fixes a definite value for all seven days.

The checker does not take that on trust either. It re-derives the table from
the printed sentences with an independently written solver and counts how many
of the five printed statements are true: exactly one for a "must be true"
question, exactly four for a "cannot be true" one. A world that was
under-determined, or a statement set that was mis-keyed, shows up as a count
that is not 1 or 4.

ALL MULTIPLE CHOICE
-------------------
CLAUDE.md's VR answer-format table puts "must be true" in the `mcq` column, and
it is the one VR subtopic where that is not a compromise: the pupil is choosing
between five stated conclusions, and there is nothing to write in.
"""
import collections
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from catalog.generators.verbal import MustBeTrue   # noqa: E402

rng = random.Random(20260916)

TAKE = {1: 2, 2: 3, 3: 4, 4: 4, 5: 3}
# Distinct rule-sets (scenarios) each band can describe, names treated as
# cosmetic. Band 1 is the only one worth watching — see the module docstring.
BAND_WORLDS = {1: 21, 2: 65, 3: 312, 4: 2170, 5: 17413}

GROUPS = [
    {
        "group_ref": "G-MBT-RULES",
        "instruction": (
            "Each question gives some rules about which days of the week places open and "
            "people work. Take the rules to be completely true, work out what happens on "
            "every day, then pick the ONE statement the rules force to be so. Rules about "
            "a person always follow from the days already worked out for whatever they "
            "depend on."
        ),
        "example": (
            "The pool opens only on Tuesday and Friday. Sam works on the days the pool is "
            "open. That fixes all seven days: the pool is open on Tuesday and Friday and "
            "shut otherwise, and Sam works on exactly those two days. So “Sam does not "
            "work on Monday” must be true, while “Sam works on Tuesday or Wednesday” is "
            "not something the rules force either way."
        ),
    },
]


def structure(item):
    """The scenario and the statement set, with names treated as cosmetic.

    `params` already identifies entities as E0/P0/P1 rather than by name, so
    two items differing only in venue and people are one question in two coats.
    """
    p = item.params
    return json.dumps({"rules": p["rules"], "pairs": sorted(map(list, p["pairs"])),
                       "variant": p["variant"], "target": p["target"],
                       "kinds": [e["kind"] for e in p["entities"]]}, sort_keys=True)


def draw(band, count):
    """`count` distinct name-blind scenarios at this band."""
    gen, seen = MustBeTrue(), {}
    for _ in range(200000):
        if len(seen) == count:
            break
        item = gen.build(rng, band)
        if item is not None:
            seen.setdefault(structure(item), item)
    if len(seen) != count:
        raise SystemExit(f"band {band}: drew {len(seen)} of {count}")
    return list(seen.values())


def key_positions(n, width=5):
    """An even spread of key positions with no long run and no cycle."""
    base = list(range(width)) * (n // width) + list(range(n % width))
    while True:
        rng.shuffle(base)
        if all(base[i] != base[i + 1] or base[i + 1] != base[i + 2]
               for i in range(len(base) - 2)):
            return base


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "contrib_prash_vr_19.json")

    questions = []
    for band in sorted(TAKE):
        for item in draw(band, TAKE[band]):
            key = next(text for text, correct in item.options if correct)
            questions.append({
                "subtopic": "Must Be True",
                "question_type": item.question_type,
                "group_ref": "G-MBT-RULES",
                "stem": item.stem,
                "difficulty": band,
                "explanation": item.explanation,
                "kind": "mcq",
                "_key": key,
                "_wrong": [text for text, correct in item.options if not correct],
            })

    rng.shuffle(questions)

    for q, pos in zip(questions, key_positions(len(questions))):
        # Every distractor is a statement about the same week that the rules
        # settle the other way. No misconception slug fits: taxonomy.json names
        # arithmetic and word-puzzle slips, and "read the rules and concluded
        # the opposite" is not among them. CLAUDE.md prefers an empty field to
        # a forced one.
        opts = [{"text": t, "correct": False} for t in q.pop("_wrong")]
        opts.insert(pos, {"text": q.pop("_key"), "correct": True})
        q["options"] = opts

    for i, q in enumerate(questions, start=1):
        ordered = {"number": str(i), "ref": f"PRASH-VR-{1307 + i:04d}"}
        ordered.update(q)
        questions[i - 1] = ordered

    pack = {
        "section": {
            "code": "VR",
            "name": "Verbal Reasoning",
            "source": "CONTRIB-PRASH-19",
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
        print(f"  band {band}: {spread[band]} of {BAND_WORLDS[band]} distinct scenarios")


if __name__ == "__main__":
    main()
