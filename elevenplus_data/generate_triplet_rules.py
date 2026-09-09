#!/usr/bin/env python3
"""
Builds elevenplus_data/contrib_prash_vr_10.json — 100 Triplet Rules.

    python3 elevenplus_data/generate_triplet_rules.py [OUTPUT.json]

The RNG is seeded, so re-running reproduces the committed pack byte for byte.
That is the point of keeping this file: the pack is checkable rather than
merely reviewable. Check what comes out with its companion,
`check_triplet_rules.py`, which re-derives every answer from the rendered stem
— refitting the rule from the printed triples without importing anything here.

BANDS 1, 2 AND 4 ARE NOT GENERATED
----------------------------------
`catalog/generators/verbal.py`'s TripletRule bands 1 and 2 both state the rule
outright and always blank the LAST number, so both are one forward calculation
and the two labels do not name two different levels of work. Band 4 is worse
than uninformative: half of it is `_apply_the_rule` — the rule stated, which
band 3 does not do — so a band-4 item can be strictly easier than the band-3
item above it. A band is a claim the weakness report relies on, so this pack
ships only the two bands whose labels carry information:

  band 3 — either four complete triples with the rule left to be found and the
           LAST number blanked (find it, then one forward step), or the rule
           stated and an EARLIER number blanked (read it, then work backwards).
           Two steps either way.
  band 5 — the rule is harder (it can double, treble, halve, or carry a
           constant) and, whichever way it reaches the pupil, the blank is
           never last: the rule has to be turned round before it can be used.

WHY FOUR EXAMPLE TRIPLES, NOT TWO OR THREE
------------------------------------------
A `find-the-rule` item is only fair if the triples shown admit ONE answer at
the blank. The upstream generator tests that against its own five-rule list,
which is the checked-against-itself trap: a pupil is not restricted to five
rules.

Take the honest space instead — every rule of the form c = p·a + q·b + r. Two
example triples give two equations in three unknowns, so infinitely many rules
fit and the "answer" is whatever the author happened to have in mind. Three
give a square system: a linear rule always fits, so a rule that is really
a·b (a product) is always also readable as a linear one, generally with a
different answer. Only at FOUR examples is the linear family over-determined:
it pins a linear rule uniquely, and it fails to fit a product rule at all,
leaving the product reading standing alone. So every find-the-rule item here
shows four complete triples, and each is kept only after the alternative
family has been checked and found either not to fit or to agree.

The space is not a secret the pupil has to guess at: the group instruction
says the rule works out the third number from the first two using adding,
subtracting, multiplying, halving or doubling, and that every number is a
whole number. That declaration is what makes "exactly one answer" a claim
about the question rather than about the author.

HOW DISTRACTORS STAY LIVE
-------------------------
Every distractor is the value one named slip actually produces: applying the
rule forwards when the blank needs it worked backwards, flipping the sign of
one term, dropping the rule's constant, reading a different rule off the
triples, or copying one of the two numbers already in the bracket. Each
carries the matching misconception slug. Where a slip's arithmetic does not
come out as a positive whole number the candidate is DROPPED rather than
nudged to a nearby number wearing a slug that does not describe it — the slug
is the sentence the pupil reads. A near-miss (the key one or two out) is a
real thing a pupil writes but is nobody's named mistake, so it is used only to
fill a gap and ships untagged.
"""
import collections
import json
import os
import random
import sys
from fractions import Fraction

rng = random.Random(20260913)

F = Fraction


class Rule:
    """c = p·a + q·b + r, or (product form) c = a·b + r."""

    def __init__(self, key, statement, sampler, p=None, q=None, r=0, product=False):
        self.key = key
        self.statement = statement
        self.sampler = sampler
        self.p, self.q, self.r = p, q, F(r)
        self.product = product

    def forward(self, a, b):
        return a * b + self.r if self.product else self.p * a + self.q * b + self.r

    def at(self, pos, a, b, c):
        """The value the rule puts at `pos`, given the other two, or None if
        that is not a positive whole number."""
        try:
            if pos == "c":
                v = self.forward(a, b)
            elif self.product:
                other = b if pos == "a" else a
                v = (F(c) - self.r) / other if other else None
            elif pos == "a":
                v = (F(c) - self.q * b - self.r) / self.p if self.p else None
            else:
                v = (F(c) - self.p * a - self.r) / self.q if self.q else None
        except ZeroDivisionError:
            return None
        if v is None or v.denominator != 1 or v <= 0:
            return None
        return int(v)


def sampler(lo_a, hi_a, b_from):
    def draw():
        a = rng.randint(lo_a, hi_a)
        span = b_from(a)
        if span[0] > span[1]:
            return None
        return a, rng.randint(*span)
    return draw


RULES = {
    "sum": Rule("sum", "the third number is the first number added to the second",
                sampler(2, 40, lambda a: (2, 40)), p=1, q=1),
    "product": Rule("product", "the third number is the first number multiplied by the second",
                    sampler(2, 12, lambda a: (2, 12)), product=True),
    "difference": Rule("difference", "the third number is the second number taken away from the first",
                       sampler(8, 60, lambda a: (2, a - 2)), p=1, q=-1),
    "average": Rule("average", "the third number is halfway between the first two numbers",
                    sampler(2, 60, lambda a: (2, 60)), p=F(1, 2), q=F(1, 2)),
    "double_minus": Rule("double_minus", "the third number is double the first number, with the second taken away",
                         sampler(4, 30, lambda a: (2, 2 * a - 2)), p=2, q=-1),
    "double_plus": Rule("double_plus", "the third number is double the first number, added to the second",
                        sampler(2, 25, lambda a: (2, 30)), p=2, q=1),
    "treble_minus": Rule("treble_minus", "the third number is three times the first number, with the second taken away",
                         sampler(3, 25, lambda a: (2, 3 * a - 2)), p=3, q=-1),
    "difference_doubled": Rule("difference_doubled",
                               "the third number is double what you get by taking the second number away from the first",
                               sampler(6, 40, lambda a: (2, a - 2)), p=2, q=-2),
}
# Rules carrying a constant are built per-question, so the constant varies.


def sum_plus(k):
    return Rule(f"sum_plus_{k}",
                f"the third number is the first two numbers added together, and then {k} more",
                sampler(2, 35, lambda a: (2, 35)), p=1, q=1, r=k)


def product_minus(k):
    return Rule(f"product_minus_{k}",
                f"the third number is the first number multiplied by the second, "
                f"with {k} taken away",
                sampler(3, 12, lambda a: (max(2, (k + 2 + a - 1) // a), 12)),
                r=-k, product=True)


def easy_pool():
    return [RULES["sum"], RULES["product"], RULES["difference"]]


def hard_pool():
    return ([RULES["average"], RULES["double_minus"], RULES["double_plus"],
             RULES["treble_minus"], RULES["difference_doubled"]]
            + [sum_plus(rng.randint(2, 6)), product_minus(rng.randint(2, 9))])


def apply_pool_b3():
    return [RULES["product"], RULES["difference"], RULES["double_minus"], RULES["average"]]


def apply_pool_b5():
    return ([RULES["treble_minus"], RULES["difference_doubled"], RULES["double_plus"]]
            + [sum_plus(rng.randint(2, 6)), product_minus(rng.randint(2, 9))])


def draw_triple(rule):
    for _ in range(200):
        drawn = rule.sampler()
        if drawn is None:
            continue
        a, b = drawn
        c = rule.forward(a, b)
        if isinstance(c, Fraction):
            if c.denominator != 1:
                continue
            c = int(c)
        if a >= 2 and b >= 2 and 2 <= c <= 150:
            return a, b, c
    return None


def solve_linear(rows):
    """Exact (p, q, r) fitting three (a, b, c) rows, or None if the system is
    singular. Fractions throughout, so nothing turns on floating point."""
    m = [[F(a), F(b), F(1), F(c)] for a, b, c in rows]
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
    return m[0][3], m[1][3], m[2][3]


def rival_answers(examples, pos, a, b, c):
    """Every answer at `pos` reachable by a rule of the declared space that
    fits all four examples: the exact linear fit (unique over the rationals
    when the examples pin it), and the product family c = a·b + r.

    This is the generator's own guarantee. It is worked out a different way
    from the checker's — exact elimination here, a parameter sweep there — so
    the two agreeing is worth something.
    """
    out = set()
    fit = solve_linear(examples[:3])
    if fit is not None:
        p, q, r = fit
        if all(p * ea + q * eb + r == ec for ea, eb, ec in examples):
            v = Rule("fit", "", None, p=p, q=q, r=r).at(pos, a, b, c)
            if v is not None:
                out.add(v)
    r0 = examples[0][2] - examples[0][0] * examples[0][1]
    if all(ec - ea * eb == r0 for ea, eb, ec in examples):
        v = Rule("fit", "", None, r=r0, product=True).at(pos, a, b, c)
        if v is not None:
            out.add(v)
    return out


def fmt(a, b, c, pos=None):
    vals = [a, b, c]
    if pos is not None:
        vals["abc".index(pos)] = "?"
    return "(" + ", ".join(str(v) for v in vals) + ")"


GROUPS = [
    {
        "group_ref": "G-TR-FIND",
        "instruction": (
            "In each question, every bracket of three numbers follows the same rule. "
            "The rule works out the third number from the first two, using only adding, "
            "subtracting, multiplying, halving or doubling, and every number is a whole "
            "number. Work out the rule, then find the number the ? stands for."
        ),
        "example": (
            "(3, 5, 8), (7, 2, 9), (4, 6, 10), (9, 3, 12) — in each bracket the first "
            "two numbers add up to the third, so in (6, ?, 11) the ? stands for 5."
        ),
    },
    {
        "group_ref": "G-TR-APPLY",
        "instruction": (
            "In each question you are told the rule that links the three numbers in a "
            "bracket, and shown one bracket that follows it. Every number is a whole "
            "number. Use the rule to find the number the ? stands for."
        ),
        "example": (
            "The third number is double the first number, with the second taken away. "
            "(7, 5, 9) follows this rule, because 7 doubled is 14 and 14 − 5 = 9. So in "
            "(?, 4, 12) the ? stands for 8."
        ),
    },
]

SLUG_CAP = {"used-the-wrong-pair-rule": 2, None: 3}


def distractors(rule, pos, a, b, c, key, pool):
    """Candidate (value, slug) pairs, each the value one named slip produces.

    A slip whose arithmetic does not come out as a positive whole number is
    dropped, not nudged onto a nearby number wearing its slug.
    """
    cands = []

    def add(v, slug):
        if v is not None and isinstance(v, int) and 0 < v <= max(key * 6, key + 60):
            cands.append((v, slug))

    # Applied the rule forwards to the two numbers on show, where the blank
    # needed it worked backwards.
    if pos != "c":
        x, y = {"a": (b, c), "b": (a, c)}[pos]
        v = rule.forward(x, y)
        v = F(v)
        add(int(v) if v.denominator == 1 else None,
            "applied-the-same-operation-not-its-inverse")

    # Read a different rule off the triples. The candidates are drawn from
    # every rule this pack uses, not just the pool this item was built from:
    # a pupil misreading the triples is not restricted to the handful the
    # generator happened to be choosing between here.
    wide, seen_keys = [], {rule.key}
    for other in list(pool) + list(RULES.values()):
        if other.key in seen_keys:
            continue
        seen_keys.add(other.key)
        wide.append(other)
    for other in wide:
        add(other.at(pos, a, b, c), "used-the-wrong-pair-rule")

    # Flipped the sign of the second term.
    if not rule.product and rule.q is not None:
        flipped = Rule("f", "", None, p=rule.p, q=-rule.q, r=rule.r)
        add(flipped.at(pos, a, b, c), "flipped-the-sign-of-one-term")

    # Dropped the rule's constant.
    if rule.r != 0:
        bare = Rule("f", "", None, p=rule.p, q=rule.q, r=0, product=rule.product)
        add(bare.at(pos, a, b, c), "skipped-a-step-of-the-equation")

    # Copied a number that was already in the bracket.
    for v in {"a": (b, c), "b": (a, c), "c": (a, b)}[pos]:
        add(v, "copied-a-given-number-instead-of-solving")

    # Near misses. Real answers a pupil writes, but nobody's named mistake, so
    # they are untagged and only fill a gap.
    tail = [(key + d, None) for d in (1, -1, 2, -2)]

    rng.shuffle(cands)
    out, seen_v, seen_slug = [], {key}, collections.Counter()
    for v, slug in cands + tail:
        # At most one distractor per named slip, so the pupil is never told the
        # same sentence twice — except reading a different rule off the
        # triples, where two options really are two different wrong rules and
        # both are live. Without the cap, "copied a number from the bracket"
        # has two candidates every time and crowds the other slips out.
        if v in seen_v or v <= 0 or seen_slug[slug] >= SLUG_CAP.get(slug, 1):
            continue
        seen_v.add(v)
        seen_slug[slug] += 1
        out.append((v, slug))
        if len(out) == 3:
            return out
    return None


def build_find(difficulty, typed):
    pool = easy_pool() if difficulty == 3 else hard_pool()
    positions = ("c",) if difficulty == 3 else ("a", "b")
    for _ in range(400):
        rule = rng.choice(pool)
        triples = []
        for _ in range(5):
            t = draw_triple(rule)
            if t is None:
                break
            if t not in triples:
                triples.append(t)
        if len(triples) < 5:
            continue
        examples, (a, b, c) = triples[:4], triples[4]
        pos = rng.choice(positions)
        key = {"a": a, "b": b, "c": c}[pos]
        answers = rival_answers(examples, pos, a, b, c)
        if answers != {key}:
            continue
        stem = ("Each of these number triples follows the same rule: "
                + ", ".join(fmt(*t) for t in examples)
                + f". Using the same rule, what is the missing number in {fmt(a, b, c, pos)}?")
        explanation = (f"The rule is: {rule.statement}. Checking it against "
                       f"{fmt(*examples[0])} and {fmt(*examples[1])} confirms it, and "
                       f"working {fmt(a, b, c, pos)} out the same way gives {key}.")
        q = {
            "subtopic": "Triplet Rules",
            "question_type": "find-the-rule",
            "group_ref": "G-TR-FIND",
            "stem": stem,
            "difficulty": difficulty,
            "explanation": explanation,
        }
        if typed:
            q["kind"] = "numeric"
            q["answer"] = key
            return q
        wrong = distractors(rule, pos, a, b, c, key, pool)
        if wrong is None:
            continue
        q["kind"] = "mcq"
        q["_key"] = key
        q["_wrong"] = wrong
        return q
    return None


def build_apply(difficulty, typed):
    pool = apply_pool_b3() if difficulty == 3 else apply_pool_b5()
    for _ in range(400):
        rule = rng.choice(pool)
        demo = draw_triple(rule)
        target = draw_triple(rule)
        # A worked example whose first two numbers are equal reads as a
        # different rule than the one stated ("square the first number", say),
        # so it is not the bracket to demonstrate with.
        if demo is None or target is None or demo == target or demo[0] == demo[1]:
            continue
        a, b, c = target
        pos = rng.choice(("a", "b"))
        key = {"a": a, "b": b, "c": c}[pos]
        stem = (f"In each triple of numbers, {rule.statement}. For example, "
                f"{fmt(*demo)} follows this rule. Using the same rule, what is the "
                f"missing number in {fmt(a, b, c, pos)}?")
        explanation = (f"{rule.statement[0].upper()}{rule.statement[1:]}. Working "
                       f"{fmt(a, b, c, pos)} backwards from the two numbers you can see "
                       f"gives {key}.")
        q = {
            "subtopic": "Triplet Rules",
            "question_type": "apply-the-rule",
            "group_ref": "G-TR-APPLY",
            "stem": stem,
            "difficulty": difficulty,
            "explanation": explanation,
        }
        if typed:
            q["kind"] = "numeric"
            q["answer"] = key
            return q
        wrong = distractors(rule, pos, a, b, c, key, pool)
        if wrong is None:
            continue
        q["kind"] = "mcq"
        q["_key"] = key
        q["_wrong"] = wrong
        return q
    return None


# The batch: (count, difficulty, builder, typed).
PLAN = [
    (28, 3, build_find, False),
    (7, 3, build_find, True),
    (16, 3, build_apply, False),
    (4, 3, build_apply, True),
    (23, 5, build_find, False),
    (7, 5, build_find, True),
    (11, 5, build_apply, False),
    (4, 5, build_apply, True),
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
        os.path.dirname(os.path.abspath(__file__)), "contrib_prash_vr_10.json")

    questions, seen = [], set()
    for count, difficulty, builder, typed in PLAN:
        made = 0
        while made < count:
            q = builder(difficulty, typed)
            if q is None or q["stem"] in seen:
                continue
            seen.add(q["stem"])
            questions.append(q)
            made += 1

    rng.shuffle(questions)

    mcqs = [q for q in questions if q["kind"] == "mcq"]
    for q, pos in zip(mcqs, key_positions(len(mcqs))):
        wrong = list(q.pop("_wrong"))
        key = q.pop("_key")
        opts = [{"text": str(v), "correct": False, **({"misconception": s} if s else {})}
                for v, s in wrong]
        opts.insert(pos, {"text": str(key), "correct": True})
        q["options"] = opts

    for i, q in enumerate(questions, start=1):
        ordered = {"number": str(i), "ref": f"PRASH-VR-{900 + i:04d}"}
        ordered.update(q)
        questions[i - 1] = ordered

    pack = {
        "section": {
            "code": "VR",
            "name": "Verbal Reasoning",
            "source": "CONTRIB-PRASH-10",
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
