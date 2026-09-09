#!/usr/bin/env python3
"""
Independent checks on the Paired Synonyms pack (contrib_prash_vr_23.json).

    python3 elevenplus_data/check_synonym_pairs.py elevenplus_data/contrib_prash_vr_23.json

Exit 0 if every mechanical check passes, 1 with a list of failures otherwise.

It never imports the generator and never reads the pool: both brackets are
parsed out of the *rendered stem* and matched against the declared
`option_groups`, so a stem that prints different words from the ones being
marked fails.

WHAT THIS CHECKER CANNOT DO, SAID PLAINLY. Whether exactly one of the nine
cross-bracket combinations is a genuine pair of near-synonyms is a semantic
question. This project has no WordNet, no POS tagger and no thesaurus —
`wordfreq` gives frequency and nothing else — so no check here can settle it.
Instead the checker PRINTS ALL NINE COMBINATIONS per question, so the judgement
a human has to make is in front of them rather than buried in the pool. Reading
those nine lists is the review; everything else below is only the mechanical
half. This is the case QUESTION_QUALITY.md marks as needing a human, and
pretending otherwise would be worse than admitting it.

Mechanically:

  * THE STEM AND THE MARKING MUST AGREE. The bracketed words in the stem, in
    order, must be exactly the `option_groups` — same words, same order, same
    brackets. Two brackets, three words each, exactly one `correct` per bracket.
  * ONE MARK FOR THE PAIR, so both keys are checked, and a question with a
    bracket carrying no key or two keys fails.
  * ALL SIX WORDS DISTINCT AND REAL. A word appearing in both brackets would be
    pickable twice; a non-word would be eliminable on sight.
  * NO PAIR TWICE, IN EITHER DIRECTION. The key pair is compared as an
    unordered pair across the whole pack, so asking "happy/cheerful" and
    "cheerful/happy" as two questions is caught — that is the same fact twice
    and the reason this pack is 9 questions and not 18.
  * THE BAND IS RE-DERIVED from the rarer word's frequency, because the pool's
    own bands are positional slices (`[0:3]`, `[3:6]`, `[6:9]`) whose measured
    gradient runs exactly backwards. Without `wordfreq` this check reports itself
    skipped.
  * KEY POSITIONS ARE CHECKED PER BRACKET, as CLAUDE.md requires: each bracket
    is its own positional answer key, so a pupil must not be able to learn that
    the answer is always the last word in the second bracket.
"""
import collections
import json
import re
import sys

PACK = sys.argv[1] if len(sys.argv) > 1 else "elevenplus_data/contrib_prash_vr_23.json"
pack = json.load(open(PACK))
qs = pack["questions"]
fail = []
RELATION = "closest-in-meaning"

try:
    from wordfreq import zipf_frequency
    WORDS = {w.strip().lower() for w in open("/usr/share/dict/words") if w.strip()}
except Exception as exc:
    WORDS, zipf_frequency, WHY_SKIPPED = None, None, str(exc)
else:
    WHY_SKIPPED = None

BRACKETS = re.compile(r"^\(([^)]+)\)\s+\(([^)]+)\)$")


def listed(word):
    """In the word list as a lemma or a regular inflection of one.

    web2 lists lemmas, so CARING and SCARED are absent from it while CARE and
    SCARE are there — the same gap that hid the plural rivals in Hidden Words
    and Letter Moves, met here from the other side.
    """
    w = word.lower()
    forms = {w}
    if w.endswith("s"):
        forms |= {w[:-1], w[:-2]}
    if w.endswith("ed"):
        forms |= {w[:-1], w[:-2]}
    if w.endswith("ing"):
        forms |= {w[:-3], w[:-3] + "e"}
    return any(f in WORDS for f in forms)


def band_of(a, b):
    rarer = min(zipf_frequency(a, "en"), zipf_frequency(b, "en"))
    return 5 if rarer < 3.98 else (4 if rarer < 4.25 else 3)


refs, stems = [], collections.Counter()
pairs = collections.Counter()
slots = [collections.Counter(), collections.Counter()]
print("Every cross-bracket combination, for the human half of this review.")
print("Exactly one line per question should be a real pair of near-synonyms:\n")

for q in qs:
    tag = q.get("ref", "?")
    stem = q["stem"]
    stems[stem] += 1
    refs.append(tag)

    if q.get("subtopic") != "Paired Synonyms":
        fail.append(f"{tag}: wrong subtopic {q.get('subtopic')!r}")
    if q.get("kind") != "grouped_options":
        fail.append(f"{tag}: kind {q.get('kind')!r}; CLAUDE.md gives this bracket shape "
                    f"its own kind and forbids flattening it into one options list")
        continue
    if q.get("options"):
        fail.append(f"{tag}: a grouped question must not also carry flat options")

    m = BRACKETS.match(stem)
    if not m:
        fail.append(f"{tag}: stem does not print two bracketed groups: {stem!r}")
        continue
    printed = [[w.strip() for w in g.split(",")] for g in m.groups()]

    groups = q.get("option_groups") or []
    if [g.get("group") for g in groups] != [1, 2]:
        fail.append(f"{tag}: groups must be numbered 1 then 2")
        continue
    keys = []
    for i, g in enumerate(groups):
        texts = [o["text"] for o in g["options"]]
        if texts != printed[i]:
            fail.append(f"{tag}: bracket {i + 1} prints {printed[i]} but marks {texts}")
        correct = [o["text"] for o in g["options"] if o.get("correct")]
        if len(correct) != 1:
            fail.append(f"{tag}: bracket {i + 1} has {len(correct)} correct words")
            keys = None
            break
        if len(texts) < 2:
            fail.append(f"{tag}: bracket {i + 1} has fewer than two words")
        keys.append(correct[0])
        slots[i][texts.index(correct[0])] += 1
    if not keys:
        continue

    words = printed[0] + printed[1]
    if len(set(words)) != len(words):
        fail.append(f"{tag}: a word appears in both brackets: "
                    f"{[w for w in set(words) if words.count(w) > 1]}")
    if WORDS is not None:
        for w in words:
            # A recognition bar, not a production one: these words are printed in
            # front of the pupil, not recalled. STUDIOUS (zipf 2.54) is an
            # ordinary word that fails a 2.8 production bar and should not fail
            # here — the same two-bar reasoning check_anagrams.py uses.
            if not listed(w) or zipf_frequency(w.lower(), "en") < 2.4:
                fail.append(f"{tag}: {w!r} is not a real word a pupil would recognise")
        want = band_of(*keys)
        if q.get("difficulty") != want:
            fail.append(f"{tag}: band {q.get('difficulty')}, but the rarer of "
                        f"{keys[0]}/{keys[1]} puts it at band {want}")

    pairs[frozenset(keys)] += 1
    for w in keys:
        if w not in q.get("explanation", ""):
            fail.append(f"{tag}: explanation does not name {w}")

    combos = [f"{a}/{b}" for a in printed[0] for b in printed[1]]
    marked = f"{keys[0]}/{keys[1]}"
    print(f"  {tag}  key {marked:24s} others: "
          f"{', '.join(c for c in combos if c != marked)}")

for s, n in stems.items():
    if n > 1:
        fail.append(f"duplicate stem x{n}: {s!r}")
for p, n in pairs.items():
    if n > 1:
        fail.append(f"the pair {sorted(p)} is asked in {n} questions — the same fact twice")
if len(set(refs)) != len(refs):
    fail.append("duplicate refs")

group_refs = {g["group_ref"] for g in pack.get("groups", [])}
for q in qs:
    if q.get("group_ref") not in group_refs:
        fail.append(f"{q.get('ref')}: group_ref {q.get('group_ref')!r} is not declared")
for g in pack.get("groups", []):
    if not g.get("instruction") or not g.get("example"):
        fail.append(f"{g.get('group_ref')}: a group needs both an instruction and an example")
    elif not BRACKETS.match(g["example"].split(" — ")[0]):
        fail.append(f"{g.get('group_ref')}: the example must show the bracket notation")

for i, c in enumerate(slots):
    if c and max(c.values()) > sum(c.values()) * 0.6:
        fail.append(f"bracket {i + 1}: the key sits in position "
                    f"{max(c, key=c.get)} in {max(c.values())} of {sum(c.values())} "
                    f"questions — a pupil can learn the slot")

print(f"\npack: {PACK}")
print(f"questions: {len(qs)}   refs: {refs[0]}..{refs[-1]}")
print(f"kind: {dict(collections.Counter(q['kind'] for q in qs))}")
print(f"difficulty: {dict(sorted(collections.Counter(q['difficulty'] for q in qs).items()))}")
print(f"distinct pairs (direction-blind): {len(pairs)} / {len(qs)}")
print(f"key position within bracket 1: {dict(sorted(slots[0].items()))}   "
      f"bracket 2: {dict(sorted(slots[1].items()))}")
if WORDS is None:
    print(f"real-word and band checks: SKIPPED — no word list ({WHY_SKIPPED})")
print(f"semantic uniqueness of the {RELATION} pair: NOT machine-checkable here — "
      f"see the nine combinations printed above")

if fail:
    print(f"\nFAIL ({len(fail)}):")
    for f in fail[:40]:
        print("  -", f)
    sys.exit(1)
print("\nALL MECHANICAL CHECKS PASS")
