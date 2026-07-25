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
import sys

# ---------------------------------------------------------------------------
# The contract. Keep this block in sync with the live taxonomy if it ever grows.
# These are the CANONICAL subtopic names (post-reclassify). Use these exact
# strings — a typo or a legacy name creates a brand-new orphan subtopic silently.
# ---------------------------------------------------------------------------
SECTIONS = {"ENG", "MAT", "VR", "NVR"}

SECTION_NAME = {
    "ENG": "English",
    "MAT": "Maths",
    "VR": "Verbal Reasoning",
    "NVR": "Non-Verbal Reasoning",
}

SUBTOPICS = {
    "ENG": {
        "Grammar & Punctuation",
        "Reading Comprehension",
        "Spelling",
        "Vocabulary",
    },
    "MAT": {
        "Algebra",
        "Four Operations",
        "Fractions, Decimals & Percentages",
        "Geometry & Shape",
        "Measurement",
        "Number & Place Value",
        "Ratio & Proportion",
        "Statistics & Data Handling",
    },
    "VR": {
        "Analogies",
        "Codes & Sequences",
        "Hidden & Compound Words",
        "Letters & Alphabet",
        "Logic Problems",
        "Odd One Out",
        "Word Meanings",
    },
    "NVR": {
        "3D Shapes & Nets",
        "Analogies",
        "Codes",
        "Odd One Out",
        "Rotation & Reflection",
        "Series & Sequences",
    },
}

# Every 11+ question is multiple choice. The True/False/Can't-tell format was
# UCAT-only and has been removed.
VALID_KINDS = {"mcq"}

# Sources already used by the built-in demo content. A contributor pack that reuses
# one of these would DELETE those questions on import — so we forbid it.
RESERVED_SOURCES = {"seed"}

# Keys the importer understands. Anything else is almost certainly a typo
# (e.g. "explaination") and gets ignored on import, so we flag it.
KNOWN_Q_KEYS = {
    "number", "ref", "subtopic", "kind", "stem",
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


def validate(path):
    r = Report(path)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        r.err("file", "not found")
        return r, "unreadable"
    except json.JSONDecodeError as e:
        r.err("file", f"not valid JSON: {e}")
        return r, "unreadable"

    # ---- section header -----------------------------------------------------
    sec = data.get("section")
    if not isinstance(sec, dict):
        r.err("section", "missing top-level 'section' object")
        return r, "fatal"

    code = sec.get("code")
    if code not in SECTIONS:
        r.err("section.code", f"must be one of {sorted(SECTIONS)}, got {code!r}")
        return r, "fatal"

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
        return r, "fatal"

    allowed_subs = SUBTOPICS[code]
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

        # difficulty: required on every contributor question, integer 1-3
        if "difficulty" not in q:
            r.err(tag, "missing required 'difficulty' (integer 1, 2 or 3)")
        else:
            d = q["difficulty"]
            if not isinstance(d, int) or isinstance(d, bool) or d not in (1, 2, 3):
                r.err(tag, f"difficulty {d!r} invalid; must be integer 1, 2 or 3")

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

    status = "fail" if r.errors else "pass"
    return r, status


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
    for p in paths:
        r, status = validate(p)
        r.print()
        if r.errors:
            any_error = True
        if status == "unreadable":
            unreadable = True

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
