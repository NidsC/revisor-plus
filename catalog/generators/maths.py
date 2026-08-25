"""
Maths generators. Each declares a canonical MAT subtopic name from
elevenplus_data/taxonomy.json — the 17-subtopic rebuild, not the eight-subtopic
list this file was first written against. A name that is not in the taxonomy does
not error: generate_bank creates it, so the questions quietly end up in a subtopic
sitting alongside the real one. Keep these strings in step with taxonomy.json.

Difficulty is derived from the numbers each template picks — see the DIFFICULTY
note in each build(). Distractors are the specific errors an 11+ pupil makes, so
each one can carry a misconception string.
"""
from . import Generator, Item, register, shuffled_options


def _money(pence):
    """Format pence as £x.yz, dropping pence when whole pounds."""
    pounds = pence / 100
    return f"£{pounds:.0f}" if pence % 100 == 0 else f"£{pounds:.2f}"


# --------------------------------------------------------------- Number & Place Value

@register
class Rounding(Generator):
    slug = "mat.rounding"
    section, subtopic = "MAT", "Number & Place Value"
    template_id = "round-to-nearest"

    def build(self, rng, difficulty):
        # DIFFICULTY: how many digits, and whether rounding carries into a new
        # column (7,962 -> 8,000 is harder than 7,412 -> 7,000).
        place = {1: 10, 2: 100, 3: 1000, 4: 1000, 5: 10000}[difficulty]
        span = {1: (100, 999), 2: (1000, 9999), 3: (1000, 9999),
                4: (10000, 99999), 5: (100000, 999999)}[difficulty]
        n = rng.randint(*span)
        if difficulty >= 3:  # force a carry, which is the actual difficulty jump
            n = (n // place) * place + int(place * rng.uniform(0.5, 0.99))
        correct = round(n / place) * place
        down = (n // place) * place
        up = down + place
        # Spares included: when n sits exactly on a boundary, `down` or `up` IS the
        # correct answer and gets dropped as a duplicate, so a fixed list of three
        # could collapse to two options.
        return Item(
            stem=f"Round {n:,} to the nearest {place:,}.",
            options=shuffled_options(rng, f"{correct:,}", [
                f"{down:,}",
                f"{up:,}",
                f"{round(n / (place * 10)) * place * 10:,}",   # rounded a column too far
                f"{down - place:,}",
                f"{up + place:,}",
                f"{n:,}",                                       # did not round at all
            ]),
            difficulty=difficulty,
            params={"n": n, "place": place},
            explanation=(f"The digit in the {place:,} column decides it. "
                         f"{n:,} is closer to {correct:,} than to "
                         f"{(down if correct != down else up):,}."),
            misconceptions={
                f"{down:,}": "always-round-down",
                f"{up:,}": "always-round-up",
                f"{round(n / (place * 10)) * place * 10:,}": "rounded-the-wrong-column",
            },
        )


@register
class FactorsMultiples(Generator):
    slug = "mat.factors"
    section, subtopic = "MAT", "Number & Place Value"
    template_id = "factor-or-multiple"
    difficulties = (1, 2, 3, 4)

    def build(self, rng, difficulty):
        # DIFFICULTY: size of the base number and whether the distractors are
        # near-misses (a factor of a factor) rather than obviously unrelated.
        base = {1: rng.choice([12, 20, 24]), 2: rng.choice([36, 48, 60]),
                3: rng.choice([72, 84, 96]), 4: rng.choice([120, 144, 168])}[difficulty]
        factors = [i for i in range(2, base) if base % i == 0]
        if len(factors) < 2:
            return None
        correct = rng.choice(factors)
        non = [i for i in range(2, base) if base % i != 0]
        rng.shuffle(non)
        return Item(
            stem=f"Which of these is a factor of {base}?",
            options=shuffled_options(rng, correct, non[:3]),
            difficulty=difficulty,
            params={"base": base, "correct": correct},
            explanation=f"{base} ÷ {correct} = {base // correct}, with nothing left over.",
        )


# --------------------------------------------------------------- Four Operations

@register
class MissingNumber(Generator):
    slug = "mat.missing"
    section, subtopic = "MAT", "Four Operations"
    template_id = "missing-number"

    def build(self, rng, difficulty):
        # DIFFICULTY: the inverse operation needed. Addition is one step;
        # division-as-inverse-of-multiplication is where pupils come unstuck.
        op = {1: "+", 2: "-", 3: "×", 4: "×", 5: "÷"}[difficulty]
        if op in "+-":
            a = rng.randint(10, 90 if difficulty == 1 else 400)
            b = rng.randint(10, 90 if difficulty == 1 else 400)
            total = a + b
            if op == "+":
                stem, correct, wrong = f"____ + {b} = {total}", a, total + b
            else:
                stem, correct, wrong = f"{total} − ____ = {a}", b, total - a - 1
            distractors = [wrong, correct + 10, correct - 1]
        elif op == "×":
            a = rng.randint(3, 9 if difficulty == 3 else 15)
            b = rng.randint(3, 12 if difficulty == 3 else 40)
            stem, correct = f"{a} × ____ = {a * b}", b
            distractors = [a * b, a * b - a, b + a]
        else:
            b = rng.randint(20, 60)
            q = rng.randint(4, 12)
            stem, correct = f"____ ÷ {b} = {q}", b * q
            distractors = [q / b if b else 0, b + q, b * q // 2]
        return Item(
            stem=f"Fill in the missing number.  {stem}",
            options=shuffled_options(rng, correct, [str(d) for d in distractors]),
            difficulty=difficulty,
            params={"stem": stem, "correct": correct},
            explanation=f"Use the inverse operation: the missing number is {correct}.",
            misconceptions={str(distractors[0]): "applied-the-same-operation-not-its-inverse"},
        )


# --------------------------------------------------------------- FDP

@register
class PercentageOfAmount(Generator):
    slug = "mat.pct-of"
    section, subtopic = "MAT", "Fractions, Decimals & Percentages"
    template_id = "percent-of-amount"

    def build(self, rng, difficulty):
        # DIFFICULTY: whether the percentage decomposes into friendly chunks.
        # 10% is one step; 35% is 30+5; 17.5% is 10+5+2.5 on an awkward base.
        pct, base = {
            1: (rng.choice([10, 50]), rng.choice([80, 200, 240, 300])),
            2: (rng.choice([20, 25, 30]), rng.choice([120, 240, 360])),
            3: (rng.choice([35, 45, 15]), rng.choice([240, 480, 620])),
            4: (rng.choice([17.5, 12.5, 65]), rng.choice([480, 3480, 1240])),
            5: (rng.choice([17.5, 87.5, 37.5]), rng.choice([3480, 5640, 2960])),
        }[difficulty]
        correct = base * pct / 100
        correct_s = f"{correct:g}"
        near_pct = pct + 5 if pct < 90 else pct - 5
        return Item(
            stem=f"What is {pct:g}% of {base:,}?",
            options=shuffled_options(rng, correct_s, [
                f"{base * near_pct / 100:g}",
                f"{correct * 10:g}",
                f"{base / pct if pct else 0:g}",
            ]),
            difficulty=difficulty,
            params={"pct": pct, "base": base},
            explanation=(f"10% of {base:,} is {base / 10:g}, so {pct:g}% is "
                         f"{correct_s}."),
            misconceptions={
                f"{base * near_pct / 100:g}": "used-the-wrong-percentage",
                f"{correct * 10:g}": "misplaced-the-decimal-point",
                f"{base / pct if pct else 0:g}": "divided-instead-of-multiplying",
            },
        )


@register
class FractionOfAmount(Generator):
    slug = "mat.frac-of"
    section, subtopic = "MAT", "Fractions, Decimals & Percentages"
    template_id = "fraction-of-amount"
    difficulties = (1, 2, 3, 4)

    def build(self, rng, difficulty):
        # DIFFICULTY: unit fractions are one division; non-unit fractions need the
        # second multiply, which is the step pupils skip.
        den = {1: rng.choice([2, 4]), 2: rng.choice([3, 5]),
               3: rng.choice([8, 6]), 4: rng.choice([7, 9, 12])}[difficulty]
        num = 1 if difficulty <= 1 else rng.randint(2, den - 1)
        base = den * rng.randint(4, 30)
        correct = base * num // den
        # With a unit fraction of a half, "stopped after dividing" and "found the
        # other part" both land on the correct answer, and shuffled_options drops
        # them as duplicates — leaving too few choices. Extra error modes that
        # cannot collide keep every difficulty at four options.
        distractors = [
            base // den,               # stopped after dividing
            base - correct,            # found the remaining part
            correct * den,             # multiplied back up
            base // (den + 1),         # used the wrong denominator
            correct + den,             # arithmetic slip
        ]
        return Item(
            stem=f"What is {num}/{den} of {base:,}?",
            options=shuffled_options(rng, correct, distractors),
            difficulty=difficulty,
            params={"num": num, "den": den, "base": base},
            explanation=(f"{base:,} ÷ {den} = {base // den}, then × {num} = {correct}."),
            misconceptions={
                str(base // den): "found-one-part-then-stopped",
                str(base - correct): "found-the-other-part-of-the-whole",
            },
        )


# --------------------------------------------------------------- Ratio

@register
class ShareInRatio(Generator):
    slug = "mat.ratio-share"
    section, subtopic = "MAT", "Ratio & Proportion"
    template_id = "share-in-ratio"

    def build(self, rng, difficulty):
        # DIFFICULTY: two-part ratios with a whole-pound share are easiest;
        # three-part ratios and awkward totals are hardest.
        names = rng.sample(["Sam", "Tia", "Amir", "Nina", "Leo", "Priya"], 3)
        if difficulty <= 3:
            a, b = rng.choice([(2, 3), (3, 5), (4, 5), (5, 7)][:1 + difficulty])
            parts, total_parts = [a, b], a + b
        else:
            a, b, cc = rng.choice([(1, 2, 3), (2, 3, 5), (3, 4, 5)])
            parts, total_parts = [a, b, cc], a + b + cc
        unit = rng.randint(3, 9) * (1 if difficulty >= 4 else 5)
        total = total_parts * unit
        who = rng.randrange(len(parts))
        correct = parts[who] * unit
        ratio = ":".join(str(p) for p in parts)
        who_names = ", ".join(names[:len(parts)])
        return Item(
            stem=(f"{who_names} share £{total:,} in the ratio {ratio}. "
                  f"How much does {names[who]} receive?"),
            options=shuffled_options(rng, _money(correct * 100), [
                _money(unit * 100),                       # gave one part
                _money((total - correct) * 100),          # gave everyone else's share
                _money(total // len(parts) * 100),        # split equally
            ]),
            difficulty=difficulty,
            params={"parts": parts, "unit": unit, "who": who},
            explanation=(f"There are {total_parts} equal parts, so each is "
                         f"£{total:,} ÷ {total_parts} = £{unit}. "
                         f"{names[who]} gets {parts[who]} × £{unit} = £{correct}."),
            misconceptions={
                _money(unit * 100): "gave-one-part-not-their-share",
                _money(total // len(parts) * 100): "split-equally-ignoring-the-ratio",
            },
        )


# --------------------------------------------------------------- Algebra

@register
class LinearEquation(Generator):
    slug = "mat.linear"
    section, subtopic = "MAT", "Algebra & Sequences"
    template_id = "solve-linear"

    def build(self, rng, difficulty):
        # DIFFICULTY: one operation, then two, then a negative solution, then
        # brackets — the standard progression, and each step is a distinct error.
        x = rng.randint(2, 12) * (-1 if difficulty >= 4 and rng.random() < 0.5 else 1)
        a = rng.randint(2, 9)
        b = rng.randint(3, 30)
        # Spares on every branch: several of these error modes coincide for
        # particular a/b/x (a=1, or b==x), and shuffled_options drops duplicates,
        # which would otherwise leave a two-option question.
        if difficulty == 1:
            stem, correct = f"x + {b} = {x + b}", x
            distractors = [x + b, x + 2 * b, b - x, x + 1, b]
        elif difficulty == 2:
            stem, correct = f"{a}x = {a * x}", x
            distractors = [a * x, a * x - a, x + a, x * a * a, x - 1]
        elif difficulty == 3:
            stem, correct = f"{a}x + {b} = {a * x + b}", x
            distractors = [a * x + b, (a * x + b) // a, x + b, x - b, x + a]
        else:
            stem, correct = f"{a}(x + {b}) = {a * (x + b)}", x
            distractors = [a * (x + b), x + b, (a * (x + b)) // a, x - b, x + a]
        return Item(
            stem=f"Solve for x.  {stem}",
            options=shuffled_options(rng, correct, [str(d) for d in distractors]),
            difficulty=difficulty,
            params={"stem": stem, "x": x},
            explanation=f"Undo each operation in turn: x = {correct}.",
            misconceptions={str(distractors[0]): "did-not-undo-the-operation"},
        )


@register
class LinearSequence(Generator):
    slug = "mat.sequence"
    section, subtopic = "MAT", "Algebra & Sequences"
    template_id = "linear-sequence"

    def build(self, rng, difficulty):
        # DIFFICULTY: ascending small steps, then larger, then descending — a
        # negative common difference is where the pattern-spotting breaks.
        step = {1: rng.randint(2, 5), 2: rng.randint(3, 9), 3: rng.randint(6, 15),
                4: -rng.randint(3, 9), 5: -rng.randint(7, 19)}[difficulty]
        first = rng.randint(2, 40) + (60 if step < 0 else 0)
        terms = [first + i * step for i in range(5)]
        correct = first + 5 * step
        return Item(
            stem=(f"What is the next number in this sequence?  "
                  f"{', '.join(str(t) for t in terms)}, ___"),
            options=shuffled_options(rng, correct, [
                terms[-1] + (step + 1),      # miscounted the step
                terms[-1] - step,            # went the wrong way
                terms[-1] + 2 * step,        # skipped a term
            ]),
            difficulty=difficulty,
            params={"first": first, "step": step},
            explanation=(f"Each term changes by {step:+d}, so the next is "
                         f"{terms[-1]} {'+' if step >= 0 else '−'} {abs(step)} = {correct}."),
            misconceptions={str(terms[-1] - step): "applied-the-step-backwards"},
        )


# --------------------------------------------------------------- Measurement

@register
class MetricConversion(Generator):
    slug = "mat.metric"
    section, subtopic = "MAT", "Measurement"
    template_id = "metric-conversion"

    def build(self, rng, difficulty):
        # DIFFICULTY: single ×1000 step, then ×100, then two steps, then decimals.
        table = {
            1: [("m", "cm", 100), ("kg", "g", 1000), ("l", "ml", 1000)],
            2: [("cm", "mm", 10), ("km", "m", 1000)],
            3: [("m", "mm", 1000), ("kg", "mg", 1000000)],
            4: [("km", "cm", 100000), ("l", "cl", 100)],
            5: [("km", "mm", 1000000), ("t", "g", 1000000)],
        }[difficulty]
        big, small, factor = rng.choice(table)
        value = rng.choice([1.5, 2.4, 3, 4.75, 6, 12.5]) if difficulty >= 4 else rng.randint(2, 40)
        correct = value * factor
        return Item(
            stem=f"Convert {value:g} {big} into {small}.",
            options=shuffled_options(rng, f"{correct:g}", [
                f"{value / factor:g}",       # divided instead of multiplied
                f"{correct * 10:g}",         # place-value slip
                f"{correct / 10:g}",
            ]),
            difficulty=difficulty,
            params={"value": value, "big": big, "small": small},
            explanation=f"1 {big} = {factor:,} {small}, so {value:g} × {factor:,} = {correct:g}.",
            misconceptions={
                f"{value / factor:g}": "divided-instead-of-multiplying",
                f"{correct * 10:g}": "misplaced-the-decimal-point",
            },
        )


@register
class TimeInterval(Generator):
    slug = "mat.time"
    section, subtopic = "MAT", "Measurement"
    template_id = "time-interval"
    difficulties = (1, 2, 3, 4)

    def build(self, rng, difficulty):
        # DIFFICULTY: whether the interval crosses an hour, and then midnight —
        # base-60 plus a wrap is the real obstacle, not the arithmetic.
        start_h = rng.randint(6, 21 if difficulty < 4 else 23)
        start_m = rng.choice([0, 15, 30, 45] if difficulty == 1 else [5, 12, 25, 37, 45, 52])
        dur_m = {1: rng.choice([30, 45, 60]), 2: rng.randint(40, 110),
                 3: rng.randint(70, 200), 4: rng.randint(120, 400)}[difficulty]
        total = start_h * 60 + start_m + dur_m
        end_h, end_m = (total // 60) % 24, total % 60
        correct = f"{end_h:02d}:{end_m:02d}"
        # The classic error: treating the minutes as decimal, so 1h50m "ends" 1.5h on.
        decimal_total = start_h * 60 + start_m + (dur_m // 60) * 100 + dur_m % 60
        return Item(
            stem=(f"A film starts at {start_h:02d}:{start_m:02d} and lasts "
                  f"{dur_m // 60} hour{'s' if dur_m // 60 != 1 else ''} "
                  f"{dur_m % 60} minutes. What time does it finish?"),
            options=shuffled_options(rng, correct, [
                f"{(decimal_total // 60) % 24:02d}:{decimal_total % 60:02d}",
                f"{(end_h + 1) % 24:02d}:{end_m:02d}",
                f"{end_h:02d}:{(end_m + 10) % 60:02d}",
            ]),
            difficulty=difficulty,
            params={"start": start_h * 60 + start_m, "dur": dur_m},
            explanation=(f"{start_h:02d}:{start_m:02d} plus {dur_m // 60}h is "
                         f"{(start_h + dur_m // 60) % 24:02d}:{start_m:02d}, "
                         f"then {dur_m % 60} more minutes gives {correct}."),
            misconceptions={
                f"{(decimal_total // 60) % 24:02d}:{decimal_total % 60:02d}":
                    "treated-minutes-as-decimal",
            },
        )


# --------------------------------------------------------------- Geometry

@register
class RectanglePerimeterArea(Generator):
    slug = "mat.rect"
    section, subtopic = "MAT", "Perimeter, Area & Volume"
    template_id = "rect-perimeter-area"

    def build(self, rng, difficulty):
        # DIFFICULTY: whole numbers, then larger, then a missing side to find
        # first, then decimals. Confusing perimeter with area is the misconception
        # the distractors are built around.
        w = rng.randint(3, 12 if difficulty <= 2 else 40)
        h = rng.randint(3, 12 if difficulty <= 2 else 40)
        if difficulty >= 5:
            w, h = w + 0.5, h + 0.5
        want_area = difficulty in (2, 4)
        area, perim = w * h, 2 * (w + h)
        correct = area if want_area else perim
        return Item(
            stem=(f"A rectangle measures {w:g} cm by {h:g} cm. "
                  f"What is its {'area' if want_area else 'perimeter'}?"),
            # Spares: for a square, or when w+h happens to equal the perimeter
            # measure, several of these error modes land on the same value.
            options=shuffled_options(rng, f"{correct:g}", [
                f"{(perim if want_area else area):g}",   # the other measure
                f"{w + h:g}",                            # added the sides once
                f"{(area / 2 if want_area else perim * 2):g}",
                f"{correct * 2:g}",
                f"{(w * 2 if want_area else w * h * 2):g}",
            ]),
            difficulty=difficulty,
            params={"w": w, "h": h, "area": want_area},
            explanation=(f"Area is {w:g} × {h:g} = {area:g} cm². "
                         f"Perimeter is 2 × ({w:g} + {h:g}) = {perim:g} cm."),
            misconceptions={
                f"{(perim if want_area else area):g}": "confused-area-with-perimeter",
                f"{w + h:g}": "added-two-sides-only",
            },
        )


@register
class AnglesOnLine(Generator):
    slug = "mat.angles"
    section, subtopic = "MAT", "2D Shapes & Angles"
    template_id = "angles-on-a-line"
    difficulties = (1, 2, 3, 4)

    def build(self, rng, difficulty):
        # DIFFICULTY: one unknown on a straight line, then in a triangle, then
        # around a point — each has a different angle sum to remember.
        setting, total = {
            1: ("on a straight line", 180), 2: ("in a triangle", 180),
            3: ("around a point", 360), 4: ("in a quadrilateral", 360),
        }[difficulty]
        n_known = 1 if difficulty == 1 else (2 if total == 180 else 3)
        known = []
        remaining = total
        for i in range(n_known):
            a = rng.randint(20, max(25, (remaining - 20) // (n_known - i)))
            known.append(a)
            remaining -= a
        correct = remaining
        listed = ", ".join(f"{k}°" for k in known)
        return Item(
            stem=(f"The angles {setting} are {listed} and x. "
                  f"Work out x. (Not drawn to scale.)"),
            options=shuffled_options(rng, f"{correct}°", [
                f"{abs(360 - total + correct)}°",   # used the wrong angle sum
                f"{sum(known)}°",                   # gave the known total
                f"{correct + 10}°",
            ]),
            difficulty=difficulty,
            params={"known": known, "total": total},
            explanation=(f"Angles {setting} add up to {total}°. "
                         f"{total} − {' − '.join(str(k) for k in known)} = {correct}°."),
            figure={"kind": "angles_on_line", "data": {}} if difficulty == 1 else None,
            misconceptions={f"{abs(360 - total + correct)}°": "used-the-wrong-angle-sum"},
        )


# --------------------------------------------------------------- Statistics

@register
class MeanMedianRange(Generator):
    slug = "mat.averages"
    section, subtopic = "MAT", "Statistics & Data"
    template_id = "mean-median-range"

    def build(self, rng, difficulty):
        # DIFFICULTY: which average, how many values, and whether the mean is a
        # whole number. Mixing up mean/median/range is the whole point here.
        n = {1: 5, 2: 5, 3: 6, 4: 7, 5: 8}[difficulty]
        values = sorted(rng.randint(1, 20 if difficulty <= 2 else 60) for _ in range(n))
        want = {1: "mean", 2: "range", 3: "median", 4: "mean", 5: "median"}[difficulty]
        if want == "mean":
            # Nudge the total so the mean is exact — a recurring decimal tests
            # division, not averages.
            values[-1] += (-sum(values)) % n
            values.sort()
        total = sum(values)
        mean = total / n
        median = (values[n // 2] if n % 2 else (values[n // 2 - 1] + values[n // 2]) / 2)
        rng_val = values[-1] - values[0]
        correct = {"mean": mean, "median": median, "range": rng_val}[want]
        others = {"mean": mean, "median": median, "range": rng_val}
        distractors = [f"{v:g}" for k, v in others.items() if k != want] + [f"{total:g}"]
        return Item(
            stem=(f"Find the {want} of these numbers:  "
                  f"{', '.join(str(v) for v in values)}"),
            options=shuffled_options(rng, f"{correct:g}", distractors),
            difficulty=difficulty,
            params={"values": values, "want": want},
            explanation={
                "mean": f"Total {total} ÷ {n} values = {mean:g}.",
                "median": f"In order, the middle value is {median:g}.",
                "range": f"Largest {values[-1]} − smallest {values[0]} = {rng_val}.",
            }[want],
            misconceptions={f"{others['mean']:g}": "found-the-mean-instead",
                            f"{others['median']:g}": "found-the-median-instead",
                            f"{others['range']:g}": "found-the-range-instead"},
        )


@register
class SimpleProbability(Generator):
    slug = "mat.probability"
    section, subtopic = "MAT", "Probability"
    template_id = "probability-fraction"
    difficulties = (1, 2, 3, 4)

    def build(self, rng, difficulty):
        # DIFFICULTY: whether the fraction needs simplifying, and whether the
        # favourable set is a combination of colours.
        colours = ["red", "blue", "green", "yellow"]
        counts = [rng.randint(2, 9) for _ in range(2 if difficulty <= 2 else 3)]
        picked = colours[:len(counts)]
        total = sum(counts)
        if difficulty >= 3:
            want_n = counts[0] + counts[1]
            want_label = f"{picked[0]} or {picked[1]}"
        else:
            want_n = counts[0]
            want_label = picked[0]
        from math import gcd
        g = gcd(want_n, total)
        correct = f"{want_n // g}/{total // g}"
        listing = ", ".join(f"{c} {p}" for c, p in zip(counts, picked))
        return Item(
            stem=(f"A bag holds {listing} counters. One counter is taken at random. "
                  f"What is the probability it is {want_label}?"),
            options=shuffled_options(rng, correct, [
                f"{want_n}/{total - want_n}",   # odds, not probability
                f"{total - want_n}/{total}",    # the complement
                f"{want_n}/{total + 1}",
            ]),
            difficulty=difficulty,
            params={"counts": counts, "want": want_label},
            explanation=(f"{want_n} of the {total} counters are {want_label}, "
                         f"so the probability is {correct}."),
            misconceptions={
                f"{want_n}/{total - want_n}": "wrote-odds-not-probability",
                f"{total - want_n}/{total}": "found-the-complement",
            },
        )
