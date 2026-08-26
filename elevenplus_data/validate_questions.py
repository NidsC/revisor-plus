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

# The drawing engine, imported rather than described. `catalog/figures` is
# deliberately Django-free and stdlib-only so this file can use it: the checks in
# `_check_figure` are then made against what the app will actually draw, not
# against a second copy of the rules that can drift from it.
#
# Optional, because this checker is also handed to contributors on its own. When
# it is missing, figure specs are checked for shape but not for vocabulary, and
# the run says so rather than quietly passing everything.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from catalog.figures import OPTION_KINDS as FIGURE_OPTION_KINDS
    from catalog.figures import SUPPORTED as FIGURE_KINDS
    from catalog.figures import intrinsic_width, render_option_figure
    from catalog.figures.glyphs import (FILLS, FLIPS, MAX_REPEAT, POSITIONS,
                                        ROTATION_STEP, SHAPES, SIZES, STROKES,
                                        fits_without_compressing)
    from catalog.figures.layout import MAX_INTRINSIC
    FIGURES_AVAILABLE = True
except ImportError:                                        # pragma: no cover
    FIGURES_AVAILABLE = False
    FIGURE_KINDS = FIGURE_OPTION_KINDS = set()

# Keys a glyph spec may carry. Every value is checked against a closed set in
# `catalog/figures/glyphs.py`, which is the point of that module being closed: an
# author who writes "octogon" is told here, rather than the app drawing nothing
# and the question reaching a pupil with a blank panel.
KNOWN_GLYPH_KEYS = {"shape", "size", "fill", "rot", "at", "stroke", "flip",
                    "repeat", "marker"}
FIGURE_DATA_KEYS = {
    "nvr_grid": ({"cells"}, {"cols", "blank", "separator_after", "alt"}),
    "nvr_panel": ({"cell"}, {"alt"}),
    "nvr_net": ({"squares"}, {"alt"}),
}

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
               "error_span", "select_word", "cloze_gap"}
# Typed by the pupil and marked against `answer`.
TYPED_KINDS = {"numeric", "short_text"}
# Answered by picking one of the options. Marked identically; presented differently.
OPTION_KINDS = {"mcq", "error_span", "select_word", "cloze_gap"}
# The options are consecutive pieces of the stem, declared as `segments`.
SELECTION_KINDS = {"error_span", "select_word"}
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
    # cloze and shared passages
    "gap_number", "passage_ref",
    # human-marked
    "marks", "model_answer", "rubric",
    # A diagram declared as data and drawn at render time. `image` still takes a
    # committed file; this is the route that did not exist, and without which a
    # non-verbal pack could not be authored at all.
    "figure",
}

# "12" or "20-21" — a line, or a range of lines, of the passage.
LINE_REF_RE = re.compile(r"^\d+(-\d+)?$")
KNOWN_OPT_KEYS = {"text", "correct", "figure"}


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


def _check_glyph(r, tag, where, glyph):
    """One glyph spec, against the closed vocabulary in catalog/figures/glyphs.py."""
    if not isinstance(glyph, dict):
        r.err(tag, f"{where} must be an object describing one shape, got "
                   f"{type(glyph).__name__}")
        return
    for key in glyph:
        if key not in KNOWN_GLYPH_KEYS:
            r.err(tag, f"{where}: unknown field {key!r}. A glyph may carry "
                       f"{sorted(KNOWN_GLYPH_KEYS)}")
    if not FIGURES_AVAILABLE:
        return
    shape = glyph.get("shape")
    if shape is None:
        r.err(tag, f"{where}: missing 'shape'")
    elif shape not in SHAPES:
        r.err(tag, f"{where}: shape {shape!r} is not one this build can draw. "
                   f"Known: {sorted(SHAPES)}")
    for field, allowed in (("size", SIZES), ("fill", FILLS),
                           ("stroke", STROKES), ("at", POSITIONS),
                           ("flip", FLIPS)):
        value = glyph.get(field)
        if value is not None and value not in allowed:
            r.err(tag, f"{where}: {field} {value!r} is not valid. "
                       f"Known: {sorted(allowed)}")
    rotation = glyph.get("rot")
    if rotation is not None:
        if not isinstance(rotation, int):
            r.err(tag, f"{where}: 'rot' must be a whole number of degrees, "
                       f"got {rotation!r}")
        elif rotation % ROTATION_STEP:
            # Not pedantry. A pupil cannot tell 20 degrees from 25 on a 46-pixel
            # glyph, so an off-step angle makes a distractor that differs from
            # the key by an amount nobody can see.
            r.err(tag, f"{where}: 'rot' must be a multiple of {ROTATION_STEP}°, "
                       f"got {rotation}. Smaller steps are not distinguishable "
                       f"at the size these draw.")
    repeat = glyph.get("repeat")
    if repeat is not None:
        if not isinstance(repeat, int) or not 1 <= repeat <= MAX_REPEAT:
            r.err(tag, f"{where}: 'repeat' must be a whole number from 1 to "
                       f"{MAX_REPEAT}, got {repeat!r}")
        elif not fits_without_compressing(glyph.get("size", "medium"), repeat):
            r.warn(tag, f"{where}: {repeat} glyphs at size "
                        f"{glyph.get('size', 'medium')!r} do not fit a panel, so "
                        f"they will be drawn smaller. If the rule is how MANY "
                        f"there are, use 'tiny' — marks that shrink as the count "
                        f"rises read as a size rule too.")


def _check_cell(r, tag, where, cell):
    if not isinstance(cell, dict):
        r.err(tag, f"{where} must be an object, got {type(cell).__name__}")
        return
    items = cell.get("items")
    if items is None:
        _check_glyph(r, tag, where, cell)
        return
    if not isinstance(items, list) or not items:
        r.err(tag, f"{where}: 'items' must be a non-empty list of shapes")
        return
    for index, item in enumerate(items):
        _check_glyph(r, tag, f"{where}.items[{index}]", item)


def _check_figure(r, tag, where, figure, allowed_kinds=None):
    """A `figure` spec, against what catalog/figures can actually draw."""
    if not isinstance(figure, dict):
        r.err(tag, f"{where} must be an object like "
                   f'{{"kind": "nvr_grid", "data": {{...}}}}, got '
                   f"{type(figure).__name__}")
        return
    unknown = set(figure) - {"kind", "data"}
    if unknown:
        r.err(tag, f"{where}: unknown field(s) {sorted(unknown)}; a figure has "
                   f"only 'kind' and 'data'")
    kind = figure.get("kind")
    known = allowed_kinds if allowed_kinds is not None else FIGURE_KINDS
    if not kind:
        r.err(tag, f"{where}: missing 'kind'")
        return
    if FIGURES_AVAILABLE and kind not in known:
        r.err(tag, f"{where}: figure kind {kind!r} is not one this build can "
                   f"draw here. Allowed: {sorted(known)}")
        return
    data = figure.get("data")
    if not isinstance(data, dict):
        r.err(tag, f"{where}: 'data' must be an object")
        return
    if kind not in FIGURE_DATA_KEYS:
        return                      # a Maths kind; its data is numbers, not glyphs
    required, optional = FIGURE_DATA_KEYS[kind]
    for key in set(data) - required - optional:
        r.err(tag, f"{where}: unknown field {key!r} for kind {kind!r}. "
                   f"Allowed: {sorted(required | optional)}")
    for key in required - set(data):
        r.err(tag, f"{where}: kind {kind!r} requires {key!r}")

    if kind == "nvr_panel" and "cell" in data:
        _check_cell(r, tag, f"{where}.data.cell", data["cell"])
    elif kind == "nvr_grid" and "cells" in data:
        cells = data["cells"]
        if not isinstance(cells, list) or not cells:
            r.err(tag, f"{where}.data.cells must be a non-empty list")
            return
        for index, cell in enumerate(cells):
            if cell is None:
                continue            # the blank panel the pupil fills in
            _check_cell(r, tag, f"{where}.data.cells[{index}]", cell)
        blank = data.get("blank")
        if blank is not None:
            if not isinstance(blank, int) or not 0 <= blank < len(cells):
                r.err(tag, f"{where}: 'blank' must be an index into 'cells' "
                           f"(0 to {len(cells) - 1}), got {blank!r}")
            elif cells[blank] is not None:
                r.err(tag, f"{where}: 'blank' points at cells[{blank}], which "
                           f"has contents. The blank cell must be null.")
        for index, cell in enumerate(cells):
            if cell is None and blank != index:
                r.err(tag, f"{where}.data.cells[{index}] is null but 'blank' is "
                           f"{blank!r}. A null cell draws nothing and is only "
                           f"meaningful as the one the pupil supplies.")
    elif kind == "nvr_net" and "squares" in data:
        squares = data["squares"]
        if not isinstance(squares, list) or not squares:
            r.err(tag, f"{where}.data.squares must be a non-empty list of "
                       f"[row, column] pairs")
            return
        for index, square in enumerate(squares):
            if (not isinstance(square, list) or len(square) != 2
                    or not all(isinstance(v, int) and v >= 0 for v in square)):
                r.err(tag, f"{where}.data.squares[{index}] must be "
                           f"[row, column], whole numbers from 0, got {square!r}")


def _check_option_figures(r, tag, opts):
    """The answers of a question whose options are pictures.

    Two rules, both learned from bugs this build actually had:

    * All or none. A question with a picture on two of its four answers is one
      whose other two render as empty tiles.
    * No two options may draw the same picture. That is checked by drawing them,
      because the parameters are not the test: `rot: 180` and `rot: -180` are
      different specs and the same panel. The generators shipped exactly that —
      a half-turn question whose "turned the wrong way" distractor was the
      correct answer — and it stayed invisible for as long as the options held
      the bare letters "A".."D", which are always distinct however identical the
      pictures behind them.
    """
    figures = [(index, opt.get("figure")) for index, opt in enumerate(opts)
               if isinstance(opt, dict)]
    present = [(index, fig) for index, fig in figures if fig is not None]
    if not present:
        return
    if len(present) != len(figures):
        missing = [index for index, fig in figures if fig is None]
        r.err(tag, f"option(s) {missing} have no 'figure' while others do. Give "
                   f"every option a picture or none of them — an option with no "
                   f"figure renders as an empty tile beside the ones that have one.")
    for index, figure in present:
        _check_figure(r, tag, f"opt[{index}].figure", figure,
                      allowed_kinds=FIGURE_OPTION_KINDS)
    if not FIGURES_AVAILABLE:
        return
    drawn = {}
    for index, figure in present:
        markup = render_option_figure(figure)
        if not markup:
            continue
        if markup in drawn:
            first = drawn[markup]
            correct = [j for j in (first, index)
                       if opts[j].get("correct")]
            detail = (" and one of them is the correct answer, so this question "
                      "has two right answers" if correct else "")
            r.err(tag, f"opt[{first}] and opt[{index}] draw the same picture"
                       f"{detail}. Two answers a pupil cannot tell apart is one "
                       f"answer with two letters on it.")
        else:
            drawn[markup] = index


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
    if q.get("segments"):
        r.err(tag, "kind 'cloze_gap' offers 'options' for the gap, not 'segments'")


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

        # difficulty: required on every contributor question, integer 1-5.
        # 1-3 until the adaptive work: the model, the generators and both
        # author papers all use 1-5, so the narrower rule rejected valid packs.
        if "difficulty" not in q:
            r.err(tag, "missing required 'difficulty' (integer 1-5)")
        else:
            d = q["difficulty"]
            if not isinstance(d, int) or isinstance(d, bool) or d not in (1, 2, 3, 4, 5):
                r.err(tag, f"difficulty {d!r} invalid; must be an integer from 1 to 5")

        # figure: a diagram declared as data, drawn by catalog/figures.
        if "figure" in q and q["figure"] is not None:
            _check_figure(r, tag, "figure", q["figure"])
            if FIGURES_AVAILABLE and isinstance(q["figure"], dict):
                width = intrinsic_width(q["figure"].get("kind"),
                                        q["figure"].get("data") or {})
                if width > MAX_INTRINSIC:
                    # A warning, not an error. The figure is still drawn at its
                    # true proportions and scrolls; it is not shrunk, because
                    # shrinking is what made two figures in one paper disagree
                    # about how big a panel is. But an author should know.
                    r.warn(tag, f"figure is {width}px wide, over the {MAX_INTRINSIC}px "
                                f"that fits a phone, so it will scroll sideways "
                                f"there. Fewer panels, or accept the scroll.")
            if q.get("image"):
                r.err(tag, "carries both 'figure' and 'image'. Only one diagram "
                           "is rendered; pick the generated one or the file.")

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
        _check_option_figures(r, tag, opts)

    for ref in sorted(set(passages) - used_passages):
        r.warn("passages", f"passage {ref!r} is declared but no question points at "
                           f"it, so it will not be imported")

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
