#!/usr/bin/env python3
"""
Diversity audit: how many genuinely different questions can this generator set
actually produce, not how many taxonomy question_types it declares.

Calls each registered Generator's build() directly -- no Django, no database --
so it is stdlib-only and belongs in the `validate` CI job, not `pipeline`.
This is deliberate, not an oversight: item.params (so params["variant"]) is
never persisted to the database -- generate_bank._write()'s defaults dict
writes question_type/kind/stem/etc but not params -- so a DB-only post-hoc
audit structurally cannot measure variant diversity. Only a script that calls
generators directly can, and the generator modules (catalog/generators/*.py)
have zero Django imports, so nothing here needs django.setup().

Four separate, DELIBERATELY NOT CONFLATED report categories:

  IDENTITY    gen_key collision rate. This is NOT a diversity measure: it
              tells you whether a generator is re-serving the same puzzle,
              not whether its puzzles are meaningfully different from each
              other. Item.key() hashes {generator_slug, template_id, params}
              only -- question_type/kind/misconceptions are not part of
              identity -- so this is really a duplicate-params rate.
  STRUCTURAL  question_type distribution reached vs. what taxonomy.json
              declares for that subtopic; params["variant"] distribution
              where a generator uses the convention.
  DIFFICULTY  does every declared difficulty band actually produce a
              non-None item within a reasonable attempt budget, tolerating a
              generator's own known finite-pool exhaustion (a RuntimeError,
              the same production behaviour generate_bank._fill_module
              already tolerates for e.g. LetterCode).
  DISTRACTOR  misconception-slug distribution per generator: which
              distractors carry a label, which don't, how varied the labels
              actually are -- not just "does at least one exist".

A fifth category -- student-facing/template/semantic duplication detection
("do two different gen_keys still read as the same question to a pupil?") --
is deliberately NOT built here. It is left as a clearly-marked, currently
empty extension point (see FUTURE EXTENSION POINT below) rather than
expanding this into a large framework.

Run:  python3 diversity_audit.py
      python3 diversity_audit.py VR
With no arguments, audits every section load_all() registers. Pass one or
more section codes (VR, MAT, ENG, NVR) to narrow it.

Advisory only -- exit 0 always. Diversity thresholds are not agreed on yet;
this reports numbers for a human to read, the same posture
elevenplus_data/check_evidence_refs.py already takes for a different kind of
"real, but not yet actionable as a hard gate" question. It is also not a
prerequisite for anything: a generator PR is gated on its own correctness/
evidence requirements (independent verification, exhaustive ambiguity
checks, real-paper citations), never on this script.
"""
import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from catalog.generators import load_all  # noqa: E402

BUILDS_PER_DIFFICULTY = 300
TAXONOMY = ROOT / "elevenplus_data" / "taxonomy.json"


def load_taxonomy_question_types():
    """(section code, subtopic name) -> {declared question_type slugs}."""
    data = json.loads(TAXONOMY.read_text())
    out = {}
    for code, section in data.get("sections", {}).items():
        for sub in section.get("subtopics", []):
            out[(code, sub["name"])] = {qt["slug"] for qt in sub.get("question_types", [])}
    return out


def audit_generator(gen):
    """Draw BUILDS_PER_DIFFICULTY items per declared difficulty band. Returns
    the raw counts every report category below reads from -- one pass over
    the generator, not four."""
    seen_keys = Counter()
    question_types = Counter()
    variants = Counter()
    misconceptions = Counter()
    difficulty_builds = {}
    total_built = total_exhausted = 0

    for difficulty in gen.difficulties:
        built_this_band = 0
        for i in range(BUILDS_PER_DIFFICULTY):
            rng = random.Random(f"diversity:{gen.slug}:{difficulty}:{i}")
            try:
                item = gen.build(rng, difficulty)
            except RuntimeError:
                # A generator's own finite without-replacement pool running
                # dry -- expected, production-tolerated behaviour (see
                # LetterCode), not a defect this script diagnoses.
                total_exhausted += 1
                continue
            except Exception:  # noqa: BLE001
                # A generator crashing is test_generator_contract.py's/
                # test_verbal_gap_batch.py's job to catch and fail loudly on,
                # not this advisory script's -- count it as a miss so one
                # broken generator can't take the whole report down, but
                # don't try to diagnose it here.
                total_exhausted += 1
                continue
            if item is None:
                total_exhausted += 1
                continue
            total_built += 1
            built_this_band += 1
            seen_keys[item.key(gen.slug, gen.template_id)] += 1
            if item.question_type:
                question_types[item.question_type] += 1
            variant = item.params.get("variant")
            if variant:
                variants[variant] += 1
            for slug in (item.misconceptions or {}).values():
                if slug:
                    misconceptions[slug] += 1
        difficulty_builds[difficulty] = built_this_band

    duplicate_draws = sum(c - 1 for c in seen_keys.values() if c > 1)
    return {
        "total_built": total_built,
        "total_exhausted": total_exhausted,
        "difficulty_builds": difficulty_builds,
        "question_types": question_types,
        "variants": variants,
        "misconceptions": misconceptions,
        "unique_keys": len(seen_keys),
        "duplicate_draws": duplicate_draws,
    }


def report_lines(gen, stats, declared_types):
    lines = [f"\n=== {gen.slug} ({gen.section} / {gen.subtopic}) ==="]
    warned = False

    # IDENTITY -- collision detection, not a diversity score. Reported first
    # and labelled explicitly so it can never be read as one.
    total = stats["total_built"]
    dup_rate = (stats["duplicate_draws"] / total) if total else 0.0
    lines.append(f"  IDENTITY    {stats['unique_keys']} unique gen_keys over {total} builds "
                 f"({stats['duplicate_draws']} duplicate draws, {dup_rate:.1%}) "
                 f"-- a collision rate, not a diversity measure")

    # STRUCTURAL
    reached = set(stats["question_types"])
    missing = declared_types - reached
    invented = reached - declared_types
    qt_str = ", ".join(f"{qt}={n}" for qt, n in stats["question_types"].most_common()) or "(none)"
    lines.append(f"  STRUCTURAL  question_type reached: {qt_str}")
    if declared_types:
        extra = f" ({sorted(missing)})" if missing else ""
        lines.append(f"              taxonomy declares {sorted(declared_types)}; "
                     f"{len(missing)} never reached this sample{extra}")
    if invented:
        lines.append(f"  WARN        question_type(s) reached but NOT in taxonomy.json "
                     f"(should be impossible): {sorted(invented)}")
        warned = True
    if stats["variants"]:
        var_str = ", ".join(f"{v}={n}" for v, n in stats["variants"].most_common())
        lines.append(f"              params[\"variant\"] reached: {var_str}")

    # DIFFICULTY
    empty_bands = [d for d in gen.difficulties if stats["difficulty_builds"].get(d, 0) == 0]
    band_str = ", ".join(f"d{d}={stats['difficulty_builds'].get(d, 0)}"
                         for d in gen.difficulties)
    lines.append(f"  DIFFICULTY  {band_str}")
    if empty_bands:
        lines.append(f"  WARN        difficulty band(s) produced ZERO items in "
                     f"{BUILDS_PER_DIFFICULTY} attempts: {empty_bands}")
        warned = True

    # DISTRACTOR
    if stats["misconceptions"]:
        mc_str = ", ".join(f"{m}={n}" for m, n in stats["misconceptions"].most_common())
        lines.append(f"  DISTRACTOR  {len(stats['misconceptions'])} distinct slug(s): {mc_str}")
    else:
        lines.append("  DISTRACTOR  no misconception labels observed in this sample")

    return lines, warned


def main(argv):
    registry = load_all()
    taxonomy_types = load_taxonomy_question_types()
    wanted = set(a.upper() for a in argv) or None

    gens = [g for g in registry if wanted is None or g.section in wanted]
    gens.sort(key=lambda g: (g.section, g.slug))

    print(f"Diversity audit: {len(gens)} generator(s), {BUILDS_PER_DIFFICULTY} "
          f"builds/difficulty band, advisory only")
    print("FUTURE EXTENSION POINT (not built here): student-facing/template/semantic "
          "duplication detection -- whether two different gen_keys still read as the "
          "same question to a pupil. Left for later; do not expand this script to add "
          "it without a deliberate decision to do so.")

    warned_count = 0
    for gen in gens:
        stats = audit_generator(gen)
        declared = taxonomy_types.get((gen.section, gen.subtopic), set())
        lines, warned = report_lines(gen, stats, declared)
        for line in lines:
            print(line)
        warned_count += warned

    print(f"\n{'-' * 60}")
    print(f"{len(gens)} generator(s) audited, {warned_count} with a WARN line above.")
    print("Advisory only -- exit 0 regardless of what was found.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
