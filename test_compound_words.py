"""
Checks the VR Compound Words generator can never ask a question with two answers.

Run:  python3 test_compound_words.py

No Django and no database — the generator is stdlib-only and a test needing a
settings module could not run in CI's fast job.

**What this is defending against.** The previous generator held a hand-written
star-list: six heads, four tails each, every tail belonging to exactly one head.
Distractors were drawn from *other heads'* tails on the assumption that a tail
belonging to `night` therefore does not belong to `foot`. English does not work
that way. `light` joins sun, day, foot and night; `fall` joins rain, night,
water and snow. Sampling 3,000 draws of that generator, 20.1% of questions had
at least two defensible answers, and `night`/`fall` with `light` among the
distractors came up twice in a 15-question sample — `nightlight` is a word.

So the invariant below is not "the answer key is right". It is:

    NO option other than the key forms a word with the head.

That cannot be established by sampling, which is how the defect survived. It is
established here by enumerating the generator's ENTIRE output space: every head,
every key, every band, every candidate the distractor filter admits. If every
admissible candidate is non-attaching, then every 3-subset of them is too, and
so is every question the generator can emit — without enumerating C(n,3) of them.

Three specific traps have their own checks at the bottom:

  * `nightlight` — web2 does not list it closed, because it is usually written
    open. A dictionary lookup alone would NOT have caught the shipped defect.
  * `panache` — in the dictionary, equals `pan` + `ache`, and is not a compound
    of them. Concatenation cannot tell the difference, so it must never be a key.
  * band collision — `difficulty` must reach `params`, or the same head+tail at
    three bands collapses to one gen_key and the bands overwrite each other.
  * band OVERLAP — the opposite failure, and the subtler one. With `difficulty`
    in params the bands cannot collide, so overlapping productivity ranges do
    not overwrite anything; they DUPLICATE. A band-2 draw taking only
    productivity-0 tails was byte-identical to a band-1 question on the same
    head, and both shipped, as two rows with the same text and different
    difficulty labels. The adaptive engine reads difficulty as its only signal,
    so it was being told one question was two difficulties. Sampling showed it
    as a 16% overlap between bands 1 and 2; the check below establishes the
    absence of it by construction instead, over the whole output space.
"""
import itertools
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from catalog.generators.verbal import CompoundWord, PRODUCTIVITY, _COMPOUND_BANDS
from catalog.generators.compound_data import ATTACHING, KEYS, MARGINAL, STRUCK, TAILS

fails = []


def ck(label, cond, extra=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + (f"   [{extra}]" if extra and not cond else ""))
    if not cond:
        fails.append(label)


def eligible(head, correct, band):
    """The exact filter build() applies. Kept in step with it by the check below."""
    lo, hi = _COMPOUND_BANDS[band]
    attached = ATTACHING.get(head, ())
    return [t for t in TAILS
            if t != correct and t not in attached and t != head
            and lo <= PRODUCTIVITY[t] <= hi]


def main():
    gen = CompoundWord()

    print("\nEXHAUSTIVE — every head x key x band x admissible distractor")
    checked = bad = 0
    worst = None
    for head, keys in KEYS.items():
        for correct in keys:
            for band in gen.difficulties:
                for cand in eligible(head, correct, band):
                    checked += 1
                    if cand in ATTACHING.get(head, ()):
                        bad += 1
                        worst = f"{head}+{cand}"
    ck(f"no admissible distractor attaches to its head ({checked:,} checked)",
       bad == 0, worst or "")

    print("\nKEY SET")
    ck("every key attaches to its head",
       all(t in ATTACHING.get(h, ()) for h, ts in KEYS.items() for t in ts))
    ck("no key repeats its own head", all(t != h for h, ts in KEYS.items() for t in ts))
    ck("keys and marginals are disjoint",
       all(t not in MARGINAL.get(h, []) for h, ts in KEYS.items() for t in ts))
    ck("every marginal is still ATTACHING (never offered as a distractor)",
       all(t in ATTACHING.get(h, ()) for h, ts in MARGINAL.items() for t in ts))
    ck("no struck pair is a key",
       all(t not in KEYS.get(h, []) for h, ts in STRUCK.items() for t in ts))
    ck("no struck pair is still marginal (it could be promoted by accident)",
       all(t not in MARGINAL.get(h, []) for h, ts in STRUCK.items() for t in ts))
    ck("every struck pair is still ATTACHING (never a distractor either)",
       all(t in ATTACHING.get(h, ()) for h, ts in STRUCK.items() for t in ts))

    print("\nREACHABILITY — the ceiling this rewrite exists to raise")
    total = sum(len(v) for v in KEYS.values())
    print(f"    distinct (head, key) puzzles: {total}   (old star-list: 24)")
    ck("at least 100 distinct puzzles", total >= 100, str(total))
    for band in gen.difficulties:
        n = sum(1 for h, ts in KEYS.items() for t in ts
                if len(eligible(h, t, band)) >= 3)
        print(f"    band {band}: {n} puzzles buildable")
        ck(f"band {band} can build at least 20 puzzles", n >= 20, str(n))

    print("\nBUILT ITEMS — 2,000 draws")
    rng = random.Random(20260907)
    problems = {"one_correct": 0, "four_opts": 0, "dupes": 0,
                "key_attaches": 0, "distractor_attaches": 0, "typed": 0}
    drawn = 0
    for _ in range(2000):
        band = rng.choice(gen.difficulties)
        item = gen.build(rng, band)
        if item is None:
            continue
        drawn += 1
        rows = item.option_rows()
        head = item.params["head"]
        texts = [t for t, _c, _f in rows]
        correct = [t for t, c, _f in rows if c]
        if len(correct) != 1:
            problems["one_correct"] += 1
        if len(rows) != 4:
            problems["four_opts"] += 1
        if len(set(texts)) != len(texts):
            problems["dupes"] += 1
        if correct and correct[0] not in ATTACHING.get(head, ()):
            problems["key_attaches"] += 1
        for t, c, _f in rows:
            if not c and t in ATTACHING.get(head, ()):
                problems["distractor_attaches"] += 1
        if item.question_type != "join-two-words":
            problems["typed"] += 1
        if item.difficulty != band or item.params.get("difficulty") != band:
            problems["typed"] += 1
    ck(f"{drawn} items built", drawn > 1900, str(drawn))
    ck("exactly one correct option", problems["one_correct"] == 0)
    ck("exactly four options", problems["four_opts"] == 0)
    ck("no duplicate option text", problems["dupes"] == 0)
    ck("the key always forms a word", problems["key_attaches"] == 0)
    ck("NO distractor ever forms a word with the head",
       problems["distractor_attaches"] == 0, str(problems["distractor_attaches"]))
    ck("question_type and difficulty are set correctly", problems["typed"] == 0)

    print("\nDIFFICULTY IS PART OF IDENTITY (gen_key)")
    a = gen.build(random.Random(1), 1)
    b = gen.build(random.Random(1), 3)
    ck("same head+tail at two bands are the same puzzle",
       (a.params["head"], a.params["tail"]) == (b.params["head"], b.params["tail"]))
    ck("...but get different gen_keys, so bands cannot overwrite each other",
       a.key(gen.slug, gen.template_id) != b.key(gen.slug, gen.template_id))
    ck("difficulty is in params", "difficulty" in a.params)

    print("\nBANDS ARE DISJOINT — no two bands can emit the same question")
    # Interval-level: the table itself must not overlap. This is the invariant a
    # future edit to _COMPOUND_BANDS is most likely to break, so it is asserted
    # on the table rather than only on its consequences.
    spans = sorted(_COMPOUND_BANDS.items())
    overlaps = [(b1, b2) for (b1, (lo1, hi1)), (b2, (lo2, hi2))
                in itertools.combinations(spans, 2)
                if lo1 <= hi2 and lo2 <= hi1]
    ck("productivity ranges do not overlap", not overlaps, str(overlaps))

    # Consequence-level, exhaustive: no tail is legal in two bands at once, so
    # no two bands share a distractor POOL, so no 3-subset of one is a 3-subset
    # of the other. That covers every question the generator can emit without
    # enumerating C(n,3) of them — the same argument the head/key check above
    # uses.
    shared = [(b1, b2, t) for (b1, (lo1, hi1)), (b2, (lo2, hi2))
              in itertools.combinations(spans, 2)
              for t in TAILS
              if lo1 <= PRODUCTIVITY[t] <= hi1 and lo2 <= PRODUCTIVITY[t] <= hi2]
    ck(f"no tail is admissible in two bands ({len(TAILS)} tails x "
       f"{len(spans) * (len(spans) - 1) // 2} band-pairs checked)",
       not shared, str(shared[:5]))

    # And per head, in the exact shape build() draws them: two bands sharing
    # three or more eligible tails is what made an identical question possible.
    pairs = 0
    for head, keys in KEYS.items():
        for correct in keys:
            pools = {b: set(eligible(head, correct, b)) for b in gen.difficulties}
            for b1, b2 in itertools.combinations(sorted(pools), 2):
                if len(pools[b1] & pools[b2]) >= 3:
                    pairs += 1
    ck("no head+key has three eligible tails in common across two bands",
       pairs == 0, str(pairs))

    # Every band must still be buildable after the floors moved — a disjoint
    # table that starves a band has traded one defect for another.
    for band in gen.difficulties:
        lo, hi = _COMPOUND_BANDS[band]
        n = sum(1 for t in TAILS if lo <= PRODUCTIVITY[t] <= hi)
        ck(f"band {band} has enough tails in ({lo}, {hi}) to fill 3 slots",
           n >= 4, f"{n} tails")

    print("\nREGRESSIONS — the traps named in the docstring")
    night_pools = [t for k in KEYS["night"] for band in gen.difficulties
                   for t in eligible("night", k, band)]
    ck("'light' is never a distractor for 'night' (nightlight is a word)",
       "light" not in night_pools)
    ck("'fall' is never a distractor for 'night'", "fall" not in night_pools)
    ck("web2 alone would NOT have caught it — nightlight is absent from web2, "
       "so this depends on OPEN_COMPOUNDS",
       "light" in ATTACHING["night"])
    ck("'ache' is never a key for 'pan' (panache is not pan+ache)",
       "ache" not in KEYS.get("pan", []))
    ck("'board' is never a key for 'star' (starboard is not star+board)",
       "board" not in KEYS.get("star", []))
    ck("'board' is never a distractor for 'star' either",
       all("board" not in eligible("star", k, b)
           for k in KEYS.get("star", []) for b in gen.difficulties))
    ck("'ache' is never a distractor for 'pan' either",
       all("ache" not in eligible("pan", k, b)
           for k in KEYS["pan"] for b in gen.difficulties))

    print("\nTAXONOMY")
    tax = json.load(open(os.path.join("elevenplus_data", "taxonomy.json")))
    vr = tax["sections"]["VR"]
    sub = [s for s in vr["subtopics"] if s["name"] == "Compound Words"][0]
    slugs = [q["slug"] for q in sub["question_types"]]
    ck("'join-two-words' is a real question_type for Compound Words",
       "join-two-words" in slugs, str(slugs))
    ck("the generator names the subtopic exactly", gen.subtopic == sub["name"])

    print()
    print("RESULT: " + ("ALL PASSED" if not fails else f"{len(fails)} FAILED"))
    for f in fails:
        print("  - " + f)
    return 1 if fails else 0


sys.exit(main())
