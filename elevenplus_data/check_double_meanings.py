#!/usr/bin/env python3
"""
Independent checks on the Double Meanings pack (contrib_prash_vr_24.json).

    python3 elevenplus_data/check_double_meanings.py elevenplus_data/contrib_prash_vr_24.json

Exit 0 if every mechanical check passes, 1 with a list of failures otherwise.

It never imports the generator and never reads the pool: both contexts are
parsed out of the *rendered stem*, and the explanation is rebuilt from them.

WHAT THIS CHECKER CANNOT DO, SAID PLAINLY. Whether a word "fits" a phrase is a
semantic question, and this project has no corpus, no WordNet and no collocation
data — `wordfreq` gives frequency and nothing else. So no check here can prove
that the key fits both contexts or that a distractor fits only one. Instead the
checker PRINTS BOTH CONTEXTS WITH EVERY OPTION SUBSTITUTED, so the judgement a
human has to make is in front of them. Reading those lists is the review.

That review has one specific thing to look for, and it is this subtopic's free
mark: **a question whose distractors all fit the same context**. If every wrong
option belongs to context A, the pupil reads context B, finds one candidate, and
never reads A — half the question. The pool avoids it by splitting distractors
across the two contexts (SAVINGS and LOAN fit "___ account"; SIDE and MOUTH fit
"river ___"), but nothing mechanical enforces that, so it is printed for
checking rather than assumed.

Mechanically:

  * TWO CONTEXTS, EACH WITH A GAP. The stem must print exactly two bracketed
    phrases and each must contain the `___` gap — a phrase with no gap is not a
    context, and a stem with one is not this question.
  * THE EXPLANATION IS REBUILT from the stem: it must show the key substituted
    into both printed contexts, so an explanation cannot drift from the question
    it explains. This needs no word list.
  * NO OPTION MAY REPEAT, none may equal the key, every option is one word, and
    a write-in question carries an answer and no options.
  * ONE QUESTION PER WORD and per context pair, unique stems and refs, band
    labels in range (2-4: there is no band 1 in this subtopic), and key
    positions neither clustered nor cyclic nor in a run of four.
"""
import collections
import json
import re
import sys

PACK = sys.argv[1] if len(sys.argv) > 1 else "elevenplus_data/contrib_prash_vr_24.json"
pack = json.load(open(PACK))
qs = pack["questions"]
fail = []

STEM = re.compile(r"^\(([^)]+)\)\s+\(([^)]+)\)$")

positions, refs, stems, answers = [], [], collections.Counter(), collections.Counter()
print("Both contexts with every option substituted, for the human half of this review.")
print("Look for a question whose wrong options all fit the SAME context — that one")
print("can be answered from the other context alone:\n")

for q in qs:
    tag = q.get("ref", "?")
    stem = q["stem"]
    stems[stem] += 1
    refs.append(tag)

    if q.get("subtopic") != "Double Meanings":
        fail.append(f"{tag}: wrong subtopic {q.get('subtopic')!r}")
    if q.get("question_type") != "word-completes-both":
        fail.append(f"{tag}: wrong question_type {q.get('question_type')!r}")
    if q.get("difficulty") not in (2, 3, 4):
        fail.append(f"{tag}: band {q.get('difficulty')!r}; this subtopic has bands 2-4 "
                    f"only — there is no band 1")

    m = STEM.match(stem)
    if not m:
        fail.append(f"{tag}: stem does not print two bracketed contexts: {stem!r}")
        continue
    ctx_a, ctx_b = m.groups()
    for c in (ctx_a, ctx_b):
        if "___" not in c:
            fail.append(f"{tag}: context {c!r} has no gap to fill")

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

    if not key:
        fail.append(f"{tag}: no answer")
        continue
    answers[key] += 1
    for w in wrong:
        if w == key:
            fail.append(f"{tag}: a distractor repeats the key")
        if len(w.split()) != 1:
            fail.append(f"{tag}: option {w!r} is more than one word")

    rebuilt_a = ctx_a.replace("___", key)
    rebuilt_b = ctx_b.replace("___", key)
    exp = q.get("explanation", "")
    if rebuilt_a not in exp or rebuilt_b not in exp:
        fail.append(f"{tag}: explanation does not show {key!r} in both printed contexts")

    print(f"  {tag}  key {key}")
    for w in [key] + wrong:
        mark = "KEY " if w == key else "    "
        print(f"      {mark}{ctx_a.replace('___', w):32s} | {ctx_b.replace('___', w)}")

for s, n in stems.items():
    if n > 1:
        fail.append(f"duplicate stem x{n}: {s!r}")
for a, n in answers.items():
    if n > 1:
        fail.append(f"the word {a!r} is the answer to {n} questions")
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
    m = STEM.match(ex.split(" — ")[0])
    named = re.search(r"— ([A-Z]+) fits both", ex)
    if not m or not named:
        fail.append(f"{g.get('group_ref')}: example must show two contexts and its answer")
    elif named.group(1).lower() in answers:
        fail.append(f"example gives away {named.group(1)}, which is also a question")

dist = collections.Counter(positions)
run = longest = 1
for a, b in zip(positions, positions[1:]):
    run = run + 1 if a == b else 1
    longest = max(longest, run)
cyclic = next((p for p in (2, 3, 4, 5)
               if positions and all(positions[i] == positions[i % p]
                                    for i in range(len(positions)))), 0)
expected = len(positions) / 5
if longest >= 4:
    fail.append(f"answer position: run of {longest} identical positions")
if cyclic:
    fail.append(f"answer position: cyclic with period {cyclic}")
for pos, c in dist.items():
    if c > expected * 2:
        fail.append(f"answer position {pos}: {c} of {len(positions)} (expected ~{expected:.0f})")

print(f"\npack: {PACK}")
print(f"questions: {len(qs)}   refs: {refs[0]}..{refs[-1]}")
print(f"kinds: {dict(collections.Counter(q['kind'] for q in qs))}")
print(f"difficulty: {dict(sorted(collections.Counter(q['difficulty'] for q in qs).items()))}")
print(f"unique stems: {len(stems)} / {len(qs)}   distinct answers: {len(answers)}")
print(f"answer positions (0-indexed, {len(positions)} mcqs): {dict(sorted(dist.items()))}"
      f"  longest run {longest}  cyclic {cyclic or 'none'}")
print("whether each word fits its context: NOT machine-checkable here — see the "
      "substitutions printed above")

if fail:
    print(f"\nFAIL ({len(fail)}):")
    for f in fail[:40]:
        print("  -", f)
    sys.exit(1)
print("\nALL MECHANICAL CHECKS PASS")
