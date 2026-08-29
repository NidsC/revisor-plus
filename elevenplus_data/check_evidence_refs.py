#!/usr/bin/env python3
"""
Checks that every taxonomy.json question_type marked "provenance": "authored" cites,
in its `evidence` field, a `ref` that actually exists in a tracked elevenplus_data/*.json
pack.

Why this exists: `evidence` is the only thing that turns "proposed" into "authored" --
elevenplus_data/CLAUDE.md builds a claim on the count ("18 of the 81 types are evidenced
by questions already written"). Nothing before this checked that the citation actually
resolves to a real, tracked question. pending_issues.md recorded a case where it didn't:
four ENG types cited a bare ordinal ("contrib q2"..."q7") naming no file, pointing at an
untracked, gitignored scratch file that exists in one person's checkout and no clone. Two
of those citations also turned out to be swapped against the wrong type.

This is the cross-pack `ref` uniqueness check validate_questions.py already runs, pointed
the other way: that check asks "does any ref appear in two packs?"; this asks "does this
evidence citation appear in any pack at all?".

**ENG only.** "Authored" means something different per section, and only ENG's means "a
question in a tracked pack proves this": elevenplus_data/CLAUDE.md's own claim ("18 of the
81 [ENG] types are evidenced by questions already written") is what this check verifies.
VR's `authored` types are evidenced by a collaborator's report of real GL papers, not by a
pack ref, and NVR's cite exam-board booklets directly (e.g. "GL Assessment familiarisation
Bk1 SS1 Q1-20") -- neither names a `ref` because neither is claiming one. Checking those
against tracked refs produces only false positives, confirmed by running an earlier,
section-generic version of this script against the current taxonomy.

Run:  python3 elevenplus_data/check_evidence_refs.py
Exit 0 always -- advisory only, never fails a build. Prints every unresolved "authored"
citation and the resolved/total count so the CLAUDE.md figure can be kept honest.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "elevenplus_data"
TAXONOMY = DATA_DIR / "taxonomy.json"

# Files in elevenplus_data/ that hold packs (or paper imports) with question refs to
# collect, as opposed to taxonomy.json / nvr_evidence_manifest.json / tooling.
PACK_GLOBS = ("contrib_*.json", "_EXAMPLE.*.json", "_TEMPLATE.*.json", "*-paper-*.json")


def known_refs():
    refs = {}
    seen = set()
    for pattern in PACK_GLOBS:
        for path in sorted(DATA_DIR.glob(pattern)):
            if path in seen:
                continue
            seen.add(path)
            try:
                data = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            for q in data.get("questions", []):
                ref = q.get("ref")
                if ref:
                    refs.setdefault(ref, path.name)
    return refs


CHECKED_SECTIONS = ("ENG",)


def check_evidence(taxonomy, refs, errors, resolved_count, total_count):
    for section_code, section in taxonomy["sections"].items():
        if section_code not in CHECKED_SECTIONS:
            continue
        for sub in section.get("subtopics", []):
            for t in sub.get("question_types", []):
                if not isinstance(t, dict) or t.get("provenance") != "authored":
                    continue
                total_count[0] += 1
                evidence = t.get("evidence", "")
                hit = next((ref for ref in refs if ref and ref in evidence), None)
                if hit:
                    resolved_count[0] += 1
                else:
                    errors.append(
                        f"{section_code} / {sub['name']} / {t['slug']}: evidence "
                        f"{evidence!r} names no ref found in a tracked pack")


def main():
    taxonomy = json.loads(TAXONOMY.read_text())
    refs = known_refs()
    errors = []
    resolved_count, total_count = [0], [0]

    check_evidence(taxonomy, refs, errors, resolved_count, total_count)

    for e in errors:
        print(f"WARN  {e}")
    print(f"\n{resolved_count[0]} of {total_count[0]} 'authored' question_types have "
          f"evidence resolving to a tracked ref ({len(errors)} unresolved).")
    print("Advisory only -- exit 0 regardless.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
