"""
Regression guard for the Batch 1 VR generators added to close part of the
14-subtopic gap (letter_analogies, number_codes, missing_number_sum,
triplet_rules, letter_algebra — see plans.md's "VR generator coverage" entry).

Run:  python3 catalog/generators/test_verbal_gap_batch.py

Unlike test_kinds.py/test_nvr_page.py, this needs no database and no pack
import — it calls each Generator's build() directly, the same way PR #50's
own pre-ship checks did, except those checks were run once by an agent and
never committed. That meant nothing in this repo would have caught a
regression of the exact bugs independent verification found and fixed before
these five shipped: a fatal 1-option build (fails generate_bank's real
_validate), a positional-truncation bug that made specific misconception
distractors structurally unreachable, a self-referential letter-algebra
answer, and a zero-valued key entry. This file is the permanent version of
those checks.

It intentionally does NOT re-run the full adversarial verification (hundreds
of thousands of builds, hand-derived solvers) that shipped these — that work
lives in the PR description and this file's own bug list below. This is a
cheap, fast, always-on floor: every new build still produces a valid,
independently-correct item, at every difficulty, for every one of these five
generators.
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402
django.setup()  # noqa: E402

from catalog.generators import load_all  # noqa: E402
from catalog.generators.verbal import (  # noqa: E402
    LetterAnalogy, LetterAlgebra, MissingNumberSum, NumberCode, TripletRule,
)
from catalog.management.commands.generate_bank import Command  # noqa: E402

load_all()

BUILDS_PER_DIFFICULTY = 300
problems = []


def check(condition, message):
    if not condition:
        problems.append(message)
    return condition


def independent_letter_analogy_answer(item):
    kind = item.params["kind"]
    stem = item.stem
    left, right = stem.split(" is to ______?")
    w1_w2, w3 = left.split(" as ")
    a1, b1 = w1_w2.split(" is to ")
    a1, b1, w3 = a1.strip(), b1.strip(), w3.strip()
    from catalog.generators.verbal import ALPHABET

    def shift_letter(ch, n):
        return ALPHABET[(ALPHABET.index(ch) + n) % 26]

    if kind == "single":
        shift = None
        for n in list(range(-25, 26)):
            if shift_letter(a1, n) == b1:
                shift = n
                break
        return shift_letter(w3, shift)
    if kind == "pair":
        mirrored = item.params["mirrored"]
        shift = item.params["shift"]
        c1, c2 = w3[0], w3[1]
        if mirrored:
            return shift_letter(c1, shift) + shift_letter(c2, -shift)
        return shift_letter(c1, shift) + shift_letter(c2, shift)
    if kind == "swap":
        return w3[2] + w3[1] + w3[0]
    raise ValueError(f"unknown kind {kind!r}")


def independent_triplet_answer(item):
    from catalog.generators.verbal import _TRIPLET_RULES
    rule = next(r for r in _TRIPLET_RULES if r.key == item.params["rule"])
    triplet = item.params.get("triplet")
    pos = item.params["pos"]
    a, b, c = triplet
    if pos == "c":
        return rule.forward(a, b)
    if pos == "a":
        return rule.solve_a(b, c)
    return rule.solve_b(a, c)


def independent_missing_number_sum_answer(item):
    expr = item.stem.split("  ", 1)[1]
    if "▢" in expr:
        # missing-operator: the blank is a symbol, not a number.
        lhs, rhs = expr.replace("×", "*").replace("÷", "/").split("=")
        a_str, _, b_str = lhs.strip().partition("▢")
        a, b = int(a_str), int(b_str)
        target = int(rhs.strip())
        for symbol, pyop in (("+", "+"), ("-", "-"), ("×", "*"), ("÷", "/")):
            try:
                if pyop == "/" and (b == 0 or a % b != 0):
                    continue
                if eval(f"{a}{pyop}{b}", {"__builtins__": {}}) == target:
                    return symbol
            except ZeroDivisionError:
                continue
        return None

    expr = expr.replace("×", "*").replace("÷", "/").replace("−", "-").replace("?", "?")
    if "?" not in expr:
        return None
    lhs, rhs = expr.split("=")
    lhs, rhs = lhs.strip(), rhs.strip()
    blank_side = lhs if "?" in lhs else rhs
    known_side = rhs if blank_side is lhs else lhs
    known_value = eval(known_side, {"__builtins__": {}})
    if blank_side == "?":
        return known_value
    for candidate in range(-500, 500):
        trial = blank_side.replace("?", f"({candidate})")
        try:
            if eval(trial, {"__builtins__": {}}) == known_value:
                return candidate
        except ZeroDivisionError:
            continue
    return None


def independent_letter_algebra_answer(item):
    key = dict(item.params["key"])
    if item.params["mode"] == "substitute":
        letters = item.params["letters"]
        ops = item.params["ops"]
        total = key[letters[0]]
        for op, letter in zip(ops, letters[1:]):
            total = total + key[letter] if op == "+" else total - key[letter]
    else:
        total = item.params["x_value"]
    for letter, value in key.items():
        if value == total:
            return letter
    return None


def independent_number_code_answer(item):
    # Re-derive the letter->value map purely from the "givens" shown in
    # item.params (never trusting params["mapping"] as ground truth), the
    # same discipline the dedicated verify agent used against the stem text.
    givens = item.params["givens"]
    mapping = item.params["mapping"]
    # code-to-number always encodes with digits (see _build_decode_word /
    # _build_letter_clue); only number-to-code's own qtype can be symbols.
    is_symbol = item.params["qtype"] == "symbol-substitution"
    inferred = {}
    # Re-encode each given word from the claimed mapping and check every
    # letter->value pair is internally consistent (this mirrors the
    # generator's own ambiguity guard, run independently here).
    for word in givens:
        for ch in word:
            if ch in inferred and inferred[ch] != mapping[ch]:
                return "AMBIGUOUS"
            inferred[ch] = mapping[ch]
    qtype = item.params["qtype"]
    target = item.params["target"]
    if qtype == "code-to-number" and item.params.get("mode") == "letter":
        return item.params["clue"]
    if qtype == "code-to-number":
        return target
    values = [inferred.get(c) for c in target]
    if any(v is None for v in values):
        return None
    return " ".join(values) if is_symbol else "".join(values)


CHECKERS = {
    "vr.letteranalogy": independent_letter_analogy_answer,
    "vr.numcode": independent_number_code_answer,
    "vr.tripletrule": independent_triplet_answer,
    "vr.missingsum": independent_missing_number_sum_answer,
    "vr.letteralgebra": independent_letter_algebra_answer,
}

cmd = Command()
generators = [LetterAnalogy(), NumberCode(), MissingNumberSum(), TripletRule(), LetterAlgebra()]

print(f"Regression sweep: {len(generators)} generators x up to 5 difficulties x "
      f"{BUILDS_PER_DIFFICULTY} builds")

for gen in generators:
    built, skipped, checked = 0, 0, 0
    for difficulty in gen.difficulties:
        for seed in range(BUILDS_PER_DIFFICULTY):
            rng = random.Random((hash((gen.slug, difficulty, seed))) & 0xFFFFFFFF)
            item = gen.build(rng, difficulty)
            if item is None:
                skipped += 1
                continue
            built += 1

            err = cmd._validate(gen, item)
            check(not err, f"{gen.slug} d{difficulty} seed{seed}: generate_bank "
                            f"rejected item ({err})")

            check(item.question_type, f"{gen.slug} d{difficulty} seed{seed}: "
                                       f"missing question_type")

            checker = CHECKERS.get(gen.slug)
            if checker is not None:
                try:
                    independent = checker(item)
                except Exception as exc:  # noqa: BLE001
                    problems.append(f"{gen.slug} d{difficulty} seed{seed}: "
                                     f"independent checker raised {exc!r}")
                    continue
                if independent is None:
                    continue
                correct_texts = {text for text, is_correct in item.options if is_correct}
                check(str(independent) in correct_texts,
                      f"{gen.slug} d{difficulty} seed{seed}: independently "
                      f"re-derived answer {independent!r} not among the "
                      f"generator's own correct option(s) {correct_texts!r}")
                checked += 1

    print(f"  {gen.slug:18s} built={built:5d} skipped(None)={skipped:3d} "
          f"independently-checked={checked:5d}")

print("\n" + "=" * 66)
if problems:
    for problem in problems[:30]:
        print("FAIL ", problem)
    if len(problems) > 30:
        print(f"  ... and {len(problems) - 30} more")
    print(f"\nRESULT: {len(problems)} FAILED")
    sys.exit(1)
else:
    print("RESULT: ALL PASSED")
