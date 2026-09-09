#!/usr/bin/env python3
"""
Independent checks on the Scenario Deduction pack (contrib_prash_vr_18.json).

    python3 elevenplus_data/check_scenario_deduction.py elevenplus_data/contrib_prash_vr_18.json

Exit 0 if every check passes, 1 with a list of failures otherwise.

It never imports the generator. Every puzzle is re-solved by brute force from
the printed clues: every ordering of the people is generated and tested against
every clue, and exactly one must survive. That is the only check that matters
for a logic item — the classic failure of one is an under-constrained world
where the "right" answer is only right in the ordering the author had in mind,
and a checker that read the generator's stored ordering would confirm it
happily.

  * EXHAUSTIVE, NOT CLEVER. n <= 5, so all n! orderings are enumerated. No
    constraint propagation, no solver, nothing that could share a bug with the
    thing being checked.
  * CLUES ARE READ AS WRITTEN, NOT AS INTENDED. "X finishes ahead of Y" is
    tested as "X is somewhere before Y", not as "X is immediately before Y",
    because that is what the sentence says. If a puzzle needed the stronger
    reading to have one answer, it would fail here — and it should, because a
    pupil reading it the weak way would be right to find two answers.
  * THE UNMENTIONED PERSON. From band 3 up, one person appears in no clue and
    is recoverable only by elimination. The checker builds the cast from the
    clues AND the options, then requires it to match the count the stem states
    ("5 friends"), so a puzzle whose unclued person is not offered as an option
    — which would be unanswerable — fails rather than passing quietly.
  * THE BAND LABEL IS CHECKED AGAINST THE SHAPE: 3 people at band 1, 4 at bands
    2-3, 5 at band 4; no distance clue at bands 1-2 and exactly one above.
    **Band 5 must be absent** — it is the same population as band 4 in the
    generator (five people, one merge, same 30 structures), and shipping both
    labels would tell the adaptive engine a pupil had moved up a band when
    nothing about the question changed.
  * NAME-BLIND DUPLICATES. Two questions differing only in their names are one
    puzzle wearing two coats, so the checker compares (framing, cast size,
    where in the order the unclued person sits, which place is asked) and
    rejects a repeat. It derives the merge position from the clues rather than
    reading the printed distance, which is always 2 and distinguishes nothing.
  * plus: every option a person named in the same question, the key never
    tagged with a misconception, unique stems and refs, explanations stating
    the full order and the answer, and answer positions neither clustered nor
    cyclic nor in a run of four.

No dictionary and no third-party module: this checker runs anywhere.
"""
import collections
import itertools
import json
import re
import sys

PACK = sys.argv[1] if len(sys.argv) > 1 else "elevenplus_data/contrib_prash_vr_18.json"
pack = json.load(open(PACK))
qs = pack["questions"]
fail = []

ORDINALS = ["first", "second", "third", "fourth", "fifth"]
PEOPLE_PER_BAND = {1: 3, 2: 4, 3: 4, 4: 5}
MERGES_PER_BAND = {1: 0, 2: 0, 3: 1, 4: 1}

RACE = re.compile(r"^(\d+) friends run a race\. (.+) Who finishes (\w+)\?$")
SEATS = re.compile(r"^(\d+) friends sit in a row of seats numbered 1 \(leftmost\) to "
                   r"(\d+) \(rightmost\)\. (.+) Who is sitting in seat (\w+) from the left\?$")

CLUES = [
    # (pattern, kind) — kind says how the clue constrains two places.
    (re.compile(r"^(\w+) finishes (\d+) places ahead of (\w+)$"), "distance"),
    (re.compile(r"^(\w+) finishes ahead of (\w+)$"), "before"),
    (re.compile(r"^(\w+) finishes last$"), "last"),
    (re.compile(r"^(\w+) sits (\d+) seats to the left of (\w+)$"), "distance"),
    (re.compile(r"^(\w+) sits immediately to the left of (\w+)$"), "adjacent"),
    (re.compile(r"^(\w+) sits in seat (\d+)$"), "seat"),
]


def parse_clues(blob):
    """Every printed clue as (kind, args), or None if one does not parse."""
    out = []
    for sentence in [s.strip() for s in blob.split(". ") if s.strip()]:
        sentence = sentence.rstrip(".")
        for pattern, kind in CLUES:
            m = pattern.match(sentence)
            if m:
                out.append((kind, m.groups()))
                break
        else:
            return None
    return out


def satisfies(order, clues, n):
    """Does this ordering obey every printed clue, read literally?"""
    at = {name: i for i, name in enumerate(order)}
    for kind, args in clues:
        if kind == "before":
            a, b = args
            if not (at[a] < at[b]):
                return False
        elif kind == "adjacent":
            a, b = args
            if at[b] != at[a] + 1:
                return False
        elif kind == "distance":
            a, k, b = args
            if at[b] != at[a] + int(k):
                return False
        elif kind == "last":
            if at[args[0]] != n - 1:
                return False
        elif kind == "seat":
            a, seat = args
            if at[a] != int(seat) - 1:
                return False
    return True


positions, refs, stems = [], [], collections.Counter()
structures = collections.Counter()
solved = 0

for q in qs:
    tag = q.get("ref", "?")
    stem = q["stem"]
    stems[stem] += 1
    refs.append(tag)

    if q.get("subtopic") != "Scenario Deduction":
        fail.append(f"{tag}: wrong subtopic {q.get('subtopic')!r}")
    band = q.get("difficulty")
    if band == 5:
        fail.append(f"{tag}: band 5 is excluded from this pack — it is the same puzzle "
                    f"population as band 4")
        continue
    if band not in PEOPLE_PER_BAND:
        fail.append(f"{tag}: band {band!r}")
        continue
    if q.get("kind") != "mcq":
        fail.append(f"{tag}: kind {q.get('kind')!r}; this pack is mcq throughout")
        continue

    race, seats = RACE.match(stem), SEATS.match(stem)
    if race:
        n, blob, ordinal = int(race.group(1)), race.group(2), race.group(3)
        framing, expected_type = "race", "ranking"
    elif seats:
        n, n2, blob, ordinal = (int(seats.group(1)), int(seats.group(2)),
                                seats.group(3), seats.group(4))
        framing, expected_type = "seating", "seating-order"
        if n != n2:
            fail.append(f"{tag}: stem says {n} friends but numbers seats to {n2}")
    else:
        fail.append(f"{tag}: stem is not in this pack's printed shape: {stem!r}")
        continue

    if q.get("question_type") != expected_type:
        fail.append(f"{tag}: {framing} stem filed as {q.get('question_type')!r}")

    clues = parse_clues(blob)
    if clues is None:
        fail.append(f"{tag}: a clue is not in a shape this checker can read: {blob!r}")
        continue

    opts = q.get("options") or []
    texts = [o["text"] for o in opts]
    if len(set(texts)) != len(texts):
        fail.append(f"{tag}: repeated option text")
    correct = [o for o in opts if o.get("correct")]
    if len(correct) != 1:
        fail.append(f"{tag}: {len(correct)} options marked correct")
        continue
    if correct[0].get("misconception"):
        fail.append(f"{tag}: the key carries a misconception slug")
    key = correct[0]["text"]
    positions.append(texts.index(key))

    # The cast comes from the clues AND the options: from band 3 up one person
    # appears in no clue and is recoverable only by elimination.
    named = {a for kind, args in clues for a in args if a.isalpha()}
    cast = sorted(named | set(texts))
    if len(cast) != n:
        fail.append(f"{tag}: stem says {n} friends but the clues and options name "
                    f"{len(cast)}: {cast} — an unclued person who is not offered as an "
                    f"option makes the question unanswerable")
        continue
    if len(cast) != PEOPLE_PER_BAND[band]:
        fail.append(f"{tag}: band {band} should have {PEOPLE_PER_BAND[band]} people, "
                    f"not {len(cast)}")
    merges = sum(1 for kind, _ in clues if kind == "distance")
    if merges != MERGES_PER_BAND[band]:
        fail.append(f"{tag}: band {band} should have {MERGES_PER_BAND[band]} distance "
                    f"clue(s), not {merges}")

    # Exhaustive: every ordering, tested against every clue as written.
    valid = [p for p in itertools.permutations(cast) if satisfies(p, clues, n)]
    if len(valid) != 1:
        fail.append(f"{tag}: {len(valid)} orderings satisfy the printed clues "
                    f"({[', '.join(v) for v in valid[:3]]}), not exactly one")
        continue
    solved += 1
    order = valid[0]

    if ordinal not in ORDINALS[:n]:
        fail.append(f"{tag}: asks for {ordinal!r} of {n}")
        continue
    answer = order[ORDINALS.index(ordinal)]
    if key != answer:
        fail.append(f"{tag}: key {key!r} but the clues give {answer!r} as {ordinal}")
    for w in texts:
        if w not in cast:
            fail.append(f"{tag}: option {w!r} is not one of the people in this question")

    exp = q.get("explanation", "")
    if ", ".join(order) not in exp:
        fail.append(f"{tag}: explanation does not state the order it derives")
    if answer not in exp:
        fail.append(f"{tag}: explanation does not name the answer {answer}")

    # What makes two of these the same puzzle: the framing, the cast size, WHERE
    # in the order the unclued person sits (which is what the merged distance
    # clue actually varies — the printed distance is always 2 and says nothing),
    # and which place is asked. Names are cosmetic.
    unclued = [i for i, name in enumerate(order) if name not in named]
    structures[(framing, n, tuple(unclued), ORDINALS.index(ordinal))] += 1

for s, n in stems.items():
    if n > 1:
        fail.append(f"duplicate stem x{n}: {s!r}")
for st, c in structures.items():
    if c > 1:
        fail.append(f"structure {st} appears in {c} questions — the same puzzle with "
                    f"different names")
if len(set(refs)) != len(refs):
    fail.append("duplicate refs")

group_refs = {g["group_ref"] for g in pack.get("groups", [])}
for q in qs:
    if q.get("group_ref") not in group_refs:
        fail.append(f"{q.get('ref')}: group_ref {q.get('group_ref')!r} is not declared")

# The worked example is solved like a question.
for g in pack.get("groups", []):
    ex = g.get("example", "")
    if not g.get("instruction") or not ex:
        fail.append(f"{g.get('group_ref')}: a group needs both an instruction and an example")
        continue
    m = RACE.match(ex.split("? ")[0] + "?")
    if not m:
        fail.append(f"{g.get('group_ref')}: example is not a solvable puzzle")
        continue
    n, clues, ordinal = int(m.group(1)), parse_clues(m.group(2)), m.group(3)
    cast = sorted({a for kind, args in clues for a in args if a.isalpha()})
    valid = [p for p in itertools.permutations(cast) if satisfies(p, clues, n)]
    if len(valid) != 1:
        fail.append(f"example: {len(valid)} orderings satisfy its clues")
    elif valid[0][ORDINALS.index(ordinal)] not in ex.split("? ")[1]:
        fail.append("example: the worked answer is not the one its clues give")
    if ex.split("? ")[0] + "?" in stems:
        fail.append("example is also a question in this pack")

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
    if c > expected * 1.7 or c < expected * 0.5:
        fail.append(f"answer position {pos}: {c} of {len(positions)} (expected ~{expected:.0f})")

print(f"pack: {PACK}")
print(f"questions: {len(qs)}   refs: {refs[0]}..{refs[-1]}")
print(f"question types: {dict(collections.Counter(q['question_type'] for q in qs))}")
print(f"difficulty: {dict(sorted(collections.Counter(q['difficulty'] for q in qs).items()))}"
      f"   (band 5 excluded by design)")
print(f"puzzles brute-forced to a unique ordering: {solved} / {len(qs)}")
print(f"distinct name-blind structures: {len(structures)} / {len(qs)}")
print(f"answer positions (0-indexed, {len(positions)} mcqs): {dict(sorted(dist.items()))}"
      f"  longest run {longest}  cyclic {cyclic or 'none'}")

if fail:
    print(f"\nFAIL ({len(fail)}):")
    for f in fail[:40]:
        print("  -", f)
    sys.exit(1)
print("\nALL CHECKS PASS")
