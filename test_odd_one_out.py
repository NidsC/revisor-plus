"""
Checks the VR Odd One Out generator can never ask a two-answer question.

Run:  python3 test_odd_one_out.py

No Django and no database.

**What this is defending against.** The previous generator carried eight
categories with three hand-listed foils each -- 24 facts, and that was the hard
ceiling, because adding a category bought exactly three questions. Four defects
sat on top of it:

  1. `rng.choice(foils if difficulty >= 3 else foils[:1])` made the odd word at
     bands 1-2 always `foils[0]`. Measured over 3,000 draws, band 1 reached 8 of
     the 24 facts: trees was `ivy` 377 times out of 377, weather `breeze` 355 of
     355. A pupil who met the trees question twice had been told the answer.
  2. Bands 1 and 2 produced byte-identical question sets, as did 3 and 4 --
     1,193 shapes with 100% overlap, and 3,535 with 100% overlap. Four labels
     described two bands.
  3. `difficulty` never reached `params`, so those pairs also collided on
     gen_key: 1,447 collisions between bands 1-2 and 1,421 between 3-4, with
     `update_or_create` keeping whichever ran last.
  4. At bands 3-4 the stem printed five words but `chosen[:3]` offered four
     options, so one word on the page could not be picked -- and the explanation
     named it as one of the words that DO belong to the category.

Foils are now COMPUTED from a category-adjacency graph rather than hand-listed,
which is what moves the ceiling: 347 near facts instead of 24, growing with the
data rather than with a typed list.

The invariant proved below is the same one `test_compound_words.py` proves for
compounds, and for the same reason -- it cannot be established by sampling:

    NO option other than the odd one is outside the category.

It is established by enumerating every category x band x admissible foil, so it
holds for every word set the generator could draw, not merely those it drew.
"""
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from catalog.generators.verbal import OddOneOut, _BANDS
from catalog.generators.oddoneout_data import (
    AMBIGUOUS, CATEGORIES, DOMAINS, FAR_FOILS, MEMBER_OF, NEAR_FOILS)

fails = []


def ck(label, cond, extra=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + (f"   [{extra}]" if extra and not cond else ""))
    if not cond:
        fails.append(label)


def main():
    gen = OddOneOut()
    domain_of = {c: d for d, cs in DOMAINS.items() for c in cs}

    print("\nEXHAUSTIVE — every category x band x admissible foil")
    checked = bad_member = bad_amb = bad_domain = 0
    for slug, (_label, members) in CATEGORIES.items():
        own = set(members)
        for band, (n, kind) in _BANDS.items():
            pool = (NEAR_FOILS if kind == "near" else FAR_FOILS)[slug]
            for foil in pool:
                checked += 1
                if foil in own:
                    bad_member += 1
                if (slug, foil) in AMBIGUOUS:
                    bad_amb += 1
                # A far foil must come from another domain, or `plum` (fruit)
                # can be the odd one out among trees -- and a plum is a tree.
                if kind == "far" and domain_of[MEMBER_OF[foil]] == domain_of[slug]:
                    bad_domain += 1
    ck(f"no foil is a member of its own category ({checked:,} checked)", bad_member == 0)
    ck("no foil is one the data marks ambiguous", bad_amb == 0)
    ck("no FAR foil comes from the same domain as its category", bad_domain == 0)

    print("\nDATA")
    ck("every word belongs to exactly one category", len(MEMBER_OF) ==
       sum(len(m) for _l, m in CATEGORIES.values()))
    ck("every category has at least one near foil",
       all(NEAR_FOILS[c] for c in CATEGORIES))
    ck("every category has six members (bands need up to six)",
       all(len(m) == 6 for _l, m in CATEGORIES.values()))
    nuts = {"walnut", "hazelnut", "chestnut", "almond", "acorn", "peanut"}
    ck("no nut appears anywhere -- `walnut` was a foil for fruit, and a walnut "
       "is botanically a fruit", not (nuts & set(MEMBER_OF)))
    ck("'plum' is never a foil for 'trees' (a plum IS a tree)",
       "plum" not in NEAR_FOILS["trees"] and "plum" not in FAR_FOILS["trees"])
    ck("'squall' is never a foil for rain (a squall brings rain)",
       "squall" not in NEAR_FOILS["precip"] and "squall" not in FAR_FOILS["precip"])
    # THE LABEL RULE: the explanation says "<members> are all <label>. <Foil> is
    # not", so a label must read false of every foil. `garments` was "things worn
    # on the body" while drawing foils from headwear and footwear -- a turban IS
    # worn on the body, so the explanation was untrue. No assertion can decide
    # this in general; this pins the case that reading the output found.
    gl = CATEGORIES["garments"][0]
    ck("the 'garments' label excludes head and feet, or its foils satisfy it",
       "head" in gl and "feet" in gl, gl)
    ck("'brass' is never a foil for wind instruments (brass IS a wind family)",
       "brass" not in NEAR_FOILS["windinst"] and "brass" not in FAR_FOILS["windinst"])

    print("\nCEILING")
    near = sum(len(v) for v in NEAR_FOILS.values())
    print(f"    near facts (category, foil needing a reason): {near}   (old data: 24)")
    ck("at least 200 near facts", near >= 200, str(near))
    for band in gen.difficulties:
        n, kind = _BANDS[band]
        reach = sum(len((NEAR_FOILS if kind == "near" else FAR_FOILS)[c])
                    for c in CATEGORIES)
        print(f"    band {band}: n={n} {kind:<4} -> {reach} facts reachable")
        ck(f"band {band} reaches at least 100 facts", reach >= 100, str(reach))

    print("\nBUILT ITEMS — 3,000 draws")
    problems = {k: 0 for k in ("one_correct", "count", "unselectable", "key_is_member",
                               "distractor_not_member", "typed", "dupes")}
    per_band_odds = {b: set() for b in gen.difficulties}
    drawn = 0
    rng = random.Random(20260907)
    for _ in range(3000):
        band = rng.choice(gen.difficulties)
        item = gen.build(rng, band)
        if item is None:
            continue
        drawn += 1
        n, _kind = _BANDS[band]
        rows = item.option_rows()
        slug = item.params["category"]
        own = set(CATEGORIES[slug][1])
        texts = [t for t, _c, _f in rows]
        correct = [t for t, c, _f in rows if c]
        shown = [w.strip() for w in item.stem.split("?")[1].split(",")]
        if len(correct) != 1:
            problems["one_correct"] += 1
        if len(rows) != n + 1:
            problems["count"] += 1
        if set(shown) != set(texts):
            problems["unselectable"] += 1
        if len(set(texts)) != len(texts):
            problems["dupes"] += 1
        if correct and correct[0] in own:
            problems["key_is_member"] += 1
        for t, c, _f in rows:
            if not c and t not in own:
                problems["distractor_not_member"] += 1
        if item.question_type != "by-category" or item.params.get("difficulty") != band:
            problems["typed"] += 1
        if correct:
            per_band_odds[band].add((slug, correct[0]))
    ck(f"{drawn} items built", drawn > 2900, str(drawn))
    ck("exactly one correct option", problems["one_correct"] == 0)
    ck("option count matches the band's word count", problems["count"] == 0)
    ck("EVERY word printed in the stem is selectable", problems["unselectable"] == 0,
       str(problems["unselectable"]))
    ck("no duplicate option text", problems["dupes"] == 0)
    ck("the odd word is never a member of the category", problems["key_is_member"] == 0)
    ck("every other option IS a member of the category",
       problems["distractor_not_member"] == 0, str(problems["distractor_not_member"]))
    ck("question_type and difficulty are set correctly", problems["typed"] == 0)

    print("\nREGRESSIONS — the four defects named in the docstring")
    b1 = {c for c, _o in per_band_odds[1]}
    ck("band 1 is not stuck on one foil per category "
       f"({len(per_band_odds[1])} distinct facts seen, over {len(b1)} categories)",
       len(per_band_odds[1]) > 3 * len(b1), str(len(per_band_odds[1])))

    def shapes(band, n=1500):
        r = random.Random(7)
        return {(i.stem, tuple(sorted(t for t, _c, _f in i.option_rows())))
                for i in (gen.build(r, band) for _ in range(n))}
    s1, s2, s3, s4 = shapes(1), shapes(2), shapes(3), shapes(4)
    ck("bands 1 and 2 are no longer identical", not (s1 == s2))
    ck("bands 3 and 4 are no longer identical", not (s3 == s4))
    a = gen.build(random.Random(1), 3)
    b = gen.build(random.Random(1), 4)
    ck("difficulty is in params", "difficulty" in a.params)
    ck("bands get different gen_keys, so they cannot overwrite each other",
       a.key(gen.slug, gen.template_id) != b.key(gen.slug, gen.template_id))

    print("\nTAXONOMY")
    tax = json.load(open(os.path.join("elevenplus_data", "taxonomy.json")))
    sub = [s for s in tax["sections"]["VR"]["subtopics"]
           if s["name"] == "Odd One Out"][0]
    slugs = [q["slug"] for q in sub["question_types"]]
    ck("'by-category' is a real question_type for Odd One Out",
       "by-category" in slugs, str(slugs))
    ck("the generator names the subtopic exactly", gen.subtopic == sub["name"])

    print()
    print("RESULT: " + ("ALL PASSED" if not fails else f"{len(fails)} FAILED"))
    for f in fails:
        print("  - " + f)
    return 1 if fails else 0


sys.exit(main())
