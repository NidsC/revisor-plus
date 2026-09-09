#!/usr/bin/env python3
"""
Independent checks on the Triplet Rules pack (contrib_prash_vr_10.json).

    python3 elevenplus_data/check_triplet_rules.py elevenplus_data/contrib_prash_vr_10.json

Exit 0 if every check passes, 1 with a list of failures otherwise.

It never imports the generator. If it did, a wrong rule would be checked
against itself and pass. Everything below is derived from the *rendered stem
text* — the printed triples are parsed back out of it and the rule is refitted
from them — in exact Fractions, so nothing turns on floating point.

  * the exhaustive two-answer sweep. The declared rule space, which the group
    instruction states to the pupil, is "work the third number out from the
    first two by adding, subtracting, multiplying, halving or doubling":
    c = p·a + q·b + r, or c = a·b + r. For a find-the-rule item the checker
    fits the linear family EXACTLY, by elimination over Fractions on three of
    the four printed triples and then verifying against the fourth. Four
    triples over-determine three unknowns, so a linear fit that survives is
    the only one over ALL rationals — not merely the only one on a sampled
    grid. The product family has a single parameter and is scanned directly.
    Whichever families fit are then asked what they put at the blank; the set
    of positive whole answers must have exactly one member, it must be the
    key, and no printed distractor may be in it. A parameter-grid sweep runs
    alongside the exact fit and must agree with it — two ways of answering the
    same question, so an error in either shows up as a disagreement.
  * for an apply-the-rule item the rule is stated in words, so the checker
    parses the stated sentence, confirms the worked example printed in the
    same stem actually satisfies it, and only then solves the blank.
  * distractor liveness: every distractor must be a positive whole number
    within reach of the key. The number carrying no misconception slug is
    counted and reported rather than hidden.
  * only bands 3 and 5 may appear, band 5's blank is never the last number,
    answer positions neither clustered nor cyclic nor in a run of four, no
    duplicate stems or refs, typed questions carrying an answer and no
    options, and every explanation stating its own answer.
"""
import collections
import json
import re
import sys
from fractions import Fraction as F

PACK = sys.argv[1]
pack = json.load(open(PACK))
qs = pack["questions"]
fail = []

TRIPLE = re.compile(r"\((\-?\d+|\?), (\-?\d+|\?), (\-?\d+|\?)\)")
FIND = re.compile(r"^Each of these number triples follows the same rule: (.+)\. "
                  r"Using the same rule, what is the missing number in (\(.+\))\?$")
APPLY = re.compile(r"^In each triple of numbers, (.+)\. For example, (\(.+\)) follows "
                   r"this rule\. Using the same rule, what is the missing number in "
                   r"(\(.+\))\?$")

# The stated rules, read straight off the printed sentence. Each maps to
# (p, q, r) for c = p*a + q*b + r, or ("product", r) for c = a*b + r.
STATEMENTS = [
    (r"^the third number is the first number added to the second$",
     lambda m: (F(1), F(1), F(0))),
    (r"^the third number is the first number multiplied by the second$",
     lambda m: ("product", F(0))),
    (r"^the third number is the second number taken away from the first$",
     lambda m: (F(1), F(-1), F(0))),
    (r"^the third number is halfway between the first two numbers$",
     lambda m: (F(1, 2), F(1, 2), F(0))),
    (r"^the third number is double the first number, with the second taken away$",
     lambda m: (F(2), F(-1), F(0))),
    (r"^the third number is double the first number, added to the second$",
     lambda m: (F(2), F(1), F(0))),
    (r"^the third number is three times the first number, with the second taken away$",
     lambda m: (F(3), F(-1), F(0))),
    (r"^the third number is double what you get by taking the second number away from "
     r"the first$", lambda m: (F(2), F(-2), F(0))),
    (r"^the third number is the first two numbers added together, and then (\d+) more$",
     lambda m: (F(1), F(1), F(int(m.group(1))))),
    (r"^the third number is the first number multiplied by the second, with (\d+) taken "
     r"away$", lambda m: ("product", F(-int(m.group(1))))),
]
STATEMENTS = [(re.compile(p), f) for p, f in STATEMENTS]

GRID = [F(n, 2) for n in range(-6, 7)] + [F(3)]
RS = [F(r) for r in range(-12, 13)]


def parse_triples(text):
    out = []
    for m in TRIPLE.finditer(text):
        out.append(tuple(m.group(i) for i in (1, 2, 3)))
    return out


def blank_pos(triple):
    return "abc"[[i for i, v in enumerate(triple) if v == "?"][0]]


def solve_at(rule, pos, a, b, c):
    """What `rule` puts at `pos`, or None if that is not a positive whole
    number. `rule` is (p, q, r) or ("product", r)."""
    if rule[0] == "product":
        r = rule[1]
        if pos == "c":
            v = F(a) * b + r
        else:
            other = b if pos == "a" else a
            if other == 0:
                return None
            v = (F(c) - r) / other
    else:
        p, q, r = rule
        if pos == "c":
            v = p * a + q * b + r
        elif pos == "a":
            if p == 0:
                return None
            v = (F(c) - q * b - r) / p
        else:
            if q == 0:
                return None
            v = (F(c) - p * a - r) / q
    if v.denominator != 1 or v <= 0:
        return None
    return int(v)


def fits(rule, triples):
    return all(solve_at(rule, "c", a, b, 0) == c for a, b, c in triples)


def exact_linear_fit(triples):
    """The unique (p, q, r) fitting every triple, or None.

    Elimination over Fractions on the first three, then verified against the
    rest. With four triples the system is over-determined, so a fit that
    survives is the only linear rule over ALL rationals — the grid sweep below
    is a cross-check on this, not the source of the guarantee.
    """
    m = [[F(a), F(b), F(1), F(c)] for a, b, c in triples[:3]]
    for col in range(3):
        pivot = next((i for i in range(col, 3) if m[i][col] != 0), None)
        if pivot is None:
            return None
        m[col], m[pivot] = m[pivot], m[col]
        pv = m[col][col]
        m[col] = [x / pv for x in m[col]]
        for i in range(3):
            if i != col and m[i][col] != 0:
                f = m[i][col]
                m[i] = [x - f * y for x, y in zip(m[i], m[col])]
    rule = (m[0][3], m[1][3], m[2][3])
    return rule if fits(rule, triples) else None


def answer_set(triples, pos, a, b, c):
    """Every positive whole answer at `pos` reachable by a rule of the declared
    space that fits all the printed triples."""
    out = set()
    lin = exact_linear_fit(triples)
    if lin is not None:
        v = solve_at(lin, pos, a, b, c)
        if v is not None:
            out.add(v)
    r0 = F(triples[0][2] - triples[0][0] * triples[0][1])
    if fits(("product", r0), triples):
        v = solve_at(("product", r0), pos, a, b, c)
        if v is not None:
            out.add(v)
    return out


def grid_answer_set(triples, pos, a, b, c):
    """The same question answered by brute force over a parameter grid, as a
    cross-check on the exact fit above."""
    out = set()
    for p in GRID:
        for q in GRID:
            for r in RS:
                if fits((p, q, r), triples):
                    v = solve_at((p, q, r), pos, a, b, c)
                    if v is not None:
                        out.add(v)
    for r in RS:
        if fits(("product", r), triples):
            v = solve_at(("product", r), pos, a, b, c)
            if v is not None:
                out.add(v)
    return out


positions, mcq_count = [], 0
stems = collections.Counter()
refs = []
variants = collections.Counter()
untagged = 0

for q in qs:
    tag = q.get("ref", "?")
    stem = q["stem"]
    stems[stem] += 1
    refs.append(tag)

    if q["kind"] in ("numeric", "short_text"):
        if "options" in q:
            fail.append(f"{tag}: typed question carries options")
        key = q.get("answer")
        if not isinstance(key, int):
            fail.append(f"{tag}: typed answer {key!r} is not a number")
            continue
        opts = []
    else:
        opts = q["options"]
        texts = [o["text"] for o in opts]
        if len(set(texts)) != len(texts):
            fail.append(f"{tag}: repeated option text")
        correct = [o for o in opts if o.get("correct")]
        if len(correct) != 1:
            fail.append(f"{tag}: {len(correct)} options marked correct")
            continue
        key = int(correct[0]["text"])
        positions.append(texts.index(correct[0]["text"]))
        mcq_count += 1
    wrong = [int(o["text"]) for o in opts if not o.get("correct")]

    mf, ma = FIND.match(stem), APPLY.match(stem)
    if mf:
        variants["find-the-rule"] += 1
        examples = [tuple(int(v) for v in t) for t in parse_triples(mf.group(1))]
        query = parse_triples(mf.group(2))[0]
        if len(examples) != 4:
            fail.append(f"{tag}: {len(examples)} example triples printed, not 4 — with "
                        f"fewer the linear family is not over-determined")
            continue
        pos = blank_pos(query)
        a, b, c = (0 if v == "?" else int(v) for v in query)
        if tuple(0 if v == "?" else int(v) for v in query) in [
                tuple(e) for e in examples]:
            fail.append(f"{tag}: the query triple is one of the examples")
        answers = answer_set(examples, pos, a, b, c)
        grid = grid_answer_set(examples, pos, a, b, c)
        if answers != grid:
            fail.append(f"{tag}: exact fit gives {sorted(answers)} but the grid sweep "
                        f"gives {sorted(grid)}")
        if len(answers) != 1:
            fail.append(f"{tag}: the printed triples admit {len(answers)} answers at the "
                        f"blank: {sorted(answers)}")
            continue
        if key not in answers:
            fail.append(f"{tag}: key {key} but the triples give {sorted(answers)}")
        for w in wrong:
            if w in answers:
                fail.append(f"{tag}: distractor {w} is also an answer to the triples")
        if q["difficulty"] == 5 and pos == "c":
            fail.append(f"{tag}: band 5 must not blank the last number")
    elif ma:
        variants["apply-the-rule"] += 1
        statement, demo_s, query_s = ma.group(1), ma.group(2), ma.group(3)
        rule = None
        for pat, make in STATEMENTS:
            m = pat.match(statement)
            if m:
                rule = make(m)
                break
        if rule is None:
            fail.append(f"{tag}: the stated rule {statement!r} is not one this pack declares")
            continue
        demo = tuple(int(v) for v in parse_triples(demo_s)[0])
        if not fits(rule, [demo]):
            fail.append(f"{tag}: the worked example {demo} does not follow the rule the "
                        f"same stem states")
        if demo[0] == demo[1]:
            fail.append(f"{tag}: the worked example {demo} has two equal inputs, so it "
                        f"demonstrates more than one rule")
        query = parse_triples(query_s)[0]
        pos = blank_pos(query)
        a, b, c = (0 if v == "?" else int(v) for v in query)
        answer = solve_at(rule, pos, a, b, c)
        if answer is None:
            fail.append(f"{tag}: the stated rule gives no positive whole answer here")
            continue
        if key != answer:
            fail.append(f"{tag}: key {key} but the stated rule gives {answer}")
        for w in wrong:
            if w == answer:
                fail.append(f"{tag}: distractor {w} is also the answer")
        if pos == "c":
            fail.append(f"{tag}: an apply-the-rule item must not blank the last number, "
                        f"or the rule needs no turning round")
    else:
        fail.append(f"{tag}: stem is not in this pack's printed shape: {stem!r}")
        continue

    for o in opts:
        if o.get("correct"):
            continue
        v = int(o["text"])
        if v <= 0:
            fail.append(f"{tag}: distractor {v} is not a positive whole number")
        if v > max(key * 6, key + 60):
            fail.append(f"{tag}: distractor {v} is out of reach of key {key}")
        if not o.get("misconception"):
            untagged += 1

    if str(key) not in q["explanation"]:
        fail.append(f"{tag}: explanation does not state the answer {key}")
    if q["difficulty"] not in (3, 5):
        fail.append(f"{tag}: band {q['difficulty']} is excluded from this pack")
    if q["subtopic"] != "Triplet Rules":
        fail.append(f"{tag}: wrong subtopic {q['subtopic']!r}")

for s, n in stems.items():
    if n > 1:
        fail.append(f"duplicate stem x{n}: {s!r}")
if len(set(refs)) != len(refs):
    fail.append("duplicate refs")

group_refs = {g["group_ref"] for g in pack.get("groups", [])}
for q in qs:
    if q.get("group_ref") not in group_refs:
        fail.append(f"{q.get('ref')}: group_ref {q.get('group_ref')!r} is not declared")

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
print(f"variants solved from the stem: {dict(variants)}")
print(f"answer positions (0-indexed, {mcq_count} mcqs): {dict(sorted(dist.items()))}"
      f"  longest run {longest}  cyclic {cyclic or 'none'}")
print(f"difficulty: {dict(sorted(collections.Counter(q['difficulty'] for q in qs).items()))}")
print(f"question types: {dict(collections.Counter(q['question_type'] for q in qs))}")
print(f"unique stems: {len(stems)} / {len(qs)}")
print(f"distractors carrying no misconception slug: {untagged}")
mis = collections.Counter(o.get("misconception") for q in qs
                          for o in q.get("options", []) if not o.get("correct"))
print("distractor misconceptions:", dict(mis))

if fail:
    print(f"\nFAIL ({len(fail)}):")
    for f in fail[:40]:
        print("  -", f)
    sys.exit(1)
print("\nALL CHECKS PASS")
