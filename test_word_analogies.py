"""Checks the VR Word Analogies generator can never ask a question with two answers.

Run:  python3 test_word_analogies.py

No Django and no database — the generator is stdlib-only, the same split
test_compound_words.py uses so this can run in CI's fast job.

**What this is defending against.** The previous generator drew every distractor
from a DIFFERENT relation:

    others = [p for r, ps in ANALOGIES if r != relation for p in ps]

Since each relation is a semantic class, that guaranteed no distractor was ever
the same kind of thing as the answer. It made two-answer questions impossible
and the questions worthless: a bot that never parses the analogy at all, and
just picks the option in the same class as the exemplar's answer, scored
**28/28 on the entire shipped bank**. On the adjective bands the tell was
visible without a bot — the key was the only adjective among four options in 54%
of band-4 and band-5 draws.

Fixing that means offering same-class distractors, which opens exactly the risk
`nightlight` opened for compound words. So the invariant here is not "the key is
right". It is:

    NO option other than the key is defensible for the target's a-word.

`DEFENSIBLE` in analogy_data is the permissive table that decides that, playing
`ATTACHING`'s role. Sampling is what let the old generator's defects sit in the
bank, so this establishes the invariant by enumerating the generator's ENTIRE
output space: every relation, every exemplar, every target, every band, every
candidate the distractor filter admits. If every admissible candidate is
non-defensible then so is every 3-subset of them, and so is every question the
generator can emit — without enumerating C(n,3) of them.

**The honest limit.** web2 settles "is nightlight a word", so #61's equivalent
test rests on evidence. Nothing settles "is a trowel a sculptor's tool".
`DEFENSIBLE` is hand-authored, so everything below proves the generator OBEYS
the table and proves nothing about whether the table is COMPLETE. That is the
weak point of this change.

Named traps, each with its own check at the bottom:

  * `trowel`/`sculptor` — a trowel is a bricklayer's tool, a gardener's tool and
    a sculptor's tool. Latent in the OLD data too; invisible only because the
    same-relation exclusion kept it out of the pool.
  * `kennel` for (dog, puppy) — defensible under a different relation, which is
    why DEFENSIBLE is flat rather than per-relation.
  * `freezing` for (hot, cold) — a defensible opposite, though keyed under
    `greater_degree`. The same cross-relation shape, in the other direction.
  * `spoke` for (rung, ladder) — an a-side word, defensible by reading the
    relation backwards. Excluded structurally, not by the table.
  * band collision — the exemplar AND the difficulty must both reach `params`,
    or 56 of the 84 stems the old generator could word were discarded unseen and
    20 of the surviving 28 keys were reachable at two bands and overwrote each
    other.
"""
import itertools
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from catalog.generators.analogy_data import (ALSO_HOLDS, B_WORDS, CLASS,
                                             DEFENSIBLE, PAIRS, RELATIONS,
                                             render)
from catalog.generators.verbal import Analogy, _ANALOGY_BANDS

fails = []


def ck(label, cond, extra=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}"
          + (f"   [{extra}]" if extra and not cond else ""))
    if not cond:
        fails.append(label)


def eligible(relation, a1, b1, a2, b2):
    """The exact candidate pools build() draws from, as (same-class, outside).

    Kept in step with Analogy._distractors by the check below, which asserts the
    generator's own output is drawn from these lists.
    """
    blocked = set(DEFENSIBLE.get(a2, ())) | {a1, b1, a2, b2}
    same = [w for w in CLASS[relation] if w not in blocked]
    outside = [w for w in B_WORDS
               if w not in blocked and w not in CLASS[relation]]
    return same, outside


def every_question():
    """Every (relation, exemplar, target, band) the generator can reach."""
    for band, (ex_tier, tg_tier, n_same) in _ANALOGY_BANDS.items():
        for relation, rows in PAIRS.items():
            ex = [(a, b) for a, b, t in rows if t == ex_tier]
            tg = [(a, b) for a, b, t in rows if t == tg_tier]
            for (a1, b1), (a2, b2) in itertools.product(ex, tg):
                if (a1, b1) == (a2, b2):
                    continue
                yield band, n_same, relation, a1, b1, a2, b2


def main():
    gen = Analogy()

    print("\nEXHAUSTIVE — every relation x exemplar x target x band x candidate")
    checked = bad = 0
    worst = None
    shapes = 0
    for band, n_same, rel, a1, b1, a2, b2 in every_question():
        shapes += 1
        same, outside = eligible(rel, a1, b1, a2, b2)
        for cand in same + outside:
            checked += 1
            if cand in DEFENSIBLE.get(a2, ()):
                bad += 1
                worst = f"{rel}: {cand!r} defensible for {a2!r}"
    ck(f"no admissible distractor is defensible for the target "
       f"({checked:,} candidates over {shapes:,} question shapes)",
       bad == 0, worst or "")

    print("\nSTRUCTURAL EXCLUSIONS — the two classes the table does not handle")
    a_side = {a for rows in PAIRS.values() for a, _b, _t in rows}
    offered = set()
    for _band, _n, rel, a1, b1, a2, b2 in every_question():
        same, outside = eligible(rel, a1, b1, a2, b2)
        offered |= set(same) | set(outside)
    ck("no candidate is an a-side word unless it is also a b-side word "
       "(reading the relation backwards is impossible)",
       all(w in set(B_WORDS) for w in offered))
    ck("the key is never offered as its own distractor",
       all(b2 not in eligible(rel, a1, b1, a2, b2)[0]
           + eligible(rel, a1, b1, a2, b2)[1]
           for _b, _n, rel, a1, b1, a2, b2 in every_question()))
    ck("the exemplar's own answer is never offered",
       all(b1 not in eligible(rel, a1, b1, a2, b2)[0]
           + eligible(rel, a1, b1, a2, b2)[1]
           for _b, _n, rel, a1, b1, a2, b2 in every_question()))
    print(f"    {len(a_side)} a-side words, {len(B_WORDS)} b-side words")

    print("\nEVERY BAND CAN BE BUILT")
    for band, (ex_tier, tg_tier, n_same) in sorted(_ANALOGY_BANDS.items()):
        ok = sum(1 for b, n, rel, a1, b1, a2, b2 in every_question()
                 if b == band
                 and len(eligible(rel, a1, b1, a2, b2)[0]) >= n
                 and len(eligible(rel, a1, b1, a2, b2)[1]) >= 3 - n)
        total = sum(1 for b, *_ in every_question() if b == band)
        print(f"    band {band}: {ok}/{total} shapes buildable "
              f"(tiers {ex_tier}->{tg_tier}, {n_same} same-class distractors)")
        ck(f"band {band} builds every shape it can reach", ok == total,
           f"{ok}/{total}")

    print("\nBANDS ARE GENUINELY DIFFERENT")
    per_band = {}
    for band, n_same, rel, a1, b1, a2, b2 in every_question():
        per_band.setdefault(band, set()).add((rel, a1, b1, a2, b2, n_same))
    for x, y in itertools.combinations(sorted(per_band), 2):
        ck(f"bands {x} and {y} are not the same question set",
           per_band[x] != per_band[y])

    print("\nCEILING — what this rewrite exists to raise")
    facts = sum(len(rows) for rows in PAIRS.values())
    stems = len({(rel, a1, b1, a2, b2)
                 for _b, _n, rel, a1, b1, a2, b2 in every_question()})
    rows = sum(len(v) for v in per_band.values())
    print(f"    target facts (a2 -> b2 pairs) : {facts}      (was 28)")
    print(f"    distinct stems                : {stems}      (was 84 wordable, "
          f"28 reachable)")
    print(f"    distinct bank rows            : {rows}     (was 28)")
    ck("at least 500 distinct stems", stems >= 500, str(stems))
    ck("at least 1,000 distinct rows", rows >= 1000, str(rows))

    print("\nTHE CATEGORY-MATCHING BOT — 100% on the old bank, per band now")
    word_class = {w: rel for rel, ws in CLASS.items() for w in ws}
    for band in sorted(_ANALOGY_BANDS):
        n = hit = 0
        rng = random.Random(f"bot:{band}")
        for _ in range(1500):
            item = gen.build(rng, band)
            if item is None:
                continue
            b1 = item.stem.split(" is to ")[1].split(" as ")[0]
            same_class = [t for t, _c in item.options
                          if word_class.get(t) == word_class.get(b1)]
            n += 1
            # The bot only scores when class-matching picks out ONE option and
            # that option is the key. More than one same-class option and it has
            # to guess, which is the whole point.
            if len(same_class) == 1 and same_class[0] == \
                    [t for t, c in item.options if c][0]:
                hit += 1
        pct = 100 * hit / n if n else 0
        print(f"    band {band}: {pct:5.1f}%  ({hit}/{n})")
        if band == 1:
            # DELIBERATE. Band 1 has no same-class distractor, so class-matching
            # is meant to work -- it is the scaffold for the weakest pupils.
            ck("band 1 is deliberately class-matchable (scaffold)", pct > 90,
               f"{pct:.0f}%")
        else:
            ck(f"band {band} defeats the category-matching bot", pct < 60,
               f"{pct:.0f}%")

    print("\nBUILT ITEMS — 3,000 draws")
    rng = random.Random(20260907)
    p = {"one_correct": 0, "four_opts": 0, "dupes": 0, "defensible": 0,
         "typed": 0, "n_same": 0, "unfilled": 0, "params": 0}
    drawn = 0
    types_seen = set()
    for _ in range(3000):
        band = rng.choice(gen.difficulties)
        item = gen.build(rng, band)
        if item is None:
            continue
        drawn += 1
        rel = item.params["relation"]
        a2, b2 = item.params["pair"]
        texts = [t for t, _c in item.options]
        correct = [t for t, c in item.options if c]
        if len(correct) != 1:
            p["one_correct"] += 1
        if len(item.options) != 4:
            p["four_opts"] += 1
        if len(set(texts)) != len(texts):
            p["dupes"] += 1
        for t, c in item.options:
            if not c and t in DEFENSIBLE.get(a2, ()):
                p["defensible"] += 1
        if item.question_type != RELATIONS[rel][0]:
            p["typed"] += 1
        types_seen.add(item.question_type)
        # The band's same-class count must actually be delivered, or the
        # difficulty axis is decorative.
        want = _ANALOGY_BANDS[band][2]
        got = sum(1 for t, c in item.options if not c and t in CLASS[rel])
        if got != want:
            p["n_same"] += 1
        if "{" in item.explanation or "{" in item.stem:
            p["unfilled"] += 1
        if (item.params.get("difficulty") != band
                or "exemplar" not in item.params):
            p["params"] += 1
    ck(f"{drawn} items built", drawn > 2900, str(drawn))
    ck("exactly one correct option", p["one_correct"] == 0)
    ck("exactly four options", p["four_opts"] == 0)
    ck("no duplicate option text", p["dupes"] == 0)
    ck("NO distractor is ever defensible for the target",
       p["defensible"] == 0, str(p["defensible"]))
    ck("question_type matches the relation", p["typed"] == 0)
    ck("each band delivers its own same-class distractor count",
       p["n_same"] == 0, str(p["n_same"]))
    ck("no unfilled slot in any stem or explanation", p["unfilled"] == 0)
    ck("exemplar and difficulty both reach params", p["params"] == 0)

    print("\nEXPLANATIONS — 16 of the old generator's 28 rows were wrong")
    bad_expl = []
    for rel, rows in PAIRS.items():
        for a, b, _t in rows:
            text = render(rel, a, b)
            if "{" in text:
                bad_expl.append(text)
            # "a scorching", "a trousers", "a otter" -- the three shapes that
            # actually shipped or nearly shipped.
            for wrong in (" a a", " a e", " a i", " a o", " a u"):
                if text.startswith(wrong.strip() + " ") or wrong in text:
                    bad_expl.append(text)
    ck(f"every one of the {sum(len(r) for r in PAIRS.values())} pairs renders "
       f"correctly", not bad_expl, str(bad_expl[:3]))
    ck("the two reversed frames from the old generator now read forwards",
       render("part_of", "petal", "flower") == "a petal is one part of a flower"
       and render("tool_of", "brush", "painter")
       == "a brush is a tool used by a painter")
    ck("the adjective relations carry no article at all",
       render("greater_degree", "warm", "scorching") == "scorching means "
       "extremely warm"
       and render("opposite", "ancient", "modern")
       == "modern is the opposite of ancient")
    ck("a/an is correct before a vowel",
       render("home_of", "otter", "holt") == "a holt is the home of an otter"
       and render("kind_of", "oak", "tree") == "an oak is a kind of tree")

    print("\nTHE SAFETY TABLE BLOCKS SOMETHING")
    # #63's real finding: almost every entry in its hand-written blocklist named
    # a word that was already a member, so the list was a comment wearing a
    # guard's clothes. _build() raises on that shape; this proves the surviving
    # entries change the pools rather than merely being well-formed.
    for rel, entries in ALSO_HOLDS.items():
        for a, extra in entries.items():
            for b in extra:
                reached = any(b in eligible(r, a1, b1, a2, b2)[0]
                              + eligible(r, a1, b1, a2, b2)[1]
                              for _bd, _n, r, a1, b1, a2, b2 in every_question()
                              if a2 == a)
                ck(f"ALSO_HOLDS[{rel}][{a}] -> {b!r} actually blocks it",
                   not reached)

    print("\nREGRESSIONS — the traps named in the docstring")
    tool_pools = [w for _b, _n, rel, a1, b1, a2, b2 in every_question()
                  if a2 == "trowel"
                  for w in eligible(rel, a1, b1, a2, b2)[0]
                  + eligible(rel, a1, b1, a2, b2)[1]]
    ck("'sculptor' is never offered against 'trowel'",
       "sculptor" not in tool_pools)
    ck("'gardener' is never offered against 'trowel'",
       "gardener" not in tool_pools)
    ck("...and the old data had the same latent pair (a trowel IS a "
       "sculptor's tool)", "sculptor" in DEFENSIBLE["trowel"])
    dog_pools = [w for _b, _n, rel, a1, b1, a2, b2 in every_question()
                 if a2 == "dog"
                 for w in eligible(rel, a1, b1, a2, b2)[0]
                 + eligible(rel, a1, b1, a2, b2)[1]]
    ck("'kennel' is never offered against 'dog' (cross-relation)",
       "kennel" not in dog_pools)
    hot_pools = [w for _b, _n, rel, a1, b1, a2, b2 in every_question()
                 if a2 == "hot"
                 for w in eligible(rel, a1, b1, a2, b2)[0]
                 + eligible(rel, a1, b1, a2, b2)[1]]
    ck("'freezing' is never offered against 'hot' (cross-relation, "
       "the other direction)", "freezing" not in hot_pools)
    rung_pools = [w for _b, _n, rel, a1, b1, a2, b2 in every_question()
                  if a2 == "rung"
                  for w in eligible(rel, a1, b1, a2, b2)[0]
                  + eligible(rel, a1, b1, a2, b2)[1]]
    ck("'spoke' is never offered against 'rung' (a-side, backwards reading)",
       "spoke" not in rung_pools)
    ck("'earth' was deleted rather than tabled (a fox's home is equally a den)",
       "earth" not in B_WORDS)

    print("\nDIFFICULTY AND EXEMPLAR ARE PART OF IDENTITY (gen_key)")
    a = gen.build(random.Random(7), 4)
    b = gen.build(random.Random(7), 5)
    ck("the same relation at two bands can be the same puzzle",
       a.params["relation"] == b.params["relation"])
    ck("...but gets different gen_keys, so bands cannot overwrite each other",
       a.key(gen.slug, gen.template_id) != b.key(gen.slug, gen.template_id))
    seen = {}
    collisions = 0
    for band in gen.difficulties:
        rng = random.Random(f"key:{band}")
        for _ in range(400):
            item = gen.build(rng, band)
            if item is None:
                continue
            k = item.key(gen.slug, gen.template_id)
            if k in seen and seen[k] != item.stem:
                collisions += 1
            seen[k] = item.stem
    ck("no two different stems share a gen_key", collisions == 0,
       str(collisions))

    print("\nTAXONOMY")
    tax = json.load(open(os.path.join("elevenplus_data", "taxonomy.json")))
    sub = [s for s in tax["sections"]["VR"]["subtopics"]
           if s["name"] == "Word Analogies"][0]
    slugs = {q["slug"] for q in sub["question_types"]}
    ck("the generator names the subtopic exactly", gen.subtopic == sub["name"])
    ck("every emitted question_type is a real slug",
       types_seen <= slugs, str(sorted(types_seen - slugs)))
    ck("all five of the subtopic's question_types are now reachable "
       "(the old generator emitted \"\", so none was)",
       {RELATIONS[r][0] for r in RELATIONS} == slugs,
       str(sorted(slugs - {RELATIONS[r][0] for r in RELATIONS})))

    # Not an assertion -- a REVIEW AID, and the answer to "how would anyone
    # check DEFENSIBLE is complete?". No test can: the table is judgement. So
    # print every same-class pairing the generator can actually offer, which is
    # the list a human has to read. Sweeping this is what found nine missing
    # entries (anvil/sculptor, hammer and chisel/bricklayer, head/scarf,
    # wrist/glove, nurse/school, bird/eyrie, bee/nest, otter/burrow) that ten
    # sampled questions did not show.
    print("\nSAME-CLASS PAIRINGS — read these; this is what the table cannot prove")
    for rel in sorted(PAIRS):
        print(f"  {rel}")
        for a2, b2, _t in PAIRS[rel]:
            blocked = sorted(set(DEFENSIBLE.get(a2, ())) - {b2})
            offered = [w for w in CLASS[rel]
                       if w not in set(DEFENSIBLE.get(a2, ())) | {a2, b2}]
            line = f"    {a2:<12} key={b2:<12} offered: {', '.join(offered)}"
            if blocked:
                line += f"   | BLOCKED: {', '.join(blocked)}"
            print(line)

    print()
    print("RESULT: " + ("ALL PASSED" if not fails else f"{len(fails)} FAILED"))
    for f in fails:
        print("  - " + f)
    return 1 if fails else 0


sys.exit(main())
