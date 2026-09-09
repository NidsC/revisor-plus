#!/usr/bin/env python3
"""
Builds elevenplus_data/contrib_prash_vr_15.json — 30 Anagram questions.

    python3 elevenplus_data/generate_anagrams.py [OUTPUT.json]

The RNG is seeded, so re-running reproduces the committed pack byte for byte.
Check what comes out with its companion, `check_anagrams.py`, which re-derives
every answer from the rendered stem without importing this file or the
generator.

SIZE: 30 OF AN AVAILABLE 40
---------------------------
`catalog/generators/verbal.py`'s `Anagram` pool holds 40 words — 22
`plain-anagram` (the scrambled word sits in a sentence, and the sentence's
meaning says which word is wanted) and 18 `anagram-with-clue` (a definition is
given instead), spread 8 / 11 / 15 / 6 across bands 2-5. Unlike Hidden Words
and Letter Moves, **re-running the pool's ambiguity check found nothing wrong
with it**: no answer word has a rival real-word anagram at a frequency an 11+
pupil would meet.

This pack ships 30 of the 40 — 6 / 8 / 11 / 5 — because 30 was the size asked
for. The 10 unused entries are not rejects: they are a clean remainder a later
pack can take, continuing from ref PRASH-VR-1222. Which 30 is a seeded draw, so
the split is reproducible rather than hand-picked.

DIFFICULTY IS WORD LENGTH, AND THE CHECKER ENFORCES IT
-------------------------------------------------------
The mechanism never changes across bands — only how many letters have to be
held in mind: 4 letters is band 2, 5 is band 3, 6 is band 4, 7 is band 5. That
makes the band label falsifiable rather than a matter of taste, so
`check_anagrams.py` recounts the letters in every printed stem and fails a
question whose label disagrees. There is no band 1: a 3-letter anagram is
brute-forceable by trying every arrangement and tests nothing.

EVIDENCE, HONESTLY SPLIT
------------------------
`plain-anagram` is confirmed against a published 11+ example (11plusehelp.co.uk,
"The girl sat on a ARCIH." -> CHAIR). `anagram-with-clue` is NOT: it is the
natural clue-based variant the taxonomy's own name for the type implies, built
to standard 11+ convention but never found in a real paper by this project.
The generator's docstring says so and this pack does not upgrade the claim.
Both groups are declared separately here partly so that distinction stays
visible in the data.

WRITE-IN THROUGHOUT: THE MULTIPLE-CHOICE VERSION NEVER TOUCHES THE LETTERS
--------------------------------------------------------------------------
An earlier draft shipped 20 of the 30 as `mcq`, with three distractors each:
other pool answers of the same letter count, never other arrangements of the
same letters.

That last constraint is doing something the format cannot survive. A distractor
that IS an anagram of the printed jumble is a second correct answer, so every
distractor has to be an unrelated word — and an unrelated word does not fit the
sentence or the clue. **So exactly one option can fit the meaning, and picking
it answers the question without rearranging anything**: "the sixth month of the
year" among BIRD, FROG, NINE and JUNE is a general-knowledge question, not an
anagram. That is true of all 20 by construction, in every band, not by bad luck
in the draw.

It is also a shortcut that fails in the exam, where the paper prints the jumble
and a blank. A child drilled on the multiple-choice version has practised
reading clues.

So the whole pack is `short_text`, which is what CLAUDE.md's VR answer-format
table prescribes for an anagram anyway. All 30 words survive; only the free
marks are gone.

**Write-in is only safe because the rival-anagram sweep came back clean.** A
written answer is marked against one string, so a jumble with a second real
solution would fail a pupil who found the other one. This pool has none — which
is what makes the format switch available here, and is worth knowing before
anyone tries the same switch on a pool that has not been swept.

WHAT WHOEVER FIXES THE GENERATOR NEEDS TO KNOW
-----------------------------------------------
There is no pool work outstanding for this subtopic: all 40 entries are clean,
and the 10 not used here are as usable as the 30 that are. The generator work
is one line — `Anagram` should carry `kind = "short_text"` (the hook exists and
`generate_bank.py` respects it) instead of building four MCQ options, for the
reason above. Its own docstring already notes the MCQ options are a workaround
for a pipeline gap rather than the right format; this is the evidence that the
workaround costs the question its skill.
"""
import collections
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from catalog.generators.verbal import (ANAGRAM_CLUE, PLAIN_ANAGRAM,   # noqa: E402
                                       Anagram)

rng = random.Random(20260912)

# Band -> (pool size, how many to ship, how many of those are write-in).
EXPECTED_POOL = {2: 8, 3: 11, 4: 15, 5: 6}
TAKE = {2: 6, 3: 8, 4: 11, 5: 5}
# Band -> the answer's letter count. Difficulty here IS word length.
LETTERS = {2: 4, 3: 5, 4: 6, 5: 7}

GROUPS = [
    {
        "group_ref": "G-AN-SENTENCE",
        "instruction": (
            "In each sentence one word has had its letters jumbled and is printed in "
            "capitals. Rearrange those letters to make the word the sentence needs. "
            "Every letter is used exactly once."
        ),
        "example": (
            "The boy kicked the BLAL across the yard. BLAL rearranges to BALL, which is "
            "the word the sentence needs."
        ),
    },
    {
        "group_ref": "G-AN-CLUE",
        "instruction": (
            "In each question, rearrange the capital letters to make one word that "
            "matches the clue after the dash. Every letter is used exactly once."
        ),
        "example": (
            "EELVNE — a number that comes between ten and twelve. The letters rearrange "
            "to ELEVEN."
        ),
    },
]


def draw(band):
    """Every distinct answer word the generator builds at this band."""
    gen, seen = Anagram(), {}
    wanted = len(PLAIN_ANAGRAM[band]) + len(ANAGRAM_CLUE[band])
    for _ in range(200000):
        if len(seen) == wanted:
            break
        item = gen.build(rng, band)
        seen.setdefault(item.params["answer"], item)
    if len(seen) != wanted:
        raise SystemExit(f"band {band}: drew {len(seen)} of {wanted} words")
    return [seen[w] for w in sorted(seen)]


# No key_positions() here, unlike most pack generators in this series: with no
# options anywhere in the pack there is no answer position to balance.


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "contrib_prash_vr_15.json")

    sizes = {b: len(PLAIN_ANAGRAM[b]) + len(ANAGRAM_CLUE[b]) for b in EXPECTED_POOL}
    if sizes != EXPECTED_POOL:
        raise SystemExit(f"Anagram pool is now {sizes}, not {EXPECTED_POOL}; "
                         f"re-read the pack sizing before regenerating")

    questions = []
    for band in sorted(EXPECTED_POOL):
        items = draw(band)
        for item in rng.sample(items, TAKE[band]):
            answer = item.params["answer"]
            scrambled = item.params["scrambled"]
            plain = item.question_type == "plain-anagram"
            context = next(c for pool in (PLAIN_ANAGRAM[band], ANAGRAM_CLUE[band])
                           for a, s, c in pool if a == answer)
            if plain:
                stem = context.replace("___", scrambled)
            else:
                stem = f"{scrambled} — {context}."
            q = {
                "subtopic": "Anagrams",
                "question_type": item.question_type,
                "group_ref": "G-AN-SENTENCE" if plain else "G-AN-CLUE",
                "stem": stem,
                "difficulty": band,
                "explanation": (
                    f"The letters of {scrambled} rearrange to {answer}"
                    + (", which is the word the sentence needs." if plain
                       else f", which matches the clue: {context}.")),
                "kind": "short_text",
                "answer": answer,
            }
            if len(answer) != LETTERS[band]:
                raise SystemExit(f"{answer} is {len(answer)} letters at band {band}")
            questions.append(q)

    rng.shuffle(questions)

    # An example that used a shipped answer would hand that question over before
    # the pupil read it. BALL and ELEVEN are deliberately outside the pool.
    shipped = {q["answer"] for q in questions}
    for word in ("BALL", "ELEVEN"):
        if word in shipped:
            raise SystemExit(f"the worked example gives away {word}, which is a question")

    for i, q in enumerate(questions, start=1):
        ordered = {"number": str(i), "ref": f"PRASH-VR-{1191 + i:04d}"}
        ordered.update(q)
        questions[i - 1] = ordered

    pack = {
        "section": {
            "code": "VR",
            "name": "Verbal Reasoning",
            "source": "CONTRIB-PRASH-15",
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
