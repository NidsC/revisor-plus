#!/usr/bin/env python3
"""
Builds elevenplus_data/contrib_prash_vr_20.json — 24 Word Pattern questions.

    python3 elevenplus_data/generate_word_patterns.py [OUTPUT.json]

The RNG is seeded, so re-running reproduces the committed pack byte for byte.
Check what comes out with its companion, `check_word_patterns.py`, which
re-derives every code word from the rule and the words printed in the stem,
without importing this file or the generator.

THE REAL CEILING IS 24, AND IT IS THE POOL
-------------------------------------------
`catalog/generators/verbal.py`'s `_WP_POOL` holds 24 rows — 6 extraction rules
x 4 (word1, word2, word3, code) rows each. A row is one question: the rule is
stated in the stem, so the same row asked again is the same question with the
same answer. 24 is therefore the ceiling however many bands are offered, and
this pack is all 24.

BANDS 4 AND 5 ARE DROPPED: THE ROWS ARE THE ANSWER SHEET
---------------------------------------------------------
The generator's bands 4 and 5 are `find-pattern`, where the rule is NOT stated
and the pupil infers it from worked examples. With only 4 rows per rule, that
cannot be done without showing most of the rule's pool in the question:

    band 4 — 3 demo rows + 1 target = **4 of the rule's 4 rows, every time**
    band 5 — 2 demo rows + 1 target = 3 of 4

At band 4 every question about a given rule prints the whole of that rule's
pool; the four questions differ only in which row is blanked. A pupil who has
met one has met the other three, and the second sitting is recall rather than
inference — a free mark rather than a hard question. Band 5 is the same fault
one row short. Both are dropped, so this pack is `apply-pattern` only, where a
question shows 2 of the 4 rows (one worked demo, one target) and states the
rule outright.

BANDS 1 AND 2 ARE THE SAME POPULATION IN THE GENERATOR, SO THIS PACK REBANDS
-----------------------------------------------------------------------------
`WordPattern.build()` sends difficulty 1 AND difficulty 2 to the same
`_EASY_SHAPES` pool and picks a rule at random, so the two bands are one
population of 8 rows wearing two labels — the same fault `LogicOrdering` has
between its bands 4 and 5. Difficulty is the adaptive engine's only signal, so
this pack labels by a property that actually differs, the extraction rule:

    band 1 (4 rows)   front1_front2 — first 1 letter of word1 + first 2 of
                      word3. A 3-letter code, both pieces from the FRONT.
    band 2 (4 rows)   front2_back2 — first 2 of word1 + last 2 of word3. A
                      4-letter code, and one piece counted from the END, which
                      is the step up.
    band 3 (16 rows)  the four harder rules: a 3+1 split, a 1+2 split from the
                      back, and the two where word3's letters come FIRST in the
                      code.

Bands 4 and 5 are left empty rather than refilled with `find-pattern`.

WHAT THE POOL WOULD NEED FOR find-pattern TO SHIP
---------------------------------------------------
More rows per rule — enough that 3 demos plus a target leave rows a pupil has
not seen. At 8 rows per rule a band-4 question would show half the pool rather
than all of it; that is the smallest change that makes the band honest. It is
pool work in `verbal.py`, not something a pack can fix.
"""
import collections
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from catalog.generators.verbal import (_WP_POOL, _WP_RULE_SHAPES,   # noqa: E402
                                       _wp_apply_rule, _wp_rule_desc)

rng = random.Random(20260917)

# Extraction rule -> the band this pack files it under. See the docstring: this
# is a property of the rule, not the band the generator happened to draw at.
BAND_OF_RULE = {
    "front1_front2": 1,
    "front2_back2": 2,
    "back2_front2": 3,
    "front2w3_back2w1": 3,
    "front3_back1": 3,
    "back1_back2": 3,
}
EXPECTED_ROWS = 4          # per rule; if this changes, re-read the sizing above
WRITE_IN = 8               # of the 24, how many ask the pupil to write the code

GROUPS = [
    {
        "group_ref": "G-WP-APPLY",
        "instruction": (
            "In each question three words are shown, and a code word is made from the "
            "FIRST and THIRD of them — never the middle one. The rule is stated, and one "
            "worked example is given. Apply the same rule to the second set of three "
            "words to make its code word."
        ),
        "example": (
            "Rule: the first 2 letters of word1, followed by the first 2 letters of "
            "word3. FLIGHT, PILOT, OWNER -> (FLOW). So TRIP, JOURNEY, APOLOGY -> (TRAP). "
            "The middle word is never used — it is there because the paper prints three."
        ),
    },
]


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "contrib_prash_vr_20.json")

    sizes = {r: len(rows) for r, rows in _WP_POOL.items()}
    if set(sizes) != set(BAND_OF_RULE) or set(sizes.values()) != {EXPECTED_ROWS}:
        raise SystemExit(f"_WP_POOL is now {sizes}; re-read the pack sizing before "
                         f"regenerating")

    all_codes = [row[3] for rows in _WP_POOL.values() for row in rows]
    questions = []
    for rule_name, rows in _WP_POOL.items():
        rule = _WP_RULE_SHAPES[rule_name]
        for i, (w1, w2, w3, code) in enumerate(rows):
            # The worked demo is another row of the SAME rule, so the rule shown
            # is the rule asked. Rotating means each row demonstrates once and is
            # the target once, and no question shows more than 2 of the 4 rows.
            d1, d2, d3, dcode = rows[(i + 1) % len(rows)]
            if _wp_apply_rule(w1, w3, rule) != code or _wp_apply_rule(d1, d3, rule) != dcode:
                raise SystemExit(f"{rule_name}: pool row does not obey its own rule")
            distractors = rng.sample([c for c in all_codes
                                      if c != code and len(c) == len(code)], 3)
            questions.append({
                "subtopic": "Word Patterns",
                "question_type": "apply-pattern",
                "group_ref": "G-WP-APPLY",
                "stem": (f"Rule: {_wp_rule_desc(rule)}.\n"
                         f"{d1}, {d2}, {d3} -> ({dcode})\n"
                         f"{w1}, {w2}, {w3} -> ( ? )"),
                "difficulty": BAND_OF_RULE[rule_name],
                "explanation": (f"Taking {_wp_rule_desc(rule)} from {w1} and {w3} "
                                f"gives {code}."),
                "kind": "mcq",
                "_key": code,
                "_wrong": distractors,
            })

    rng.shuffle(questions)
    for q in rng.sample(questions, WRITE_IN):
        q["kind"] = "short_text"
        q["answer"] = q.pop("_key")
        q.pop("_wrong")

    mcqs = [q for q in questions if q["kind"] == "mcq"]
    base = [0, 1, 2, 3] * (len(mcqs) // 4) + list(range(len(mcqs) % 4))
    while True:
        rng.shuffle(base)
        if all(base[i] != base[i + 1] or base[i + 1] != base[i + 2]
               for i in range(len(base) - 2)):
            break
    for q, pos in zip(mcqs, base):
        # Distractors are other rules' code words: real short words of the same
        # length as the key, so none is eliminable for looking wrong. No
        # misconception slug fits — "applied a different extraction" is not one
        # taxonomy.json names, and these are not that anyway.
        opts = [{"text": t, "correct": False} for t in q.pop("_wrong")]
        opts.insert(pos, {"text": q.pop("_key"), "correct": True})
        q["options"] = opts

    for i, q in enumerate(questions, start=1):
        ordered = {"number": str(i), "ref": f"PRASH-VR-{1323 + i:04d}"}
        ordered.update(q)
        questions[i - 1] = ordered

    pack = {
        "section": {"code": "VR", "name": "Verbal Reasoning",
                    "source": "CONTRIB-PRASH-20", "is_placeholder": False},
        "groups": GROUPS,
        "questions": questions,
    }
    with open(out_path, "w") as fh:
        json.dump(pack, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    spread = collections.Counter(q["difficulty"] for q in questions)
    print(f"wrote {out_path}: {len(questions)} questions ({dict(sorted(spread.items()))})")
    print("  apply-pattern only; bands 4-5 (find-pattern) dropped, bands 1-2 rebanded "
          "by extraction rule")


if __name__ == "__main__":
    main()
