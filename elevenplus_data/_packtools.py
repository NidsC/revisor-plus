"""
Shared helpers for the question-pack generators and checkers in this folder.

The leading underscore is deliberate. build.sh imports only `contrib_*.json` and
`*-paper-*.json` from this folder, and the validator reads packs, not modules, so
neither ever sees this file; it is an importable module for `generate_*.py` and
`check_*.py`, which run as scripts from this folder and so find it on sys.path.
Standard library only.

Four helpers, each replacing a block that had been copied file to file:

  key_positions(n, rng, width=4)   the shuffle-until-no-run-of-three picker
  renumber(questions, ...)         the number/ref renumbering loop
  duplicate_stems / duplicate_refs / undeclared_group_refs / check_duplicates
                                   the duplicate and group_ref checks
  answer_position_report(...)      the answer-position findings

Every helper reproduces the original text and the original random-call sequence
exactly; the pack generators' output and the checkers' printed reports are
byte-identical before and after (scripts/tooling_gate.sh proves it for the
generators).
"""

import collections


def key_positions(n, rng, width=4):
    """An even spread of `n` key positions 0..width-1, with no run of three.

    Replaces the eleven `key_positions` / `_even_slots` copies and the three inline
    copies in the generators. It takes the caller's module-level `rng` and makes
    the same `rng.shuffle(base)` calls in the same order as every original, so a
    seeded generator draws exactly the numbers it drew before.
    """
    base = list(range(width)) * (n // width) + list(range(n % width))
    while True:
        rng.shuffle(base)
        if all(base[i] != base[i + 1] or base[i + 1] != base[i + 2]
               for i in range(len(base) - 2)):
            return base


def renumber(questions, prefix="PRASH-VR-", offset=0, start=1):
    """Give each question a leading "number" and "ref", in place, and return the list.

    Replaces the renumbering loop in sixteen generators. Each dict is rebuilt with
    "number" first, "ref" second and the question's own keys after, which is the
    key order the packs have always had.
    """
    for i, q in enumerate(questions, start=start):
        ordered = {"number": str(i), "ref": f"{prefix}{offset + i:04d}"}
        ordered.update(q)
        questions[i - start] = ordered
    return questions


def duplicate_stems(stems):
    """Findings for every stem seen more than once (`stems` maps stem -> count)."""
    return [f"duplicate stem x{n}: {s!r}" for s, n in stems.items() if n > 1]


def duplicate_refs(refs):
    """Findings for a repeated ref (a one-element list, or empty)."""
    return ["duplicate refs"] if len(set(refs)) != len(refs) else []


def undeclared_group_refs(pack, qs):
    """Findings for each question whose group_ref the pack does not declare."""
    group_refs = {g["group_ref"] for g in pack.get("groups", [])}
    return [f"{q.get('ref')}: group_ref {q.get('group_ref')!r} is not declared"
            for q in qs if q.get("group_ref") not in group_refs]


def check_duplicates(stems, refs, pack, qs):
    """The three duplicate checks in the order the checkers ran them.

    Replaces the stems -> refs -> group_ref block in eighteen checkers. A checker
    that runs a local check between those pieces calls the three pieces itself at
    the same points, so its findings keep their order.
    """
    return duplicate_stems(stems) + duplicate_refs(refs) + undeclared_group_refs(pack, qs)


def answer_position_report(positions, width=4, high=1.7, low=0.5, max_run=3,
                           guard_empty=True):
    """The answer-position checks every MCQ checker ran over its key positions.

    Returns (findings, dist, longest, cyclic): the findings in the order the
    checkers appended them (a run longer than `max_run`, then a cycle of period
    2-5, then each position used more than `high` or fewer than `low` times its
    even share of len(positions) / width), plus the three values the checkers
    print below. `low=0` switches the lower bound off. An empty list is not
    cyclic and does not raise.

    `guard_empty=False` keeps one quirk of three originals (check_directions,
    check_number_codes, check_triplet_rules): they had no `positions and` guard, so
    an empty list read as "cyclic with period 2" when one of them was run over a
    pack with no MCQs. Their printed output over such a pack is kept byte for byte.
    """
    findings = []
    dist = collections.Counter(positions)
    run = longest = 1
    for a, b in zip(positions, positions[1:]):
        run = run + 1 if a == b else 1
        longest = max(longest, run)
    cyclic = next((p for p in (2, 3, 4, 5)
                   if (positions or not guard_empty) and all(positions[i] == positions[i % p]
                                        for i in range(len(positions)))), 0)
    expected = len(positions) / width
    if longest > max_run:
        findings.append(f"answer position: run of {longest} identical positions")
    if cyclic:
        findings.append(f"answer position: cyclic with period {cyclic}")
    for pos, c in dist.items():
        if c > expected * high or c < expected * low:
            findings.append(f"answer position {pos}: {c} of {len(positions)} "
                            f"(expected ~{expected:.0f})")
    return findings, dist, longest, cyclic
