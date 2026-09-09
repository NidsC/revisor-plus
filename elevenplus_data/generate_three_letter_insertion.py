#!/usr/bin/env python3
"""
Builds elevenplus_data/contrib_prash_vr_21.json — 18 Three-Letter Insertion questions.

    python3 elevenplus_data/generate_three_letter_insertion.py [OUTPUT.json]

The RNG is seeded, so re-running reproduces the committed pack byte for byte.
Check what comes out with its companion, `check_three_letter_insertion.py`,
which re-derives every answer from the rendered stem and sweeps all 17,576
three-letter strings against it, without importing this file or the generator.

THE REAL CEILING IS 14, NOT THE POOL'S 18
------------------------------------------
`catalog/generators/verbal.py`'s `_TLI_POOLS` holds 18 entries, 6 per band
across bands 2, 3 and 4. Each is one word with one gap in one sentence, so an
entry is a question — but **four of the 18 fragments are not words**, and both
the stem and the answer key depend on their being words.

    band 2  HAN  (CHANGE)   the Han dynasty, Han Solo — not an English word
    band 3  ALA  (GALAXY)   a wing-like structure in anatomy; no 11-year-old's word
    band 3  ALT  (WEALTH)   an abbreviation, not a word
    band 4  PHI  (DOLPHIN)  a Greek letter

All four clear a frequency bar (zipf 3.5-3.9) and all four are listed in
`/usr/share/dict/web2`, which is why they survived the pool's own screening:
the frequency comes from proper nouns and from `alt` as a key name, and web2
lists plenty that no pupil would call a word.

This matters twice over, and the second is the worse one:

  * **As keys**, they break the rule the stem states.** "Find the three letters
    -- themselves a real word" tells the pupil to rule out anything that is not
    a word, and a pupil who does that correctly rules out the right answer.
    That is worse than a hard question; it punishes the reasoning the item is
    teaching.
  * **As distractors**, they are eliminable on sight. Every distractor is drawn
    from `_TLI_ALL_FRAGMENTS`, so HAN, ALA, ALT and PHI appear as wrong options
    all over the pack, and each one a pupil can strike out without reading the
    sentence.

So all four are excluded here, as keys and as distractors, and the ceiling is
14: bands 2, 3 and 4 at 5 / 4 / 5. No band is empty and none is dropped —
**there is no band 5 to drop**, `ThreeLetterInsertion.difficulties` being
(2, 3, 4).

The remaining 14 fragments are ordinary words: OUR, HUM, LEA, RIG, ORE, EAR,
EAT, AGO, RED, BAG, AIR, TAG, LET. (LEA, a meadow, is the least familiar and is
kept: it is a common noun in any dictionary and the sort of word a verbal
reasoning paper legitimately stretches to, unlike an abbreviation or a Greek
letter.)

ONE MORE THING THE SWEEP TURNED UP, recorded because the pool comment claims
otherwise. `_TLI_ALL_FRAGMENTS`' own comment says "every fragment in the whole
pool has already been checked to not fit any OTHER entry's gap either, so no
distractor can accidentally make its own second correct answer". For the band-2
entry YOURS that is not quite true: the printed word is `YS`, and EAR gives
YEARS and EAT gives YEATS, both real. The item is still sound — the sentence is
"Is this coat YS or mine?", and neither YEARS nor YEATS makes sense in it — but
the reason it is sound is the SENTENCE, not the word list, and the pool comment
credits the wrong guard. That entry ships: a distractor that makes a real word
but a nonsense sentence is a better distractor than one that makes neither.

The checker prints, for every question, how many other three-letter words fit
the gap as a word, so the size of that sentence-dependence is visible rather
than assumed.
"""
import collections
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from catalog.generators.verbal import _TLI_ALL_FRAGMENTS, _TLI_POOLS   # noqa: E402

rng = random.Random(20260918)

EXPECTED_POOL = {2: 6, 3: 6, 4: 6}
WRITE_IN = {2: 2, 3: 1, 4: 2}

# Fragments that are not words a pupil would recognise as words — see the
# module docstring. Excluded as keys AND as distractors: as a key each breaks
# the rule the stem states, and as a distractor each is eliminable on sight.
NOT_WORDS = {"HAN", "ALA", "ALT", "PHI"}

GROUPS = [
    {
        "group_ref": "G-TLI-INSERT",
        "instruction": (
            "In each sentence one word has had three letters taken out and the letters "
            "left behind have been run together with no gap, printed in capitals. Find "
            "the three missing letters. They are always a real word themselves, they go "
            "back in without changing their order, and the sentence has to make sense."
        ),
        "example": (
            "In “She lit a CLE on the cake”, putting AND back gives CANDLE: "
            "“She lit a CANDLE on the cake”."
        ),
    },
]


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "contrib_prash_vr_21.json")

    sizes = {b: len(p) for b, p in _TLI_POOLS.items()}
    if sizes != EXPECTED_POOL:
        raise SystemExit(f"_TLI_POOLS is now {sizes}, not {EXPECTED_POOL}; re-read the "
                         f"pack sizing before regenerating")

    # sorted(set(...)): RIG is the key of two entries (BRIGHT and UPRIGHT), so the
    # raw list holds it twice and a distractor draw could print it as two options.
    fragments = sorted({f for f in _TLI_ALL_FRAGMENTS if f not in NOT_WORDS})
    questions = []
    for band in sorted(EXPECTED_POOL):
        entries = [e for e in _TLI_POOLS[band] if e[2] not in NOT_WORDS]
        write_in = set(rng.sample(range(len(entries)), WRITE_IN[band]))
        for i, (word, start, fragment, sentence) in enumerate(entries):
            remainder = word[:start] + word[start + 3:]
            rendered = sentence.format(remainder)
            q = {
                "subtopic": "Three-Letter Insertion",
                "question_type": "insert-to-complete",
                "group_ref": "G-TLI-INSERT",
                # The rule lives in the group block; the stem is the sentence.
                "stem": rendered,
                "difficulty": band,
                "explanation": (f"Putting {fragment} back into {remainder} gives {word}: "
                                f"“{sentence.format(word)}”."),
                "kind": "short_text" if i in write_in else "mcq",
            }
            if q["kind"] == "short_text":
                q["answer"] = fragment
            else:
                q["_key"] = fragment
                q["_wrong"] = rng.sample([f for f in fragments if f != fragment], 3)
            questions.append(q)

    rng.shuffle(questions)

    mcqs = [q for q in questions if q["kind"] == "mcq"]
    base = [0, 1, 2, 3] * (len(mcqs) // 4) + list(range(len(mcqs) % 4))
    while True:
        rng.shuffle(base)
        if all(base[i] != base[i + 1] or base[i + 1] != base[i + 2]
               for i in range(len(base) - 2)):
            break
    for q, pos in zip(mcqs, base):
        # Distractors are other entries' own fragments: real three-letter words,
        # so a wrong option is never eliminable for not being a word. No
        # misconception slug fits — taxonomy.json names no slip that produces
        # "a different real word", and inventing one would be pupil-facing prose
        # nobody reviewed.
        opts = [{"text": t, "correct": False} for t in q.pop("_wrong")]
        opts.insert(pos, {"text": q.pop("_key"), "correct": True})
        q["options"] = opts

    for i, q in enumerate(questions, start=1):
        ordered = {"number": str(i), "ref": f"PRASH-VR-{1347 + i:04d}"}
        ordered.update(q)
        questions[i - 1] = ordered

    pack = {
        "section": {"code": "VR", "name": "Verbal Reasoning",
                    "source": "CONTRIB-PRASH-21", "is_placeholder": False},
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
