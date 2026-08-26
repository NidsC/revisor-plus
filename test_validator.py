"""
Checks the whole-pack rules in `elevenplus_data/validate_questions.py`.

Run:  python3 test_validator.py

Everything else the validator does is checked by running it over the template and
the example packs in CI, which works because those are real files with real
defects to not have. That does not work for a rule about the pack as a WHOLE —
"too many of your answers are option A" cannot be demonstrated by a file that is
also supposed to be the thing authors copy. So the pure functions behind that
rule are exercised here instead, on packs built in memory.

Stdlib only and no Django, matching the promise validate_questions.py's own
header makes: a contributor runs it, and a contributor cannot be asked to debug
an import error.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "elevenplus_data"))

from validate_questions import (  # noqa: E402
    KEY_RUN_LIMIT, KEY_SKEW_MIN, check_key_distribution, key_positions,
)

fails = []


def ck(label, cond, extra=""):
    print(f"  [{'OK  ' if cond else 'FAIL'}] {label}" + (f" — {extra}" if extra else ""))
    if not cond:
        fails.append(label)


def q(ref, correct_index, n_options=4, kind="mcq"):
    """One positional question with its key at `correct_index`."""
    return {
        "ref": ref, "kind": kind,
        "options": [{"text": f"{ref}-{i}", "correct": i == correct_index}
                    for i in range(n_options)],
    }


def messages(questions):
    return [m for _, m in check_key_distribution(key_positions(questions))]


print("== key_positions reads the key out of a pack ==")
pack = [q("A1", 0), q("A2", 2), q("A3", 3)]
ck("one entry per question, in file order",
   key_positions(pack) == [("A1", 0), ("A2", 2), ("A3", 3)])
ck("a question with no ref is named by its index",
   key_positions([{"kind": "mcq", "options": [{"text": "x", "correct": True}]}])
   == [("q[0]", 0)])
ck("a question with no key at all is skipped rather than crashing",
   key_positions([{"kind": "mcq", "options": [{"text": "x"}]}]) == [])
ck("a malformed entry is skipped rather than crashing",
   key_positions(["not a dict", None, q("OK", 1)]) == [("OK", 1)])

print("\n== the kinds it counts ==")
ck("cloze_gap counts — its options are answers offered for the gap",
   key_positions([q("C1", 1, kind="cloze_gap")]) == [("C1", 1)])
ck("numeric and short_text are not positional, so they are ignored",
   key_positions([{"ref": "N1", "kind": "numeric", "answer": "7"},
                  {"ref": "S1", "kind": "short_text", "answer": "gear"}]) == [])
# The reason this matters: a spot-the-error question's options are the pieces of
# its sentence, lettered left to right. The key cannot be moved without rewriting
# the sentence, so reporting a skew across a spelling section would be an
# instruction the author has no way to follow.
ck("error_span and select_word are excluded — their order is the sentence",
   key_positions([{"ref": "E1", "kind": "error_span",
                   "segments": [{"label": "A", "text": "x"}], "answer": "A"},
                  {"ref": "W1", "kind": "select_word",
                   "segments": [{"label": "A", "text": "y"}], "answer": "A"}]) == [])

print("\n== the reported symptom: 25 questions, every answer A ==")
all_a = [q(f"VR-{i:03d}", 0) for i in range(25)]
msgs = messages(all_a)
ck("both warnings fire", len(msgs) == 2, f"got {len(msgs)}")
ck("the run warning names the letter", any("in a row" in m and "option A" in m for m in msgs))
ck("the skew warning gives the share",
   any("25 of this pack's 25 answers are option A (100%)" in m for m in msgs))
# A run of 25 naming all 25 refs is a wall of text nobody reads to the end of.
ck("a long run is summarised rather than listed in full",
   any("… and 19 more" in m for m in msgs), msgs)

print("\n== a pack that spreads its keys is left alone ==")
spread = [q(f"S-{i:03d}", i % 4) for i in range(24)]
ck("no warnings", messages(spread) == [], messages(spread))

print("\n== a run inside an otherwise spread pack ==")
run_only = ([q(f"R-{i:03d}", i % 4) for i in range(12)]
            + [q(f"R-1{i:02d}", 1) for i in range(KEY_RUN_LIMIT)]
            + [q(f"R-2{i:02d}", (i + 2) % 4) for i in range(12)])
msgs = messages(run_only)
ck("the run is reported", len(msgs) == 1 and "in a row" in msgs[0], msgs)
ck("the run warning names every question in it",
   msgs and all(f"R-1{i:02d}" in msgs[0] for i in range(KEY_RUN_LIMIT)))
ck("no skew warning, because the pack overall is fine",
   not any("of this pack's" in m for m in msgs))

print("\n== the thresholds are boundaries, not approximations ==")
just_under_run = [q(f"U-{i}", 0) for i in range(KEY_RUN_LIMIT - 1)]
ck(f"a run of {KEY_RUN_LIMIT - 1} is not reported", messages(just_under_run) == [])
ck(f"a run of {KEY_RUN_LIMIT} is",
   len(messages([q(f"V-{i}", 0) for i in range(KEY_RUN_LIMIT)])) == 1)
# Exactly half is not "more than half": a four-option pack of eight questions with
# four As is unremarkable, and reporting it would train authors to ignore the check.
half = [q(f"H-{i}", 0) for i in range(4)] + [q(f"H-1{i}", i % 3 + 1) for i in range(4)]
ck("exactly half in one position is not a skew",
   not any("of this pack's" in m for m in messages(half)), messages(half))
five_of_eight = ([q(f"F-{i}", 0) for i in range(3)]
                 + [q("F-x", 1), q("F-y", 0), q("F-z", 2), q("F-w", 0), q("F-v", 3)])
ck("five of eight is",
   any("5 of this pack's 8 answers are option A" in m for m in messages(five_of_eight)),
   messages(five_of_eight))
short_skew = [q(f"P-{i}", 0) for i in range(KEY_SKEW_MIN - 1)]
ck(f"a pack of {KEY_SKEW_MIN - 1} gets no skew warning, however lopsided",
   not any("of this pack's" in m for m in messages(short_skew)))

print("\n== an empty or optionless pack says nothing ==")
ck("empty", check_key_distribution([]) == [])
ck("no positional questions", messages([{"ref": "N", "kind": "numeric", "answer": "1"}]) == [])

if fails:
    print("\nRESULT: FAILURES:", fails)
    raise SystemExit(1)
print("\nRESULT: all checks passed.")
