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
import io
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "elevenplus_data"))

from validate_questions import (  # noqa: E402
    FIELD_LIMITS, KEY_RUN_LIMIT, KEY_SKEW_MIN, QUESTION_IMAGE_DIR, Report,
    _check_field_lengths, _check_groups, _check_image, _check_option_groups,
    _check_tables, check_key_distribution, key_positions,
)
from passage_lines import PASSAGE_LINE_WIDTH, last_line_number  # noqa: E402

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


# ---------------------------------------------------------------------------
# The shared-stimulus and bracket checks.
#
# These take a Report rather than returning their findings, so they are driven
# through a throwaway Report here. The point of testing them at all is that each
# one exists to catch a defect that imports CLEANLY and is only visible to a
# pupil — a code table with two blank cells, a bracket with two right answers, an
# instruction block with no worked example. Nothing downstream would complain.
# ---------------------------------------------------------------------------

def errors_from(fn, *args):
    r = Report("<test>")
    fn(r, *args)
    return [m for _, m in r.errors]


def group(**over):
    g = {"group_ref": "G", "instruction": "Choose one word from each bracket.",
         "example": "Bee is to hive as spider is to web."}
    g.update(over)
    return g


def table(**over):
    t = {"table_ref": "T", "headers": ["Word", "Code"],
         "rows": [["CAT", "DBU"], ["DOG", ""]]}
    t.update(over)
    return t


def grouped(groups):
    return {"kind": "grouped_options", "stem": "x", "option_groups": groups}


def bracket(number, texts, key):
    return {"group": number,
            "options": [{"text": t, **({"correct": True} if i == key else {})}
                        for i, t in enumerate(texts)]}


print("\n== shared instruction blocks ==")
ck("a complete group is accepted",
   errors_from(_check_groups, [group()]) == [])
ck("a group with no instruction is rejected",
   any("instruction" in m for m in errors_from(_check_groups, [group(instruction="")])))
# The example is required, not optional: for several VR subtopics the item is
# unreadable without one, and an author who omits it has not noticed.
ck("a group with no worked example is rejected",
   any("example" in m for m in errors_from(_check_groups, [group(example="")])))
ck("two groups with the same ref are rejected",
   any("duplicate" in m for m in errors_from(_check_groups, [group(), group()])))
ck("groups are optional",
   _check_groups(Report("<test>"), None) == {})

print("\n== shared data tables ==")
ck("a table with exactly one blank cell is accepted",
   errors_from(_check_tables, [table()]) == [])
# Two blanks and the pupil cannot tell which cell the question is asking for;
# none and the author has pasted the answer key by mistake.
ck("a table with no blank cell is rejected",
   any("no blank cell" in m
       for m in errors_from(_check_tables, [table(rows=[["CAT", "DBU"], ["DOG", "EPH"]])])))
ck("a table with two blank cells is rejected",
   any("2 blank cells" in m
       for m in errors_from(_check_tables, [table(rows=[["CAT", ""], ["DOG", ""]])])))
ck("null counts as blank, as well as an empty string",
   any("no blank cell" not in m
       for m in errors_from(_check_tables, [table(rows=[["CAT", "DBU"], ["DOG", None]])]))
   or errors_from(_check_tables, [table(rows=[["CAT", "DBU"], ["DOG", None]])]) == [])
ck("a ragged row is rejected",
   any("headers" in m
       for m in errors_from(_check_tables, [table(rows=[["CAT", "DBU"], ["DOG", "", "x"]])])))

print("\n== one word from each bracket ==")
two = [bracket(1, ["coins", "bank", "shopping"], 2),
       bracket(2, ["sandwich", "cup", "caddy"], 1)]
ck("two well-formed brackets are accepted",
   errors_from(_check_option_groups, "q[0]", grouped(two)) == [])
ck("the key position of each bracket is reported, in order",
   key_positions([{**grouped(two), "ref": "Q1"}])
   == [("Q1 bracket 1", 2), ("Q1 bracket 2", 1)])
ck("a single bracket is rejected — that is an ordinary mcq",
   any("at least 2 brackets" in m
       for m in errors_from(_check_option_groups, "q[0]",
                            grouped([bracket(1, ["a", "b"], 0)]))))
# One mark for the pair, so a bracket with two keys or none makes the question
# unmarkable rather than merely generous.
ck("a bracket with two correct answers is rejected",
   any("2 correct options" in m
       for m in errors_from(_check_option_groups, "q[0]", grouped([
           {"group": 1, "options": [{"text": "a", "correct": True},
                                    {"text": "b", "correct": True}]},
           bracket(2, ["c", "d"], 0)]))))
ck("a bracket with no correct answer is rejected",
   any("0 correct options" in m
       for m in errors_from(_check_option_groups, "q[0]", grouped([
           bracket(1, ["a", "b"], None), bracket(2, ["c", "d"], 0)]))))
ck("brackets numbered with a gap are rejected",
   any("1..N" in m
       for m in errors_from(_check_option_groups, "q[0]",
                            grouped([bracket(1, ["a", "b"], 0),
                                     bracket(3, ["c", "d"], 0)]))))
ck("a flat 'options' list alongside the brackets is rejected",
   any("not 'options'" in m
       for m in errors_from(_check_option_groups, "q[0]",
                            {**grouped(two), "options": [{"text": "x", "correct": True}]})))

REPO = os.path.dirname(os.path.abspath(__file__))


def errs(fn, *args):
    """The error messages one check produces for one question."""
    r = Report("test")
    fn(r, "q[0]", *args)
    return [m for _, m in r.errors]


print("== field limits still match the columns they were copied from ==")
# FIELD_LIMITS is transcribed from catalog/models.py because this validator is
# stdlib-only and cannot import Django to read `max_length` off the fields.
# Transcription drifts silently, and the drift only shows up as a DataError on
# the Postgres deploy — SQLite ignores VARCHAR lengths, so no local run and no
# test against db.sqlite3 would ever catch it. This is the check that ties the
# two together: widen a column and it tells you to update the validator.
models_src = io.open(os.path.join(REPO, "catalog", "models.py"),
                     encoding="utf-8").read()


def declared(field, cls=None):
    """The max_length declared for `field` in models.py, or None."""
    body = models_src
    if cls:
        start = body.index("class %s(" % cls)
        nxt = body.find("\nclass ", start + 1)
        body = body[start:nxt if nxt != -1 else len(body)]
    m = re.search(r"^\s+%s = models\.CharField\(max_length=(\d+)" % re.escape(field),
                  body, re.M)
    return int(m.group(1)) if m else None


for key, cls, field in [
    ("passage_title", "Question", "passage_title"),
    ("passage_source", "Question", "passage_source"),
    ("line_ref", "Question", "line_ref"),
    ("image", "Question", "image"),
    ("source", "Question", "source"),
    ("question_type", "Question", "question_type"),
    ("answer_text", "Question", "answer_text"),
    ("unit", "Question", "unit"),
    ("option_text", "AnswerOption", "text"),
    ("misconception", "AnswerOption", "misconception"),
    ("subtopic", "Subtopic", "name"),
]:
    actual = declared(field, cls)
    ck(f"FIELD_LIMITS[{key!r}] == {cls}.{field}.max_length",
       actual is not None and FIELD_LIMITS[key] == actual,
       f"validator says {FIELD_LIMITS[key]}, models.py says {actual}")


print("== a field longer than its column is refused ==")
long_qt = "x" * (FIELD_LIMITS["question_type"] + 1)
ck("an over-length question_type errors",
   any("question_type" in m for m in errs(_check_field_lengths,
                                          {"question_type": long_qt}, "Grammar")))
ck("one exactly at the limit is fine",
   not errs(_check_field_lengths,
            {"question_type": "x" * FIELD_LIMITS["question_type"]}, "Grammar"))
ck("an over-length option is refused",
   any("opt[1]" in m for m in errs(
       _check_field_lengths,
       {"options": [{"text": "ok"},
                    {"text": "y" * (FIELD_LIMITS["option_text"] + 1)}]},
       "Grammar")))
ck("an over-length subtopic name is refused",
   any("subtopic" in m for m in errs(_check_field_lengths, {},
                                     "z" * (FIELD_LIMITS["subtopic"] + 1))))
ck("a clean question produces nothing",
   not errs(_check_field_lengths,
            {"question_type": "word-meaning-in-context", "unit": "cm",
             "options": [{"text": "a"}, {"text": "b"}]}, "Vocabulary"))


print("== a figure has to be a bare filename that is actually committed ==")
ck("a path rather than a filename is refused",
   any("path" in m for m in errs(_check_image, {"image": "questions/shape.png"})))
ck("a filename that is not committed is refused",
   any("not committed" in m
       for m in errs(_check_image, {"image": "definitely_absent_figure.png"})))
ck("no image at all is fine",
   not errs(_check_image, {}) and not errs(_check_image, {"image": ""}))
# The one image that does exist in the repo is .gitkeep, which proves the
# positive branch without committing a binary just to be test scaffolding.
if os.path.isfile(os.path.join(QUESTION_IMAGE_DIR, ".gitkeep")):
    ck("a filename that IS present passes",
       not errs(_check_image, {"image": ".gitkeep"}))


print("== a line_ref is checked against the passage it points at ==")
# The wrapping is the renderer's, not a copy of it — that is the whole reason
# passage_lines.py exists as its own module.
one_liner = "A short line."
ck("a one-line passage is one line", last_line_number(one_liner) == 1)
long_para = ("word " * 400).strip()
expected = -(-len(long_para) // PASSAGE_LINE_WIDTH)   # ceiling, roughly
ck("a long paragraph wraps to several lines",
   last_line_number(long_para) >= expected - 2, str(last_line_number(long_para)))
ck("a blank paragraph separator consumes no line number",
   last_line_number("One.\n\nTwo.") == 2)
ck("an empty passage has no lines", last_line_number("") == 0)

if fails:
    print("\nRESULT: FAILURES:", fails)
    raise SystemExit(1)
print("\nRESULT: all checks passed.")
