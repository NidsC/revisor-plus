#!/usr/bin/env python3
"""Move MCQ/cloze_gap/grouped_options answer keys so they stop clustering.

`validate_questions.py`'s `check_key_distribution` only warns — a hand- or
model-authored pack has nothing shuffling it the way `shuffled_options` in
`catalog/generators/__init__.py` shuffles a generated one, so a run of
identical key positions (famously twenty-five in a row, once) has to be
caught by an author eyeballing the file. This script does that mechanically:
it re-reads the same constants and the same check the validator uses, tries
random reorderings until that check comes back clean, and rewrites the file
in place — content, correctness and explanations untouched, only the order
of each question's options changes.

Usage:
    python3 elevenplus_data/rebalance_keys.py <pack.json> [pack2.json ...] [--seed N]

Run this after drafting a batch, before `validate_questions.py`.
"""
import argparse
import json
import random
import re
import sys

from validate_questions import (
    GROUPED_KINDS,
    POSITIONAL_KINDS,
    check_key_distribution,
)

MAX_ATTEMPTS = 500

# Text that names a literal option position — reordering a question like this
# would make its own explanation wrong, so such a question is left alone.
POSITION_REFERENCE = re.compile(
    r"\boption\s+[A-H]\b"
    r"|\b[A-H]\)"
    r"|\(\s*[A-H]\s*\)"
    r"|\b(first|second|third|fourth|last)\s+option\b"
    r"|\boption\s+(one|two|three|four)\b",
    re.IGNORECASE,
)


def question_text(q):
    """Every string a pupil or reviewer reads for this question, for the position-reference check."""
    yield q.get("stem", "")
    yield q.get("explanation", "")
    for opt in q.get("options") or []:
        if isinstance(opt, dict):
            yield opt.get("text", "")
            yield opt.get("misconception", "")
    for g in q.get("option_groups") or []:
        if not isinstance(g, dict):
            continue
        for opt in g.get("options") or []:
            if isinstance(opt, dict):
                yield opt.get("text", "")
                yield opt.get("misconception", "")


def references_a_position(q):
    return any(POSITION_REFERENCE.search(t) for t in question_text(q) if t)


def key_index(opts):
    if not isinstance(opts, list):
        return None
    for i, opt in enumerate(opts):
        if isinstance(opt, dict) and opt.get("correct") is True:
            return i
    return None


def collect_slots(questions):
    """[(label, options_list)] for every reorderable positional choice.

    Mirrors `key_positions()` in validate_questions.py: one slot per mcq/
    cloze_gap question, one slot per bracket of a grouped_options question.
    Skips anything without a marked correct option, and skips every slot of
    a question whose own text names a literal option letter.
    """
    slots = []
    skipped = []
    for idx, q in enumerate(questions):
        if not isinstance(q, dict):
            continue
        kind = q.get("kind", "mcq")
        label = q.get("ref") or f"q[{idx}]"

        if kind in GROUPED_KINDS:
            groups = q.get("option_groups") or []
            if references_a_position(q):
                if groups:
                    skipped.append(label)
                continue
            for n, g in enumerate(groups, start=1):
                if isinstance(g, dict) and key_index(g.get("options")) is not None:
                    slots.append((f"{label} bracket {n}", g["options"]))
            continue

        if kind not in POSITIONAL_KINDS:
            continue
        if key_index(q.get("options")) is None:
            continue
        if references_a_position(q):
            skipped.append(label)
            continue
        slots.append((label, q["options"]))
    return slots, skipped


def find_balanced_assignment(slots, seed):
    """A target index per slot for which check_key_distribution has nothing to say.

    Independent random placement, retried with a fresh seed until the exact
    check the validator runs comes back clean, or MAX_ATTEMPTS is exhausted —
    in which case the least-bad attempt is returned along with its warnings.
    """
    sizes = [len(options) for _, options in slots]
    labels = [label for label, _ in slots]
    rng = random.Random(seed)

    best = None
    for _ in range(MAX_ATTEMPTS):
        assignment = [rng.randrange(size) if size else 0 for size in sizes]
        positions = list(zip(labels, assignment))
        warnings = check_key_distribution(positions)
        if not warnings:
            return assignment, []
        if best is None or len(warnings) < len(best[1]):
            best = (assignment, warnings)
    return best if best else ([0] * len(slots), [])


def apply_assignment(slots, assignment):
    for (label, options), target in zip(slots, assignment):
        current = key_index(options)
        if current is None or current == target:
            continue
        opt = options.pop(current)
        options.insert(target, opt)


def rebalance(path, seed):
    with open(path, encoding="utf-8") as f:
        pack = json.load(f)

    questions = pack.get("questions") or []
    slots, skipped = collect_slots(questions)

    if not slots:
        print(f"{path}: no reorderable positional questions found.")
        return

    assignment, warnings = find_balanced_assignment(slots, seed)
    apply_assignment(slots, assignment)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(pack, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"{path}: rebalanced {len(slots)} answer key(s).")
    if skipped:
        print(f"  Left untouched (text names a literal option position): {', '.join(skipped)}")
    if warnings:
        print("  Could not fully balance within the attempt limit — still warns:")
        for where, msg in warnings:
            print(f"    [{where}] {msg}")


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packs", nargs="+", help="pack JSON file(s) to rebalance in place")
    parser.add_argument("--seed", type=int, default=None, help="random seed, for a reproducible run")
    args = parser.parse_args(argv)

    for path in args.packs:
        rebalance(path, args.seed)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
