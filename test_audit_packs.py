"""
Regression guard for audit_packs.py's difficulty handling.

Run:  python3 test_audit_packs.py

Covers the bug found and fixed this session: a question with a missing/None
`difficulty` crashed two separate checks in audit_packs.py --
`sorted(diff.items())` in the difficulty-spread check ([2], a TypeError
comparing None against int) and `q["difficulty"]` direct key access in
type_seq (a KeyError), used by the cross-pack question-skeleton check ([6]).
Both are advisory-only findings -- validate_questions.py remains the real
import gate and already requires `difficulty` on every question -- but an
advisory tool should degrade to a clean warning, not crash.

Stdlib only, no Django, matching audit_packs.py's own posture.
"""
import io
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from audit_packs import audit_pack, type_seq, type_seq_check  # noqa: E402

fails = []


def ck(label, cond, extra=""):
    print(f"  [{'OK  ' if cond else 'FAIL'}] {label}" + (f" — {extra}" if extra else ""))
    if not cond:
        fails.append(label)


def q(ref, subtopic="Paired Antonyms", question_type="opposite-pair", difficulty=3,
      correct_index=0, n_options=3):
    return {
        "ref": ref, "subtopic": subtopic, "question_type": question_type,
        "stem": f"Stem for {ref}",
        "options": [{"text": f"{ref}-opt{i}", "correct": i == correct_index}
                    for i in range(n_options)],
        "difficulty": difficulty,
    }


def run_audit_pack(qs, target=None):
    """audit_pack() prints its report as a side effect -- capture stdout so
    the test output stays readable and to let a future assertion inspect the
    printed [2] line if needed."""
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        errs, warns = audit_pack("synthetic.json", {"questions": qs}, target)
    finally:
        sys.stdout = old
    return errs, warns, buf.getvalue()


print("== [2] difficulty spread: a missing/None difficulty must not crash the sort ==")
qs = [q("T-1", difficulty=3), q("T-2")]
del qs[1]["difficulty"]  # simulate a question that never got a difficulty field at all
try:
    errs, warns, out = run_audit_pack(qs)
    ck("audit_pack() completes without raising", True)
except TypeError as e:
    ck("audit_pack() completes without raising", False, str(e))
    errs, warns, out = [], [], ""

ck("the missing-difficulty question is reported as a warning, not silently dropped",
   any("missing difficulty" in w for w in warns), str(warns))
ck("the real difficulty value (3) still appears in the printed band count",
   "bands(1-2/3/4/5)=(0, 1, 0, 0)" in out, out)
ck("the printed 'raw' dict excludes the None entry (no None/int mix to sort)",
   "raw {3: 1}" in out, out)

print("\n== [2] a pack with no missing difficulty is unaffected (no false warning) ==")
qs_clean = [q("C-1", difficulty=3), q("C-2", difficulty=4)]
errs, warns, out = run_audit_pack(qs_clean)
ck("no 'missing difficulty' warning on a pack where every question has one",
   not any("missing difficulty" in w for w in warns), str(warns))

print("\n== [6] type_seq: a question missing 'difficulty' entirely must not KeyError ==")
with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
    q_missing = q("K-1", difficulty=0)
    del q_missing["difficulty"]
    json.dump({"section": {"code": "VR"}, "questions": [q_missing]}, f)
    tmp_path = f.name
try:
    try:
        seq = type_seq(tmp_path)
        ck("type_seq() completes without raising", True)
    except KeyError as e:
        ck("type_seq() completes without raising", False, str(e))
        seq = None
    ck("the missing difficulty becomes None in the skeleton tuple, not a crash",
       seq == (("opposite-pair", None),), str(seq))
finally:
    os.unlink(tmp_path)

print("\n== [6] type_seq_check still catches genuine duplicate skeletons ==")
with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as fa, \
     tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as fb:
    same = [q("D-1", difficulty=3), q("D-2", difficulty=4)]
    json.dump({"section": {"code": "VR"}, "questions": same}, fa)
    json.dump({"section": {"code": "VR"}, "questions": same}, fb)
    path_a, path_b = fa.name, fb.name
try:
    dup_errs = type_seq_check([path_a], [path_b])
    ck("identical type/difficulty sequences across two packs are still flagged",
       len(dup_errs) == 1 and "identical type/difficulty sequence" in dup_errs[0],
       str(dup_errs))
finally:
    os.unlink(path_a)
    os.unlink(path_b)

print()
if fails:
    print(f"RESULT: {len(fails)} FAILED")
    sys.exit(1)
print("RESULT: ALL PASSED")
