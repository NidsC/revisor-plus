"""
Exercises elevenplus_data/_packtools.py's helpers against hand-computed answers, then
runs scripts/tooling_gate.sh, which regenerates every pack generator's output and
compares it byte for byte with the committed pack (or a recorded sha256).

Run:  python3 test_packtools.py

Stdlib only, like the helpers themselves.
"""
import collections
import os
import random
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(REPO, "elevenplus_data"))

from _packtools import (answer_position_report, check_duplicates,  # noqa: E402
                        duplicate_refs, duplicate_stems, key_positions, renumber,
                        undeclared_group_refs)

fails = []


def ck(label, cond, extra=""):
    print(f"  [{'OK  ' if cond else 'FAIL'}] {label}" + (f" — {extra}" if extra else ""))
    if not cond:
        fails.append(label)


def no_run_of_three(seq):
    return all(seq[i] != seq[i + 1] or seq[i + 1] != seq[i + 2] for i in range(len(seq) - 2))


def original_key_positions(n, rng):
    """The loop that was copied into fourteen generators, verbatim, as the oracle."""
    base = [0, 1, 2, 3] * (n // 4) + list(range(n % 4))
    while True:
        rng.shuffle(base)
        if all(base[i] != base[i + 1] or base[i + 1] != base[i + 2]
               for i in range(len(base) - 2)):
            return base


print("key_positions")
got = key_positions(8, random.Random(1))
ck("n=8 is a permutation of [0,1,2,3]*2", sorted(got) == [0, 0, 1, 1, 2, 2, 3, 3], got)
ck("n=8 has no run of three", no_run_of_three(got))
ck("n=8 equals the original loop on a fresh Random(1)",
   got == original_key_positions(8, random.Random(1)))
shared, twin = random.Random(7), random.Random(7)
first, second = key_positions(11, shared), key_positions(11, shared)
ck("consumes the caller's rng exactly as the original did (two draws in a row)",
   (first, second) == (original_key_positions(11, twin), original_key_positions(11, twin)))
ck("rng state afterwards matches the original's", shared.random() == twin.random())
got3 = key_positions(7, random.Random(2), width=3)
ck("n=7 width=3 counts are {0:3, 1:2, 2:2}",
   dict(collections.Counter(got3)) == {0: 3, 1: 2, 2: 2}, got3)

print("renumber")
qs = [{"stem": "a"}, {"stem": "b"}]
out = renumber(qs, offset=1191)
ck("numbers and refs, in place and returned",
   out is qs and qs == [{"number": "1", "ref": "PRASH-VR-1192", "stem": "a"},
                        {"number": "2", "ref": "PRASH-VR-1193", "stem": "b"}], qs)
ck("key order is number, ref, stem", list(qs[0]) == ["number", "ref", "stem"], list(qs[0]))
ck("prefix and start are honoured",
   renumber([{"stem": "x"}], prefix="X-", offset=10, start=5)
   == [{"number": "5", "ref": "X-0015", "stem": "x"}])

print("duplicate checks")
ck("duplicate_stems", duplicate_stems({"x": 2, "y": 1}) == ["duplicate stem x2: 'x'"])
ck("duplicate_stems clean", duplicate_stems({"x": 1}) == [])
ck("duplicate_refs", duplicate_refs(["a", "a"]) == ["duplicate refs"])
ck("duplicate_refs clean", duplicate_refs(["a", "b"]) == [])
pack = {"groups": [{"group_ref": "G1"}]}
ck("undeclared_group_refs",
   undeclared_group_refs(pack, [{"ref": "R1", "group_ref": "G2"}, {"ref": "R2", "group_ref": "G1"}])
   == ["R1: group_ref 'G2' is not declared"])
ck("check_duplicates is the three in order",
   check_duplicates({"x": 2}, ["a", "a"], pack, [{"ref": "R1", "group_ref": "G2"}])
   == ["duplicate stem x2: 'x'", "duplicate refs", "R1: group_ref 'G2' is not declared"])

print("answer_position_report")
findings, dist, longest, cyclic = answer_position_report([0, 0, 0, 0, 1, 2, 3])
ck("a run of four is reported", longest == 4 and
   findings[0] == "answer position: run of 4 identical positions", findings)
ck("dist is the Counter", dict(dist) == {0: 4, 1: 1, 2: 1, 3: 1})
ck("an over-used position is reported",
   "answer position 0: 4 of 7 (expected ~2)" in findings, findings)
ck("empty positions: no findings, no raise", answer_position_report([]) == ([], collections.Counter(), 1, 0))
ck("empty positions without the guard read as cyclic with period 2 (the three originals' quirk)",
   answer_position_report([], guard_empty=False)[3] == 2)
findings, _, longest, cyclic = answer_position_report([0, 1, 0, 1], width=4)
ck("[0,1,0,1] is cyclic with period 2", cyclic == 2 and
   "answer position: cyclic with period 2" in findings, findings)
ck("low=0 switches the lower bound off",
   answer_position_report([0, 1, 2, 3, 4, 1, 0, 3, 2, 4, 0, 2], width=5, high=2, low=0)[0] == [])

print("tooling gate")
result = subprocess.run(["bash", os.path.join(REPO, "scripts", "tooling_gate.sh")],
                        env={**os.environ, "PYTHON": sys.executable},
                        capture_output=True, text=True, timeout=300)
print(result.stdout, end="")
last = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
ck("scripts/tooling_gate.sh exits 0", result.returncode == 0, last or result.stderr)

if fails:
    print("\nRESULT: FAILURES:", fails)
    raise SystemExit(1)
print("\nRESULT: all checks passed.")
