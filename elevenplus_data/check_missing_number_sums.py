#!/usr/bin/env python3
"""
Independent checks on the Missing Number Sums pack (contrib_prash_vr_08.json).

    python3 elevenplus_data/check_missing_number_sums.py elevenplus_data/contrib_prash_vr_08.json

Exit 0 if every check passes, 1 with a list of failures otherwise.

It never imports the generator. If it did, a wrong template would be checked
against itself and pass. Everything below is derived from the *rendered stem
text*, evaluated in exact Fractions so nothing turns on floating point:

  * the exhaustive two-answer sweep — a number stem is solved by substituting
    every value in 0..2000, a sign stem by trying every sign (or every one of
    the 16 sign pairs). Exactly one must work, it must be the key, and no
    printed distractor may be among the solutions. This is what catches the
    `2 ? 2 = 4` family, where two signs both make the sum true;
  * distractor liveness, the band-2 fault this pack was asked to avoid: every
    number distractor must be a positive whole number, within reach of the key,
    carrying a misconception. The count of items whose distractors all sit on
    one side of the key is reported rather than hidden;
  * band 2 must be absent, answer positions neither clustered nor cyclic nor in
    a run of four, no duplicate stems or refs, typed questions carrying an
    answer and no options, and every explanation stating its own answer.
"""
import collections
import itertools
import json
import re
import sys
from fractions import Fraction

PACK = sys.argv[1]
qs = json.load(open(PACK))["questions"]
fail, notes = [], []

SIGNS = {"+": "+", "−": "-", "×": "*", "÷": "/"}


def evaluate(expr):
    """Exact value of an arithmetic expression, or None if it is undefined."""
    e = expr
    for uni, ascii_ in SIGNS.items():
        e = e.replace(uni, ascii_)
    e = re.sub(r"\d+", r"Fraction(\g<0>)", e)
    try:
        return eval(e, {"__builtins__": {}}, {"Fraction": Fraction})
    except ZeroDivisionError:
        return None


def holds(stem):
    lhs, rhs = stem.split("=")
    a, b = evaluate(lhs), evaluate(rhs)
    return a is not None and b is not None and a == b


CANDIDATES = range(0, 2001)

positions, mcq_count = [], 0
stems = collections.Counter()
refs = []
one_sided = 0

for q in qs:
    tag = q.get("ref", "?")
    stem = q["stem"]
    stems[stem] += 1
    refs.append(tag)
    n_marks = stem.count("?")

    if q["kind"] == "numeric":
        if "options" in q:
            fail.append(f"{tag}: typed question carries options")
        key = q.get("answer")
        if not isinstance(key, int):
            fail.append(f"{tag}: typed answer {key!r} is not a number")
            continue
        opts, texts = [], []
    else:
        opts = q["options"]
        texts = [o["text"] for o in opts]
        if len(set(texts)) != len(texts):
            fail.append(f"{tag}: repeated option text")
        correct = [o for o in opts if o.get("correct")]
        if len(correct) != 1:
            fail.append(f"{tag}: {len(correct)} options marked correct")
            continue
        key = correct[0]["text"]
        positions.append(texts.index(key))
        mcq_count += 1

    if q["question_type"] == "missing-operator":
        # exhaustive sweep over every sign (or pair of signs) that could go in
        combos = list(itertools.product(SIGNS, repeat=n_marks))
        works = []
        for combo in combos:
            filled = stem
            for sign in combo:
                filled = filled.replace("?", sign, 1)
            if holds(filled):
                works.append(" then ".join(combo) if n_marks > 1 else combo[0])
        if len(works) != 1:
            fail.append(f"{tag}: {stem!r} is satisfied by {len(works)} sign choices: {works}")
        elif works[0] != key:
            fail.append(f"{tag}: key {key!r} but the sum only works with {works[0]!r}")
        for o in opts:
            if not o.get("correct") and o["text"] in works:
                fail.append(f"{tag}: distractor {o['text']!r} also makes the sum true")
    else:
        if n_marks != 1:
            fail.append(f"{tag}: {n_marks} question marks in a number item")
            continue
        sols = [v for v in CANDIDATES if holds(stem.replace("?", str(v)))]
        if len(sols) != 1:
            fail.append(f"{tag}: {stem!r} has {len(sols)} solutions in 0..2000: {sols[:6]}")
            continue
        if sols[0] != int(key):
            fail.append(f"{tag}: key {key} but the sum solves to {sols[0]}")
        # exhaustive two-answer sweep across the printed options
        for o in opts:
            if not o.get("correct") and holds(stem.replace("?", o["text"])):
                fail.append(f"{tag}: distractor {o['text']} also solves the sum")
        # distractor liveness — the band-2 fault this pack was asked to avoid
        if opts:
            k = int(key)
            vals = [int(o["text"]) for o in opts if not o.get("correct")]
            for v in vals:
                if v <= 0:
                    fail.append(f"{tag}: distractor {v} is not a positive whole number")
                if v > max(k * 6, k + 60):
                    fail.append(f"{tag}: distractor {v} is out of reach of key {k}")
                if not any(o.get("misconception") for o in opts
                           if o["text"] == str(v)):
                    fail.append(f"{tag}: distractor {v} carries no misconception")
            if vals and (all(v < k for v in vals) or all(v > k for v in vals)):
                one_sided += 1

    if str(key) not in q["explanation"]:
        fail.append(f"{tag}: explanation does not state the answer {key}")
    if q["difficulty"] == 2:
        fail.append(f"{tag}: band 2 is excluded from this pack")

for s, n in stems.items():
    if n > 1:
        fail.append(f"duplicate stem x{n}: {s!r}")
if len(set(refs)) != len(refs):
    fail.append("duplicate refs")

dist = collections.Counter(positions)
run, longest = 1, 1
for a, b in zip(positions, positions[1:]):
    run = run + 1 if a == b else 1
    longest = max(longest, run)
cyclic = next((p for p in (2, 3, 4, 5)
               if all(positions[i] == positions[i % p] for i in range(len(positions)))), 0)
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
print(f"answer positions (0-indexed, {mcq_count} mcqs): {dict(sorted(dist.items()))}"
      f"  longest run {longest}  cyclic {cyclic or 'none'}")
print(f"difficulty: {dict(sorted(collections.Counter(q['difficulty'] for q in qs).items()))}")
print(f"question types: {dict(collections.Counter(q['question_type'] for q in qs))}")
print(f"unique stems: {len(stems)} / {len(qs)}")
print(f"number items whose distractors all sit on one side of the key: {one_sided}")
mis = collections.Counter(o.get("misconception") for q in qs
                          for o in q.get("options", []) if not o.get("correct"))
print("distractor misconceptions:", dict(mis))

if fail:
    print(f"\nFAIL ({len(fail)}):")
    for f in fail[:40]:
        print("  -", f)
    sys.exit(1)
print("\nALL CHECKS PASS")
