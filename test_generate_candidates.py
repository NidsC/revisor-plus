"""
Regression guard for generate_candidates.py's CLI hardening: --handle
validation and the --into naming warning.

Run:  python3 test_generate_candidates.py

Stdlib only, no Django, matching generate_candidates.py's own posture.
Tests the real functions directly (no shelling out) plus one end-to-end CLI
invocation each, to confirm the validation is actually wired into both
`generate` and `accept`, not just defined and unused.
"""
import io
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "elevenplus_data"))

from generate_candidates import validate_handle, warn_if_not_contrib_pack  # noqa: E402

fails = []


def ck(label, cond, extra=""):
    print(f"  [{'OK  ' if cond else 'FAIL'}] {label}" + (f" — {extra}" if extra else ""))
    if not cond:
        fails.append(label)


def exits_with_error(fn, *args):
    """Call fn(*args), expecting sys.exit(str). Returns the message, or None
    if it didn't exit."""
    buf = io.StringIO()
    old = sys.stderr
    sys.stderr = buf
    try:
        fn(*args)
        return None
    except SystemExit as e:
        return str(e.code)
    finally:
        sys.stderr = old


print("== validate_handle: rejects path components, accepts bare identifiers ==")
for bad in ["../../../../tmp/pwned", "/tmp/pwned", "sub/dir", "..", "has space",
            "trailing/", ""]:
    msg = exits_with_error(validate_handle, bad)
    ck(f"{bad!r} is rejected", msg is not None, f"got no error, expected one")

for good in ["alex", "prash-vr-01", "handle_2", "ABC123"]:
    msg = exits_with_error(validate_handle, good)
    ck(f"{good!r} is accepted", msg is None, msg or "")


print("\n== warn_if_not_contrib_pack: warns on non-matching names, silent on real ones ==")


def captures_warning(path):
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        warn_if_not_contrib_pack(path)
    finally:
        sys.stdout = old
    return buf.getvalue()


for bad_path in ["/tmp/scratch.json", "/tmp/contrib_no_json_ext",
                  "/tmp/not_contrib_prefixed.json"]:
    out = captures_warning(bad_path)
    ck(f"{bad_path!r} triggers a WARNING", "WARNING" in out, out)

for good_path in ["/tmp/contrib_alex_vr_01.json", "elevenplus_data/contrib_x_01.json"]:
    out = captures_warning(good_path)
    ck(f"{good_path!r} produces no warning", out == "", out)


print("\n== end-to-end: `generate` rejects a hostile --handle before writing anything ==")
with tempfile.TemporaryDirectory() as tmp:
    hostile_target = os.path.join(tmp, "pwned.json")
    result = subprocess.run(
        [sys.executable, "elevenplus_data/generate_candidates.py", "generate", "VR",
         "--handle", "../../../../../../../../tmp/pwned", "--spread", "5"],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        capture_output=True, text=True,
    )
    ck("CLI exits non-zero", result.returncode != 0, str(result.returncode))
    ck("error message names the bad --handle", "--handle" in result.stderr, result.stderr)
    ck("nothing was written outside elevenplus_data/", not os.path.exists("/tmp/pwned.json"))


print("\n== end-to-end: `accept` warns (not blocks) on a non-contrib --into, still accepts ==")
with tempfile.TemporaryDirectory() as tmp:
    candidates_path = os.path.join(tmp, "_candidates_t_vr.json")
    target_path = os.path.join(tmp, "scratch_target.json")  # deliberately not contrib_*.json
    json.dump({
        "section": {"code": "VR", "name": "Verbal Reasoning",
                    "source": "CONTRIB-T-CANDIDATES", "is_placeholder": False},
        "questions": [{"ref": "T-1", "number": "1", "subtopic": "Letter Codes",
                       "difficulty": 3, "stem": "x",
                       "options": [{"text": "a", "correct": True}, {"text": "b"}]}],
        "_draw_count": 1,
    }, open(candidates_path, "w"))
    json.dump({
        "section": {"code": "VR", "name": "Verbal Reasoning",
                    "source": "CONTRIB-T-01", "is_placeholder": False},
        "questions": [],
    }, open(target_path, "w"))

    result = subprocess.run(
        [sys.executable, "elevenplus_data/generate_candidates.py", "accept",
         "--candidates", candidates_path, "--into", target_path, "--all"],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        capture_output=True, text=True,
    )
    ck("CLI still succeeds (warn, not block)", result.returncode == 0, result.stderr)
    ck("warning is printed", "WARNING" in result.stdout, result.stdout)
    ck("the question was actually accepted",
       json.load(open(target_path))["questions"] != [], "target pack still empty")


print()
if fails:
    print(f"RESULT: {len(fails)} FAILED")
    sys.exit(1)
print("RESULT: ALL PASSED")
