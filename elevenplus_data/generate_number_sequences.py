#!/usr/bin/env python3
"""
Builds elevenplus_data/contrib_prash_vr_17.json — 53 Number Sequences questions.

    python3 elevenplus_data/generate_number_sequences.py [OUTPUT.json]

The RNG is seeded, so re-running reproduces the committed pack byte for byte.
Check what comes out with its companion, `check_number_sequences.py`, which
re-fits every rule family to the printed numbers — never reading this file or
the generator — and requires every family that fits to agree on the answer.

THE CEILING HERE IS A BAND, NOT A PACK
---------------------------------------
This is the one subtopic in this batch whose generator is computational rather
than curated, so its overall ceiling is not the binding constraint: counting
distinct printed number lines, `catalog/generators/verbal.py`'s NumberSequence
can build roughly 80 / 976 / 765 / 44 / 11,025 across bands 1-5.

**Band 4 is the exception and it is genuinely thin: 44.** It draws from
multiplicative (ratio 2 or 3, multiply or divide, 8 start values = 16
sequences) and two-step (mult 2 or 3, start 3-6, sub 1..start-1 = 28
sequences), and that is the whole of it. 12 of those 44 are used here, which is
27% of the band — high enough to be worth stating, and the reason this pack
does not lean on band 4 the way its difficulty spread otherwise might. A future
pack drawing band 4 heavily will repeat sequences a pupil has already seen; the
fix is new rule shapes in the generator (the class's own comment lists
Fibonacci-like recurrences and special number families as real paper shapes it
does not yet cover, held back for want of a taxonomy slot), not a bigger draw
from the same 44.

WHAT MAKES A SEQUENCE QUESTION FAIR
------------------------------------
Strictly, any next term continues *some* rule, so "what comes next" is only a
question because one rule is overwhelmingly the simplest reading. That is not
something to assert — it is something to test. The checker re-fits all five
rule families this generator can produce to the printed terms and requires
every family that fits them ALL to predict the same next number. A stem where
two different families fit and disagree has two defensible answers and fails.

DESCENDING SEQUENCES NEVER RUN PAST ZERO, which is a real-paper constraint the
generator holds to (the one descending example seen, 100, 90, _, 40, 0, stops
at zero). The checker re-checks it on the printed numbers rather than trusting
it: a band-2 or band-3 sequence that went negative would be arithmetically fine
and pedagogically wrong for this age group.

ANSWER FORMAT
-------------
CLAUDE.md's VR answer-format table puts "the missing number in a sequence" in
the write-in column, and `numeric` is the kind for a number, so 15 of the 53
ship that way. The other 38 are `mcq`, which is what carries the generator's
error-model distractors: overshooting or undershooting by one step, continuing
the wrong one of two interleaved sequences, using the other common ratio, and
repeating the last term shown.

ONE MISCONCEPTION SLUG, NOT FOUR
--------------------------------
`NumberSequence` names none of its distractors — it is one of the older
generators and predates the `misconceptions` field — so the slugs here are
added by this script, and only where the mapping is exact. **Only "repeated the
last number shown" is tagged** (`copied-a-given-number-instead-of-solving`),
because that one is identifiable from the printed numbers alone: the option
equals the last term of the row. "Overshot by a step" looks equally taggable
and is not: one step further on is `key + step` for a constant rule, a
different amount for a changing one, and `key x ratio` for a multiplicative
one, so recognising it means re-deriving the rule and betting the tag on that
derivation. A slug is pupil-facing prose, and a wrong one tells a child they
made a mistake they did not make. The rest ship untagged, which CLAUDE.md
allows and prefers to a forced fit.
"""
import collections
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from catalog.generators.verbal import NumberSequence   # noqa: E402

rng = random.Random(20260914)

# Band -> how many questions, and how many of those are write-in. Band 4 is
# deliberately not the biggest slice: its whole population is 44 sequences.
TAKE = {1: 5, 2: 10, 3: 15, 4: 12, 5: 11}
WRITE_IN = {1: 1, 2: 3, 3: 4, 4: 4, 5: 3}
# The measured number of distinct printed sequences each band can produce, for
# the record and for the share-of-band figure printed at the end of a run.
BAND_CEILING = {1: 80, 2: 976, 3: 765, 4: 44, 5: 11025}

GROUPS = [
    {
        "group_ref": "G-NS-NEXT",
        "instruction": (
            "Work out the rule each row of numbers follows, then give the number that "
            "comes next in place of the dash."
        ),
        "example": (
            "2, 5, 8, 11, 14, ___ goes up by 3 each time, so the next number is 17. The "
            "rule is not always a fixed step: sometimes the step itself changes, "
            "sometimes each number is multiplied, and sometimes two sequences run "
            "together, taking turns."
        ),
    },
]


def draw(band, count):
    """`count` distinct printed sequences at this band, as the generator makes them."""
    gen, seen = NumberSequence(), {}
    for _ in range(400000):
        if len(seen) == count:
            break
        item = gen.build(rng, band)
        seen.setdefault(item.stem, item)
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
        os.path.dirname(os.path.abspath(__file__)), "contrib_prash_vr_17.json")

    questions = []
    for band in sorted(TAKE):
        items = draw(band, TAKE[band])
        write_in = set(rng.sample(range(len(items)), WRITE_IN[band]))
        for i, item in enumerate(items):
            # The generator's stem carries its own instruction; the group block
            # holds it here, so the stem is the number line alone.
            numbers = item.stem.split("?  ", 1)[1]
            key = next(text for text, correct in item.options if correct)
            q = {
                "subtopic": "Number Sequences",
                "question_type": item.question_type,
                "group_ref": "G-NS-NEXT",
                "stem": numbers,
                "difficulty": band,
                "explanation": item.explanation,
                "kind": "numeric" if i in write_in else "mcq",
            }
            if q["kind"] == "numeric":
                q["answer"] = int(key)
            else:
                # The last number printed in the row: an option equal to it is a
                # pupil who copied a given number instead of continuing the rule.
                last_shown = numbers.split(", ")[-2]
                q["_key"] = key
                q["_wrong"] = [
                    (text, "copied-a-given-number-instead-of-solving"
                     if text == last_shown else None)
                    for text, correct in item.options if not correct]
            questions.append(q)

    rng.shuffle(questions)

    mcqs = [q for q in questions if q["kind"] == "mcq"]
    for q, pos in zip(mcqs, key_positions(len(mcqs))):
        opts = [{"text": t, "correct": False, **({"misconception": s} if s else {})}
                for t, s in q.pop("_wrong")]
        opts.insert(pos, {"text": q.pop("_key"), "correct": True})
        q["options"] = opts

    for i, q in enumerate(questions, start=1):
        ordered = {"number": str(i), "ref": f"PRASH-VR-{1238 + i:04d}"}
        ordered.update(q)
        questions[i - 1] = ordered

    pack = {
        "section": {
            "code": "VR",
            "name": "Verbal Reasoning",
            "source": "CONTRIB-PRASH-17",
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
        print(f"  band {band}: {spread[band]} of {BAND_CEILING[band]} distinct sequences "
              f"({spread[band] / BAND_CEILING[band]:.0%} of the band)")


if __name__ == "__main__":
    main()
