#!/usr/bin/env python3
"""
Checks that every NVR question_type's evidence names at least one exam board,
and flags (non-fatally) a question_type whose evidence is single-board while a
sibling in the same subtopic is multi-board -- turning taxonomy.json's own
prose warnings (e.g. "3D Shapes & Nets ... zero GL evidence across three
official booklets") into a structured, permanent check instead of something
only visible to someone who happens to reread the comment.

This is what "the taxonomy stays valid across multiple exam boards" means
operationally: it can't re-verify pedagogical correctness -- that needs a
human reading a real paper -- but it stops the taxonomy silently drifting
toward single-board bias as future contributors add question_types without
rereading all nine source papers. When a new board's papers are added, add
its name to BOARD_TOKENS; no other code changes needed, since this reads
taxonomy.json generically.

Board names are recognised by simple word-boundary matching against a small,
closed vocabulary -- evidence text is human-authored prose, not structured
data, so this is pattern matching, not parsing.

Also warns about any elevenplus_data/nvr_evidence_manifest.json source marked
locally_available: false, so the current Bk2/Bk3 sourcing gap (see the
manifest's own _comment) stays visible in CI output rather than only in a
file someone has to remember to open.

Run:  python3 elevenplus_data/check_nvr_board_coverage.py
Exit 0 unless a question_type's evidence names no board at all (an ERROR).
Single-board-vs-multi-board-sibling and locally_available: false are both
WARNINGS -- known, already-tracked conditions, not new regressions.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TAXONOMY = ROOT / "elevenplus_data" / "taxonomy.json"
MANIFEST = ROOT / "elevenplus_data" / "nvr_evidence_manifest.json"

BOARD_TOKENS = ["GL", "CEM", "Bond", "Examberry"]

# A type honestly declaring itself unevidenced by any paper -- e.g. it matches
# something the figure engine already draws natively, with no paper behind it
# (corner-marker-code, apply-rotation) -- is not the same defect as evidence
# text that simply forgot to name a board. The first is the whole point of
# marking a type this way (see 0e97a1c's precedent); only the second is a real
# gap worth failing CI over.
NOT_EVIDENCED_MARKERS = ("not evidenced", "no paper evidence", "not directly evidenced")


def boards_in(text):
    return {b for b in BOARD_TOKENS if re.search(rf"\b{re.escape(b)}\b", text)}


def check_evidence_coverage(nvr, errors, warnings):
    for sub in nvr["subtopics"]:
        per_type = {}
        for t in sub.get("question_types", []):
            if not isinstance(t, dict):
                continue
            evidence = t.get("evidence", "")
            boards = boards_in(evidence)
            per_type[t["slug"]] = boards
            if not boards:
                declared_unevidenced = any(
                    m in evidence.lower() for m in NOT_EVIDENCED_MARKERS)
                if declared_unevidenced:
                    warnings.append(
                        f"{sub['name']} / {t['slug']}: honestly declared "
                        f"unevidenced by any paper (engine-native, no board) "
                        f"-- not a defect, just tracked here")
                else:
                    errors.append(
                        f"{sub['name']} / {t['slug']}: evidence names no "
                        f"recognised board (know about: {', '.join(BOARD_TOKENS)}) "
                        f"and does not declare itself unevidenced -- looks like "
                        f"a missing citation")
        multi = any(len(b) > 1 for b in per_type.values())
        if multi:
            for slug, b in per_type.items():
                if len(b) == 1:
                    warnings.append(
                        f"{sub['name']} / {slug}: single-board evidence "
                        f"({next(iter(b))}) while a sibling type in this "
                        f"subtopic is multi-board")


def check_manifest(warnings):
    if not MANIFEST.exists():
        warnings.append(f"no evidence manifest found at {MANIFEST} -- board "
                         f"citations cannot be cross-checked against known sources")
        return
    manifest = json.loads(MANIFEST.read_text())
    for src in manifest.get("sources", []):
        if not src.get("locally_available"):
            warnings.append(
                f"evidence manifest: {src['id']} ({src.get('cited_as')}) is "
                f"locally_available: false -- its citations cannot currently "
                f"be independently re-verified from this repo")


def main():
    data = json.loads(TAXONOMY.read_text())
    nvr = data["sections"]["NVR"]
    errors, warnings = [], []

    check_evidence_coverage(nvr, errors, warnings)
    check_manifest(warnings)

    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"FAIL  {e}")
    print(f"\n{len(errors)} error(s), {len(warnings)} warning(s).")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
