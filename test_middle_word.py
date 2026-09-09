"""
Checks the VR Middle Word generator can never be answered with half its rule.

Run:  python3 test_middle_word.py

No Django and no database — the generator is stdlib-only and a test needing a
settings module could not run in CI's fast job.

**What this is defending against.** The rule is stated outright in every stem:
the answer is the last two letters of word1 joined to the first two of word3.
That makes a two-answer defect impossible — the computation is exact — but it
opens a subtler one. If none of the three distractors happens to share the
answer's first two letters, the pupil can identify the key from word1 alone and
never read word3. If none shares its last two, word1 is never read. Either way
the pupil scores without doing the thing the question is for.

Measured on the first 16-entry pool, exhaustively over all 7,280 questions it
could emit: 99% were solvable from half the rule, and band 4 was 100%. That was
not a vocabulary problem — it is what a uniform sample of 3 distractors from a
flat list of middles does, whatever the list contains. Pool density alone does
not fix it either: with ~37 answers, three random draws rarely land on the one
sibling that matters.

So the invariant below is not "the answer key is right". It is:

    EVERY question offers a distractor that is wrong ONLY in its back half,
    and another that is wrong ONLY in its front half.

That forces both flanking words to be read. It is established here by
enumerating the generator's ENTIRE output space — every band, every entry,
every front-sharer x back-sharer x spare the draw can produce — not by
sampling, which is how the original defect survived.

The pool's own invariants are checked the same way: the stated rule reproduces
every keyed answer exactly, no word appears twice anywhere in any role, no pool
word collides with the worked example printed in every stem, and every answer
has at least one sibling on each side for the draw to reach for.
"""
import itertools
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from catalog.generators.verbal import (MiddleWord, _MW_ALL_MIDDLES, _MW_BY_BACK,
                                       _MW_BY_FRONT, _MW_DEMO, _MW_POOLS)

fails = []


def ck(label, cond, extra=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + (f"   [{extra}]" if extra and not cond else ""))
    if not cond:
        fails.append(label)


def every_question(gen):
    """Every question the generator can emit, as (band, key, distractors).

    build() picks one front-sharer, one back-sharer and one spare, so the
    output space is exactly that product — small enough to enumerate whole.
    """
    for band in gen.difficulties:
        for word1, word3, middle in _MW_POOLS[band]:
            fronts = [m for m in _MW_BY_FRONT[middle[:2]] if m != middle]
            backs = [m for m in _MW_BY_BACK[middle[2:]] if m != middle]
            for front_twin, back_twin in itertools.product(fronts, backs):
                for spare in _MW_ALL_MIDDLES:
                    if spare in (middle, front_twin, back_twin):
                        continue
                    yield band, middle, (front_twin, back_twin, spare)


def main():
    gen = MiddleWord()
    pool_words = [w for pool in _MW_POOLS.values() for entry in pool for w in entry]

    print("\nPOOL INVARIANTS")
    ck("the stated rule reproduces every keyed answer exactly",
       all(w1[-2:] + w3[:2] == mid
           for pool in _MW_POOLS.values() for w1, w3, mid in pool))
    ck(f"no word appears twice anywhere, in any role "
       f"({len(pool_words)} slots)",
       len(pool_words) == len(set(pool_words)),
       str(len(pool_words) - len(set(pool_words))) + " repeats")
    demo = {w for triple in _MW_DEMO for w in triple}
    ck("no pool word collides with the worked example in the stem",
       not (set(pool_words) & demo), str(sorted(set(pool_words) & demo)))
    ck("every answer is a 4-letter word", all(len(m) == 4 for m in _MW_ALL_MIDDLES))
    ck("no answer is reachable from two different entries",
       len(_MW_ALL_MIDDLES) == len(set(_MW_ALL_MIDDLES)))

    print("\nTHE DRAW CAN ALWAYS BE MADE — every answer has a sibling each side")
    no_front = [m for m in _MW_ALL_MIDDLES if len(_MW_BY_FRONT[m[:2]]) < 2]
    no_back = [m for m in _MW_ALL_MIDDLES if len(_MW_BY_BACK[m[2:]]) < 2]
    ck("every answer shares its first two letters with another answer",
       not no_front, str(no_front))
    ck("every answer shares its last two letters with another answer",
       not no_back, str(no_back))
    ck("a spare distractor always exists outside those two",
       all(len(_MW_ALL_MIDDLES) - len(set([m]) | set(_MW_BY_FRONT[m[:2]])
                                       | set(_MW_BY_BACK[m[2:]])) >= 1
           for m in _MW_ALL_MIDDLES))

    print("\nEXHAUSTIVE — HALF THE RULE IS NEVER ENOUGH")
    total = front_only = back_only = 0
    worst = None
    per_band = {b: [0, 0] for b in gen.difficulties}
    for band, key, distractors in every_question(gen):
        total += 1
        per_band[band][1] += 1
        f = not any(m[:2] == key[:2] for m in distractors)
        b = not any(m[2:] == key[2:] for m in distractors)
        if f:
            front_only += 1
        if b:
            back_only += 1
        if f or b:
            per_band[band][0] += 1
            worst = worst or f"{key} vs {distractors}"
    ck(f"no question is solvable from word1 alone ({total:,} enumerated)",
       front_only == 0, str(front_only))
    ck("no question is solvable from word3 alone", back_only == 0, str(back_only))
    for band in gen.difficulties:
        bad, n = per_band[band]
        ck(f"band {band}: 0 of {n:,} solvable from half the rule", bad == 0, str(bad))
    ck("no half-rule-solvable question exists at all", worst is None, worst or "")

    print("\nEXHAUSTIVE — NO SECOND DEFENSIBLE ANSWER")
    second = [(w1, w3, mid, other)
              for pool in _MW_POOLS.values() for w1, w3, mid in pool
              for other in _MW_ALL_MIDDLES
              if other != mid and w1[-2:] + w3[:2] == other]
    ck("no option other than the key satisfies the stated rule",
       not second, str(second[:3]))
    ck("every distractor the draw can offer is a real pool answer",
       all(d in _MW_ALL_MIDDLES for _b, _k, ds in every_question(gen) for d in ds))

    print("\nCEILING")
    for band in gen.difficulties:
        n = len(_MW_POOLS[band])
        print(f"    band {band}: {n} distinct questions")
        ck(f"band {band} has at least 10 distinct questions", n >= 10, str(n))
    print(f"    total: {len(_MW_ALL_MIDDLES)}   (previous pool: 16)")

    print("\nBUILT ITEMS — 12,000 draws")
    rng = random.Random(20260909)
    problems = {"one_correct": 0, "four_opts": 0, "dupes": 0, "typed": 0,
                "no_front_twin": 0, "no_back_twin": 0, "key_wrong": 0}
    drawn = 0
    for _ in range(12000):
        band = rng.choice(gen.difficulties)
        item = gen.build(rng, band)
        if item is None:
            continue
        drawn += 1
        texts = [t for t, _c in item.options]
        correct = [t for t, c in item.options if c]
        wrong = [t for t, c in item.options if not c]
        if len(correct) != 1:
            problems["one_correct"] += 1
        if len(item.options) != 4:
            problems["four_opts"] += 1
        if len(set(texts)) != len(texts):
            problems["dupes"] += 1
        key = correct[0]
        if item.params["word1"][-2:] + item.params["word3"][:2] != key:
            problems["key_wrong"] += 1
        if not any(m[:2] == key[:2] for m in wrong):
            problems["no_front_twin"] += 1
        if not any(m[2:] == key[2:] for m in wrong):
            problems["no_back_twin"] += 1
        if (item.question_type != "derive-from-both-sides"
                or item.difficulty != band
                or item.params.get("difficulty") != band):
            problems["typed"] += 1
    ck(f"{drawn} items built", drawn > 11900, str(drawn))
    ck("exactly one correct option", problems["one_correct"] == 0)
    ck("exactly four options", problems["four_opts"] == 0)
    ck("no duplicate option text", problems["dupes"] == 0)
    ck("the key is always what the stated rule produces", problems["key_wrong"] == 0)
    ck("every built question offers a front-sharing distractor",
       problems["no_front_twin"] == 0, str(problems["no_front_twin"]))
    ck("every built question offers a back-sharing distractor",
       problems["no_back_twin"] == 0, str(problems["no_back_twin"]))
    ck("question_type and difficulty are set correctly", problems["typed"] == 0)

    print("\nDIFFICULTY IS PART OF IDENTITY (gen_key)")
    ck("difficulty reaches params",
       "difficulty" in gen.build(random.Random(1), 3).params)
    seen = {}
    for band in gen.difficulties:
        r = random.Random(7)
        for _ in range(4000):
            seen.setdefault(gen.build(r, band).key(gen.slug, gen.template_id),
                            set()).add(band)
    ck("no gen_key is reachable at two bands",
       all(len(v) == 1 for v in seen.values()),
       str([k for k, v in seen.items() if len(v) > 1][:3]))

    print("\nTAXONOMY")
    tax = json.load(open(os.path.join("elevenplus_data", "taxonomy.json")))
    sub = [s for s in tax["sections"]["VR"]["subtopics"]
           if s["name"] == "Middle Word"][0]
    slugs = [q["slug"] for q in sub["question_types"]]
    ck("'derive-from-both-sides' is a real question_type for Middle Word",
       "derive-from-both-sides" in slugs, str(slugs))
    ck("the generator names the subtopic exactly", gen.subtopic == sub["name"])
    misc = set(tax["misconceptions"]["slugs"])
    used = {s for _b in gen.difficulties
            for s in gen.build(random.Random(5), _b).misconceptions.values()}
    ck("every misconception slug is in the controlled vocabulary",
       used <= misc, str(sorted(used - misc)))

    print()
    print("RESULT: " + ("ALL PASSED" if not fails else f"{len(fails)} FAILED"))
    for f in fails:
        print("  - " + f)
    return 1 if fails else 0


sys.exit(main())
