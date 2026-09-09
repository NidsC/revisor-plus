#!/usr/bin/env python3
"""
Builds elevenplus_data/contrib_prash_vr_11.json — 100 Directions questions.

    python3 elevenplus_data/generate_directions.py [OUTPUT.json]

The RNG is seeded, so re-running reproduces the committed pack byte for byte.
That is the point of keeping this file: the pack is checkable rather than
merely reviewable. Check what comes out with its companion,
`check_directions.py`, which re-plots every layout from the rendered stem and
re-derives every answer without importing anything here.

BAND 1 IS NOT GENERATED
-----------------------
`catalog/generators/verbal.py`'s Directions builds band 1 from one turn, and
its own parameters cap that band at **32 distinct questions**: 8 starting
directions x 2 angles (`_TURN_ANGLES_D1` is 90 and 180) x 2 turn directions.
A hundred-question pack cannot draw 20-odd band-1 items from a pool of 32
without near-repeats, and a band whose whole population a pupil can meet twice
in a term is not measuring much. So this pack starts at band 2, where two turns
from the full four-angle pool give 8 x 8 x 8 = 512.

The four bands here:

  band 2 — two turns to hold in mind at once.
  band 3 — three turns, or a two-leg walk whose resultant is asked for.
  band 4 — a three-leg walk, or a three-point layout where the pair asked about
           was never stated directly.
  band 5 — a four-point layout in which at least one point hangs off another
           spoke rather than off the hub, so the pair asked about can need two
           hops of plotting.

WHY EVERY QUESTION HAS EXACTLY ONE ANSWER
-----------------------------------------
Two failure modes, both inherited as warnings from the upstream generator's own
docstring, and both closed here by construction rather than by inspection.

1. A vector points at exactly one of the eight compass points only if it lies
   on an axis or on a true diagonal. "2 east, 3 north" is about 56 degrees from
   north — neither North-East nor due East — and rounding it to the closest
   point would invent an answer. `compass_of_vector` is an exact INTEGER test,
   never a tolerance on an angle, so there is no boundary case to round wrong.
   A layout with no exactly-aligned pair to ask about is discarded, not
   rounded.

2. A statement that gives only a direction ("R is North of Q") fixes one axis
   and says nothing about the other, so an indirect pair's bearing depends on
   leg lengths the pupil was never told. Every statement here states its
   distance, so a pupil could in principle plot every point exactly from what
   is printed — which is what makes the bearing a fact about the question
   rather than about the generator's hidden state.

Distances are in SQUARES on a square grid, never in kilometres. A diagonal leg
moves the same number of squares on both axes, which is a grid abstraction and
not real-world displacement; saying "8km North-West" would promise Euclidean
geometry the grid does not deliver, and the two disagree.

ANSWERS ARE MULTIPLE CHOICE THROUGHOUT
--------------------------------------
The answer is always one of the eight compass points — a closed set, which
elevenplus_data/CLAUDE.md's VR answer-format table maps to `mcq`. There is no
write-in here to route around: unlike a hidden word or a missing number, the
pupil is choosing from a set the question itself defines.

HOW DISTRACTORS STAY LIVE
-------------------------
Every distractor is the answer one named slip produces: turning one of the
turns the wrong way round, forgetting to turn at all, applying only some of the
turns and stopping, reading one statement of a layout and stopping, or
answering the reverse of the pair that was asked. Each carries the matching
misconception slug, and named slips are always offered before anything else, so
an untagged option only ever fills a gap the named ones could not.

Two slugs are capped at two options rather than one, because each names a
family of moves rather than a single one — "turned one of them the wrong way"
and "read one part and stopped" are both true of several different wrong
answers here, and each of those is separately live.

The compass points either side of the correct one are a real thing a pupil
writes — an eighth of a turn out — but no slug in taxonomy.json names that, so
they ship untagged rather than borrow one that does not describe the slip. A
leg's OPPOSITE direction is only offered where the question asks for its pair
the other way round; without that framing nothing would have prompted a pupil
to turn a statement round, and tagging it would claim a slip nobody made.
"""
import collections
import json
import os
import random
import sys

rng = random.Random(20260914)

POINTS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
WORDS = {"N": "North", "NE": "North-East", "E": "East", "SE": "South-East",
         "S": "South", "SW": "South-West", "W": "West", "NW": "North-West"}
STEP = {"N": (0, 1), "NE": (1, 1), "E": (1, 0), "SE": (1, -1),
        "S": (0, -1), "SW": (-1, -1), "W": (-1, 0), "NW": (-1, 1)}
OPPOSITE = {d: POINTS[(i + 4) % 8] for i, d in enumerate(POINTS)}

PEOPLE = ["Priya", "Marcus", "Aisha", "Leo", "Nadia", "Tomas", "Beth", "Omar",
          "Freya", "Idris", "Clara", "Jonah"]
PLACES = ["Ashford", "Denby", "Elmsworth", "Fenwick", "Gorley", "Harden",
          "Ipswold", "Kelston", "Marbury", "Netherby", "Oxley", "Padgate"]
LABELS = list("PQRST")
ANGLES = [45, 90, 135, 180]


def compass_of_vector(dx, dy):
    """The exact compass point of an (east, north) integer vector, or None.

    An exact integer test, not a tolerance on an angle: a vector is one of the
    eight points only when it lies on an axis or on a true diagonal. Anything
    else sits between two points with no single correct answer and must be
    discarded rather than rounded to the closest.
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


GROUPS = [
    {
        "group_ref": "G-DIR-TURN",
        "instruction": (
            "In each question, someone starts out facing one compass direction and then "
            "makes one or more turns. A quarter turn is 90°, a half turn is 180° and an "
            "eighth of a turn is 45°. Work out the direction they are facing at the end."
        ),
        "example": (
            "Facing North and turning 90° clockwise gives East; turning a further 45° "
            "anticlockwise from East gives North-East."
        ),
    },
    {
        "group_ref": "G-DIR-GRID",
        "instruction": (
            "In each question, places are set out on a square grid and each one is "
            "described by how many squares it lies in a compass direction from another. "
            "A diagonal move of 3 squares means 3 squares across and 3 squares up or "
            "down. Plot the places, then work out the direction you are asked for."
        ),
        "example": (
            "If Denby is 4 squares North of Ashford and Elmsworth is 4 squares East of "
            "Denby, then Elmsworth is 4 across and 4 up from Ashford, so Elmsworth is "
            "North-East of Ashford."
        ),
    },
]

# One distractor per named slip, so the pupil is never told the same sentence
# twice — except the two slips that name a family rather than a single move
# ("turned one of them the wrong way", "read one part and stopped"), where two
# options really are two different moves and both are live.
SLUG_CAP = {"found-one-part-then-stopped": 2, "shifted-the-wrong-way": 2, None: 3}


def offset_words(dx, dy):
    """How far East/West and North/South, leaving out a component that is zero
    rather than printing '0 squares South'."""
    parts = []
    if dx:
        parts.append(f"{abs(dx)} squares {'East' if dx > 0 else 'West'}")
    if dy:
        parts.append(f"{abs(dy)} squares {'North' if dy > 0 else 'South'}")
    return " and ".join(parts)


def choose(cands, key, n=3):
    """Pick n distinct distractors, at most one per named slip."""
    # Named slips first, in random order; the untagged eighth-turn neighbours
    # only ever fill a gap the named ones could not, rather than competing with
    # them for a slot.
    tagged = [c for c in cands if c[1] is not None]
    plain = [c for c in cands if c[1] is None]
    rng.shuffle(tagged)
    rng.shuffle(plain)
    cands = tagged + plain
    out, seen, slugs = [], {key}, collections.Counter()
    for value, slug in cands:
        if value in seen or slugs[slug] >= SLUG_CAP.get(slug, 1):
            continue
        seen.add(value)
        slugs[slug] += 1
        out.append((value, slug))
        if len(out) == n:
            return out
    return None


def neighbours(d):
    i = POINTS.index(d)
    return [POINTS[(i + 1) % 8], POINTS[(i - 1) % 8]]


def build_turns(difficulty, n_turns):
    name = rng.choice(PEOPLE)
    start = rng.choice(POINTS)
    turns = [(rng.choice(ANGLES), rng.random() < 0.5) for _ in range(n_turns)]

    def facing(seq):
        i = POINTS.index(start)
        for angle, clockwise in seq:
            i = (i + (angle // 45) * (1 if clockwise else -1)) % 8
        return POINTS[i]

    key = facing(turns)
    if key == start:
        return None
    phrases = [f"turns {a}° {'clockwise' if cw else 'anticlockwise'}" for a, cw in turns]
    stem = (f"{name} is facing {WORDS[start]}. {name} "
            + ", then ".join(phrases)
            + f". Which direction is {name} facing now?")

    cands = [(start, "no-shift-applied")]
    for i in range(n_turns):
        # Turned one of them the wrong way round.
        flipped = turns[:i] + [(turns[i][0], not turns[i][1])] + turns[i + 1:]
        cands.append((facing(flipped), "shifted-the-wrong-way"))
        # Applied some of the turns and stopped.
        cands.append((facing(turns[:i + 1]), "found-one-part-then-stopped"))
        cands.append((facing(turns[i:]), "found-one-part-then-stopped"))
    cands += [(d, None) for d in neighbours(key)]
    wrong = choose(cands, key)
    if wrong is None:
        return None
    return {
        "subtopic": "Directions",
        "question_type": "turns-and-facing",
        "group_ref": "G-DIR-TURN",
        "stem": stem,
        "difficulty": difficulty,
        "explanation": (f"Starting at {WORDS[start]} and applying each turn in order, "
                        f"an eighth of a turn at a time, ends at {WORDS[key]}."),
        "kind": "mcq",
        "_key": WORDS[key],
        "_wrong": [(WORDS[d], s) for d, s in wrong],
    }


def build_bearing(difficulty, n_legs):
    names = rng.sample(PLACES, n_legs + 1)
    dirs, dists = [], []
    x = y = 0
    for _ in range(n_legs):
        d = rng.choice(POINTS)
        dist = rng.randint(2, 8)
        dirs.append(d)
        dists.append(dist)
        x += STEP[d][0] * dist
        y += STEP[d][1] * dist
    resultant = compass_of_vector(x, y)
    # Neither the resultant nor its opposite may be one of the legs, or the
    # walk can be answered by glancing at a single statement instead of
    # combining them — the opposite matters because half these questions ask
    # for the reverse pair, whose answer is the resultant turned round.
    if resultant is None or resultant in dirs or OPPOSITE[resultant] in dirs:
        return None

    reverse = rng.random() < 0.5
    first, last = names[0], names[-1]
    if reverse:
        key, asked_of, asked_from = OPPOSITE[resultant], last, first
    else:
        key, asked_of, asked_from = resultant, first, last

    statements = [f"{names[i + 1]} is {dists[i]} squares {WORDS[dirs[i]]} of {names[i]}."
                  for i in range(n_legs)]
    stem = ("On a square grid, " + " ".join(statements)
            + f" Which direction is {asked_from} from {asked_of}?")

    # Read one leg of the walk and stopped. Both orientations of a leg count:
    # which one a pupil writes depends on which way round they read the pair,
    # and either way they have used one statement instead of combining them.
    cands = [(OPPOSITE[key], "did-not-swap")]
    for d in dirs:
        cands.append((d, "found-one-part-then-stopped"))
        if reverse:
            # The question asks for the pair the other way round, so a pupil
            # who reads one leg and reverses that instead of the whole walk
            # lands on the leg's opposite. Without the reverse framing they
            # would have had no reason to turn anything round, so the opposite
            # is not offered there.
            cands.append((OPPOSITE[d], "found-one-part-then-stopped"))
    cands += [(d, None) for d in neighbours(key)]
    wrong = choose(cands, key)
    if wrong is None:
        return None
    return {
        "subtopic": "Directions",
        "question_type": "compass-bearing",
        "group_ref": "G-DIR-GRID",
        "stem": stem,
        "difficulty": difficulty,
        "explanation": (f"Adding the legs together, {last} ends up "
                        f"{offset_words(x, y)} of {first}, so {asked_from} is "
                        f"{WORDS[key]} of {asked_of}."),
        "kind": "mcq",
        "_key": WORDS[key],
        "_wrong": [(WORDS[d], s) for d, s in wrong],
    }


def build_relative(difficulty, n_points):
    names = rng.sample(LABELS, n_points)
    hub = names[0]
    coords = {hub: (0, 0)}
    parent_of, legs, statements = {}, {}, []
    for name in names[1:]:
        # Band 4 hangs every point off the hub. Band 5 may hang one off an
        # earlier spoke, so the pair asked about can need two hops.
        parent = hub if difficulty == 4 else rng.choice(list(coords))
        for _ in range(60):
            d = rng.choice(POINTS)
            dist = rng.randint(2, 6)
            px, py = coords[parent]
            spot = (px + STEP[d][0] * dist, py + STEP[d][1] * dist)
            if spot not in coords.values():
                break
        else:
            return None
        coords[name] = spot
        parent_of[name] = parent
        legs[name] = d
        statements.append(f"{name} is {dist} squares {WORDS[d]} of {parent}.")

    if difficulty == 5 and all(p == hub for p in parent_of.values()):
        return None  # a pure star is the band-4 shape, whatever the label says

    direct = {(c, p) for c, p in parent_of.items()} | {(p, c) for c, p in parent_of.items()}
    askable = []
    for i in names:
        for j in names:
            if i == j or (i, j) in direct:
                continue
            bearing = compass_of_vector(coords[i][0] - coords[j][0],
                                        coords[i][1] - coords[j][1])
            if bearing is not None:
                askable.append((i, j, bearing))
    if not askable:
        return None
    asked_from, asked_of, key = rng.choice(askable)

    stem = ("On a square grid, " + " ".join(statements)
            + f" Which direction is {asked_from} from {asked_of}?")
    # A stated leg's own direction is what a pupil writes who grabs one
    # statement and stops. Its opposite is not: nothing in the layout would
    # have prompted them to turn it round, so offering it would tag an option
    # with a slip nobody made.
    cands = [(OPPOSITE[key], "did-not-swap")]
    for d in legs.values():
        cands.append((d, "found-one-part-then-stopped"))
    cands += [(d, None) for d in neighbours(key)]
    wrong = choose(cands, key)
    if wrong is None:
        return None
    dx = coords[asked_from][0] - coords[asked_of][0]
    dy = coords[asked_from][1] - coords[asked_of][1]
    return {
        "subtopic": "Directions",
        "question_type": "relative-position",
        "group_ref": "G-DIR-GRID",
        "stem": stem,
        "difficulty": difficulty,
        "explanation": (f"Plotting every point from the statements puts {asked_from} "
                        f"{offset_words(dx, dy)} of {asked_of}, so {asked_from} is "
                        f"{WORDS[key]} of {asked_of}."),
        "kind": "mcq",
        "_key": WORDS[key],
        "_wrong": [(WORDS[d], s) for d, s in wrong],
    }


PLAN = [
    (20, 2, lambda d: build_turns(d, 2)),
    (12, 3, lambda d: build_turns(d, 3)),
    (18, 3, lambda d: build_bearing(d, 2)),
    (12, 4, lambda d: build_bearing(d, 3)),
    (13, 4, lambda d: build_relative(d, 3)),
    (25, 5, lambda d: build_relative(d, 4)),
]


def key_positions(n):
    """An even spread of key positions with no long run and no cycle.

    rebalance_keys.py would fix a bad spread after the fact; doing it here
    means the committed pack is right the first time and that step has nothing
    to do.
    """
    base = [0, 1, 2, 3] * (n // 4) + list(range(n % 4))
    while True:
        rng.shuffle(base)
        if all(base[i] != base[i + 1] or base[i + 1] != base[i + 2]
               for i in range(len(base) - 2)):
            return base


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "contrib_prash_vr_11.json")

    questions, seen = [], set()
    for count, difficulty, builder in PLAN:
        made = 0
        for _ in range(200000):
            if made == count:
                break
            q = builder(difficulty)
            if q is None or q["stem"] in seen:
                continue
            seen.add(q["stem"])
            questions.append(q)
            made += 1
        if made != count:
            raise SystemExit(f"only drew {made} of {count} at band {difficulty}")

    rng.shuffle(questions)

    for q, pos in zip(questions, key_positions(len(questions))):
        wrong = list(q.pop("_wrong"))
        key = q.pop("_key")
        opts = [{"text": t, "correct": False, **({"misconception": s} if s else {})}
                for t, s in wrong]
        opts.insert(pos, {"text": key, "correct": True})
        q["options"] = opts

    for i, q in enumerate(questions, start=1):
        ordered = {"number": str(i), "ref": f"PRASH-VR-{1000 + i:04d}"}
        ordered.update(q)
        questions[i - 1] = ordered

    pack = {
        "section": {
            "code": "VR",
            "name": "Verbal Reasoning",
            "source": "CONTRIB-PRASH-11",
            "is_placeholder": False,
        },
        "groups": GROUPS,
        "questions": questions,
    }
    with open(out_path, "w") as fh:
        json.dump(pack, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"wrote {out_path}: {len(questions)} questions")


if __name__ == "__main__":
    main()
