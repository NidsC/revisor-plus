#!/usr/bin/env python3
"""
Builds elevenplus_data/contrib_prash_vr_13.json — 37 Middle Word questions.

    python3 elevenplus_data/generate_middle_words.py [OUTPUT.json]

The RNG is seeded, so re-running reproduces the committed pack byte for byte.
Check what comes out with its companion, `check_middle_words.py`, which
recomputes every answer from the rendered stem without importing this file or
the generator.

SIZED TO THE POOL, WHICH IS THE CEILING
---------------------------------------
This pack is `catalog/generators/verbal.py`'s `MiddleWord` pool in full: 37
(word1, word3) pairs, 12 + 12 + 13 across bands 2, 3 and 4. There is no 38th
question to write. The middle word is fully determined by the two flanking
words, so one pair is one question and the pool size IS the ceiling — no
reshuffling of distractors makes a pupil-distinct 38th item, it only makes the
same puzzle again with different wrong answers.

That ceiling is a deliberate one, not an oversight: the pool comment in
`verbal.py` records that ~35 per band was the target and is not reachable,
because an answer must be a common 4-letter word whose first two letters end a
common word and whose last two begin one, it needs a sibling sharing each half,
and no word may repeat anywhere in the pool.

DRIVEN, NOT REIMPLEMENTED
-------------------------
Unlike `generate_directions.py`, this script does not rebuild the mechanic. It
drives the real `MiddleWord.build()` with a seeded RNG and keeps the first item
drawn for each (word1, word3) pair, so the pack is literally what the adaptive
engine serves. Two things follow, and both are the point:

  * The distractor discipline comes along with it. Every question offers one
    wrong answer sharing the key's FIRST two letters and one sharing its LAST
    two, so a pupil who computes only `word1[-2:]` cannot separate the key from
    the front-sharer, and one who computes only `word3[:2]` cannot separate it
    from the back-sharer. Both flanking words have to be read. Reimplementing
    that here would be a second copy to keep in step.
  * If the upstream pool changes, this pack changes with it. `EXPECTED_POOL`
    below asserts the sizes this file was built against, so a silent upstream
    edit fails the run instead of quietly reshaping a committed pack.

WHAT THE GENERATOR'S STEM CARRIES, AND WHERE IT GOES HERE
---------------------------------------------------------
`MiddleWord`'s stem repeats the rule and the worked example inside every
question, because a generated question is served alone with nothing to hang an
instruction on. A pack has somewhere better: `groups`, which CLAUDE.md copies
onto every question that points at it. So the rule and the paper's own worked
example (PAIN/INTO/TOOK, ALSO/SOON/ONLY) move to `G-MW-MIDDLE`, and the stem is
the three-word row alone. Nothing is lost to the pupil, and the pack stops
repeating 40 words of boilerplate 37 times.

ANSWER FORMAT
-------------
CLAUDE.md's VR answer-format table puts "the middle word" in the write-in
column, so 12 of the 37 ship as `short_text`. The other 25 stay `mcq`, which is
what carries the front-sharer/back-sharer pair and the
`found-one-part-then-stopped` slug on each — the whole reason the distractors
are chosen the way they are. Both formats ask for the same word.
"""
import collections
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from catalog.generators.verbal import MiddleWord, _MW_DEMO, _MW_POOLS   # noqa: E402

rng = random.Random(20260910)

# Band -> number of (word1, word3) pairs this file was built against. A change
# upstream should fail here rather than silently reshape a committed pack.
EXPECTED_POOL = {2: 12, 3: 12, 4: 13}
# How many of each band's questions are write-in rather than multiple choice.
WRITE_IN = {2: 4, 3: 4, 4: 4}

GROUPS = [
    {
        "group_ref": "G-MW-MIDDLE",
        "instruction": (
            "In each question a word is missing from the middle of three. The middle "
            "word is made from the two words either side of it: the last two letters of "
            "the first word, then the first two letters of the third. Both of the other "
            "words are needed — half the rule gives half the answer."
        ),
        "example": (
            f"{_MW_DEMO[0][0]}   {_MW_DEMO[0][2]}   {_MW_DEMO[0][1]}   and   "
            f"{_MW_DEMO[1][0]}   {_MW_DEMO[1][2]}   {_MW_DEMO[1][1]}. "
            f"{_MW_DEMO[0][2]} is the last two letters of {_MW_DEMO[0][0]} "
            f"({_MW_DEMO[0][0][-2:].lower()}) followed by the first two of "
            f"{_MW_DEMO[0][1]} ({_MW_DEMO[0][1][:2].lower()})."
        ),
    },
]


def draw(band):
    """Every distinct (word1, word3) pair the generator can build at this band.

    Coupon collection rather than reaching into the pool list: the pack is then
    made of items the generator actually emitted, distractors and all.
    """
    gen, seen = MiddleWord(), {}
    for _ in range(200000):
        if len(seen) == len(_MW_POOLS[band]):
            break
        item = gen.build(rng, band)
        seen.setdefault((item.params["word1"], item.params["word3"]), item)
    if len(seen) != len(_MW_POOLS[band]):
        raise SystemExit(f"band {band}: drew {len(seen)} of {len(_MW_POOLS[band])} pairs")
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
        os.path.dirname(os.path.abspath(__file__)), "contrib_prash_vr_13.json")

    sizes = {b: len(p) for b, p in _MW_POOLS.items()}
    if sizes != EXPECTED_POOL:
        raise SystemExit(f"MiddleWord pool is now {sizes}, not {EXPECTED_POOL}; "
                         f"re-read the pack sizing before regenerating")

    questions = []
    for band in sorted(EXPECTED_POOL):
        items = draw(band)
        write_in = set(rng.sample(range(len(items)), WRITE_IN[band]))
        for i, item in enumerate(items):
            word1, word3 = item.params["word1"], item.params["word3"]
            middle = item.params["middle"]
            q = {
                "subtopic": "Middle Word",
                "question_type": item.question_type,
                "group_ref": "G-MW-MIDDLE",
                # The rule and the worked example live in the group block; the
                # stem is the row the pupil completes.
                "stem": f"{word1}   ______   {word3}",
                "difficulty": band,
                "explanation": item.explanation,
                "kind": "short_text" if i in write_in else "mcq",
            }
            if q["kind"] == "short_text":
                q["answer"] = middle
            else:
                q["_key"] = middle
                q["_wrong"] = [(text, item.misconceptions.get(text))
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
        ordered = {"number": str(i), "ref": f"PRASH-VR-{1129 + i:04d}"}
        ordered.update(q)
        questions[i - 1] = ordered

    pack = {
        "section": {
            "code": "VR",
            "name": "Verbal Reasoning",
            "source": "CONTRIB-PRASH-13",
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
