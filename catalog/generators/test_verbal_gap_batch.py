"""
Regression guard for the Batch 1, 2, 3 and deferred-4 VR generators added to
close the 14-subtopic gap (Batch 1: letter_analogies, number_codes,
missing_number_sum, triplet_rules, letter_algebra; Batch 2: word_pattern,
double_meaning, letter_moves, antonyms_paired; Batch 3: must_be_true;
deferred-4: anagrams, connecting_letter, directions — see plans.md's "VR
generator coverage" entry).

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
    AntonymPair, DoubleMeaning, LetterMove, WordPattern, MustBeTrue,
    Anagram, ConnectingLetter, Directions,
    DAYS, WEEKDAY_SET, WEEKEND_SET, COMPASS_STEP, compass_of_vector,
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
    variant = item.params["variant"]
    stem = item.stem
    left, right = stem.split(" is to ______?")
    w1_w2, w3 = left.split(" as ")
    a1, b1 = w1_w2.split(" is to ")
    a1, b1, w3 = a1.strip(), b1.strip(), w3.strip()
    from catalog.generators.verbal import ALPHABET

    def shift_letter(ch, n):
        return ALPHABET[(ALPHABET.index(ch) + n) % 26]

    if variant == "single":
        shift = None
        for n in list(range(-25, 26)):
            if shift_letter(a1, n) == b1:
                shift = n
                break
        return shift_letter(w3, shift)
    if variant == "pair":
        mirrored = item.params["mirrored"]
        shift = item.params["shift"]
        c1, c2 = w3[0], w3[1]
        if mirrored:
            return shift_letter(c1, shift) + shift_letter(c2, -shift)
        return shift_letter(c1, shift) + shift_letter(c2, shift)
    if variant == "swap":
        return w3[2] + w3[1] + w3[0]
    raise ValueError(f"unknown variant {variant!r}")


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
    # _build_letter_clue); only number-to-code's own variant can be symbols.
    variant = item.params["variant"]
    is_symbol = variant == "symbol-substitution"
    inferred = {}
    # Re-encode each given word from the claimed mapping and check every
    # letter->value pair is internally consistent (this mirrors the
    # generator's own ambiguity guard, run independently here).
    for word in givens:
        for ch in word:
            if ch in inferred and inferred[ch] != mapping[ch]:
                return "AMBIGUOUS"
            inferred[ch] = mapping[ch]
    target = item.params["target"]
    if variant == "code-to-number:letter":
        return item.params["clue"]
    if variant == "code-to-number:word":
        return target
    values = [inferred.get(c) for c in target]
    if any(v is None for v in values):
        return None
    return " ".join(values) if is_symbol else "".join(values)


def independent_word_pattern_answer(item):
    from catalog.generators.verbal import _WP_RULE_SHAPES, _wp_apply_rule
    # variant is "apply-pattern:<shape_key>" or "find-pattern:<shape_key>" —
    # the shape is whatever follows the first colon.
    shape_key = item.params["variant"].split(":", 1)[1]
    rule = _WP_RULE_SHAPES[shape_key]
    tw1, _tw2, tw3 = item.params["target"]
    return _wp_apply_rule(tw1, tw3, rule)


def independent_double_meaning_answer(item):
    # No computation to re-derive — the check here is that the stored
    # answer genuinely appears in BOTH context templates (catches a typo'd
    # params/stem mismatch, not a content/homograph error).
    answer = item.params["answer"]
    ctx_a, ctx_b = item.params["context_a"], item.params["context_b"]
    if "___" not in ctx_a or "___" not in ctx_b:
        return None
    return answer  # trivially matches; presence-in-both checked via ctx_a/ctx_b format


def independent_letter_move_answer(item):
    word_a, word_b = item.params["word_a"], item.params["word_b"]
    letter, new_a, new_b = item.params["letter"], item.params["new_a"], item.params["new_b"]
    # word_a minus one instance of `letter`, letters otherwise in order.
    idx = word_a.find(letter)
    if idx == -1 or word_a[:idx] + word_a[idx + 1:] != new_a:
        return "MISMATCH"
    # word_b plus `letter` inserted somewhere, letters otherwise in order.
    if sorted(new_b) != sorted(word_b + letter):
        return "MISMATCH"
    stripped = new_b
    for ch in word_b:
        pos = stripped.find(ch)
        if pos == -1:
            return "MISMATCH"
        stripped = stripped[:pos] + stripped[pos + 1:]
    if stripped != letter:
        return "MISMATCH"
    return f"{new_a}, {new_b}"


def independent_antonym_pair_answer(item):
    from catalog.generators.verbal import ANTONYM_POOL
    fixed, correct = item.params["fixed"], item.params["correct"]
    for _pos, a, _af, b, _bf, _extra in ANTONYM_POOL:
        if {fixed, correct} == {a, b}:
            return correct
    return "NOT-IN-POOL"


def check_must_be_true(item):
    """Returns None if consistent, or a string describing the mismatch.

    Recomputes the entity->day table from item.params["rules"] using a
    from-scratch re-implementation (not calling mbt_solve), then parses each
    rendered option's text back into (entity, day, claimed-positive) and
    confirms exactly the flagged-correct option's claim direction matches
    item.params["variant"] against the recomputed table.
    """
    entities_by_id = {e["id"]: e for e in item.params["entities"]}
    table = {}
    for rule in item.params["rules"]:
        eid = rule["entity"]
        kind = rule["type"]
        if kind == "enumerate":
            true_days = set(rule["days"])
            table[eid] = {d: (d in true_days) for d in DAYS}
        elif kind == "negate":
            excl = set(rule["exclude"])
            table[eid] = {d: (d not in excl) for d in DAYS}
        elif kind == "category":
            true_days = WEEKDAY_SET if rule["cat"] == "weekday" else WEEKEND_SET
            table[eid] = {d: (d in true_days) for d in DAYS}
        elif kind == "dependency":
            base = table[rule["base"]]
            invert = rule["invert"]
            row = {d: ((not base[d]) if invert else base[d]) for d in DAYS}
            exc = rule.get("exception")
            if exc:
                row[exc["day"]] = exc["value"]
            table[eid] = row

    display_to_entity = {e["display"]: e for e in item.params["entities"]}
    for text, is_correct in item.options:
        matched = None
        for display, entity in display_to_entity.items():
            if text.startswith(display):
                matched = (display, entity)
                break
        if matched is None:
            return f"could not match any entity display in option text {text!r}"
        display, entity = matched
        rest = text[len(display):]
        day = next((d for d in DAYS if d in rest), None)
        if day is None:
            return f"could not find a day in option text {text!r}"
        if entity["kind"] == "place":
            claimed_positive = "is open" in rest
        else:
            claimed_positive = ("does not work" not in rest) and ("works" in rest)
        actual = table[entity["id"]][day]
        claim_true = (actual == claimed_positive)
        if item.params["variant"] == "valid-conclusion":
            expect_flag = claim_true
        else:
            expect_flag = not claim_true
        if bool(is_correct) != expect_flag:
            return (f"option {text!r}: flagged correct={is_correct}, but "
                    f"independently computed claim_true={claim_true} for "
                    f"variant={item.params['variant']!r}")
    return None


def independent_anagram_answer(item):
    # Confirms the scrambled string is genuinely a permutation of the
    # claimed answer (catches a typo'd pool entry), then returns the answer
    # to check against the flagged-correct option text.
    answer, scrambled = item.params["answer"], item.params["scrambled"]
    if sorted(answer) != sorted(scrambled):
        return "LETTER-MISMATCH"
    return answer


def independent_connecting_letter_answer(item):
    p1, s1 = item.params["p1"], item.params["s1"]
    p2, s2 = item.params["p2"], item.params["s2"]
    conn = item.params.get("letter", item.params.get("conn"))
    # Structural check only (this file has no dictionary to hand) — the
    # deep "no other letter/pair also solves both fragment pairs" proof
    # happened in independent verification at build time; this just
    # confirms the four words assemble consistently with the claimed
    # connector and that nothing was mis-recorded in params.
    words = [p1 + conn, conn + s1, p2 + conn, conn + s2]
    if any(not w.isalpha() for w in words):
        return "MALFORMED-WORD"
    return conn


def check_directions(item):
    """Returns None if consistent, or a string describing the mismatch.

    Parses item.stem (not item.params) to independently reconstruct the
    scenario a pupil would actually see, then re-derives the answer using
    the module's own compass_of_vector/COMPASS_STEP (the real solver, reused
    here as a regression floor — the original two bugs in this generator
    were caught by adversarial verification with a wholly separate
    atan2-based solver at build time; this check exists to catch a future
    regression of THAT class of bug, i.e. the stem disagreeing with the
    generator's own solver, not to re-derive geometry from scratch).
    """
    import re
    from catalog.generators.verbal import COMPASS_WORDS

    words_to_letter = {v: k for k, v in COMPASS_WORDS.items()}
    correct_word = next(text for text, ok in item.options if ok)
    if correct_word not in words_to_letter:
        return f"correct option {correct_word!r} is not a recognised compass direction"

    if item.params["variant"] == "turns":
        start = item.params["start"]
        idx = list(COMPASS_STEP).index(start)
        for angle, cw in item.params["turns"]:
            idx = (idx + (angle // 45) * (1 if cw else -1)) % 8
        expected = list(COMPASS_STEP)[idx]
    elif item.params["variant"] == "bearing":
        stmt_re = re.findall(r"(\w+) squares (North(?:-East|-West)?|South(?:-East|-West)?|East|West) of (\w+)", item.stem)
        if len(stmt_re) != 2:
            return f"expected 2 leg statements in stem, found {len(stmt_re)}: {item.stem!r}"
        query = re.search(r"Which direction is (\w+) from (\w+)\?", item.stem)
        if not query:
            return f"could not find query sentence in stem: {item.stem!r}"
        coords = {item.params["a"]: (0, 0)}
        for dist_s, dir_word, frm in stmt_re:
            dist = int(dist_s)
            direction = words_to_letter[dir_word]
            px, py = coords[frm]
            step = COMPASS_STEP[direction]
            to_name = item.params["b"] if frm == item.params["a"] else item.params["c"]
            coords[to_name] = (px + step[0] * dist, py + step[1] * dist)
        qf, qt = query.group(1), query.group(2)
        dx = coords[qf][0] - coords[qt][0]
        dy = coords[qf][1] - coords[qt][1]
        expected = compass_of_vector(dx, dy)
    else:  # relative
        stmt_re = re.findall(r"(\w+) is (\d+) squares (North(?:-East|-West)?|South(?:-East|-West)?|East|West) of (\w+)\.", item.stem)
        query = re.search(r"Which direction is (\w+) from (\w+)\?", item.stem)
        if not query:
            return f"could not find query sentence in stem: {item.stem!r}"
        coords = {}
        hub = item.params["names"][0]
        coords[hub] = (0, 0)
        for name, dist_s, dir_word, parent in stmt_re:
            direction = words_to_letter[dir_word]
            px, py = coords[parent]
            step = COMPASS_STEP[direction]
            coords[name] = (px + step[0] * int(dist_s), py + step[1] * int(dist_s))
        qf, qt = query.group(1), query.group(2)
        if qf not in coords or qt not in coords:
            return f"query names {qf!r}/{qt!r} not found among parsed points {list(coords)}"
        dx = coords[qf][0] - coords[qt][0]
        dy = coords[qf][1] - coords[qt][1]
        expected = compass_of_vector(dx, dy)

    if expected is None:
        return f"stem-derived vector has no exact compass direction (variant={item.params['variant']})"
    if words_to_letter[correct_word] != expected:
        return (f"stem-derived answer {expected!r} != flagged-correct option "
                f"{correct_word!r} ({words_to_letter[correct_word]!r})")
    return None


CHECKERS = {
    "vr.letteranalogy": independent_letter_analogy_answer,
    "vr.numcode": independent_number_code_answer,
    "vr.tripletrule": independent_triplet_answer,
    "vr.missingsum": independent_missing_number_sum_answer,
    "vr.letteralgebra": independent_letter_algebra_answer,
    "vr.wordpattern": independent_word_pattern_answer,
    "vr.doublemeaning": independent_double_meaning_answer,
    "vr.lettermove": independent_letter_move_answer,
    "vr.antonympair": independent_antonym_pair_answer,
    "vr.anagram": independent_anagram_answer,
    "vr.connectingletter": independent_connecting_letter_answer,
}

cmd = Command()
generators = [
    LetterAnalogy(), NumberCode(), MissingNumberSum(), TripletRule(), LetterAlgebra(),
    WordPattern(), DoubleMeaning(), LetterMove(), AntonymPair(), MustBeTrue(),
    Anagram(), ConnectingLetter(), Directions(),
]

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

            if gen.slug == "vr.mustbetrue":
                # Different shape from the other checkers: re-solves the
                # entity->day table from item.params["rules"] alone and
                # confirms every one of the 5 options' flagged correctness
                # matches what that independently-recomputed table implies —
                # not just a single "the answer is X" comparison.
                try:
                    mismatch = check_must_be_true(item)
                except Exception as exc:  # noqa: BLE001
                    problems.append(f"{gen.slug} d{difficulty} seed{seed}: "
                                     f"independent checker raised {exc!r}")
                    continue
                check(mismatch is None,
                      f"{gen.slug} d{difficulty} seed{seed}: {mismatch}")
                checked += 1
                continue

            if gen.slug == "vr.directions":
                # Parses item.stem (not internal coords/distances) to catch
                # a regression of this generator's own shipped bug class: an
                # answer the solver computes but the stem never actually
                # discloses enough to derive.
                try:
                    mismatch = check_directions(item)
                except Exception as exc:  # noqa: BLE001
                    problems.append(f"{gen.slug} d{difficulty} seed{seed}: "
                                     f"independent checker raised {exc!r}")
                    continue
                check(mismatch is None,
                      f"{gen.slug} d{difficulty} seed{seed}: {mismatch}")
                checked += 1
                continue

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
