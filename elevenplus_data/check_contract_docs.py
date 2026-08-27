#!/usr/bin/env python3
"""
Checks that the authoring contract's supporting docs and tools agree with
taxonomy.json's `rebuilt` flags per section.

This is the class of staleness the NVR taxonomy rebuild actually hit: v6 of
taxonomy.json flipped NVR from `rebuilt: false` to `true` (question_type went
from forbidden to required), but that PR only touched taxonomy.json and the
worked example — CLAUDE.md's NVR section and preview_questions.py's hardcoded
`if code == "NVR"` branch both kept telling an author the opposite for two
more commits, and nothing caught it because neither file is generated from
taxonomy.json, they're hand-maintained prose that has to be updated in step.

Not a parser: taxonomy.json is JSON, so that side is exact. CLAUDE.md and
preview_questions.py are read as text and checked with plain string/regex
matching — enough to catch "this section's rebuilt flag changed and a doc or
code branch still assumes the old value". It is not a substitute for reading
the doc when you touch it, and a clean run here does not mean the prose is
otherwise accurate — only that it doesn't contradict the flag.

Run:  python3 elevenplus_data/check_contract_docs.py
Exit 0 clean, exit 1 if something disagrees. Stdlib only, reads three files,
writes nothing.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TAXONOMY = ROOT / "elevenplus_data" / "taxonomy.json"
CLAUDE_MD = ROOT / "elevenplus_data" / "CLAUDE.md"
PREVIEW = ROOT / "elevenplus_data" / "preview_questions.py"

# Phrases that only make sense for a NOT-rebuilt section (question_type
# forbidden). Finding one inside a rebuilt section's own text is the bug.
STALE_FORBIDDEN_PHRASES = ("must not carry", "must be omitted", "not rebuilt yet")


def load_taxonomy():
    if not TAXONOMY.exists():
        sys.exit(f"taxonomy not found at {TAXONOMY}")
    return json.loads(TAXONOMY.read_text())


def claude_md_section(code, text):
    """The chunk of CLAUDE.md between this section's '### CODE —' header and
    the next '### ' header (or end of file). None if there is no such header."""
    match = re.search(rf"^### {re.escape(code)} —.*$", text, re.MULTILINE)
    if not match:
        return None
    rest = text[match.end():]
    next_header = re.search(r"^### ", rest, re.MULTILINE)
    end = match.end() + (next_header.start() if next_header else len(rest))
    return text[match.start():end]


def check_claude_md(data, problems):
    if not CLAUDE_MD.exists():
        problems.append(f"CLAUDE.md not found at {CLAUDE_MD}")
        return
    text = CLAUDE_MD.read_text()

    for code, sec in data["sections"].items():
        block = claude_md_section(code, text)
        if block is None:
            problems.append(f"CLAUDE.md: no '### {code} —' section header found")
            continue
        if sec.get("rebuilt"):
            lowered = block.lower()
            for phrase in STALE_FORBIDDEN_PHRASES:
                if phrase in lowered:
                    problems.append(
                        f"CLAUDE.md: {code} is rebuilt:true in taxonomy.json, but its "
                        f"own section still contains {phrase!r} — stale doc")

    # The single shared requirement-table row, checked separately: it names
    # every section on one line rather than living inside a per-section block.
    table_row = next(
        (line for line in text.splitlines() if line.startswith("| `question_type`")), None)
    if table_row is None:
        problems.append("CLAUDE.md: could not find the `question_type` requirement table row")
        return
    all_rebuilt = all(sec.get("rebuilt") for sec in data["sections"].values())
    if all_rebuilt:
        lowered_row = table_row.lower()
        for phrase in STALE_FORBIDDEN_PHRASES:
            if phrase in lowered_row:
                problems.append(
                    f"CLAUDE.md: every section is rebuilt:true in taxonomy.json, but "
                    f"the question_type requirement table row still says {phrase!r}: "
                    f"{table_row.strip()!r}")


def check_preview_questions(data, problems):
    if not PREVIEW.exists():
        problems.append(f"preview_questions.py not found at {PREVIEW}")
        return
    text = PREVIEW.read_text()
    for code, sec in data["sections"].items():
        if not sec.get("rebuilt"):
            continue
        # A hardcoded branch on this section's code, near "question_type",
        # asserting it must NOT be set — the exact shape of the bug this
        # check exists for.
        for match in re.finditer(rf'if\s+code\s*==\s*"{re.escape(code)}"', text):
            window = text[match.start():match.start() + 400]
            lowered = window.lower()
            if "question_type" in lowered and (
                "must not" in lowered or "must be omitted" in lowered
            ):
                line_no = text.count("\n", 0, match.start()) + 1
                problems.append(
                    f"preview_questions.py:{line_no}: hardcoded 'if code == "
                    f"{code!r}' branch says question_type must not be set, but "
                    f"{code} is rebuilt:true in taxonomy.json")


def main():
    data = load_taxonomy()
    problems = []
    check_claude_md(data, problems)
    check_preview_questions(data, problems)
    if problems:
        for p in problems:
            print(f"FAIL  {p}")
        print(f"\n{len(problems)} contract-doc consistency problem(s).")
        return 1
    print("Contract docs agree with taxonomy.json's rebuilt flags.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
