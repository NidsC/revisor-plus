#!/usr/bin/env python3
"""
Independent checks on the Word Patterns pack (contrib_prash_vr_20.json).

    python3 elevenplus_data/check_word_patterns.py elevenplus_data/contrib_prash_vr_20.json

Exit 0 if every check passes, 1 with a list of failures otherwise.

It never imports the generator. The extraction rule is parsed back out of the
*English sentence printed in the stem* — "the first 3 letters of word1,
followed by the last 1 letter of word3" — and re-applied to the words printed
beside it. If the pack's own explanation and the stem disagree, the stem wins,
because the stem is what the pupil reads.

  * THE RULE IS PARSED, NOT ASSUMED. The description must resolve to exactly
    one extraction spec; a wording that parses two ways would leave the pupil
    with two defensible answers even though the rule is "stated".
  * THE DEMO IS SELF-CHECKING. The worked row printed above the question must
    itself obey the rule the stem states. A demo that does not is worse than no
    demo: it teaches a rule the question then does not use.
  * EXHAUSTIVE TWO-ANSWER SWEEP over the whole space of extraction rules this
    subtopic uses — every (front|back, 1-3 letters) piece of word1 paired with
    every such piece of word3, in both concatenation orders — 72 candidates.
    Every rule consistent with the demo row is applied to the target row, and
    they must all give the same code word. Where they do not, the stated rule
    is what disambiguates, and the checker records that the item leans on the
    statement rather than on the demonstration.
  * NO OPTION MAY BE THE KEY TWICE OVER, and distractors must be real words of
    the same length as the key, so none is eliminable on sight.
  * THE BAND LABEL IS DERIVED FROM THE PARSED RULE, not trusted: band 1 is the
    front1+front2 rule, band 2 front2+back2, band 3 the four harder shapes.
    **Bands 4 and 5 must be absent** — they are `find-pattern`, which with only
    four rows per rule prints the whole of a rule's pool inside the question.
  * NO QUESTION MAY PRINT MORE THAN TWO ROWS of its rule (one demo, one
    target), which is the mechanical form of that same rule.
  * plus: one question per target row, unique stems and refs, every question
    `apply-pattern`, write-in questions carrying an answer and no options, and
    answer positions neither clustered nor cyclic nor in a run of four.
"""
import collections
import itertools
import json
import re
import sys

PACK = sys.argv[1] if len(sys.argv) > 1 else "elevenplus_data/contrib_prash_vr_20.json"
pack = json.load(open(PACK))
qs = pack["questions"]
fail = []

try:
    from wordfreq import zipf_frequency
    WORDS = {w.strip().lower() for w in open("/usr/share/dict/words") if w.strip()}
except Exception as exc:
    WORDS, zipf_frequency, WHY_SKIPPED = None, None, str(exc)
else:
    WHY_SKIPPED = None

STEM = re.compile(r"^Rule: (.+?)\.\n"
                  r"([A-Z]+), ([A-Z]+), ([A-Z]+) -> \(([A-Z]+)\)\n"
                  r"([A-Z]+), ([A-Z]+), ([A-Z]+) -> \( \? \)$")
PIECE = re.compile(r"the (first|last) (\d) letters? of (word1|word3)")
BAND_OF_SPEC = {(("front", 1), ("front", 2), "w1w3"): 1,
                (("front", 2), ("back", 2), "w1w3"): 2}


def parse_rule(desc):
    """Every extraction spec the printed sentence can mean. More than one is a bug."""
    pieces = PIECE.findall(desc)
    if len(pieces) != 2:
        return []
    (pos1, n1, which1), (pos2, n2, which2) = pieces
    if {which1, which2} != {"word1", "word3"}:
        return []
    spec1 = ("front" if pos1 == "first" else "back", int(n1))
    spec2 = ("front" if pos2 == "first" else "back", int(n2))
    if which1 == "word1":
        return [(spec1, spec2, "w1w3")]          # word1's piece printed first
    return [(spec2, spec1, "w3w1")]              # word3's piece printed first


def apply_spec(w1, w3, spec):
    (p1, n1), (p3, n3), order = spec
    a = w1[:n1] if p1 == "front" else w1[-n1:]
    b = w3[:n3] if p3 == "front" else w3[-n3:]
    return a + b if order == "w1w3" else b + a


ALL_SPECS = [((p1, n1), (p3, n3), order)
             for p1 in ("front", "back") for n1 in (1, 2, 3)
             for p3 in ("front", "back") for n3 in (1, 2, 3)
             for order in ("w1w3", "w3w1")]


def real_word(word):
    w = word.lower()
    return zipf_frequency(w, "en") >= 2.8 and (
        w in WORDS or (w.endswith("s") and w[:-1] in WORDS))


positions, refs, stems, targets = [], [], collections.Counter(), collections.Counter()
leaned = 0

for q in qs:
    tag = q.get("ref", "?")
    stem = q["stem"]
    stems[stem] += 1
    refs.append(tag)

    if q.get("subtopic") != "Word Patterns":
        fail.append(f"{tag}: wrong subtopic {q.get('subtopic')!r}")
    if q.get("question_type") != "apply-pattern":
        fail.append(f"{tag}: {q.get('question_type')!r}; find-pattern is excluded from "
                    f"this pack — with four rows per rule it prints the whole rule pool")
    band = q.get("difficulty")
    if band in (4, 5):
        fail.append(f"{tag}: band {band} is excluded from this pack")
        continue

    m = STEM.match(stem)
    if not m:
        fail.append(f"{tag}: stem is not in this pack's printed shape: {stem!r}")
        continue
    desc, d1, d2, d3, dcode, w1, w2, w3 = m.groups()
    targets[(w1, w2, w3)] += 1
    if stem.count(" -> ") != 2:
        fail.append(f"{tag}: stem prints more than a demo row and a target row")

    specs = parse_rule(desc)
    if len(specs) != 1:
        fail.append(f"{tag}: the printed rule parses {len(specs)} ways: {desc!r}")
        continue
    spec = specs[0]

    if apply_spec(d1, d3, spec) != dcode:
        fail.append(f"{tag}: the worked demo {d1}/{d3} -> {dcode} does not obey the rule "
                    f"the stem states (that rule gives {apply_spec(d1, d3, spec)})")
    answer = apply_spec(w1, w3, spec)

    kind = q.get("kind")
    if kind == "short_text":
        if q.get("options"):
            fail.append(f"{tag}: a write-in question must not carry options")
        key, wrong = q.get("answer"), []
    elif kind == "mcq":
        opts = q.get("options") or []
        texts = [o["text"] for o in opts]
        if len(set(texts)) != len(texts):
            fail.append(f"{tag}: repeated option text")
        correct = [o for o in opts if o.get("correct")]
        if len(correct) != 1:
            fail.append(f"{tag}: {len(correct)} options marked correct")
            continue
        key = correct[0]["text"]
        positions.append(texts.index(key))
        wrong = [o["text"] for o in opts if not o.get("correct")]
    else:
        fail.append(f"{tag}: kind {kind!r}; this pack is mcq and short_text only")
        continue

    if key != answer:
        fail.append(f"{tag}: key {key!r} but the stated rule gives {answer!r}")
    for w in wrong:
        if w == answer:
            fail.append(f"{tag}: distractor {w!r} is also the answer")
        if len(w) != len(answer):
            fail.append(f"{tag}: distractor {w!r} is not the key's length")
        if WORDS is not None and not real_word(w):
            fail.append(f"{tag}: distractor {w!r} is not a common real word")

    # Exhaustive sweep over the whole extraction-rule space.
    consistent = {apply_spec(w1, w3, s) for s in ALL_SPECS
                  if apply_spec(d1, d3, s) == dcode}
    if answer not in consistent:
        fail.append(f"{tag}: no rule consistent with the demo produces the key")
    if len(consistent) > 1:
        leaned += 1

    if band != BAND_OF_SPEC.get(spec, 3):
        fail.append(f"{tag}: band {band}, but the rule {spec} is band "
                    f"{BAND_OF_SPEC.get(spec, 3)} in this pack's model")
    if answer not in q.get("explanation", ""):
        fail.append(f"{tag}: explanation does not state the answer {answer}")

for s, n in stems.items():
    if n > 1:
        fail.append(f"duplicate stem x{n}: {s!r}")
for t, n in targets.items():
    if n > 1:
        fail.append(f"target row {t} used in {n} questions")
if len(set(refs)) != len(refs):
    fail.append("duplicate refs")

group_refs = {g["group_ref"] for g in pack.get("groups", [])}
for q in qs:
    if q.get("group_ref") not in group_refs:
        fail.append(f"{q.get('ref')}: group_ref {q.get('group_ref')!r} is not declared")
for g in pack.get("groups", []):
    ex = g.get("example", "")
    if not g.get("instruction") or not ex:
        fail.append(f"{g.get('group_ref')}: a group needs both an instruction and an example")
        continue
    specs = parse_rule(ex)
    rows = re.findall(r"([A-Z]+), ([A-Z]+), ([A-Z]+) -> \(([A-Z]+)\)", ex)
    if len(specs) != 1 or len(rows) != 2:
        fail.append(f"{g.get('group_ref')}: example must state one rule and show two rows")
        continue
    for a, _, c, code in rows:
        if apply_spec(a, c, specs[0]) != code:
            fail.append(f"example row {a}/{c} -> {code} does not obey its own stated rule")
    if any(row[:3] in targets for row in rows):
        fail.append("example reuses a row that is also a question")

dist = collections.Counter(positions)
run = longest = 1
for a, b in zip(positions, positions[1:]):
    run = run + 1 if a == b else 1
    longest = max(longest, run)
cyclic = next((p for p in (2, 3, 4, 5)
               if positions and all(positions[i] == positions[i % p]
                                    for i in range(len(positions)))), 0)
expected = len(positions) / 4
if longest >= 4:
    fail.append(f"answer position: run of {longest} identical positions")
if cyclic:
    fail.append(f"answer position: cyclic with period {cyclic}")
for pos, c in dist.items():
    if c > expected * 1.6 or c < expected * 0.55:
        fail.append(f"answer position {pos}: {c} of {len(positions)} (expected ~{expected:.0f})")

print(f"pack: {PACK}")
print(f"questions: {len(qs)}   refs: {refs[0]}..{refs[-1]}")
print(f"kinds: {dict(collections.Counter(q['kind'] for q in qs))}")
print(f"difficulty: {dict(sorted(collections.Counter(q['difficulty'] for q in qs).items()))}"
      f"   (bands 4-5 excluded by design)")
print(f"unique stems: {len(stems)} / {len(qs)}   distinct target rows: {len(targets)}")
print(f"rule space swept per question: {len(ALL_SPECS)} extraction rules")
print(f"items where the demo alone leaves more than one reading (the stated rule "
      f"settles it): {leaned} / {len(qs)}")
print(f"answer positions (0-indexed, {len(positions)} mcqs): {dict(sorted(dist.items()))}"
      f"  longest run {longest}  cyclic {cyclic or 'none'}")
if WORDS is None:
    print(f"real-word check on distractors: SKIPPED — no word list ({WHY_SKIPPED})")

if fail:
    print(f"\nFAIL ({len(fail)}):")
    for f in fail[:40]:
        print("  -", f)
    sys.exit(1)
print("\nALL CHECKS PASS")
