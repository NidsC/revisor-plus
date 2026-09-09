#!/usr/bin/env python3
"""
Builds elevenplus_data/contrib_prash_vr_24.json — 20 Double Meaning questions.

    python3 elevenplus_data/generate_double_meanings.py [OUTPUT.json]

The RNG is seeded, so re-running reproduces the committed pack byte for byte.
Check what comes out with its companion, `check_double_meanings.py`, which
re-reads both contexts from the rendered stem without importing this file or
the generator.

THE REAL CEILING IS 20, AND IT IS THE POOL
-------------------------------------------
`DOUBLE_MEANING` holds 20 entries — 5 / 11 / 4 across bands 2, 3 and 4. Each is
one word with two contexts, so an entry is a question and 20 is the ceiling.
This pack is all 20.

NO BAND IS DROPPED, AND HERE IS WHY NOT
----------------------------------------
The defect expected here was a band where only one option is a homograph, so a
pupil could pick the answer by spotting the one word with two meanings and
never read the contexts. **There is no band 1**, and band 2 does not have that
shape. Its five entries were read option by option:

    river ___ / ___ account -> BANK, against side, savings, mouth, loan
    cricket ___ / ___ cave  -> BAT,  against ball, wicket, man, sea
    wrist ___ / ___ TV      -> WATCH, against strap, see, band, note
    traffic ___ / ___ as a feather -> LIGHT, against signal, cone, jam, white
    the dog's ___ / the ___ of the tree -> BARK, against howl, growl, trunk, root

Two things make these sound. The distractors are **split across the two
contexts** — SAVINGS and LOAN fit "___ account" and could not fit "river ___";
SIDE and MOUTH are the reverse — so a pupil who reads only one context is left
with three candidates and has to read the other. And the key is **not** the only
word with two meanings: BAND (wrist band, brass band), NOTE (a note, a banknote),
JAM (traffic jam, jam jar) and MOUTH (a mouth, the mouth of a river) are all
homographs sitting in the option lists. Scanning for "the word with two
meanings" does not answer these questions.

So nothing is dropped here. The one thing worth recording for later is that this
soundness is a property of the curated distractors, not of the mechanic: an
entry whose four distractors all fit the same context would be answerable from
that context alone, and nothing in the generator prevents one being added.

ANSWER FORMAT
-------------
Real papers print the two bracketed contexts and a line to write on, so 7 of the
20 ship as `short_text`. The other 13 keep the five-option MCQ, which is what
carries the split-across-contexts distractors described above.
"""
import collections
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from catalog.generators.verbal import DOUBLE_MEANING   # noqa: E402

rng = random.Random(20260920)

EXPECTED_POOL = {2: 5, 3: 11, 4: 4}
WRITE_IN = {2: 2, 3: 4, 4: 1}

GROUPS = [
    {
        "group_ref": "G-DM-BOTH",
        "instruction": (
            "Each question shows two phrases, each with a gap. The SAME word fills both "
            "gaps, but it means something different in each. Find that word."
        ),
        "example": (
            "(a ___ of bread)   (___ around) — LOAF fits both: a loaf of bread, and to "
            "loaf around means to idle."
        ),
    },
]


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "contrib_prash_vr_24.json")
    sizes = {b: len(p) for b, p in DOUBLE_MEANING.items()}
    if sizes != EXPECTED_POOL:
        raise SystemExit(f"DOUBLE_MEANING is now {sizes}, not {EXPECTED_POOL}; re-read "
                         f"the pack sizing before regenerating")

    questions = []
    for band in sorted(EXPECTED_POOL):
        entries = list(DOUBLE_MEANING[band])
        write_in = set(rng.sample(range(len(entries)), WRITE_IN[band]))
        for i, (context_a, context_b, answer, distractors) in enumerate(entries):
            q = {
                "subtopic": "Double Meanings",
                "question_type": "word-completes-both",
                "group_ref": "G-DM-BOTH",
                # The rule lives in the group block; the stem is the two contexts.
                "stem": f"({context_a})   ({context_b})",
                "difficulty": band,
                "explanation": (f"“{answer}” fits both: "
                                f"{context_a.replace('___', answer)} and "
                                f"{context_b.replace('___', answer)}."),
                "kind": "short_text" if i in write_in else "mcq",
            }
            if q["kind"] == "short_text":
                q["answer"] = answer
            else:
                q["_key"] = answer
                q["_wrong"] = list(distractors)
            questions.append(q)

    rng.shuffle(questions)

    mcqs = [q for q in questions if q["kind"] == "mcq"]
    base = [0, 1, 2, 3, 4] * (len(mcqs) // 5) + list(range(len(mcqs) % 5))
    while True:
        rng.shuffle(base)
        if all(base[i] != base[i + 1] or base[i + 1] != base[i + 2]
               for i in range(len(base) - 2)):
            break
    for q, pos in zip(mcqs, base):
        # Each distractor fits ONE of the two contexts, which is what forces a
        # pupil to read both. No misconception slug fits: "read one bracket and
        # stopped" is close to `found-one-part-then-stopped`, but that slug is
        # used where a pupil computed half an answer, not where they answered a
        # different question, and a slug is pupil-facing prose.
        opts = [{"text": t, "correct": False} for t in q.pop("_wrong")]
        opts.insert(pos, {"text": q.pop("_key"), "correct": True})
        q["options"] = opts

    for i, q in enumerate(questions, start=1):
        ordered = {"number": str(i), "ref": f"PRASH-VR-{1379 + i:04d}"}
        ordered.update(q)
        questions[i - 1] = ordered

    pack = {
        "section": {"code": "VR", "name": "Verbal Reasoning",
                    "source": "CONTRIB-PRASH-24", "is_placeholder": False},
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
