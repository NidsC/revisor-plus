#!/usr/bin/env python3
"""
Builds elevenplus_data/contrib_prash_vr_07.json — 100 Letter Analogy questions.

    python3 elevenplus_data/generate_letter_analogies.py [OUTPUT.json]

The RNG is seeded, so re-running reproduces the committed pack byte for byte.
That is the point of keeping this file: the pack is checkable rather than
merely reviewable, and anyone can regenerate it, diff it, or change the plan at
the bottom and rebuild. Check what comes out with its companion,
`check_letter_analogies.py`, which re-derives every answer from the rendered
stems without importing this file.

WHY THE SECOND STIMULUS IS ALWAYS A SHIFT OF THE FIRST
------------------------------------------------------
`X is to Y as Z is to ___` does not pin its own rule down. One worked pair is
consistent with every positional permutation of a per-letter shift, and
different permutations generally give different answers — the "key too narrow"
fault the audit found concentrated in bands 1-2.

So Z is always a uniform shift of X (Z = X + k). Every per-position shift rule
consistent with X -> Y, under every permutation, then lands on the same answer,
and the question has one defensible key. Items where a mirror-alphabet reading
(A<->Z) of any position is also consistent are rejected outright, since that
reading would diverge. Bands 1-2 are not generated at all.

A two-letter "swap" is only ever a pure swap. Swap-plus-shift on two letters is
indistinguishable from a plain per-letter shift, so `position-swap` would not
have been an honest label for it; the harder swaps are three-letter items.
"""
import json
import os
import random
import sys

A = ord('A')


def L(n):            # 0..25 -> letter
    return chr(A + (n % 26))


def N(c):            # letter -> 0..25
    return ord(c) - A


def s2n(s):
    return [N(c) for c in s]


def n2s(v):
    return ''.join(L(x) for x in v)


def add(v, deltas):
    return [(x + d) % 26 for x, d in zip(v, deltas)]


def shift_all(v, k):
    return [(x + k) % 26 for x in v]


def wraps(v, deltas):
    """True if applying deltas to any position runs off either end of A-Z."""
    for x, d in zip(v, deltas):
        if not (0 <= x + d <= 25):
            return True
    return False


def mirror_clash(X, Y):
    """Reject items where a mirror reading of any position is consistent."""
    return any(y == 25 - x for y in Y for x in X)


rng = random.Random(20260909)

GROUPS = [
    {
        "group_ref": "G-LA-PAIR",
        "instruction": (
            "In each question, work out how the first pair of letters changes to make the "
            "second pair, then change the third pair in the same way. The alphabet is printed "
            "here to help you:\n"
            "A B C D E F G H I J K L M N O P Q R S T U V W X Y Z\n"
            "If counting runs off the end of the alphabet, carry on from the other end."
        ),
        "example": (
            "AC is to BD as MO is to ___ . Each letter moves one place forward, so A becomes B "
            "and C becomes D; doing the same to MO gives NP."
        ),
    },
    {
        "group_ref": "G-LA-TRIPLE",
        "instruction": (
            "In each question, work out how the first group of three letters changes to make the "
            "second group, then change the third group in the same way. The alphabet is printed "
            "here to help you:\n"
            "A B C D E F G H I J K L M N O P Q R S T U V W X Y Z\n"
            "If counting runs off the end of the alphabet, carry on from the other end."
        ),
        "example": (
            "BDF is to FDB as HJL is to ___ . The three letters are written in the opposite "
            "order, so BDF becomes FDB; doing the same to HJL gives LJH."
        ),
    },
]


def build(kind, difficulty, allow_wrap):
    """Return one candidate question dict, or None if it must be rejected."""
    length = 3 if kind.endswith("3") else 2
    kind = kind[:-1] if kind.endswith("3") else kind   # "pair3" is pair-shift, three letters

    # --- first stimulus X ---
    if length == 2:
        gap = rng.choice([1, 2, 3, 4, 5, 6, 7])
        x0 = rng.randrange(26)
        X = [x0, (x0 + gap) % 26]
    else:
        step = rng.choice([1, 2, 3, 4])
        x0 = rng.randrange(26)
        X = [x0, (x0 + step) % 26, (x0 + 2 * step) % 26]

    # --- the relation X -> Y ---
    perm = list(range(length))
    deltas = [0] * length
    if kind == "single":
        p = rng.randrange(length)
        s = rng.choice([1, 2, 3, 4]) if difficulty == 3 else rng.choice([-5, -4, -3, -2, 5, 6, 7])
        deltas[p] = s
        qtype, family = "single-letter-shift", ("single", p, s)
    elif kind == "pair":
        if difficulty == 3:
            a = b = rng.choice([1, 2, 3, 4])
        elif difficulty == 4:
            a, b = rng.choice([(2, 3), (3, 1), (1, 4), (4, 2), (-1, -2), (-3, -1), (2, -2), (-2, 3)])
        else:
            a, b = rng.choice([(5, -4), (-6, 5), (7, 3), (-5, -6), (6, -7), (-4, 6)])
        deltas = [a, b]
        if length == 3:
            deltas = [a, b, rng.choice([c for c in (-3, -2, -1, 1, 2, 3) if c not in (a, b)])]
        qtype, family = "pair-shift", ("pair", tuple(deltas))
    else:  # swap
        if length == 2:
            perm = [1, 0]
            s = 0
            deltas = [s, s]
            family = ("swap2", s)
        else:
            style = rng.choice(["reverse", "rotate"]) if difficulty >= 4 else "reverse"
            perm = [2, 1, 0] if style == "reverse" else [1, 2, 0]
            s = 0 if difficulty <= 4 else rng.choice([-2, -1, 1, 2])
            deltas = [s] * 3
            family = ("swap3", style, s)
        qtype = "position-swap"

    Y = [(X[perm[i]] + deltas[i]) % 26 for i in range(length)]

    # --- second stimulus Z = X + k ---
    k = rng.choice([c for c in range(-12, 13) if c not in (0,)])
    Z = shift_all(X, k)
    ANS = [(Z[perm[i]] + deltas[i]) % 26 for i in range(length)]

    # --- wrap control: bands 3 and 4 stay inside A-Z end to end ---
    ran_off = (
        wraps(X, [k] * length)
        or any(not (0 <= X[perm[i]] + deltas[i] <= 25) for i in range(length))
        or any(not (0 <= Z[perm[i]] + deltas[i] <= 25) for i in range(length))
    )
    if ran_off and not allow_wrap:
        return None
    if allow_wrap and not ran_off:
        return None
    if mirror_clash(X, Y):
        return None
    if ANS == Z or Y == X:
        return None

    # --- distractors, each one a named slip ---
    cands = []
    if family[0] == "single":
        _, p, s = family
        d = [0] * length
        d[p] = -s
        cands.append((n2s(add(Z, d)), "shifted-the-wrong-way"))
        other = [0] * length
        other[(p + 1) % length] = s
        cands.append((n2s(add(Z, other)), "used-the-wrong-pair-rule"))
        cands.append((n2s(Z), "no-shift-applied"))
        off = list(ANS)
        off[p] = (off[p] + rng.choice([-1, 1])) % 26
        cands.append((n2s(off), "miscounted-the-alphabet-by-one"))
    elif family[0] == "pair":
        ds = list(family[1])
        cands.append((n2s(add(Z, [-x for x in ds])), "shifted-the-wrong-way"))
        if length == 2:
            cands.append((n2s(add(Z, [ds[0]] * length)), "used-the-wrong-pair-rule"))
        one = list(ds)
        one[-1] = 0
        cands.append((n2s(add(Z, one)),
                      "moved-only-one-letter-of-the-pair" if length == 2
                      else "found-one-part-then-stopped"))
        cands.append((n2s(Z), "no-shift-applied"))
        off = list(ANS)
        i = rng.randrange(length)
        off[i] = (off[i] + rng.choice([-1, 1])) % 26
        cands.append((n2s(off), "miscounted-the-alphabet-by-one"))
    else:
        s = deltas[0]
        cands.append((n2s(shift_all(Z, s)), "did-not-swap"))
        if s != 0:
            cands.append((n2s([Z[perm[i]] for i in range(length)]), "found-one-part-then-stopped"))
            cands.append((n2s(shift_all([Z[perm[i]] for i in range(length)], -s)),
                          "shifted-the-wrong-way"))
        else:
            cands.append((n2s(Z), "did-not-swap"))
        if length == 3:
            alt = [1, 0, 2] if perm == [2, 1, 0] else [2, 0, 1]
            cands.append((n2s([(Z[alt[i]] + deltas[i]) % 26 for i in range(length)]),
                          "swapped-the-wrong-letters"))
        off = list(ANS)
        i = rng.randrange(length)
        off[i] = (off[i] + rng.choice([-1, 1])) % 26
        cands.append((n2s(off), "miscounted-the-alphabet-by-one"))

    # every answer has near-misses one place out in the alphabet; they are the
    # commonest slip and keep short-pool families (a plain two-letter swap) fed.
    # They come last so a structural distractor is always preferred to one.
    near = []
    for i in range(length):
        for step in (-1, 1):
            off = list(ANS)
            off[i] = (off[i] + step) % 26
            near.append((n2s(off), "miscounted-the-alphabet-by-one"))

    zs_text = n2s(Z)
    near = [(t, "no-shift-applied" if t == zs_text else m) for t, m in near]
    cands = [(t, "no-shift-applied" if t == zs_text and m != "no-shift-applied" else m)
             for t, m in cands]

    ans_s = n2s(ANS)
    seen, distractors = {ans_s}, []
    rng.shuffle(cands)
    rng.shuffle(near)
    for text, mis in cands + near:
        if text in seen:
            continue
        seen.add(text)
        distractors.append({"text": text, "correct": False, "misconception": mis})
        if len(distractors) == 3:
            break
    if len(distractors) < 3:
        return None

    options = distractors + [{"text": ans_s, "correct": True}]
    rng.shuffle(options)

    # --- explanation ---
    xs, ys, zs = n2s(X), n2s(Y), n2s(Z)
    ord_words = ["first", "second", "third"]
    if family[0] == "single":
        _, p, s = family
        moved = f"the {ord_words[p]} letter moves {abs(s)} place{'s' if abs(s) != 1 else ''} " \
                f"{'forward' if s > 0 else 'back'}"
        kept = " and ".join(f"the {ord_words[i]} letter stays the same"
                            for i in range(length) if i != p)
        rule = f"{moved} and {kept}"
    elif family[0] == "pair":
        ds = list(family[1])
        parts = []
        for i, d in enumerate(ds):
            if d == 0:
                parts.append(f"the {ord_words[i]} letter stays the same")
            else:
                parts.append(f"the {ord_words[i]} letter moves {abs(d)} "
                             f"place{'s' if abs(d) != 1 else ''} "
                             f"{'forward' if d > 0 else 'back'}")
        rule = " and ".join(parts) if len(parts) == 2 else ", ".join(parts[:-1]) + " and " + parts[-1]
    elif family[0] == "swap2":
        s = family[1]
        rule = "the two letters swap places"
        if s:
            rule += (f" and then each moves {abs(s)} place{'s' if abs(s) != 1 else ''} "
                     f"{'forward' if s > 0 else 'back'}")
    else:
        _, style, s = family
        rule = ("the three letters are written in the opposite order" if style == "reverse"
                else "each letter moves one place to the left, and the first letter goes to the end")
        if s:
            rule += (f", then each moves {abs(s)} place{'s' if abs(s) != 1 else ''} "
                     f"{'forward' if s > 0 else 'back'}")
    explanation = f"{xs} becomes {ys} because {rule}. Doing the same to {zs} gives {ans_s}."

    return {
        "subtopic": "Letter Analogies",
        "question_type": qtype,
        "group_ref": "G-LA-PAIR" if length == 2 else "G-LA-TRIPLE",
        "kind": "mcq",
        "difficulty": difficulty,
        "stem": f"{xs} is to {ys} as {zs} is to ___",
        "options": options,
        "explanation": explanation,
    }


# (kind, difficulty, allow_wrap, count) — kinds ending in 3 are three-letter items
PLAN = [
    ("single", 3, False, 18),
    ("single", 4, False, 12),
    ("single", 5, True, 3),
    ("pair", 3, False, 17),
    ("pair", 4, False, 8),
    ("pair3", 4, False, 4),
    ("pair", 5, True, 3),
    ("pair3", 5, True, 2),
    ("swap", 3, False, 10),
    ("swap3", 4, False, 16),
    ("swap3", 5, True, 7),
]

questions, stems = [], set()
for kind, diff, wrap, count in PLAN:
    made = 0
    guard = 0
    base = kind[:-1] if kind.endswith("3") else kind
    while made < count:
        guard += 1
        if guard > 200000:
            raise SystemExit(f"could not build {kind} d{diff}")
        q = build(kind if kind.endswith("3") else base, diff, wrap)
        if q is None:
            continue
        if kind.endswith("3") and len(q["stem"].split(" is to ")[0]) != 3:
            continue
        if not kind.endswith("3") and len(q["stem"].split(" is to ")[0]) != 2:
            continue
        if q["stem"] in stems:
            continue
        stems.add(q["stem"])
        questions.append(q)
        made += 1

rng.shuffle(questions)
for i, q in enumerate(questions, 1):
    q["number"] = str(i)
    q["ref"] = f"PRASH-VR-{600 + i:04d}"
    # field order for readability
    for key in ("number", "ref", "subtopic", "question_type", "group_ref", "stem",
                "difficulty", "explanation", "kind", "options"):
        q[key] = q.pop(key)


def key_pos(q):
    return [o.get("correct", False) for o in q["options"]].index(True)


def move_key(q, target):
    """Reorder one question's options so its key sits at `target`."""
    opts = q["options"]
    key = opts.pop(key_pos(q))
    opts.insert(target, key)


# A run of four identical key positions is exactly what the validator warns on,
# and a pupil spots it. Break any run by moving the last key of it elsewhere.
for _ in range(20):
    pos = [key_pos(q) for q in questions]
    runs = [i for i in range(3, len(pos))
            if pos[i] == pos[i - 1] == pos[i - 2] == pos[i - 3]]
    if not runs:
        break
    for i in runs:
        choices = [c for c in range(len(questions[i]["options"])) if c != pos[i]]
        move_key(questions[i], rng.choice(choices))

pack = {
    "section": {"code": "VR", "name": "Verbal Reasoning",
                "source": "CONTRIB-PRASH-07", "is_placeholder": False},
    "groups": GROUPS,
    "questions": questions,
}
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "contrib_prash_vr_07.json")
with open(out, "w") as f:
    json.dump(pack, f, indent=2, ensure_ascii=False)
    f.write("\n")
print("wrote", out, len(questions))
