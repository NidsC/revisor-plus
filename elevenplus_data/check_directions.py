#!/usr/bin/env python3
"""
Independent checks on the Directions pack (contrib_prash_vr_11.json).

    python3 elevenplus_data/check_directions.py elevenplus_data/contrib_prash_vr_11.json

Exit 0 if every check passes, 1 with a list of failures otherwise.

It never imports the generator. If it did, a wrong layout would be checked
against itself and pass — and this subtopic's two known faults are both
disagreements between what the stem TELLS the pupil and what the generator
held internally, which only a checker reading the stem can catch. Everything
below is re-derived from the *rendered stem text*: the turns are re-applied
from the printed angles, and every layout is re-plotted from the printed
statements.

  * the exhaustive two-answer sweep. The answer space here is closed and small
    — the eight compass points — so the sweep is over the whole of it, not a
    sample. For a turns item every one of the eight is tested as the final
    facing and exactly one must survive; for a grid item every one is tested
    against the plotted vector and exactly one must match. The key must be
    that one, and no printed distractor may be in the surviving set.
  * exactness, which is this subtopic's real ambiguity risk. A vector is one
    of the eight points only if it lies on an axis or a true diagonal —
    "2 east, 3 north" is about 56 degrees from north, neither North-East nor
    due East. `compass_of_vector` here is an exact INTEGER test with no
    tolerance on an angle, so there is no boundary case to round wrong, and a
    question whose asked-about pair is not exactly aligned fails rather than
    being rounded to the closest point.
  * derivability, the other real risk. A statement giving only a direction
    fixes one axis and leaves the other free, so an indirect pair's bearing
    would depend on lengths the pupil was never told. Every printed statement
    must give a distance, name a point already placed, and introduce a new
    one — which is what makes the layout forced by the stem rather than by the
    generator's hidden state.
  * the band labels are checked, not trusted: band 1 must be absent; a
    compass-bearing item's resultant must differ from every leg, so it cannot
    be answered by reading one statement; a band-4 relative-position layout
    must be a pure star and a band-5 one must not be; and the pair asked about
    must never be one a statement gave directly.
  * plus: answer positions neither clustered nor cyclic nor in a run of four,
    every option one of the eight compass points, no duplicate stems or refs,
    and every explanation stating its own answer.
"""
import collections
import json
import re
import sys

PACK = sys.argv[1]
pack = json.load(open(PACK))
qs = pack["questions"]
fail = []

POINTS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
WORDS = {"N": "North", "NE": "North-East", "E": "East", "SE": "South-East",
         "S": "South", "SW": "South-West", "W": "West", "NW": "North-West"}
CODE = {v: k for k, v in WORDS.items()}
STEP = {"N": (0, 1), "NE": (1, 1), "E": (1, 0), "SE": (1, -1),
        "S": (0, -1), "SW": (-1, -1), "W": (-1, 0), "NW": (-1, 1)}

TURNS = re.compile(r"^(\w+) is facing ([\w\-]+)\. \1 (turns .+)\. "
                   r"Which direction is \1 facing now\?$")
ONE_TURN = re.compile(r"^turns (\d+)° (clockwise|anticlockwise)$")
GRID = re.compile(r"^On a square grid, (.+) Which direction is (\w+) from (\w+)\?$")
STATEMENT = re.compile(r"(\w+) is (\d+) squares ([\w\-]+) of (\w+)\.")


def compass_of_vector(dx, dy):
    """The exact compass point of an (east, north) integer vector, or None.

    Exact integer arithmetic, no angle and no tolerance: a vector is one of the
    eight points only on an axis or a true diagonal, and anything else has no
    single correct answer.
    """
    if dx == 0 and dy == 0:
        return None
    if dx == 0:
        return "N" if dy > 0 else "S"
    if dy == 0:
        return "E" if dx > 0 else "W"
    if abs(dx) != abs(dy):
        return None
    return {(1, 1): "NE", (1, -1): "SE", (-1, -1): "SW", (-1, 1): "NW"}[
        (1 if dx > 0 else -1, 1 if dy > 0 else -1)]


positions = []
stems = collections.Counter()
refs = []
variants = collections.Counter()
untagged = 0

for q in qs:
    tag = q.get("ref", "?")
    stem = q["stem"]
    stems[stem] += 1
    refs.append(tag)

    opts = q.get("options")
    if not opts:
        fail.append(f"{tag}: this pack is multiple choice throughout, but it has no options")
        continue
    texts = [o["text"] for o in opts]
    if len(set(texts)) != len(texts):
        fail.append(f"{tag}: repeated option text")
    for t in texts:
        if t not in CODE:
            fail.append(f"{tag}: option {t!r} is not one of the eight compass points")
    correct = [o for o in opts if o.get("correct")]
    if len(correct) != 1:
        fail.append(f"{tag}: {len(correct)} options marked correct")
        continue
    key = correct[0]["text"]
    positions.append(texts.index(key))
    wrong = [o["text"] for o in opts if not o.get("correct")]
    untagged += sum(1 for o in opts if not o.get("correct") and not o.get("misconception"))

    mt, mg = TURNS.match(stem), GRID.match(stem)
    if mt:
        variants["turns-and-facing"] += 1
        start_word, turn_text = mt.group(2), mt.group(3)
        if start_word not in CODE:
            fail.append(f"{tag}: {start_word!r} is not a compass point")
            continue
        moves = []
        for chunk in turn_text.split(", then "):
            m = ONE_TURN.match(chunk)
            if not m or int(m.group(1)) % 45:
                fail.append(f"{tag}: {chunk!r} is not a whole number of eighth-turns")
                moves = None
                break
            moves.append((int(m.group(1)), m.group(2) == "clockwise"))
        if moves is None:
            continue
        # Exhaustive sweep over the whole answer space: all eight points.
        survivors = []
        for candidate in POINTS:
            i = POINTS.index(CODE[start_word])
            for angle, cw in moves:
                i = (i + (angle // 45) * (1 if cw else -1)) % 8
            if POINTS[i] == candidate:
                survivors.append(candidate)
        if len(survivors) != 1:
            fail.append(f"{tag}: {len(survivors)} of the eight points survive the turns")
            continue
        answer = WORDS[survivors[0]]
        if key != answer:
            fail.append(f"{tag}: key {key!r} but the turns end facing {answer!r}")
        for w in wrong:
            if w == answer:
                fail.append(f"{tag}: distractor {w!r} is also the answer")
        if q["question_type"] != "turns-and-facing":
            fail.append(f"{tag}: a turns stem filed as {q['question_type']!r}")
    elif mg:
        body, asked_from, asked_of = mg.group(1), mg.group(2), mg.group(3)
        variants[q["question_type"]] += 1
        statements = STATEMENT.findall(body)
        if not statements:
            fail.append(f"{tag}: no plottable statements in {body!r}")
            continue
        if len(statements) != body.count(" is "):
            fail.append(f"{tag}: a statement in {body!r} does not give a distance")
            continue
        coords, parent_of, legs = {}, {}, []
        ok = True
        for child, dist, word, parent in statements:
            if word not in CODE:
                fail.append(f"{tag}: {word!r} is not a compass point")
                ok = False
                break
            if not coords:
                coords[parent] = (0, 0)
            if parent not in coords:
                fail.append(f"{tag}: {parent} is used before it is placed, so the layout "
                            f"is not forced by the stem")
                ok = False
                break
            if child in coords:
                fail.append(f"{tag}: {child} is placed twice")
                ok = False
                break
            d, n = CODE[word], int(dist)
            coords[child] = (coords[parent][0] + STEP[d][0] * n,
                             coords[parent][1] + STEP[d][1] * n)
            parent_of[child] = parent
            legs.append(d)
        if not ok:
            continue
        for name in (asked_from, asked_of):
            if name not in coords:
                fail.append(f"{tag}: {name} is asked about but never placed")
                ok = False
        if not ok:
            continue
        if parent_of.get(asked_from) == asked_of or parent_of.get(asked_of) == asked_from:
            fail.append(f"{tag}: {asked_from} from {asked_of} was stated directly")
        dx = coords[asked_from][0] - coords[asked_of][0]
        dy = coords[asked_from][1] - coords[asked_of][1]
        # Exhaustive sweep over the whole answer space: all eight points.
        exact = compass_of_vector(dx, dy)
        survivors = [c for c in POINTS if c == exact]
        if len(survivors) != 1:
            fail.append(f"{tag}: the vector ({dx}, {dy}) does not point exactly at one of "
                        f"the eight compass points")
            continue
        answer = WORDS[survivors[0]]
        if key != answer:
            fail.append(f"{tag}: key {key!r} but {asked_from} is {answer!r} of {asked_of}")
        for w in wrong:
            if w == answer:
                fail.append(f"{tag}: distractor {w!r} is also the answer")
        qt, band = q["question_type"], q["difficulty"]
        if qt == "compass-bearing":
            # A chain: each statement hangs off the one before it.
            if any(statements[i][3] != statements[i - 1][0]
                   for i in range(1, len(statements))):
                fail.append(f"{tag}: a compass-bearing walk must be a chain of legs")
            if CODE[key] in legs or compass_of_vector(dx, dy) in legs:
                fail.append(f"{tag}: the resultant is one of the legs, so the walk can be "
                            f"answered from a single statement")
        elif qt == "relative-position":
            hub = statements[0][3]
            star = all(p == hub for p in parent_of.values())
            if band == 4 and not star:
                fail.append(f"{tag}: band 4 relative-position must hang every point off "
                            f"the hub")
            if band == 5 and star:
                fail.append(f"{tag}: band 5 relative-position is a pure star, which is the "
                            f"band-4 shape whatever the label says")
        else:
            fail.append(f"{tag}: a grid stem filed as {qt!r}")
    else:
        fail.append(f"{tag}: stem is not in this pack's printed shape: {stem!r}")
        continue

    if key not in q["explanation"]:
        fail.append(f"{tag}: explanation does not state the answer {key}")
    if q["difficulty"] == 1:
        fail.append(f"{tag}: band 1 is excluded from this pack")
    if q["subtopic"] != "Directions":
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
print(f"answer positions (0-indexed, {len(positions)} mcqs): {dict(sorted(dist.items()))}"
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
