#!/usr/bin/env python3
"""
Independent checks on the Middle Word pack (contrib_prash_vr_13.json).

    python3 elevenplus_data/check_middle_words.py elevenplus_data/contrib_prash_vr_13.json

Exit 0 if every check passes, 1 with a list of failures otherwise.

It never imports the generator, and it never reads the pool. Every answer is
recomputed from the two words *printed in the stem* — if the stem says
`TUBE   ______   EFFORT` then the answer is `BE` + `EF` and nothing else, and a
key that disagrees is wrong however confidently the pool asserts it.

  * THE ANSWER IS RECOMPUTED, not compared. `word1[-2:] + word3[:2]` is the
    whole rule, so there is one right answer per stem and it is arithmetic on
    the printed text.
  * THE HALF-RULE GUARD, which is the real quality risk here and the reason
    this pool was rebuilt. If no distractor happens to share the key's first
    two letters, a pupil never has to read word3; if none shares its last two,
    word1 is never read. Under a uniform draw that is what almost always
    happens — measured at 99% of items over the pool this one replaced. So
    every MCQ here is required to offer BOTH: an option wrong only in its back
    half and an option wrong only in its front half. The check is not "are
    there three distractors", it is "is either half of the rule sufficient",
    and it is run against the printed options.
  * NO SECOND ANSWER. No distractor may equal the recomputed middle, and no two
    options may share both halves — two options sharing both halves would be
    the same word.
  * EVERY OPTION IS A REAL WORD, where a dictionary is available. A wrong
    option that is obviously not a word is eliminable without doing the rule.
  * THE WORKED EXAMPLE is recomputed from its own printed text, both triples.
    It is where the pupil learns the notation, so an example that does not obey
    the rule it demonstrates is worse than no example.
  * plus: one question per (word1, word3) pair, unique stems and refs, write-in
    questions carrying an answer and no options, explanations naming both
    halves, band labels in range, and answer positions neither clustered nor
    cyclic nor in a run of four.

THE WORD LIST is optional: where `/usr/share/dict/words` and `wordfreq` are
both missing the real-word check is REPORTED AS SKIPPED rather than quietly
passing, and everything else still runs.
"""
import collections
import json
import re
import sys

PACK = sys.argv[1] if len(sys.argv) > 1 else "elevenplus_data/contrib_prash_vr_13.json"
pack = json.load(open(PACK))
qs = pack["questions"]
fail = []

try:
    from wordfreq import zipf_frequency
    WEB2 = {w.strip().lower() for w in open("/usr/share/dict/words") if w.strip()}
except Exception as exc:
    WEB2, zipf_frequency, WHY_SKIPPED = None, None, str(exc)
else:
    WHY_SKIPPED = None

STEM = re.compile(r"^([A-Z]+)\s+_+\s+([A-Z]+)$")


def real_word(word):
    w = word.lower()
    return zipf_frequency(w, "en") >= 3.0 and (
        w in WEB2 or (w.endswith("s") and w[:-1] in WEB2))


positions, refs, stems, pairs = [], [], collections.Counter(), collections.Counter()
checked_words = 0

for q in qs:
    tag = q.get("ref", "?")
    stem = q["stem"]
    stems[stem] += 1
    refs.append(tag)

    if q.get("subtopic") != "Middle Word":
        fail.append(f"{tag}: wrong subtopic {q.get('subtopic')!r}")
    if q.get("question_type") != "derive-from-both-sides":
        fail.append(f"{tag}: wrong question_type {q.get('question_type')!r}")
    if q.get("difficulty") not in (2, 3, 4):
        fail.append(f"{tag}: band {q.get('difficulty')!r}; this pack is bands 2-4")

    m = STEM.match(stem)
    if not m:
        fail.append(f"{tag}: stem is not a three-word row: {stem!r}")
        continue
    word1, word3 = m.groups()
    pairs[(word1, word3)] += 1
    answer = word1[-2:] + word3[:2]          # the whole rule, recomputed

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
        if any(o.get("misconception") for o in opts if o.get("correct")):
            fail.append(f"{tag}: the key carries a misconception slug")
    else:
        fail.append(f"{tag}: kind {kind!r}; this pack is mcq and short_text only")
        continue

    if key != answer:
        fail.append(f"{tag}: key {key!r} but {word1}[-2:] + {word3}[:2] is {answer}")

    for w in wrong:
        if w == answer:
            fail.append(f"{tag}: distractor {w!r} is also the answer")
        if len(w) != 4:
            fail.append(f"{tag}: distractor {w!r} is not four letters")

    if kind == "mcq":
        front = [w for w in wrong if w[:2] == answer[:2] and w[2:] != answer[2:]]
        back = [w for w in wrong if w[2:] == answer[2:] and w[:2] != answer[:2]]
        if not front:
            fail.append(f"{tag}: no distractor shares the key's first two letters, so "
                        f"{word3} never has to be read")
        if not back:
            fail.append(f"{tag}: no distractor shares the key's last two letters, so "
                        f"{word1} never has to be read")
        for w in front + back:
            slug = next((o.get("misconception") for o in q["options"] if o["text"] == w), None)
            if slug != "found-one-part-then-stopped":
                fail.append(f"{tag}: half-right distractor {w!r} tagged {slug!r}")

    if WEB2 is not None:
        for w in [key] + wrong:
            checked_words += 1
            if not real_word(w):
                fail.append(f"{tag}: option {w!r} is not a common real word, so it can be "
                            f"eliminated without applying the rule")

    exp = q.get("explanation", "")
    for part in (word1[-2:], word3[:2], answer, word1, word3):
        if part not in exp:
            fail.append(f"{tag}: explanation does not mention {part}")
            break

for s, n in stems.items():
    if n > 1:
        fail.append(f"duplicate stem x{n}: {s!r}")
for p, n in pairs.items():
    if n > 1:
        fail.append(f"pair {p} used in {n} questions")
if len(set(refs)) != len(refs):
    fail.append("duplicate refs")

group_refs = {g["group_ref"] for g in pack.get("groups", [])}
for q in qs:
    if q.get("group_ref") not in group_refs:
        fail.append(f"{q.get('ref')}: group_ref {q.get('group_ref')!r} is not declared")

# The worked example is recomputed from its own printed text.
for g in pack.get("groups", []):
    if not g.get("instruction") or not g.get("example"):
        fail.append(f"{g.get('group_ref')}: a group needs both an instruction and an example")
        continue
    triples = re.findall(r"([A-Z]{3,})   ([A-Z]{3,})   ([A-Z]{3,})", g["example"])
    if not triples:
        fail.append(f"{g.get('group_ref')}: example shows no three-word row")
    for a, mid, c in triples:
        if mid != a[-2:] + c[:2]:
            fail.append(f"example row {a} {mid} {c} does not obey the rule "
                        f"({a[-2:]}+{c[:2]} = {a[-2:] + c[:2]})")

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
print(f"difficulty: {dict(sorted(collections.Counter(q['difficulty'] for q in qs).items()))}")
print(f"unique stems: {len(stems)} / {len(qs)}   distinct word pairs: {len(pairs)}")
print(f"answer positions (0-indexed, {len(positions)} mcqs): {dict(sorted(dist.items()))}"
      f"  longest run {longest}  cyclic {cyclic or 'none'}")
print("half-rule guard: every MCQ offers a front-sharer and a back-sharer")
if WEB2 is None:
    print(f"real-word check: SKIPPED — no word list ({WHY_SKIPPED})")
else:
    print(f"real-word check: ran over {checked_words} options")

if fail:
    print(f"\nFAIL ({len(fail)}):")
    for f in fail[:40]:
        print("  -", f)
    sys.exit(1)
print("\nALL CHECKS PASS")
