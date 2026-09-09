#!/usr/bin/env python3
"""
Builds elevenplus_data/contrib_prash_vr_22.json — 11 Paired Antonym questions.

    python3 elevenplus_data/generate_antonym_pairs.py [OUTPUT.json]

The RNG is seeded, so re-running reproduces the committed pack byte for byte.
Check what comes out with its companion, `check_antonym_pairs.py`, which
re-reads every bracket from the rendered stem without importing this file or
the generator.

THE REAL CEILING IS 11: ONE QUESTION PER PAIR
----------------------------------------------
`ANTONYM_POOL` holds 11 entries, each a pair of opposites plus four same-topic
fillers. The generator can emit 22 items from those 11 by fixing either word
and asking for the other, but **asking "the opposite of victory" and "the
opposite of defeat" is the same fact twice** — a pupil who knows one knows the
other, and meeting both teaches nothing the first did not. The strict ceiling
is therefore 11, and this pack is all 11.

The pool ships at 11 of an originally-drafted 26 because three successive
filler designs each let a pupil answer with no antonym knowledge at all (word
class, then topic, then an obvious decoy pair). The 15 deferred entries are
described in `verbal.py`; they are pool work, not pack work.

BRACKETS, NOT A FLATTENED MCQ
------------------------------
`AntonymPair` prints both brackets but then fixes one word and offers the other
bracket's three words as flat options, because `Item` has no `option_groups`
field and `generate_bank._write()` only writes flat `options` — a pipeline gap
its own docstring records. **A pack has no such gap.** CLAUDE.md gives this
exact shape its own answer kind, `grouped_options`, and says in terms: "Do not
flatten two brackets into one `options` list. Nine combined pairs is not what
the child is shown, and `mcq` cannot say which words belong to which bracket."

So this pack ships the real mechanic: both brackets, one word to pick from
each, one mark for the pair. That also disposes of the direction problem above
— a grouped question has no fixed word and no direction.

THE BANDS ARE THIS PACK'S, BECAUSE THE POOL'S ARE POSITIONAL
--------------------------------------------------------------
`_ANTONYM_D3/D4/D5` are `ANTONYM_POOL[0:3]`, `[3:7]` and `[7:11]` — the pool
sliced in order, not graded. Measured against the rarer word of each pair
(`wordfreq` zipf, the only objective axis available for vocabulary), the
shipped labels run 3.99 / 3.33 / 3.56: band 4 holds the rarest pairs and band 3
the commonest, so the gradient is not just absent but partly inverted.
Difficulty is the adaptive engine's only signal, so this pack rebands by that
measure — commonest pairs at band 3, rarest at band 5 — and the checker
re-derives it rather than trusting it.

WHAT NO CHECKER HERE CAN DO
----------------------------
Whether exactly one of the nine cross-bracket combinations is a genuine pair of
opposites is a semantic question, and this project has no WordNet, no POS
tagger and no thesaurus to settle it — `wordfreq` gives frequency, nothing
more. So the checker does what is mechanical (structure, distinctness, real
words, the band label) and then PRINTS ALL NINE COMBINATIONS for each question
so a human can redo the judgement in seconds. That is the honest division of
labour, and it is what QUESTION_QUALITY.md means by a defect that "needs a
human to read the questions".
"""
import collections
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from catalog.generators.verbal import ANTONYM_POOL   # noqa: E402

try:
    from wordfreq import zipf_frequency
except ImportError:                     # banding needs it; the pack is committed anyway
    zipf_frequency = None

rng = random.Random(20260919)
EXPECTED_POOL = 11

GROUPS = [
    {
        "group_ref": "G-AP-BRACKETS",
        "instruction": (
            "Each question shows two groups of words in brackets. Choose ONE word from "
            "the first group and ONE word from the second group so that the two words "
            "you pick are as nearly OPPOSITE in meaning as possible. Both words must be "
            "right to score the mark."
        ),
        "example": (
            "(early, striped, wooden)   (square, late, heavy) — early and late are "
            "opposites, so those are the two words to choose."
        ),
    },
]


def _even_slots(n, width=3):
    """Key positions 0..width-1, evenly spread, with no run of three."""
    base = list(range(width)) * (n // width) + list(range(n % width))
    while True:
        rng.shuffle(base)
        if all(base[i] != base[i + 1] or base[i + 1] != base[i + 2]
               for i in range(len(base) - 2)):
            return base


def band_of(a, b):
    """Bands by the rarer word of the pair: the pool's own slicing is positional.

    Thresholds are the tertile boundaries of this pool's own rarer-word
    frequencies, so the three bands are populated by construction rather than by
    a bar borrowed from somewhere else.
    """
    rarer = min(zipf_frequency(a, "en"), zipf_frequency(b, "en"))
    return 5 if rarer < 3.35 else (4 if rarer < 3.8 else 3)


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "contrib_prash_vr_22.json")
    if len(ANTONYM_POOL) != EXPECTED_POOL:
        raise SystemExit(f"ANTONYM_POOL is now {len(ANTONYM_POOL)} entries, not "
                         f"{EXPECTED_POOL}; re-read the pack sizing")
    if zipf_frequency is None:
        raise SystemExit("this script needs wordfreq to band the pairs; see the docstring")

    # Each bracket is its own positional answer key (CLAUDE.md), so the key's
    # slot is assigned from an even schedule per bracket rather than left to a
    # shuffle — with eleven questions a shuffle drifts far enough for a pupil to
    # notice, and the first draft put the second bracket's key last 6 times in 11.
    slots = [_even_slots(len(ANTONYM_POOL)), _even_slots(len(ANTONYM_POOL))]

    questions = []
    for n, (pos, a_target, a_fillers, b_target, b_fillers, extra) in enumerate(ANTONYM_POOL):
        bracket_a = list(a_fillers)
        bracket_b = list(b_fillers)
        rng.shuffle(bracket_a)
        rng.shuffle(bracket_b)
        if rng.random() < 0.5:                      # which bracket prints first
            bracket_a, bracket_b = bracket_b, bracket_a
            a_target, b_target = b_target, a_target
        bracket_a.insert(slots[0][n], a_target)
        bracket_b.insert(slots[1][n], b_target)
        questions.append({
            "subtopic": "Paired Antonyms",
            "question_type": "one-from-each-group",
            "group_ref": "G-AP-BRACKETS",
            "stem": f"({', '.join(bracket_a)})   ({', '.join(bracket_b)})",
            "difficulty": band_of(a_target, b_target),
            "explanation": (f"{a_target} and {b_target} are opposites: "
                            f"{a_target} is the reverse of {b_target}. The other words "
                            f"in the brackets are about the same subject but are not "
                            f"opposites of each other."),
            "kind": "grouped_options",
            "option_groups": [
                {"group": 1, "options": [
                    {"text": w, **({"correct": True} if w == a_target else {})}
                    for w in bracket_a]},
                {"group": 2, "options": [
                    {"text": w, **({"correct": True} if w == b_target else {})}
                    for w in bracket_b]},
            ],
        })

    rng.shuffle(questions)
    for i, q in enumerate(questions, start=1):
        ordered = {"number": str(i), "ref": f"PRASH-VR-{1361 + i:04d}"}
        ordered.update(q)
        questions[i - 1] = ordered

    pack = {
        "section": {"code": "VR", "name": "Verbal Reasoning",
                    "source": "CONTRIB-PRASH-22", "is_placeholder": False},
        "groups": GROUPS,
        "questions": questions,
    }
    with open(out_path, "w") as fh:
        json.dump(pack, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    spread = collections.Counter(q["difficulty"] for q in questions)
    print(f"wrote {out_path}: {len(questions)} questions ({dict(sorted(spread.items()))})")
    print("  one question per pair — the same pair asked both ways round is the same fact")


if __name__ == "__main__":
    main()
