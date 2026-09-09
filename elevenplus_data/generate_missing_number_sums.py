#!/usr/bin/env python3
"""
Builds elevenplus_data/contrib_prash_vr_08.json — 100 Missing Number Sums.

    python3 elevenplus_data/generate_missing_number_sums.py [OUTPUT.json]

The RNG is seeded, so re-running reproduces the committed pack byte for byte.
That is the point of keeping this file: the pack is checkable rather than
merely reviewable. Check what comes out with its companion,
`check_missing_number_sums.py`, which re-derives every answer by brute force
over the rendered stems without importing this file.

BAND 2 IS NOT GENERATED
-----------------------
The audit found a dead distractor — one no pupil would ever pick — in 100% of
the band-2 items, so the pack steps from band 1 to band 3 rather than reproduce
that template. `audit_packs.py --target 10,45,30,15` matches what is built here.

HOW DISTRACTORS STAY LIVE
-------------------------
Every number distractor is the value one named slip actually produces. Where a
slip's arithmetic does not come out whole, the candidate is DROPPED (it becomes
None and is filtered out) rather than replaced by some nearby number wearing a
misconception slug that does not describe it — the slug is the sentence the
pupil reads, so a fallback value with a borrowed slug is a lie to the child.
Beyond that, `number_options` keeps distractors positive, distinct, within
reach of the key, and where the arithmetic allows puts one on each side of it.

Sign items need none of this: the wrong options are the other signs, and a
pupil has to do the sum to rule them out. Only the reversed pair of signs
carries a slug; the rest stand untagged rather than claim a mistake that was
not made.

Every value a pupil meets on the intended solution path is a positive whole
number — `ok()` enforces it, and templates that cannot manage it return None
and are regenerated.
"""
import json
import os
import random
import sys
from fractions import Fraction

rng = random.Random(20260910)

GROUPS = [
    {
        "group_ref": "G-MS-NUMBER",
        "instruction": (
            "In each question, work out the number that the ? stands for so that the "
            "sum is correct. Work out anything in brackets first, then multiply and "
            "divide, then add and subtract."
        ),
        "example": (
            "? × 4 + 3 = 23 — take away the 3 to get 20, then divide by 4, so the ? "
            "stands for 5."
        ),
    },
    {
        "group_ref": "G-MS-SIGN",
        "instruction": (
            "In each question, choose the sign or signs that make the sum correct. "
            "Work out anything in brackets first."
        ),
        "example": (
            "36 ? 9 = 4 — dividing is the only sign that works here, because 36 ÷ 9 = 4, "
            "so the missing sign is ÷."
        ),
    },
    {
        "group_ref": "G-MS-BALANCE",
        "instruction": (
            "In each question, the two sides of the sum are worth the same. Work out "
            "the side you can, then find the number that the ? stands for."
        ),
        "example": (
            "5 × 6 = 3 × ? — the left side is worth 30, and 3 × 10 = 30, so the ? "
            "stands for 10."
        ),
    },
]


def ok(*vals):
    """Every working value a pupil meets must be a positive whole number."""
    return all(isinstance(v, int) and v > 0 for v in vals)


# --------------------------------------------------------------- operand items
def operand(difficulty):
    """(stem, key, explanation, [(distractor, misconception)])"""
    style = rng.choice({
        1: ["add", "sub", "mul", "div"],
        3: ["mul_add", "mul_sub", "brk_mul", "div_add"],
        4: ["brk_div", "mul_sub_prod", "brk_mul_prod", "div_sub"],
        5: ["mul_brk_sub", "brk_mul_two", "mul_eq_prod_sum"],
    }[difficulty])

    if style == "add":
        x, b = rng.randint(4, 40), rng.randint(3, 30)
        R = x + b
        stem, expl = f"? + {b} = {R}", f"{R} − {b} = {x}, so the ? stands for {x}."
        d = [(R + b, "applied-the-same-operation-not-its-inverse"),
             (R, "copied-a-given-number-instead-of-solving"),
             (b, "copied-a-given-number-instead-of-solving")]
    elif style == "sub":
        x, b = rng.randint(15, 60), rng.randint(3, 12)
        R = x - b
        stem, expl = f"? − {b} = {R}", f"{R} + {b} = {x}, so the ? stands for {x}."
        d = [(R - b, "applied-the-same-operation-not-its-inverse"),
             (R, "copied-a-given-number-instead-of-solving"),
             (b + R + b, "applied-the-step-backwards")]
    elif style == "mul":
        x, b = rng.randint(3, 12), rng.randint(3, 9)
        R = x * b
        stem, expl = f"? × {b} = {R}", f"{R} ÷ {b} = {x}, so the ? stands for {x}."
        d = [(R * b, "applied-the-same-operation-not-its-inverse"),
             (R - b, "did-not-undo-the-operation"),
             (R, "copied-a-given-number-instead-of-solving")]
    else:  # div
        x, b = rng.randint(12, 60), rng.randint(2, 6)
        x -= x % b
        R = x // b
        stem, expl = f"? ÷ {b} = {R}", f"{R} × {b} = {x}, so the ? stands for {x}."
        d = [(R, "copied-a-given-number-instead-of-solving"),
             (R + b, "did-not-undo-the-operation"),
             (R * b * b, "applied-the-same-operation-not-its-inverse")]

    if difficulty == 3:
        if style == "mul_add":
            x, b, c = rng.randint(3, 12), rng.randint(3, 9), rng.randint(2, 20)
            R = x * b + c
            stem = f"? × {b} + {c} = {R}"
            expl = (f"Take away the {c}: {R} − {c} = {x * b}. Then {x * b} ÷ {b} = {x}, "
                    f"so the ? stands for {x}.")
            d = [(R // b if R % b == 0 else None, "skipped-a-step-of-the-equation"),
                 (x * b, "found-one-part-then-stopped"),
                 ((R + c) // b if (R + c) % b == 0 else None,
                  "flipped-the-sign-of-one-term"),
                 (R, "copied-a-given-number-instead-of-solving")]
        elif style == "mul_sub":
            x, b, c = rng.randint(4, 12), rng.randint(3, 9), rng.randint(2, 15)
            R = x * b - c
            stem = f"? × {b} − {c} = {R}"
            expl = (f"Add the {c} back: {R} + {c} = {x * b}. Then {x * b} ÷ {b} = {x}, "
                    f"so the ? stands for {x}.")
            d = [((R - c) // b if (R - c) % b == 0 and R > c else None,
                  "flipped-the-sign-of-one-term"),
                 (x * b, "found-one-part-then-stopped"),
                 (R, "copied-a-given-number-instead-of-solving")]
        elif style == "brk_mul":
            x, b, c = rng.randint(3, 15), rng.randint(2, 12), rng.randint(2, 6)
            R = (x + b) * c
            stem = f"(? + {b}) × {c} = {R}"
            expl = (f"Divide by {c}: {R} ÷ {c} = {x + b}. Then take away {b}: "
                    f"{x + b} − {b} = {x}, so the ? stands for {x}.")
            d = [(x + b, "found-one-part-then-stopped"),
                 (R - b, "skipped-a-step-of-the-equation"),
                 (x + 2 * b, "flipped-the-sign-of-one-term")]
        else:  # div_add
            x, b, c = rng.randint(2, 12), rng.randint(2, 6), rng.randint(2, 15)
            x *= b
            R = x // b + c
            stem = f"? ÷ {b} + {c} = {R}"
            expl = (f"Take away the {c}: {R} − {c} = {x // b}. Then {x // b} × {b} = {x}, "
                    f"so the ? stands for {x}.")
            d = [(x // b, "found-one-part-then-stopped"),
                 (R * b, "skipped-a-step-of-the-equation"),
                 ((R + c) * b, "flipped-the-sign-of-one-term")]

    if difficulty == 4:
        if style == "brk_div":
            x, b, c = rng.randint(10, 60), rng.randint(2, 20), rng.randint(2, 8)
            t = ((x + b) // c) * c
            x = t - b
            R = t // c
            if not ok(x, R):
                return None
            stem = f"(? + {b}) ÷ {c} = {R}"
            expl = (f"Multiply by {c}: {R} × {c} = {t}. Then take away {b}: "
                    f"{t} − {b} = {x}, so the ? stands for {x}.")
            d = [(t, "found-one-part-then-stopped"),
                 (R + b, "skipped-a-step-of-the-equation"),
                 (t + b, "flipped-the-sign-of-one-term")]
        elif style == "mul_sub_prod":
            x, b, c, e = rng.randint(4, 15), rng.randint(3, 9), rng.randint(2, 12), rng.randint(2, 9)
            R = x * b - c
            if R != c * e:
                e = None
            f2 = rng.randint(2, 9)
            prod = x * b - c
            if prod % f2:
                return None
            g = prod // f2
            if not ok(g) or g > 60:
                return None
            stem = f"? × {b} − {c} = {f2} × {g}"
            expl = (f"The right side is {f2} × {g} = {prod}. Add the {c} back: "
                    f"{prod} + {c} = {x * b}, and {x * b} ÷ {b} = {x}, so the ? stands for {x}.")
            d = [(prod, "found-one-part-then-stopped"),
                 ((prod - c) // b if (prod - c) % b == 0 and prod > c else None,
                  "flipped-the-sign-of-one-term"),
                 (prod // b if prod % b == 0 else None, "skipped-a-step-of-the-equation"),
                 (g, "copied-a-given-number-instead-of-solving")]
        elif style == "brk_mul_prod":
            x, b, c = rng.randint(6, 25), rng.randint(2, 12), rng.randint(2, 6)
            prod = (x - b) * c
            if not ok(x - b):
                return None
            f2 = rng.choice([2, 3, 4, 5, 6])
            if prod % f2:
                return None
            g = prod // f2
            if not ok(g) or g > 80:
                return None
            stem = f"(? − {b}) × {c} = {f2} × {g}"
            expl = (f"The right side is {f2} × {g} = {prod}. Divide by {c}: "
                    f"{prod} ÷ {c} = {x - b}, then add {b} back, so the ? stands for {x}.")
            d = [(x - b, "found-one-part-then-stopped"),
                 (x - 2 * b, "flipped-the-sign-of-one-term"),
                 (prod + b, "skipped-a-step-of-the-equation")]
        else:  # div_sub
            x, b, c = rng.randint(3, 15), rng.randint(2, 8), rng.randint(2, 12)
            x *= b
            R = x // b - c
            if not ok(R):
                return None
            stem = f"? ÷ {b} − {c} = {R}"
            expl = (f"Add the {c} back: {R} + {c} = {x // b}. Then {x // b} × {b} = {x}, "
                    f"so the ? stands for {x}.")
            d = [(x // b, "found-one-part-then-stopped"),
                 (R * b, "skipped-a-step-of-the-equation"),
                 ((R - c) * b if R > c else R + b, "flipped-the-sign-of-one-term")]

    if difficulty == 5:
        if style == "mul_brk_sub":
            x, b, c, e = (rng.randint(3, 15), rng.randint(2, 6),
                          rng.randint(2, 10), rng.randint(3, 30))
            total = b * (x + c) - e
            if not ok(total):
                return None
            f2 = rng.choice([2, 3, 4, 5, 6, 7])
            if total % f2:
                return None
            g = total // f2
            if not ok(g) or g > 90:
                return None
            stem = f"{b} × (? + {c}) − {e} = {f2} × {g}"
            expl = (f"The right side is {f2} × {g} = {total}. Add the {e} back: "
                    f"{total} + {e} = {b * (x + c)}, divide by {b} to get {x + c}, "
                    f"then take away {c}, so the ? stands for {x}.")
            d = [(x + c, "found-one-part-then-stopped"),
                 (total // b - c if total % b == 0 else None,
                  "skipped-a-step-of-the-equation"),
                 (x + 2 * c, "flipped-the-sign-of-one-term"),
                 (g, "copied-a-given-number-instead-of-solving")]
        elif style == "brk_mul_two":
            x, b, c, e = (rng.randint(4, 20), rng.randint(2, 9), rng.randint(2, 6),
                          rng.randint(2, 9))
            left = (x * b - c)
            if left % e:
                return None
            R = left // e
            if not ok(R, left):
                return None
            stem = f"(? × {b} − {c}) ÷ {e} = {R}"
            expl = (f"Multiply by {e}: {R} × {e} = {left}. Add the {c} back: "
                    f"{left} + {c} = {x * b}, then divide by {b}, so the ? stands for {x}.")
            d = [(left, "found-one-part-then-stopped"),
                 ((left - c) // b if (left - c) % b == 0 and left > c else None,
                  "flipped-the-sign-of-one-term"),
                 (x * b, "found-one-part-then-stopped"),
                 (R * b if R * b != x else None, "skipped-a-step-of-the-equation")]
        else:  # mul_eq_prod_sum
            x, b, c, e = (rng.randint(4, 20), rng.randint(3, 9), rng.randint(2, 9),
                          rng.randint(2, 12))
            total = x * b
            rest = total - c * e
            if not ok(rest) or rest > 90:
                return None
            stem = f"? × {b} = {c} × {e} + {rest}"
            expl = (f"The right side is {c} × {e} + {rest} = {total}. "
                    f"{total} ÷ {b} = {x}, so the ? stands for {x}.")
            d = [(total, "found-one-part-then-stopped"),
                 (c * e, "skipped-a-step-of-the-equation"),
                 ((total - rest) // b if (total - rest) % b == 0 else None,
                  "flipped-the-sign-of-one-term"),
                 (rest, "copied-a-given-number-instead-of-solving")]

    if not ok(x):
        return None
    return stem, x, expl, d


# --------------------------------------------------------------- balance items
def balance(difficulty):
    if difficulty == 1:
        a, b = rng.randint(3, 20), rng.randint(3, 20)
        c = rng.choice([n for n in range(2, a + b - 1) if n not in (a, b)])
        x = a + b - c
        stem = f"{a} + {b} = {c} + ?"
        expl = f"The left side is {a} + {b} = {a + b}, and {a + b} − {c} = {x}, so the ? stands for {x}."
        d = [(a + b, "found-one-part-then-stopped"),
             (a + b + c, "applied-the-same-operation-not-its-inverse"),
             (b, "copied-a-given-number-instead-of-solving")]
    elif difficulty == 3:
        kind = rng.choice(["mul", "sub"])
        if kind == "mul":
            a, b = rng.randint(3, 12), rng.randint(2, 12)
            left = a * b
            divisors = [n for n in range(2, 13) if left % n == 0 and n not in (a, b)]
            if not divisors:
                return None
            c = rng.choice(divisors)
            x = left // c
            if x > 60:
                return None
            stem = f"{a} × {b} = {c} × ?"
            expl = (f"The left side is {a} × {b} = {left}, and {left} ÷ {c} = {x}, "
                    f"so the ? stands for {x}.")
            d = [(a * b, "found-one-part-then-stopped"),
                 (b, "copied-a-given-number-instead-of-solving"),
                 (a * b * c, "divided-instead-of-multiplying")]
        else:
            a, b = rng.randint(20, 60), rng.randint(2, 18)
            c = rng.randint(a - b + 2, a + 10)
            x = c - (a - b)
            if not ok(x):
                return None
            stem = f"{a} − {b} = {c} − ?"
            expl = (f"The left side is {a} − {b} = {a - b}, and {c} − {a - b} = {x}, "
                    f"so the ? stands for {x}.")
            d = [(a - b, "found-one-part-then-stopped"),
                 (c + a - b, "applied-the-same-operation-not-its-inverse"),
                 (b, "copied-a-given-number-instead-of-solving")]
    elif difficulty == 4:
        kind = rng.choice(["div", "mixed"])
        if kind == "div":
            v = rng.choice([2, 3, 4, 5, 6, 7, 8])
            a = v * rng.randint(4, 12)
            b = a // v
            x = rng.choice([n for n in range(2, 13) if (v * n) <= 144])
            c = v * x
            stem = f"{a} ÷ {b} = {c} ÷ ?"
            expl = (f"The left side is {a} ÷ {b} = {v}, and {c} ÷ {v} = {x}, "
                    f"so the ? stands for {x}.")
            d = [(v, "found-one-part-then-stopped"),
                 (c * v, "divided-instead-of-multiplying"),
                 (c - v, "did-not-undo-the-operation")]
        else:
            a, b = rng.randint(4, 12), rng.randint(3, 12)
            c = rng.choice([n for n in range(2, 13) if (a * b) % n == 0])
            x = (a * b) // c
            stem = f"{a} × {b} = {c} × ?"
            expl = (f"The left side is {a} × {b} = {a * b}, and {a * b} ÷ {c} = {x}, "
                    f"so the ? stands for {x}.")
            d = [(a * b, "found-one-part-then-stopped"),
                 (a * b * c, "divided-instead-of-multiplying"),
                 (a + b, "skipped-a-step-of-the-equation")]
    else:
        kind = rng.choice(["brk_left", "brk_right"])
        if kind == "brk_left":
            a, b = rng.randint(8, 30), rng.randint(2, 7)
            left = a - b
            c = rng.choice([n for n in range(2, 10) if (left * rng.randint(2, 9)) > 0])
            x = rng.randint(2, 12)
            total = left * c
            if total % x:
                return None
            e = total // x
            if not ok(e) or e > 90:
                return None
            stem = f"({a} − {b}) × {c} = {e} × ?"
            expl = (f"The left side is ({a} − {b}) × {c} = {total}, and {total} ÷ {e} = {x}, "
                    f"so the ? stands for {x}.")
            d = [(total, "found-one-part-then-stopped"),
                 (left, "skipped-a-step-of-the-equation"),
                 (total * e, "divided-instead-of-multiplying")]
        else:
            c, e = rng.randint(2, 9), rng.randint(2, 9)
            x = rng.randint(2, 12)
            total = (c + e) * x
            a = rng.choice([n for n in range(2, 13) if total % n == 0])
            b = total // a
            if b > 90:
                return None
            stem = f"{a} × {b} = ({c} + {e}) × ?"
            expl = (f"The left side is {a} × {b} = {total}, the bracket is {c} + {e} = {c + e}, "
                    f"and {total} ÷ {c + e} = {x}, so the ? stands for {x}.")
            d = [(total, "found-one-part-then-stopped"),
                 (c + e, "copied-a-given-number-instead-of-solving"),
                 (total * (c + e), "divided-instead-of-multiplying")]
    if not ok(x):
        return None
    return stem, x, expl, d


# ---------------------------------------------------------------- sign items
OPS = {"+": lambda a, b: a + b,
       "−": lambda a, b: a - b,
       "×": lambda a, b: a * b,
       "÷": lambda a, b: Fraction(a, b) if b else None}


def apply_op(op, a, b):
    if op == "÷" and (b == 0):
        return None
    return OPS[op](a, b)


def sign_item(difficulty):
    if difficulty in (1, 3):
        lo, hi = (2, 12) if difficulty == 1 else (3, 30)
        op = rng.choice(list(OPS))
        a, b = rng.randint(lo, hi), rng.randint(2, 12)
        if op == "÷":
            a = b * rng.randint(2, 12)
        R = apply_op(op, a, b)
        if R is None or R != int(R) or R <= 0:
            return None
        R = int(R)
        # exactly one sign may work
        hits = [o for o in OPS if apply_op(o, a, b) == R]
        if hits != [op]:
            return None
        stem = f"{a} ? {b} = {R}"
        expl = f"{a} {op} {b} = {R}, and no other sign works, so the missing sign is {op}."
        return stem, op, expl, None
    # two signs, brackets make the order explicit
    ops = list(OPS)
    for _ in range(400):
        o1, o2 = rng.choice(ops), rng.choice(ops)
        a, b, c = rng.randint(2, 40), rng.randint(2, 12), rng.randint(2, 12)
        if o1 == "÷":
            a = b * rng.randint(2, 12)
        t = apply_op(o1, a, b)
        if t is None or t != int(t) or t <= 0:
            continue
        t = int(t)
        R = apply_op(o2, t, c)
        if R is None or R != int(R) or R <= 0:
            continue
        R = int(R)
        if difficulty == 5:
            d1, d2 = rng.randint(2, 12), rng.randint(2, 12)
            rhs_op = rng.choice(["+", "×"])
            if apply_op(rhs_op, d1, d2) != R:
                continue
            stem = f"({a} ? {b}) ? {c} = {d1} {rhs_op} {d2}"
            rhs = f"{d1} {rhs_op} {d2} = {R}"
        else:
            stem = f"({a} ? {b}) ? {c} = {R}"
            rhs = None
        hits = [(p, q) for p in ops for q in ops
                if (lambda v: v is not None and v == R)(
                    apply_op(q, apply_op(p, a, b), c)
                    if apply_op(p, a, b) is not None else None)]
        if hits != [(o1, o2)]:
            continue
        expl = (f"{'The right side is ' + rhs + '. ' if rhs else ''}"
                f"{a} {o1} {b} = {t}, and {t} {o2} {c} = {R}, "
                f"so the missing signs are {o1} then {o2}.")
        return stem, f"{o1} then {o2}", expl, None
    return None


SIGN_MIS = {("×", "÷"): "divided-instead-of-multiplying",
            ("÷", "×"): "applied-the-same-operation-not-its-inverse",
            ("+", "−"): "flipped-the-sign-of-one-term",
            ("−", "+"): "flipped-the-sign-of-one-term"}


def sign_options(key):
    """Four sign options: the key plus three wrong ones, tagged where honest."""
    ops = list(OPS)
    if " then " in key:
        k1, k2 = key.split(" then ")
        pool = [(f"{p} then {q}", p, q) for p in ops for q in ops
                if (p, q) != (k1, k2)]
        rng.shuffle(pool)
        picked, out = [], []
        # prefer near misses: one sign right, or the two signs the other way round
        pool.sort(key=lambda t: (t[1] != k1) + (t[2] != k2))
        for text, p, q in pool[:6]:
            mis = "applied-the-step-backwards" if (p, q) == (k2, k1) else None
            picked.append((text, mis))
        rng.shuffle(picked)
        out = picked[:3]
    else:
        out = [(o, SIGN_MIS.get((key, o))) for o in ops if o != key]
    opts = [{"text": t, "correct": False, **({"misconception": m} if m else {})}
            for t, m in out]
    opts.append({"text": key, "correct": True})
    rng.shuffle(opts)
    return opts


# ------------------------------------------------------------------- assembly
def number_options(key, cands):
    """Pick three live distractors: positive, distinct, in a believable range."""
    limit = max(key * 6, key + 60)
    seen, out = {key}, []
    for val, mis in cands:
        if not isinstance(val, int) or val <= 0 or val in seen or val > limit:
            continue
        seen.add(val)
        out.append({"text": str(val), "correct": False, "misconception": mis})
    if len(out) < 3:
        return None
    # keep the key surrounded where the arithmetic allows it, so no option is
    # dead on sight
    below = [o for o in out if int(o["text"]) < key]
    above = [o for o in out if int(o["text"]) > key]
    chosen = []
    if below and above:
        chosen = [below[0], above[0]]
        chosen += [o for o in out if o not in chosen][:1]
    else:
        chosen = out[:3]
    opts = chosen[:3] + [{"text": str(key), "correct": True}]
    rng.shuffle(opts)
    return opts


PLAN = [
    ("missing-operand", 1, 5), ("missing-operand", 3, 18),
    ("missing-operand", 4, 12), ("missing-operand", 5, 5),
    ("missing-operator", 1, 3), ("missing-operator", 3, 13),
    ("missing-operator", 4, 9), ("missing-operator", 5, 5),
    ("balance-both-sides", 1, 2), ("balance-both-sides", 3, 14),
    ("balance-both-sides", 4, 9), ("balance-both-sides", 5, 5),
]

# a fifth of the number-answer items are typed rather than chosen, which is
# what the CEM/Bond papers do with this section
TYPED_TARGET = 20

questions, stems = [], set()
for qtype, diff, count in PLAN:
    made, guard = 0, 0
    while made < count:
        guard += 1
        if guard > 400000:
            raise SystemExit(f"could not build {qtype} d{diff}")
        built = (sign_item(diff) if qtype == "missing-operator" else
                 operand(diff) if qtype == "missing-operand" else balance(diff))
        if built is None:
            continue
        stem, key, expl, cands = built
        if stem in stems:
            continue
        if qtype == "missing-operator":
            opts = sign_options(key)
            q = {"subtopic": "Missing Number Sums", "question_type": qtype,
                 "group_ref": "G-MS-SIGN", "kind": "mcq", "difficulty": diff,
                 "stem": stem, "options": opts, "explanation": expl}
        else:
            opts = number_options(key, cands)
            if opts is None:
                continue
            group = "G-MS-NUMBER" if qtype == "missing-operand" else "G-MS-BALANCE"
            q = {"subtopic": "Missing Number Sums", "question_type": qtype,
                 "group_ref": group, "kind": "mcq", "difficulty": diff,
                 "stem": stem, "options": opts, "explanation": expl,
                 "_key": key}
        stems.add(stem)
        questions.append(q)
        made += 1

# turn a spread of the number-answer items into typed questions
typed_pool = [q for q in questions if "_key" in q and q["difficulty"] in (3, 4, 5)]
rng.shuffle(typed_pool)
for q in typed_pool[:TYPED_TARGET]:
    q["kind"] = "numeric"
    q["answer"] = q["_key"]
    q.pop("options")
for q in questions:
    q.pop("_key", None)

rng.shuffle(questions)


def key_pos(q):
    return [o.get("correct", False) for o in q["options"]].index(True)


for _ in range(30):
    mcqs = [q for q in questions if q["kind"] == "mcq"]
    pos = [key_pos(q) for q in mcqs]
    runs = [i for i in range(3, len(pos))
            if pos[i] == pos[i - 1] == pos[i - 2] == pos[i - 3]]
    if not runs:
        break
    for i in runs:
        opts = mcqs[i]["options"]
        key = opts.pop(key_pos(mcqs[i]))
        opts.insert(rng.choice([c for c in range(len(opts) + 1) if c != pos[i]]), key)

for i, q in enumerate(questions, 1):
    q["number"] = str(i)
    q["ref"] = f"PRASH-VR-{700 + i:04d}"
    order = ["number", "ref", "subtopic", "question_type", "group_ref", "stem",
             "difficulty", "explanation", "kind", "options", "answer"]
    for key in order:
        if key in q:
            q[key] = q.pop(key)

pack = {
    "section": {"code": "VR", "name": "Verbal Reasoning",
                "source": "CONTRIB-PRASH-08", "is_placeholder": False},
    "groups": GROUPS,
    "questions": questions,
}
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "contrib_prash_vr_08.json")
with open(out, "w") as f:
    json.dump(pack, f, indent=2, ensure_ascii=False)
    f.write("\n")
print("wrote", out, len(questions),
      "typed:", sum(1 for q in questions if q["kind"] == "numeric"))
