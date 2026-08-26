#!/usr/bin/env python3
"""
validate_questions.py — objective pre-merge checker for RevisorPlus question packs.

Stdlib only. No Django, no pip install — a contributor can run it with nothing but
Python 3. It mirrors exactly what `catalog/management/commands/import_pack.py` will do
on Render, and refuses anything that would import badly, silently corrupt the bank,
or overwrite someone else's work.

Usage
-----
    python3 validate_questions.py my_pack.json
    python3 validate_questions.py elevenplus_data/*.json   # check several at once

Exit codes
----------
    0  no ERRORS (warnings may still be printed)
    1  at least one ERROR — do NOT merge until fixed
    2  the file could not be read or parsed as JSON

The rule of thumb: ERRORS block a merge, WARNINGS are things a human should eyeball.
"""
import glob
import json
import os
import re
import sys
from fractions import Fraction

# ---------------------------------------------------------------------------
# The contract is loaded from taxonomy.json, which sits next to this file and is
# the single source of truth: `manage.py sync_taxonomy` writes the same file to
# the database and CLAUDE.md documents it. Editing the taxonomy is therefore one
# edit, not three that can drift apart.
#
# Subtopic names and question-type slugs are matched CHARACTER FOR CHARACTER. A
# typo does not error on import — it silently creates an orphan subtopic and
# hides the question in it — which is exactly why this check exists.
# ---------------------------------------------------------------------------
TAXONOMY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "taxonomy.json")


def _load_taxonomy(path=TAXONOMY_PATH):
    """Return (sections, names, subtopics, question_types, rebuilt, axes, aliases)."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        sys.exit(f"FATAL: cannot read the taxonomy at {path}: {e}\n"
                 "It is the contract this checker enforces; without it nothing "
                 "can be validated.")

    sections, names, subs, qtypes, rebuilt, axes = set(), {}, {}, {}, {}, {}
    # snake_case subtopic slug -> the canonical Title Case name, per section.
    # The English and VR schemas identify a subtopic by slug (`literal_retrieval`)
    # while the bank displays a name ("Literal Retrieval"), so a pack may write
    # either and both resolve to the same subtopic.
    aliases = {}
    for code, sec in data["sections"].items():
        sections.add(code)
        names[code] = sec["name"]
        subs[code] = {s["name"] for s in sec["subtopics"]}
        qtypes[code] = {s["name"]: {t["slug"] for t in s["question_types"]}
                        for s in sec["subtopics"]}
        aliases[code] = {s["slug"]: s["name"] for s in sec["subtopics"] if s.get("slug")}
        rebuilt[code] = bool(sec.get("rebuilt"))
        # Subtopics whose types split across axes (Statistics & Data is the only
        # one today): slug -> axis name. See "the pairing convention" below.
        for st in sec["subtopics"]:
            if "axes" in st:
                axes[(code, st["name"])] = {
                    t["slug"]: t["axis"] for t in st["question_types"] if "axis" in t
                }
    return sections, names, subs, qtypes, rebuilt, axes, aliases


SECTIONS, SECTION_NAME, SUBTOPICS, QUESTION_TYPES, REBUILT, AXES, ALIASES = _load_taxonomy()


def canonical_subtopic(code, value):
    """The canonical subtopic name for `value`, which may be a name or a slug.

    Returns None when it is neither, so the caller reports it as invalid.
    """
    if not value:
        return None
    if value in SUBTOPICS.get(code, ()):
        return value
    return ALIASES.get(code, {}).get(value)

# What a contributor pack may declare.
#
# Free-response was opened up because the seven-paper audit found it is not
# optional: GL and ISEB papers were 150/150 multiple choice, but CEM and Bond
# papers ran 58/100 free numeric entry. An MCQ-only bank cannot represent a CEM
# paper honestly.
#
# The rest were opened up for the same reason, one board further on: roughly a
# third of a GL English paper is not standard multiple choice either. Whole
# spelling and punctuation sections are spot-the-error, and every paper ends with
# a cloze passage. Bending those into `mcq` marks correctly and shows the child
# something they never meet in the exam.
#
# `extended_text` was in the model and the marking engine from the start — the
# engine routes it to a human marker — and only this list kept it out of packs.
# That is the same shape of gap as the importer silently dropping `question_type`:
# a feature that exists everywhere except where an author can reach it.
VALID_KINDS = {"mcq", "numeric", "short_text", "extended_text",
               "error_span", "select_word", "cloze_gap", "grouped_options"}
# Typed by the pupil and marked against `answer`.
TYPED_KINDS = {"numeric", "short_text"}
# Answered by picking one of the options. Marked identically; presented differently.
OPTION_KINDS = {"mcq", "error_span", "select_word", "cloze_gap"}
# The options are consecutive pieces of the stem, declared as `segments`.
SELECTION_KINDS = {"error_span", "select_word"}
# The options are divided into brackets, declared as `option_groups`, and the
# pupil picks one word from each. One mark for the whole pair.
GROUPED_KINDS = {"grouped_options"}
# Goes to a human marker; carries a rubric rather than an answer.
MARKED_KINDS = {"extended_text"}

# The label an error-span question gives its "no mistake" answer, and the
# letters printed beside ordinary choices. Mirrors catalog/models.py.
NO_ERROR_LABEL = "N"
OPTION_LABELS = ("A", "B", "C", "D", "E", "F", "G", "H")

# Sources already used by the built-in demo content. A contributor pack that reuses
# one of these would DELETE those questions on import — so we forbid it.
RESERVED_SOURCES = {"seed"}

# Keys the importer understands. Anything else is almost certainly a typo
# (e.g. "explaination") and gets ignored on import, so we flag it.
KNOWN_Q_KEYS = {
    "number", "ref", "subtopic", "question_type", "also_tests", "kind", "stem",
    "passage", "line_ref", "explanation", "image", "difficulty", "options",
    "is_placeholder", "answer", "tolerance", "accepted_alternatives", "unit",
    # selection kinds
    "segments", "allow_no_error",
    # one word from each bracket
    "option_groups",
    # cloze and shared passages
    "gap_number", "passage_ref",
    # shared instruction-and-example blocks, and shared data tables
    "group_ref", "table_ref",
    # human-marked
    "marks", "model_answer", "rubric",
}

# "12" or "20-21" — a line, or a range of lines, of the passage.
LINE_REF_RE = re.compile(r"^\d+(-\d+)?$")
KNOWN_OPT_KEYS = {"text", "correct"}


class Report:
    def __init__(self, path):
        self.path = path
        self.errors = []
        self.warnings = []

    def err(self, where, msg):
        self.errors.append((where, msg))

    def warn(self, where, msg):
        self.warnings.append((where, msg))

    def print(self):
        print(f"\n=== {self.path} ===")
        for where, msg in self.errors:
            print(f"  ERROR  [{where}] {msg}")
        for where, msg in self.warnings:
            print(f"  warn   [{where}] {msg}")
        if not self.errors and not self.warnings:
            print("  OK — clean.")
        elif not self.errors:
            print(f"  PASS with {len(self.warnings)} warning(s).")
        else:
            print(f"  FAIL — {len(self.errors)} error(s), {len(self.warnings)} warning(s).")


def _numeric_shape(text):
    """Split an option into (prefix, value, suffix), or None if it isn't numeric.

    "2/3" -> ("", Fraction(2,3), "") and "30/45" -> ("", Fraction(2,3), "").
    Prefix and suffix are kept so that "£20" and "20%" are never compared: they
    are the same number but not the same answer.
    """
    t = str(text).strip()
    if not t:
        return None
    i, j = 0, len(t)
    while i < j and not (t[i].isdigit() or (t[i] == "-" and i + 1 < j and t[i + 1].isdigit())):
        i += 1
    k = i
    while k < j and (t[k].isdigit() or t[k] in "-./,"):
        k += 1
    body = t[i:k].rstrip("./,")
    if not body or not any(c.isdigit() for c in body):
        return None
    body = body.replace(",", "")
    try:
        value = Fraction(body) if "/" in body else Fraction(body)
    except (ValueError, ZeroDivisionError):
        return None
    prefix = t[:i].strip()
    suffix = t[k:].strip().lstrip("./,").strip()
    return prefix, value, suffix


def _check_equivalent_options(r, tag, opts):
    """Flag two options that are the same value written differently.

    This is the defect that automated checks usually miss and pupils always
    find: "Calculate 2/3 x 10/9" offering both 2/3 and 30/45 has two correct
    answers, and nothing else in this file would notice. It is an ERROR when one
    of the pair is the key, and a warning when two distractors collide.
    """
    shapes = []
    for j, opt in enumerate(opts):
        if not isinstance(opt, dict):
            continue
        shape = _numeric_shape(opt.get("text", ""))
        if shape is not None:
            shapes.append((j, shape, bool(opt.get("correct", False))))

    for a in range(len(shapes)):
        for b in range(a + 1, len(shapes)):
            ja, (pa, va, sa), ca = shapes[a]
            jb, (pb, vb, sb), cb = shapes[b]
            if pa != pb or sa != sb or va != vb:
                continue
            ta = str(opts[ja].get("text", "")).strip()
            tb = str(opts[jb].get("text", "")).strip()
            if ta == tb:
                r.err(tag, f"opt[{ja}] and opt[{jb}] are both {ta!r} — duplicate option")
            elif ca or cb:
                r.err(tag, f"opt[{ja}] {ta!r} and opt[{jb}] {tb!r} are the same value, "
                           f"and one of them is the correct answer — this question has "
                           f"two right answers. Change the distractor, or make the stem "
                           f"ask for a specific form (e.g. 'in its simplest form').")
            else:
                r.warn(tag, f"opt[{ja}] {ta!r} and opt[{jb}] {tb!r} are the same value "
                            f"written differently; a pupil cannot choose between them")


# Kinds whose answer sits at a POSITION in a list the author chose, and could
# just as easily have sat at another. Those are the ones whose key can drift to
# one letter without anything looking wrong.
#
# `error_span` and `select_word` are deliberately excluded: their options are
# consecutive pieces of the sentence, lettered left to right, and `_check_segments`
# already requires exactly that order. The key of "which part of this sentence is
# wrong" cannot be moved without rewriting the sentence, so counting it here would
# report a skew nobody is able to act on.
POSITIONAL_KINDS = {"mcq", "cloze_gap"}

# A run of this many consecutive questions sharing a key position is reported.
# Four is the point at which a pupil could notice; the run that prompted this
# check was twenty-five.
KEY_RUN_LIMIT = 4
# Below this many positional questions a pack is too short for a share to mean
# anything — three keys in the same place out of four is ordinary chance.
KEY_SKEW_MIN = 8


def key_positions(questions):
    """[(label, index)] — where the key sits in each positionally-answered question.

    `label` is the question's `ref`, or `q[i]` when it has none, so a warning can
    name the entries an author has to go and look at. `index` is 0-based into the
    options as written, which is the same order the pupil sees them in.

    Pure and Django-free, taking the raw pack entries rather than the validator's
    per-question state, so it can be exercised directly from a test.
    """
    out = []
    for idx, q in enumerate(questions):
        if not isinstance(q, dict):
            continue
        kind = q.get("kind", "mcq")
        label = q.get("ref") or f"q[{idx}]"

        # Each bracket of a grouped question is its own positional choice, so it
        # can drift to one letter on its own — and does, because an author writes
        # the two right words first and then fills each bracket around them.
        if kind in GROUPED_KINDS:
            for n, g in enumerate(q.get("option_groups") or [], start=1):
                if not isinstance(g, dict):
                    continue
                at = _key_index(g.get("options"))
                if at is not None:
                    out.append((f"{label} bracket {n}", at))
            continue

        if kind not in POSITIONAL_KINDS:
            continue
        at = _key_index(q.get("options"))
        if at is not None:
            out.append((label, at))
    return out


def _key_index(opts):
    """The 0-based position of the correct option, or None."""
    if not isinstance(opts, list):
        return None
    for j, opt in enumerate(opts):
        if isinstance(opt, dict) and opt.get("correct") is True:
            return j
    return None


def check_key_distribution(positions):
    """[(where, message)] — warnings about where a pack puts its correct answers.

    A pupil who cannot do the question can still score by noticing that the answer
    is usually A. That makes the bank measure test-wiseness rather than reasoning,
    which is the one thing the analytics are supposed to be able to tell apart. The
    generators have never had this problem — `shuffled_options` in
    catalog/generators/__init__.py randomises — but a pack written by hand or by a
    model has nothing shuffling it, and nothing here used to look.

    Warnings, never errors. A short pack can land four keys in a row honestly, and
    a contributor should not be blocked from merging by a coincidence.

    Two checks, because they catch different things: a run is visible to a child
    working down the page, a skew is visible to one who has sat several papers.

    There is deliberately no "position E is never used" check. Packs mix three-,
    four- and five-option questions, so an unused fifth slot is usually just a pack
    of four-option questions and would report every honest file.
    """
    out = []
    if not positions:
        return out

    letter = lambda i: OPTION_LABELS[i] if i < len(OPTION_LABELS) else f"#{i + 1}"

    run = [positions[0]]
    for entry in positions[1:]:
        if entry[1] == run[-1][1]:
            run.append(entry)
            continue
        if len(run) >= KEY_RUN_LIMIT:
            out.append(_run_warning(run, letter))
        run = [entry]
    if len(run) >= KEY_RUN_LIMIT:
        out.append(_run_warning(run, letter))

    total = len(positions)
    if total >= KEY_SKEW_MIN:
        counts = {}
        for _, i in positions:
            counts[i] = counts.get(i, 0) + 1
        top, n = max(counts.items(), key=lambda kv: (kv[1], -kv[0]))
        if n * 2 > total:
            spread = ", ".join(f"{letter(i)}={counts[i]}"
                               for i in sorted(counts))
            out.append(("answer key",
                        f"{n} of this pack's {total} answers are option {letter(top)} "
                        f"({100 * n // total}%). Spread: {spread}. A pupil who works "
                        f"that out scores without reading the question. Move some keys "
                        f"and reorder the options around them."))
    return out


# Enough refs to find the run in the file without the message becoming a wall.
_RUN_NAMES_SHOWN = 6


def _run_warning(run, letter):
    shown = [label for label, _ in run[:_RUN_NAMES_SHOWN]]
    names = ", ".join(shown)
    if len(run) > _RUN_NAMES_SHOWN:
        names += f", … and {len(run) - _RUN_NAMES_SHOWN} more"
    return ("answer key",
            f"{len(run)} questions in a row have option {letter(run[0][1])} as the "
            f"answer ({names}). Reorder the options on some of them so the key "
            f"moves.")


def _check_typed_answer(r, tag, q, kind):
    """Checks for a question the pupil types rather than picks.

    The marking engine reads `answer` for both kinds, `tolerance` for numeric and
    `accepted_alternatives` for short text. A typed question with no `answer`
    imports cleanly and can never be marked right, so that is an error, not a
    warning.
    """
    if q.get("options"):
        r.err(tag, f"kind {kind!r} is typed by the pupil, so it must not carry "
                   f"'options'. Use kind 'mcq' if you meant multiple choice.")

    if "answer" not in q or str(q.get("answer", "")).strip() == "":
        r.err(tag, f"kind {kind!r} requires 'answer' — the value the pupil types. "
                   f"Without it nothing can ever be marked correct.")
        return

    ans = q["answer"]
    if kind == "numeric":
        if isinstance(ans, bool) or not isinstance(ans, (int, float, str)):
            r.err(tag, f"'answer' must be a number for kind 'numeric', got {ans!r}")
        elif isinstance(ans, str):
            try:
                float(ans.replace(",", "").replace("£", "").strip())
            except ValueError:
                r.err(tag, f"'answer' {ans!r} is not a number. Put units in 'unit', "
                           f"which is shown to the pupil rather than typed.")
        tol = q.get("tolerance", 0)
        if isinstance(tol, bool) or not isinstance(tol, (int, float)):
            r.err(tag, f"'tolerance' must be a number, got {tol!r}")
        elif tol < 0:
            r.err(tag, "'tolerance' cannot be negative")
        # `accepted_alternatives` is NOT ignored for numeric — `_mark_numeric` in
        # catalog/marking.py parses each alternative as a number and also compares
        # it as text, which is how "0.5" accepts "a half". This warned that the
        # field was ignored, which was false and told authors to delete a field
        # that works. It is still the wrong tool for a *range* — that is tolerance
        # — so the shape is checked and the nudge kept.
        alts = q.get("accepted_alternatives", [])
        if not isinstance(alts, list):
            r.err(tag, f"'accepted_alternatives' must be a list, got {alts!r}")
        elif any(not isinstance(a, str) or not a.strip() for a in alts):
            r.err(tag, "every entry in 'accepted_alternatives' must be a non-empty string")
        elif alts:
            r.warn(tag, "'accepted_alternatives' on a numeric answer accepts specific "
                        "extra forms (e.g. 'a half'); to accept a *range* use 'tolerance'")

    if kind == "short_text":
        alts = q.get("accepted_alternatives", [])
        if not isinstance(alts, list):
            r.err(tag, f"'accepted_alternatives' must be a list, got {alts!r}")
        elif any(not isinstance(a, str) or not a.strip() for a in alts):
            r.err(tag, "every entry in 'accepted_alternatives' must be a non-empty string")
        if q.get("tolerance"):
            r.warn(tag, "'tolerance' is ignored for short text; list the spellings "
                        "you accept in 'accepted_alternatives'")


def _check_segments(r, tag, q, kind):
    """Checks for a question answered by picking a stretch of its own stem.

    The segments are not answer texts — they are consecutive pieces of the
    sentence the pupil is reading. So the one check that matters is that they
    join back to the stem exactly: a segmentation that drops a word, doubles a
    space or quietly rewrites the sentence would render as a sentence the author
    never wrote, and nothing else would notice.
    """
    if q.get("options"):
        r.err(tag, f"kind {kind!r} carries 'segments', not 'options' — the pupil "
                   f"picks part of the sentence rather than an answer beneath it.")

    segments = q.get("segments")
    if not isinstance(segments, list) or not segments:
        r.err(tag, f"kind {kind!r} requires a non-empty 'segments' list of "
                   f"{{\"label\": \"A\", \"text\": \"...\"}} objects")
        return

    labels, texts = [], []
    for i, seg in enumerate(segments):
        where = f"{tag} segments[{i}]"
        if not isinstance(seg, dict):
            r.err(where, "each segment must be an object with 'label' and 'text'")
            return
        unknown = set(seg) - {"label", "text"}
        if unknown:
            r.warn(where, f"unknown field(s) {sorted(unknown)} ignored on import")
        label, text = seg.get("label"), seg.get("text")
        if not isinstance(label, str) or label not in OPTION_LABELS:
            r.err(where, f"label {label!r} must be one of {list(OPTION_LABELS[:5])}")
        else:
            labels.append(label)
        if not isinstance(text, str) or text == "":
            r.err(where, "'text' must be a non-empty string")
        else:
            texts.append(text)

    if len(labels) != len(set(labels)):
        dupes = sorted({x for x in labels if labels.count(x) > 1})
        r.err(tag, f"duplicate segment label(s) {dupes}")
    if labels and labels != sorted(labels, key=OPTION_LABELS.index):
        r.err(tag, f"segment labels {labels} are out of order; they letter the "
                   f"sentence from left to right")

    stem = q.get("stem")
    if isinstance(stem, str) and len(texts) == len(segments):
        joined = "".join(texts)
        if joined != stem:
            r.err(tag, "the segments do not join back to the stem exactly. "
                       f"Joined: {joined!r} — stem: {stem!r}. Every character of "
                       f"the sentence must sit in exactly one segment, spaces "
                       f"included.")

    allow_none = q.get("allow_no_error", False)
    if not isinstance(allow_none, bool):
        r.err(tag, f"'allow_no_error' must be true or false, got {allow_none!r}")
        allow_none = bool(allow_none)

    answer = q.get("answer")
    valid = set(labels) | ({NO_ERROR_LABEL} if allow_none else set())
    if not isinstance(answer, str) or not answer:
        r.err(tag, f"kind {kind!r} requires 'answer' — the label of the segment "
                   f"the pupil should pick. One of {sorted(valid)}.")
    elif answer not in valid:
        if answer == NO_ERROR_LABEL:
            r.err(tag, f"answer {NO_ERROR_LABEL!r} means \"no mistake\", but this "
                       f"question does not offer that choice. Set "
                       f"\"allow_no_error\": true.")
        else:
            r.err(tag, f"answer {answer!r} is not one of this question's labels "
                       f"{sorted(valid)}")

    if kind == "error_span" and not allow_none:
        r.warn(tag, "spot-the-error questions usually offer 'N' for no mistake; "
                    "without it a pupil who thinks the sentence is correct has "
                    "nowhere to say so. Set \"allow_no_error\": true unless the "
                    "section genuinely never offers it.")


def _check_cloze(r, tag, q):
    """Checks for one numbered gap of a cloze passage."""
    gap = q.get("gap_number")
    if not isinstance(gap, int) or isinstance(gap, bool) or gap < 1:
        r.err(tag, f"kind 'cloze_gap' requires 'gap_number', a whole number from 1, "
                   f"got {gap!r}")
    if not q.get("passage") and not q.get("passage_ref"):
        r.err(tag, "kind 'cloze_gap' requires the passage the gap sits in — give "
                   "a 'passage_ref' pointing at the pack's 'passages', or an "
                   "inline 'passage'.")
    # A cloze gap carrying `segments` is caught by the general wrong-kind-field
    # check in validate(), which covers every kind rather than just this one.


def _check_passages(r, passages):
    """The pack's shared passages. Returns {ref: passage} for the ones that stand.

    A passage is declared once and pointed at by every question that uses it, so
    the text lives in one place rather than being copied into each question — and
    so its title and source note have somewhere to live at all.
    """
    if passages is None:
        return {}
    if not isinstance(passages, list):
        r.err("passages", f"'passages' must be a list, got {type(passages).__name__}")
        return {}

    out = {}
    for i, p in enumerate(passages):
        where = f"passages[{i}]"
        if not isinstance(p, dict):
            r.err(where, "each passage must be an object")
            continue
        unknown = set(p) - {"passage_ref", "title", "text", "source_note"}
        if unknown:
            r.warn(where, f"unknown field(s) {sorted(unknown)} ignored on import")
        ref = p.get("passage_ref")
        if not isinstance(ref, str) or not ref.strip():
            r.err(where, "missing 'passage_ref' — questions point at a passage by it")
            continue
        if ref in out:
            r.err(where, f"duplicate passage_ref {ref!r}")
            continue
        for field in ("title", "text"):
            if not isinstance(p.get(field), str) or not p[field].strip():
                r.err(where, f"missing or empty {field!r}")
        # Not cosmetic: this is what separates a public-domain extract from
        # someone else's copyright, and a bank that cannot tell them apart
        # cannot safely be published.
        if not isinstance(p.get("source_note"), str) or not p["source_note"].strip():
            r.err(where, "missing 'source_note' — say where the text came from, "
                         "e.g. \"Original work written for this pack\" or the "
                         "public-domain source. Without it nobody can tell "
                         "whether this text is ours to publish.")
        out[ref] = p
    return out


def _check_groups(r, groups):
    """The pack's shared instructions. Returns {ref: group} for the ones that stand.

    A paper prints an instruction and one worked example above a run of five or
    six items, not above each one. Declaring it once here is how an author says
    that, and on import it is copied onto every question in the block — see the
    comment on `Question.instruction` for why it is copied rather than shared
    through a container row.

    The example is required, not optional. For much of verbal reasoning the
    instruction alone does not make the item answerable: "mal ( ) ens" is
    meaningless until the example shows what the brackets are for.
    """
    if groups is None:
        return {}
    if not isinstance(groups, list):
        r.err("groups", f"'groups' must be a list, got {type(groups).__name__}")
        return {}

    out = {}
    for i, g in enumerate(groups):
        where = f"groups[{i}]"
        if not isinstance(g, dict):
            r.err(where, "each group must be an object")
            continue
        unknown = set(g) - {"group_ref", "instruction", "example"}
        if unknown:
            r.warn(where, f"unknown field(s) {sorted(unknown)} ignored on import")
        ref = g.get("group_ref")
        if not isinstance(ref, str) or not ref.strip():
            r.err(where, "missing 'group_ref' — questions point at a group by it")
            continue
        if ref in out:
            r.err(where, f"duplicate group_ref {ref!r}")
            continue
        if not isinstance(g.get("instruction"), str) or not g["instruction"].strip():
            r.err(where, "missing or empty 'instruction' — this is the line a paper "
                         "prints above the block, and for several VR subtopics it "
                         "is the rule rather than the framing")
        if not isinstance(g.get("example"), str) or not g["example"].strip():
            r.err(where, "missing or empty 'example' — a worked example is what "
                         "makes the item readable at all. \"mal ( ) ens\" is not a "
                         "hard question without one, it is not a question.")
        out[ref] = g
    return out


def _check_tables(r, tables):
    """The pack's shared data tables. Returns {ref: table} for the ones that stand.

    A GL code block prints three or four words with their codes and withholds
    one, then asks several questions against it. That is tabular data rather than
    prose, so `passages` is the wrong container — and `image` takes a committed
    file, which a code grid should not need.

    Nothing new renders this: `catalog/figures.py` has drawn
    {"kind": "table", "data": {headers, rows}} since the imported papers needed
    it, blank cells included. It was simply unreachable from a pack.
    """
    if tables is None:
        return {}
    if not isinstance(tables, list):
        r.err("tables", f"'tables' must be a list, got {type(tables).__name__}")
        return {}

    out = {}
    for i, t in enumerate(tables):
        where = f"tables[{i}]"
        if not isinstance(t, dict):
            r.err(where, "each table must be an object")
            continue
        unknown = set(t) - {"table_ref", "headers", "rows"}
        if unknown:
            r.warn(where, f"unknown field(s) {sorted(unknown)} ignored on import")
        ref = t.get("table_ref")
        if not isinstance(ref, str) or not ref.strip():
            r.err(where, "missing 'table_ref' — questions point at a table by it")
            continue
        if ref in out:
            r.err(where, f"duplicate table_ref {ref!r}")
            continue

        headers = t.get("headers")
        if not isinstance(headers, list) or not headers:
            r.err(where, "missing 'headers' — a non-empty list of column names")
            headers = []
        rows = t.get("rows")
        if not isinstance(rows, list) or not rows:
            r.err(where, "missing 'rows' — a non-empty list of rows, each a list "
                         "of cells")
            continue

        blanks = 0
        for j, row in enumerate(rows):
            if not isinstance(row, list):
                r.err(f"{where} rows[{j}]", "each row must be a list of cells")
                continue
            if headers and len(row) != len(headers):
                r.err(f"{where} rows[{j}]",
                      f"has {len(row)} cells but there are {len(headers)} headers; "
                      f"a ragged table renders with cells in the wrong columns")
            for cell in row:
                if cell is None or (isinstance(cell, str) and not cell.strip()):
                    blanks += 1
                elif not isinstance(cell, (str, int, float)) or isinstance(cell, bool):
                    r.err(f"{where} rows[{j}]",
                          f"cell {cell!r} must be text or a number")

        # The withheld cell IS the question. Two of them and the pupil cannot
        # tell which one is being asked for; none and there is nothing to work
        # out, which usually means the author pasted the answer key by mistake.
        if blanks == 0:
            r.err(where, "no blank cell. A code table withholds exactly one cell — "
                         'that is what the question asks for. Use "" or null.')
        elif blanks > 1:
            r.err(where, f"{blanks} blank cells. Exactly one may be withheld, or the "
                         f"pupil cannot tell which the question is asking for.")
        out[ref] = t
    return out


def _check_option_groups(r, tag, q):
    """Checks a question answered by picking one word from each bracket.

    "Money is to (coins, bank, shopping) as tea is to (sandwich, cup, caddy)."
    The answer is the pair, worth one mark, so each bracket carries exactly one
    key and the pupil has to get both.
    """
    if q.get("options"):
        r.err(tag, "kind 'grouped_options' carries 'option_groups', not 'options' — "
                   "the pupil picks one word from each bracket, and a flat list "
                   "cannot say which words are in which bracket.")

    groups = q.get("option_groups")
    if not isinstance(groups, list) or len(groups) < 2:
        r.err(tag, "kind 'grouped_options' requires an 'option_groups' list of at "
                   "least 2 brackets, each {\"group\": 1, \"options\": [...]}. One "
                   "bracket is an ordinary 'mcq'.")
        return []

    keys, numbers = [], []
    for i, g in enumerate(groups):
        where = f"{tag} option_groups[{i}]"
        if not isinstance(g, dict):
            r.err(where, "each bracket must be an object with 'group' and 'options'")
            continue
        unknown = set(g) - {"group", "options"}
        if unknown:
            r.warn(where, f"unknown field(s) {sorted(unknown)} ignored on import")

        number = g.get("group")
        if isinstance(number, bool) or not isinstance(number, int) or number < 1:
            r.err(where, f"'group' must be a whole number from 1, got {number!r}")
        else:
            numbers.append(number)

        opts = g.get("options")
        if not isinstance(opts, list) or len(opts) < 2:
            r.err(where, "'options' must be a list with at least 2 entries — a "
                         "bracket offering one word is not a choice")
            continue

        n_correct, key_at = 0, None
        for j, opt in enumerate(opts):
            if not isinstance(opt, dict):
                r.err(f"{where} opt[{j}]", "not an object")
                continue
            for k in opt:
                if k not in KNOWN_OPT_KEYS:
                    r.warn(f"{where} opt[{j}]", f"unknown field {k!r} ignored on import")
            if not opt.get("text") or not str(opt["text"]).strip():
                r.err(f"{where} opt[{j}]", "missing or empty 'text'")
            c = opt.get("correct", False)
            if not isinstance(c, bool):
                r.err(f"{where} opt[{j}]", f"'correct' must be true/false, got {c!r}")
            elif c:
                n_correct += 1
                key_at = j
        if n_correct != 1:
            r.err(where, f"bracket {number!r} has {n_correct} correct options; each "
                         f"bracket needs exactly one, because the answer is one word "
                         f"from each")
        else:
            keys.append(key_at)

        # Two words meaning the same thing inside one bracket is the same defect
        # `_check_equivalent_options` already catches in a flat option list.
        _check_equivalent_options(r, where, opts)

    if numbers and sorted(numbers) != list(range(1, len(numbers) + 1)):
        r.err(tag, f"brackets are numbered {sorted(numbers)}; they must run 1..N "
                   f"with no gaps, left to right as the stem prints them")

    return keys


def _check_marked_by_human(r, tag, q, kind):
    """Checks for a question no engine can score."""
    if q.get("options"):
        r.err(tag, f"kind {kind!r} goes to a human marker, so it must not carry "
                   f"'options'")
    if str(q.get("answer", "")).strip():
        r.warn(tag, f"'answer' is ignored for kind {kind!r}; put the answer a "
                    f"marker should compare against in 'model_answer'")
    rubric = q.get("rubric")
    if rubric is not None and not isinstance(rubric, dict):
        r.err(tag, f"'rubric' must be an object, got {type(rubric).__name__}")
    marks = q.get("marks", 1)
    if isinstance(marks, bool) or not isinstance(marks, int) or marks < 1:
        r.err(tag, f"'marks' must be a whole number from 1, got {marks!r}")
    if not rubric and not q.get("model_answer"):
        r.warn(tag, f"kind {kind!r} has neither 'rubric' nor 'model_answer', so "
                    f"whoever marks it has nothing to mark against")


def validate(path):
    r = Report(path)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        r.err("file", "not found")
        return r, "unreadable", None
    except json.JSONDecodeError as e:
        r.err("file", f"not valid JSON: {e}")
        return r, "unreadable", None

    # ---- not a question pack? -----------------------------------------------
    # This folder also holds the taxonomy and the author-written exam papers,
    # which are different formats with different importers. A natural glob
    # (`elevenplus_data/*.json`) sweeps them in, so recognise them and skip
    # rather than reporting a failure the contributor cannot act on. Only these
    # two shapes are skipped; anything else missing `section` is still an error.
    if "section" not in data:
        if "paper_id" in data:
            return r, "skipped", None
        if "sections" in data and "version" in data:
            return r, "skipped", None

    # ---- section header -----------------------------------------------------
    sec = data.get("section")
    if not isinstance(sec, dict):
        r.err("section", "missing top-level 'section' object")
        return r, "fatal", None

    code = sec.get("code")
    if code not in SECTIONS:
        r.err("section.code", f"must be one of {sorted(SECTIONS)}, got {code!r}")
        return r, "fatal", None

    if not sec.get("name"):
        r.warn("section.name", f"missing; import will still work but should read {SECTION_NAME[code]!r}")
    elif sec.get("name") != SECTION_NAME[code]:
        r.warn("section.name", f"is {sec['name']!r}; canonical name for {code} is {SECTION_NAME[code]!r}")

    source = sec.get("source")
    if not source:
        r.err("section.source",
              "no 'source' set. Every pack MUST declare a unique source "
              "(e.g. \"CONTRIB-ALEX-01\"). Without it the importer refuses the file.")
    elif source in RESERVED_SOURCES:
        r.err("section.source",
              f"{source!r} is reserved by the built-in packs. Importing this would "
              f"DELETE those questions. Choose a unique source for your batch.")

    # is_placeholder marks disposable content vs owned IP. Contributor packs should
    # declare it false (their questions are IP). It is optional (importer defaults to
    # False), but if present it must be a boolean.
    if "is_placeholder" in sec:
        ip = sec["is_placeholder"]
        if not isinstance(ip, bool):
            r.err("section.is_placeholder", f"must be true or false, got {ip!r}")
        elif ip is True:
            r.warn("section.is_placeholder",
                   "set to true — this marks the whole pack as disposable placeholder, "
                   "not owned IP. Team-authored packs normally use false.")

    # ---- questions ----------------------------------------------------------
    questions = data.get("questions")
    if not isinstance(questions, list) or not questions:
        r.err("questions", "missing or empty 'questions' list")
        return r, "fatal", None

    allowed_subs = SUBTOPICS[code]
    allowed_types = QUESTION_TYPES[code]
    section_rebuilt = REBUILT.get(code, False)
    seen_refs = {}
    seen_stems = {}
    passages = _check_passages(r, data.get("passages"))
    used_passages = set()
    groups = _check_groups(r, data.get("groups"))
    used_groups = set()
    tables = _check_tables(r, data.get("tables"))
    used_tables = set()
    # (passage_ref, gap_number) -> the question that claimed it. Two questions
    # numbered gap 3 of the same passage would render on top of each other.
    seen_gaps = {}

    for idx, q in enumerate(questions):
        tag = f"q[{idx}]"
        ref = q.get("ref")
        if ref:
            tag = f"q[{idx}] ref={ref}"

        if not isinstance(q, dict):
            r.err(tag, "not an object")
            continue

        # unknown keys (typo catcher). A leading underscore marks a deliberate
        # note to whoever is reading the JSON — the same convention the pack
        # header uses — so those are skipped rather than reported as typos.
        for k in q:
            if k.startswith("_"):
                continue
            if k not in KNOWN_Q_KEYS:
                r.warn(tag, f"unknown field {k!r} will be ignored on import (typo?)")

        # required: subtopic. A pack may name it either way round — the Title
        # Case display name, or the snake_case slug the English and VR schemas
        # use — and everything downstream works from the canonical name.
        raw_sub = q.get("subtopic")
        sub = canonical_subtopic(code, raw_sub)
        if not raw_sub:
            r.err(tag, "missing required 'subtopic'")
        elif not sub:
            r.err(tag, f"subtopic {raw_sub!r} is not a canonical {code} subtopic. "
                       f"Allowed: {sorted(allowed_subs)}")

        # question_type — the third level of the taxonomy. Slugs are scoped by
        # subtopic, so this is only checked once the subtopic itself is valid.
        # Required for sections whose taxonomy has been rebuilt; the others have
        # no question types defined yet, so it is silently optional there.
        qt = q.get("question_type")
        if sub in allowed_types:
            valid_qt = allowed_types[sub]
            if not qt:
                if section_rebuilt and valid_qt:
                    r.err(tag, f"missing required 'question_type'. Valid for "
                               f"{sub!r}: {sorted(valid_qt)}")
            elif not valid_qt:
                # An empty set is not a typo — it means this section's taxonomy has
                # not been rebuilt yet, so there is no list to pick from. Saying
                # "Allowed: []" sent authors hunting for a slug that cannot exist.
                r.err(tag, f"{code} has no question types yet, so 'question_type' "
                           f"cannot be set on a {code} question. Remove it; it "
                           f"becomes required when the {code} taxonomy is rebuilt.")
            elif qt not in valid_qt:
                r.err(tag, f"question_type {qt!r} is not valid for subtopic "
                           f"{sub!r}. Allowed: {sorted(valid_qt)}")
        elif qt and not sub:
            r.warn(tag, "'question_type' set but 'subtopic' is missing, so it "
                        "cannot be checked")

        # also_tests — secondary (subtopic, question_type) pairs. Same canonical
        # names as the primary pair; a typo here is as silent as one there.
        extra = q.get("also_tests", [])
        if not isinstance(extra, list):
            r.err(tag, f"'also_tests' must be a list, got {type(extra).__name__}")
            extra = []
        for k, pair in enumerate(extra):
            where = f"{tag} also_tests[{k}]"
            if not isinstance(pair, dict):
                r.err(where, "each entry must be an object with 'subtopic' and "
                             "'question_type'")
                continue
            unknown = set(pair) - {"subtopic", "question_type"}
            if unknown:
                r.warn(where, f"unknown field(s) {sorted(unknown)} ignored on import")
            raw_psub, pqt = pair.get("subtopic"), pair.get("question_type")
            psub = canonical_subtopic(code, raw_psub)
            if not raw_psub:
                r.err(where, "missing 'subtopic'")
                continue
            if not psub:
                r.err(where, f"subtopic {raw_psub!r} is not a canonical {code} subtopic")
                continue
            if psub == sub and pqt == qt:
                r.err(where, "repeats the question's own subtopic and type; "
                             "also_tests records what ELSE the question needs")
                continue
            if pqt and pqt not in allowed_types.get(psub, set()):
                r.err(where, f"question_type {pqt!r} is not valid for {psub!r}")

        # The pairing convention, for subtopics whose types split across axes.
        # Statistics questions are a grid: an operation performed on a
        # representation. Filing only one half loses the other, so nudge — but
        # only warn, because "find the median of 4, 7, 8" genuinely has no
        # representation.
        axis_of = AXES.get((code, sub))
        if axis_of and qt in axis_of:
            here = axis_of[qt]
            others = {axis_of.get(p.get("question_type"))
                      for p in extra if isinstance(p, dict) and p.get("subtopic") == sub}
            if here == "representation" and "operation" not in others:
                r.warn(tag, f"{qt!r} is a representation; what does the pupil DO "
                            f"with it? Add the operation to 'also_tests' unless "
                            f"the question really is only about reading the format.")

        # passage_ref — points at one of the pack's shared passages.
        p_ref = q.get("passage_ref")
        if p_ref is not None:
            if not isinstance(p_ref, str) or not p_ref.strip():
                r.err(tag, "'passage_ref' must be a non-empty string")
            elif p_ref not in passages:
                r.err(tag, f"passage_ref {p_ref!r} does not match any passage in "
                           f"this pack. Declared: {sorted(passages) or 'none'}")
            else:
                used_passages.add(p_ref)
                if q.get("passage"):
                    r.err(tag, "has both 'passage_ref' and an inline 'passage'. "
                               "Use one: the ref shares the pack's passage, the "
                               "inline field carries text only this question uses.")

        # group_ref / table_ref — the instruction block and the data table this
        # question sits under. Unlike a passage these are copied onto the
        # question at import rather than shared through a container row, so a
        # question may legitimately carry a passage AND a group AND a table.
        g_ref = q.get("group_ref")
        if g_ref is not None:
            if not isinstance(g_ref, str) or not g_ref.strip():
                r.err(tag, "'group_ref' must be a non-empty string")
            elif g_ref not in groups:
                r.err(tag, f"group_ref {g_ref!r} does not match any group in this "
                           f"pack. Declared: {sorted(groups) or 'none'}")
            else:
                used_groups.add(g_ref)

        t_ref = q.get("table_ref")
        if t_ref is not None:
            if not isinstance(t_ref, str) or not t_ref.strip():
                r.err(tag, "'table_ref' must be a non-empty string")
            elif t_ref not in tables:
                r.err(tag, f"table_ref {t_ref!r} does not match any table in this "
                           f"pack. Declared: {sorted(tables) or 'none'}")
            else:
                used_tables.add(t_ref)
                if q.get("image"):
                    r.err(tag, "has both 'table_ref' and an 'image'. A question "
                               "shows one figure, and the table would replace the "
                               "image without saying so.")

        # gap numbers are unique within one passage
        if q.get("kind") == "cloze_gap":
            gap_key = (p_ref or "(inline)", q.get("gap_number"))
            if q.get("gap_number") is not None:
                if gap_key in seen_gaps:
                    r.err(tag, f"gap {q['gap_number']} of this passage is already "
                               f"filled by q[{seen_gaps[gap_key]}]")
                else:
                    seen_gaps[gap_key] = idx

        # line_ref — the passage line this question is about. Only meaningful
        # alongside a passage, and only as a line or a range of them.
        line_ref = q.get("line_ref")
        if line_ref is not None:
            text = str(line_ref).strip()
            if not text:
                r.err(tag, "'line_ref' is empty; omit it rather than leaving it blank")
            elif not LINE_REF_RE.match(text):
                r.err(tag, f"line_ref {line_ref!r} must be a line number or range, "
                           f"e.g. \"12\" or \"20-21\"")
            else:
                lo, _, hi = text.partition("-")
                if hi and int(hi) < int(lo):
                    r.err(tag, f"line_ref {text!r} runs backwards")
                if not q.get("passage") and not q.get("passage_ref"):
                    r.warn(tag, "'line_ref' is set but this question has no "
                                "passage, so there are no lines to point at")

        # required: stem
        stem = q.get("stem")
        if not stem or not str(stem).strip():
            r.err(tag, "missing or empty 'stem'")
        else:
            key = str(stem).strip()
            if key in seen_stems:
                r.warn(tag, f"duplicate stem also at q[{seen_stems[key]}] (accidental copy?)")
            else:
                seen_stems[key] = idx

        # kind
        kind = q.get("kind", "mcq")
        if kind not in VALID_KINDS:
            r.err(tag, f"kind {kind!r} invalid; must be one of {sorted(VALID_KINDS)}")

        # A field belonging to a kind this question is not. The importer would
        # drop it without a word, and the question would import looking fine and
        # answering nothing — the same silent shape as a mistyped field name,
        # which is why that is already caught above.
        if q.get("option_groups") and kind not in GROUPED_KINDS:
            r.err(tag, f"'option_groups' belongs to kind 'grouped_options', but "
                       f"this question is {kind!r}. It would be ignored on import.")
        if q.get("segments") and kind not in SELECTION_KINDS:
            r.err(tag, f"'segments' belongs to kinds {sorted(SELECTION_KINDS)}, but "
                       f"this question is {kind!r}. It would be ignored on import.")

        # difficulty: required on every contributor question, integer 1-5.
        # 1-3 until the adaptive work: the model, the generators and both
        # author papers all use 1-5, so the narrower rule rejected valid packs.
        if "difficulty" not in q:
            r.err(tag, "missing required 'difficulty' (integer 1-5)")
        else:
            d = q["difficulty"]
            if not isinstance(d, int) or isinstance(d, bool) or d not in (1, 2, 3, 4, 5):
                r.err(tag, f"difficulty {d!r} invalid; must be an integer from 1 to 5")

        # per-question is_placeholder override, if present, must be bool
        if "is_placeholder" in q and not isinstance(q["is_placeholder"], bool):
            r.err(tag, f"'is_placeholder' must be true or false, got {q['is_placeholder']!r}")

        # ref / number bookkeeping (traceability, not used by importer)
        if not ref:
            r.warn(tag, "no 'ref' code — recommended for tracking and dedup")
        else:
            if ref in seen_refs:
                r.err(tag, f"duplicate ref {ref!r} also at q[{seen_refs[ref]}]; refs must be unique")
            seen_refs[ref] = idx
        if "number" not in q:
            r.warn(tag, "no 'number' — recommended so humans can find the question")

        # ---- the answer, which differs entirely by kind ----------------
        if kind in TYPED_KINDS:
            _check_typed_answer(r, tag, q, kind)
            continue

        if kind in SELECTION_KINDS:
            _check_segments(r, tag, q, kind)
            continue

        if kind in GROUPED_KINDS:
            _check_option_groups(r, tag, q)
            continue

        if kind in MARKED_KINDS:
            _check_marked_by_human(r, tag, q, kind)
            continue

        if kind == "cloze_gap":
            _check_cloze(r, tag, q)
            # and then the ordinary option checks below, because a gap is
            # answered by picking one of the words offered for it.

        # options — every kind that is answered by picking one
        opts = q.get("options")
        if not isinstance(opts, list) or len(opts) < 2:
            r.err(tag, "must have an 'options' list with at least 2 entries")
            continue

        n_correct = 0
        for j, opt in enumerate(opts):
            if not isinstance(opt, dict):
                r.err(f"{tag} opt[{j}]", "not an object")
                continue
            for k in opt:
                if k not in KNOWN_OPT_KEYS:
                    r.warn(f"{tag} opt[{j}]", f"unknown field {k!r} ignored on import")
            if not opt.get("text") or not str(opt["text"]).strip():
                r.err(f"{tag} opt[{j}]", "missing or empty 'text'")
            c = opt.get("correct", False)
            if not isinstance(c, bool):
                r.err(f"{tag} opt[{j}]", f"'correct' must be true/false, got {c!r}")
            elif c:
                n_correct += 1

        if n_correct != 1:
            r.err(tag, f"has {n_correct} correct options; every question needs exactly one "
                       f"'correct': true")

        _check_equivalent_options(r, tag, opts)

    # Where the answers sit. A whole-pack check rather than a per-question one:
    # no single question can be wrong about this, which is exactly why it went
    # unnoticed until a pack arrived with the key in the same place 25 times.
    for where, msg in check_key_distribution(key_positions(questions)):
        r.warn(where, msg)

    for ref in sorted(set(passages) - used_passages):
        r.warn("passages", f"passage {ref!r} is declared but no question points at "
                           f"it, so it will not be imported")
    for ref in sorted(set(groups) - used_groups):
        r.warn("groups", f"group {ref!r} is declared but no question points at it, "
                         f"so its instruction and example will not be imported")
    for ref in sorted(set(tables) - used_tables):
        r.warn("tables", f"table {ref!r} is declared but no question points at it, "
                         f"so it will not be imported")

    status = "fail" if r.errors else "pass"
    facts = {
        "source": source,
        "code": code,
        "refs": set(seen_refs),
        "stems": set(seen_stems),
    }
    return r, status, facts


def _cross_pack(packs):
    """Check the packs against EACH OTHER. Returns True if anything failed.

    Every other check in this file is scoped to one file, which is fine for one
    author and wrong for four working in parallel: two packs can each be
    perfectly valid and still collide. The collision that matters most is
    `source` — import_pack.py deletes by (source, section), so two packs sharing
    one means the second import erases the first author's questions.

    Only meaningful when several packs are passed at once, so CI should run this
    over the whole folder rather than just the files a branch changed.
    """
    if len(packs) < 2:
        return False

    print(f"\n=== cross-pack checks ({len(packs)} packs) ===")
    failed = False

    by_source = {}
    for path, f in packs:
        if f["source"]:
            by_source.setdefault((f["code"], f["source"]), []).append(path)
    for (code, source), where in sorted(by_source.items()):
        if len(where) > 1:
            failed = True
            print(f"  ERROR  [source] {code} packs share source {source!r}: "
                  f"{', '.join(where)}")
            print(f"           import_pack.py deletes by (source, section), so "
                  f"importing these in sequence DELETES the earlier pack's "
                  f"questions. Give each batch its own source.")

    by_ref = {}
    for path, f in packs:
        for ref in f["refs"]:
            by_ref.setdefault(ref, []).append(path)
    dupe_refs = {r: w for r, w in by_ref.items() if len(w) > 1}
    for ref, where in sorted(dupe_refs.items()):
        failed = True
        print(f"  ERROR  [ref] {ref!r} used in {len(where)} packs: "
              f"{', '.join(sorted(set(where)))}")

    by_stem = {}
    for path, f in packs:
        for stem in f["stems"]:
            by_stem.setdefault(" ".join(stem.lower().split()), []).append(path)
    dupe_stems = {s: w for s, w in by_stem.items() if len(set(w)) > 1}
    for stem, where in sorted(dupe_stems.items())[:20]:
        short = stem if len(stem) <= 70 else stem[:67] + "..."
        print(f"  warn   [stem] {short!r} appears in {len(set(where))} packs: "
              f"{', '.join(sorted(set(where)))}")
    if len(dupe_stems) > 20:
        print(f"  warn   [stem] ...and {len(dupe_stems) - 20} more duplicated "
              f"across packs")

    if not failed and not dupe_stems:
        print("  OK — no collisions between packs.")
    return failed


def main(argv):
    args = argv[1:]
    if not args:
        print(__doc__)
        return 0

    # expand globs the shell may not have (Windows, quoted args)
    paths = []
    for a in args:
        matched = glob.glob(a)
        paths.extend(matched if matched else [a])

    any_error = False
    unreadable = False
    packs = []
    skipped = []
    for p in paths:
        r, status, facts = validate(p)
        if status == "skipped":
            skipped.append(p)
            continue
        r.print()
        if r.errors:
            any_error = True
        if status == "unreadable":
            unreadable = True
        if facts:
            packs.append((p, facts))

    for p in skipped:
        print(f"\n=== {p} ===\n  skipped — not a question pack "
              f"(exam paper or taxonomy file, loaded by a different importer).")

    if _cross_pack(packs):
        any_error = True

    print("\n" + "-" * 60)
    if unreadable:
        print("RESULT: some files could not be read/parsed.")
        return 2
    if any_error:
        print("RESULT: FAIL — do not merge until the errors above are fixed.")
        return 1
    print("RESULT: PASS — all packs conform to the import contract.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
