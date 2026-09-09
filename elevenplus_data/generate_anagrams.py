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

ANSWER FORMAT
-------------
CLAUDE.md's VR answer-format table makes an anagram a write-in, so 10 of the 30
ship as `short_text` — the pupil types the word, which is exactly the real
task. The other 20 are `mcq`. Distractors there are other pool answers of the
SAME letter count, never other arrangements of the same letters: a distractor
that was itself an anagram of the stem would reintroduce the ambiguity the pool
was built to avoid.
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
WRITE_IN = {2: 2, 3: 3, 4: 3, 5: 2}
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
        os.path.dirname(os.path.abspath(__file__)), "contrib_prash_vr_15.json")

    sizes = {b: len(PLAIN_ANAGRAM[b]) + len(ANAGRAM_CLUE[b]) for b in EXPECTED_POOL}
    if sizes != EXPECTED_POOL:
        raise SystemExit(f"Anagram pool is now {sizes}, not {EXPECTED_POOL}; "
                         f"re-read the pack sizing before regenerating")

    questions = []
    for band in sorted(EXPECTED_POOL):
        items = draw(band)
        chosen = rng.sample(items, TAKE[band])
        write_in = set(rng.sample(range(len(chosen)), WRITE_IN[band]))
        for i, item in enumerate(chosen):
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
                "kind": "short_text" if i in write_in else "mcq",
            }
            if q["kind"] == "short_text":
                q["answer"] = answer
            else:
                q["_key"] = answer
                q["_wrong"] = [text for text, correct in item.options if not correct]
            if len(answer) != LETTERS[band]:
                raise SystemExit(f"{answer} is {len(answer)} letters at band {band}")
            questions.append(q)

    rng.shuffle(questions)

    mcqs = [q for q in questions if q["kind"] == "mcq"]
    for q, pos in zip(mcqs, key_positions(len(mcqs))):
        # Distractors are other pool answers of the same length, never other
        # arrangements of these letters — so none carries a misconception slug:
        # there is no slip that produces "a different word entirely", and
        # taxonomy.json has no slug that would honestly describe one.
        opts = [{"text": t, "correct": False} for t in q.pop("_wrong")]
        opts.insert(pos, {"text": q.pop("_key"), "correct": True})
        q["options"] = opts

    # An example that used a shipped answer would hand that question over before
    # the pupil read it. BALL and ELEVEN are deliberately outside the pool.
    shipped = {q.get("answer") or q["options"] and next(
        o["text"] for o in q["options"] if o["correct"]) for q in questions}
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
