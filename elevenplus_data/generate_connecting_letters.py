#!/usr/bin/env python3
"""
Builds elevenplus_data/contrib_prash_vr_16.json — 17 Connecting Letters questions.

    python3 elevenplus_data/generate_connecting_letters.py [OUTPUT.json]

The RNG is seeded, so re-running reproduces the committed pack byte for byte.
Check what comes out with its companion, `check_connecting_letters.py`, which
re-solves every question from the rendered stem — sweeping all 26 letters, or
all 676 letter pairs — without importing this file or the generator.

SIZE: 17 OF AN AVAILABLE 33
---------------------------
`catalog/generators/verbal.py`'s `ConnectingLetter` pool holds 34 entries: 22
single-connector (9 + 9 + 4 across bands 2-4) and 12 two-connector (band 5).

**One entry is dropped.** Re-sweeping all 26 letters against a word list that
includes regular plurals found a second solution for the first band-2 entry:

    BA(_)AG   BAN(_)ET   — intended G (BAG/GAG, BANG/GET)
                          — but S also works: BAS/SAG, BANS/SET

`BANS` is the giveaway: a lemma-only dictionary does not list it, which is the
same blind spot that put eleven ambiguous sentences into `HiddenWord`'s pool
and three ambiguous pairs into `LetterMove`'s. `BAS` is thin (it is listed, but
no 11-year-old writes it), so this one is more arguable than those — which is
exactly why it is dropped rather than defended. A question whose fairness rests
on a pupil not knowing a word is not a question worth shipping when 32 clean
ones are available.

That leaves 33. This pack ships **17** — the size asked for — as 4 / 5 / 3 / 5.
The 16 unused entries are a clean remainder for a later pack, continuing from
ref PRASH-VR-1239.

THE BANDS HERE ARE THIS PACK'S, NOT THE GENERATOR'S
----------------------------------------------------
`ConnectingLetter` bands by connector width and by the combined length of the
four resulting words: d2-d4 are single-letter tiers of increasing word length,
d5 is the two-letter type. Measuring what the items actually demand shows that
those labels do not describe them.

Solving each printed fragment pair independently over all 26 letters (or all
676 pairs) shows **14 of these 17 items have a pair with a unique solution on
its own**, so the second pair is confirmation rather than work — the same
family as the half-rule shortcut `MiddleWord`'s pool was rebuilt to close. Only
3 items need both pairs. That is not a free mark (the pupil still searches the
alphabet and writes a correct letter, which is the skill, and the shortcut does
not fail in a real paper), but it does mean the shipped d2/d3/d4/d5 labels were
spread across items that all ask for roughly the same work. Difficulty is the
adaptive engine's only signal, so a label that fine-grained and that wrong is
worse than a coarse one that is right.

So this pack relabels every item against what it actually demands, and there
are exactly three things it can demand:

  band 2 (10 items) — a single-letter connector where one pair settles it.
      Search 26 letters against one pair of fragments.
  band 4 (4 items)  — a two-letter connector where one pair settles it. The
      candidate space is 676 rather than 26, so it cannot be brute-forced by
      trying letters; the pupil has to see the chunk (AB in CRAB/ABBEY).
  band 5 (3 items)  — the connector is NOT settled by either pair alone. These
      are the only items that require the whole stated rule: hold the
      candidates from one pair, hold the candidates from the other, and take
      what is in both.

**Bands 1 and 3 are empty and left empty.** Splitting the ten band-2 items into
two tiers on a two-letter difference in combined word length would be inventing
the same over-fine labelling this relabelling exists to remove.

WHAT THE POOL NEEDS, FOR WHOEVER PICKS THIS UP
-----------------------------------------------
Entries where **neither** fragment pair has a unique solution on its own. That
is a stricter search than the one that built this pool, whose `wrong_letters`
are vetted only against solving BOTH pairs at once, and it is much stricter than
it sounds: across all 34 pool entries only 4 clear it, one of which is the
BA(_)AG entry already excluded above for having two solutions. Band 4 of the
single-letter pool has none at all. Until that search is run, this subtopic has
three band-5 questions and no more.

WHAT MAKES THIS SUBTOPIC HARD TO GET RIGHT
-------------------------------------------
Uniqueness IS the puzzle. "The same letter goes in both gaps" is only a
question if exactly one letter does, and there are only 26 candidates, so a
near-miss is common rather than exotic. The pool comment in `verbal.py`
documents finding one of these itself (COLT/TRAM, BELT/TOLL picking up a
spurious D from the archaic BELD) and fixing it with a frequency floor. The
sweep in the checker is the same idea run again with plurals included.

ANSWER FORMAT
-------------
CLAUDE.md's VR answer-format table puts "the connecting letter" in the write-in
column, and says explicitly that a one-letter `short_text` answer works — `t`
marks `t` and `T` right and everything else wrong. So 6 of the 17 ship that
way. The other 11 are `mcq`, whose distractors are the pool's own vetted wrong
letters, each confirmed not to solve both fragment pairs at once.
"""
import collections
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from catalog.generators.verbal import (ConnectingLetter, _CONNECT_D2,   # noqa: E402
                                       _CONNECT_D3, _CONNECT_D4, _CONNECT_TWO)

rng = random.Random(20260913)

POOLS = {2: _CONNECT_D2, 3: _CONNECT_D3, 4: _CONNECT_D4, 5: _CONNECT_TWO}
EXPECTED_POOL = {2: 9, 3: 9, 4: 4, 5: 12}
TAKE = {2: 4, 3: 5, 4: 3, 5: 5}
WRITE_IN = {2: 2, 3: 2, 4: 1, 5: 1}

# Frames with a second working connector — see the module docstring.
EXCLUDED = {("BA", "AG", "BAN", "ET")}      # G intended; S also solves both pairs

# Frames where NEITHER fragment pair pins the connector down on its own, so the
# pupil has to intersect two candidate sets. Frozen here rather than recomputed
# so this script needs no dictionary; `check_connecting_letters.py` re-derives
# the counts in full wherever a word list is available. The comment on each is
# (letters fitting pair 1, letters fitting pair 2).
BOTH_PAIRS = {
    ("AI", "ACE", "BA", "EEF"): (2, 2),
    ("DIS", "EY", "PAR", "ING"): (2, 3),
    ("ADO", "ACH", "BRI", "AR"): (2, 4),
}


def band_of(frame, width):
    """What the item actually demands — see the module docstring's three tiers."""
    if frame in BOTH_PAIRS:
        return 5
    return 4 if width == 2 else 2

GROUPS = [
    {
        "group_ref": "G-CL-ONE",
        "instruction": (
            "Each question shows two pairs of word fragments, each with a gap. The SAME "
            "single letter goes in every gap, making a real word out of each fragment "
            "every time. Find that letter."
        ),
        "example": (
            "WEE(_)ID     WOR(_)IND — the letter K gives WEEK and KID from the first "
            "pair, and WORK and KIND from the second."
        ),
    },
    {
        "group_ref": "G-CL-TWO",
        "instruction": (
            "Each question shows two pairs of word fragments, each with a gap. The SAME "
            "two letters go in every gap, in the same order, making a real word out of "
            "each fragment every time. Find those two letters."
        ),
        "example": (
            "REVE(__)ONE     USU(__)WAYS — the letters AL give REVEAL and ALONE from "
            "the first pair, and USUAL and ALWAYS from the second."
        ),
    },
]


def draw(band):
    """Every distinct frame the generator builds at this band, minus the excluded."""
    gen, seen = ConnectingLetter(), {}
    wanted = {(p1, s1, p2, s2) for p1, s1, p2, s2, *_ in POOLS[band]} - EXCLUDED
    for _ in range(200000):
        if len(seen) == len(wanted):
            break
        item = gen.build(rng, band)
        p = item.params
        frame = (p["p1"], p["s1"], p["p2"], p["s2"])
        if frame in wanted:
            seen.setdefault(frame, item)
    if len(seen) != len(wanted):
        raise SystemExit(f"band {band}: drew {len(seen)} of {len(wanted)} frames")
    return [seen[f] for f in sorted(seen)]


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
        os.path.dirname(os.path.abspath(__file__)), "contrib_prash_vr_16.json")

    sizes = {b: len(p) for b, p in POOLS.items()}
    if sizes != EXPECTED_POOL:
        raise SystemExit(f"ConnectingLetter pool is now {sizes}, not {EXPECTED_POOL}; "
                         f"re-read the pack sizing before regenerating")

    questions = []
    for band in sorted(EXPECTED_POOL):
        items = draw(band)
        chosen = rng.sample(items, TAKE[band])
        write_in = set(rng.sample(range(len(chosen)), WRITE_IN[band]))
        for i, item in enumerate(chosen):
            p = item.params
            conn = p.get("letter") or p["conn"]
            gap = "_" * len(conn)
            frame = (p["p1"], p["s1"], p["p2"], p["s2"])
            q = {
                "subtopic": "Connecting Letters",
                "question_type": item.question_type,
                "group_ref": "G-CL-ONE" if len(conn) == 1 else "G-CL-TWO",
                # The rule lives in the group block; the stem is the two frames.
                "stem": f"{p['p1']}({gap}){p['s1']}     {p['p2']}({gap}){p['s2']}",
                # NOT the band the generator drew this at — see the docstring.
                "difficulty": band_of(frame, len(conn)),
                "explanation": item.explanation,
                "kind": "short_text" if i in write_in else "mcq",
            }
            if q["kind"] == "short_text":
                q["answer"] = conn
            else:
                q["_key"] = conn
                q["_wrong"] = [text for text, correct in item.options if not correct]
            questions.append(q)

    rng.shuffle(questions)

    mcqs = [q for q in questions if q["kind"] == "mcq"]
    for q, pos in zip(mcqs, key_positions(len(mcqs))):
        # Distractors are the pool's own vetted wrong letters, each confirmed
        # not to solve both fragment pairs. No misconception slug fits: the slip
        # is "did not check every gap", which taxonomy.json does not name, and
        # CLAUDE.md says leave the field off rather than force a bad match.
        opts = [{"text": t, "correct": False} for t in q.pop("_wrong")]
        opts.insert(pos, {"text": q.pop("_key"), "correct": True})
        q["options"] = opts

    # An example built on a frame that is also a question would hand that
    # question over. Both examples deliberately use frames outside the pool.
    # (The first draft of the single-letter one reused the generator docstring's
    # own CU(_)EN / BA(_)ON, which the checker's sweep then showed is not even
    # unique — B and M also fit, on the strength of BAB and BAM.)
    printed = {q["stem"] for q in questions}
    for frame in ("WEE(_)ID     WOR(_)IND", "REVE(__)ONE     USU(__)WAYS"):
        if frame in printed:
            raise SystemExit(f"the worked example gives away {frame}, which is a question")

    for i, q in enumerate(questions, start=1):
        ordered = {"number": str(i), "ref": f"PRASH-VR-{1221 + i:04d}"}
        ordered.update(q)
        questions[i - 1] = ordered

    pack = {
        "section": {
            "code": "VR",
            "name": "Verbal Reasoning",
            "source": "CONTRIB-PRASH-16",
            "is_placeholder": False,
        },
        "groups": GROUPS,
        "questions": questions,
    }
    with open(out_path, "w") as fh:
        json.dump(pack, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    spread = collections.Counter(q["difficulty"] for q in questions)
    both = sum(1 for q in questions if q["difficulty"] == 5)
    print(f"wrote {out_path}: {len(questions)} questions ({dict(sorted(spread.items()))})")
    print(f"  relabelled against what each item demands: {spread[2]} settled by one pair "
          f"(single letter), {spread[4]} settled by one pair (two letters), "
          f"{both} needing both pairs")


if __name__ == "__main__":
    main()
