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
    """Return (sections, section_name, subtopics, question_types, rebuilt)."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        sys.exit(f"FATAL: cannot read the taxonomy at {path}: {e}\n"
                 "It is the contract this checker enforces; without it nothing "
                 "can be validated.")

    sections, names, subs, qtypes, rebuilt = set(), {}, {}, {}, {}
    for code, sec in data["sections"].items():
        sections.add(code)
        names[code] = sec["name"]
        subs[code] = {s["name"] for s in sec["subtopics"]}
        qtypes[code] = {s["name"]: {t["slug"] for t in s["question_types"]}
                        for s in sec["subtopics"]}
        rebuilt[code] = bool(sec.get("rebuilt"))
    return sections, names, subs, qtypes, rebuilt


SECTIONS, SECTION_NAME, SUBTOPICS, QUESTION_TYPES, REBUILT = _load_taxonomy()

# Every 11+ question is multiple choice. The True/False/Can't-tell format was
# UCAT-only and has been removed.
VALID_KINDS = {"mcq"}

# Sources already used by the built-in demo content. A contributor pack that reuses
# one of these would DELETE those questions on import — so we forbid it.
RESERVED_SOURCES = {"seed"}

# Keys the importer understands. Anything else is almost certainly a typo
# (e.g. "explaination") and gets ignored on import, so we flag it.
KNOWN_Q_KEYS = {
    "number", "ref", "subtopic", "question_type", "kind", "stem",
    "passage", "explanation", "image", "difficulty", "options", "is_placeholder",
}
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

    for idx, q in enumerate(questions):
        tag = f"q[{idx}]"
        ref = q.get("ref")
        if ref:
            tag = f"q[{idx}] ref={ref}"

        if not isinstance(q, dict):
            r.err(tag, "not an object")
            continue

        # unknown keys (typo catcher)
        for k in q:
            if k not in KNOWN_Q_KEYS:
                r.warn(tag, f"unknown field {k!r} will be ignored on import (typo?)")

        # required: subtopic
        sub = q.get("subtopic")
        if not sub:
            r.err(tag, "missing required 'subtopic'")
        elif sub not in allowed_subs:
            r.err(tag, f"subtopic {sub!r} is not a canonical {code} subtopic. "
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
            elif qt not in valid_qt:
                r.err(tag, f"question_type {qt!r} is not valid for subtopic "
                           f"{sub!r}. Allowed: {sorted(valid_qt)}")
        elif qt and not sub:
            r.warn(tag, "'question_type' set but 'subtopic' is missing, so it "
                        "cannot be checked")

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

        # options
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
