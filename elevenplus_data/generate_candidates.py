#!/usr/bin/env python3
"""
generate_candidates.py — the /questions bridge: bulk-generate candidate
questions from the existing generator registry (`catalog/generators/`), for
an author to review before folding the good ones into a real contrib pack.

Stdlib + generator imports only — no Django, no database, no pip install.
`catalog/generators/{english,maths,nonverbal,verbal}.py` have zero Django
imports (confirmed by grep — the same fact `diversity_audit.py`'s own
docstring relies on), so this needs no `django.setup()` at all.

Why this exists: `/questions` (`.claude/commands/questions.md`) is entirely
hand-authoring today — its only generator contact is a fixed list of ~15
`python3 -c "...().build(...)"` one-liners, run one at a time, whose raw
stdout an author retypes into pack JSON by hand. That doesn't scale to "the
generator layer produces the bulk of a pack" and doesn't know about 8 of the
23 registered VR generators at all. This script is the bridge: it discovers
generators from `REGISTRY` (never a second hardcoded list), converts their
`Item` output directly into valid pack-JSON, and writes it to a staging file
an author reviews with the SAME tools that already review a real pack
(`preview_questions.py`, `validate_questions.py`) — nothing new to learn.

Two subcommands:

  generate — draw candidates and write/append them to a staging file.
      python3 elevenplus_data/generate_candidates.py generate VR --handle alex --spread 40
      python3 elevenplus_data/generate_candidates.py generate VR --handle alex \\
          --subtopic "Letter Codes" --count 10 --subtopic "Paired Synonyms" --count 8
      python3 elevenplus_data/generate_candidates.py generate VR --handle alex --spread 20 --difficulty 3-5

  accept — move selected candidates (by ref, or --all) out of the staging
  file and into a real contrib pack, renumbering them into the pack's own
  ref/number sequence as it goes. This is the only write to the real pack;
  everything before it only ever touches the staging file.
      python3 elevenplus_data/generate_candidates.py accept \\
          --candidates elevenplus_data/_candidates_alex_vr.json \\
          --into elevenplus_data/contrib_alex_vr_01.json --all
      python3 elevenplus_data/generate_candidates.py accept \\
          --candidates elevenplus_data/_candidates_alex_vr.json \\
          --into elevenplus_data/contrib_alex_vr_01.json --refs GEN-VR-0001 GEN-VR-0004

The staging file is an ordinary pack — same schema, same `section`/`questions`
shape — so `preview_questions.py`/`rebalance_keys.py`/`validate_questions.py`
all already work on it unmodified. It is named with a leading underscore
(`_candidates_...`), the same convention `_EXAMPLE.*`/`_TEMPLATE.*` already
use to mean "never auto-imported, never auto-deployed" — `build.sh` only
picks up `contrib_*.json`. Never run `import_pack` on a candidates file
directly; `accept` is the only sanctioned way candidates reach a real pack.

Rejecting a candidate needs no code: delete its object from the staging
file's `questions` array (or just don't `accept` its ref) and it's gone.
Regenerating is re-running `generate` for the same subtopic — it reads
whatever is still in the staging file and will not hand back a gen_key
already sitting there, so a trimmed-down staging file naturally gets
backfilled with fresh candidates rather than repeats.

Provenance: candidates carry no field marking them as generated once
`accept`ed into a real pack — matching this project's existing, deliberate
"no stored marker" convention for generator-assisted questions (see
`.claude/commands/questions.md`'s Step 3b) — a generated-then-reviewed
question is an ordinary authored one. The staging file itself, while it
exists, IS the marker: everything in it is a candidate, nothing in the real
pack is, until `accept` moves it across.
"""
import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from catalog.generators import load_all, REGISTRY  # noqa: E402

TAXONOMY_PATH = os.path.join(os.path.dirname(__file__), "taxonomy.json")


def load_taxonomy():
    with open(TAXONOMY_PATH, encoding="utf-8") as f:
        return json.load(f)


def section_name(code):
    return {"ENG": "English", "MAT": "Maths", "VR": "Verbal Reasoning",
            "NVR": "Non-Verbal Reasoning"}[code]


def registry_for_section(section_code):
    """subtopic name -> generator instance, for one section. Reads REGISTRY
    directly — this is the "discover from the existing registry" contract:
    nothing here hardcodes a generator's name or class."""
    load_all()
    by_subtopic = {}
    for gen in REGISTRY:
        if gen.section == section_code:
            by_subtopic[gen.subtopic] = gen
    return by_subtopic


def difficulty_weights(available):
    """A symmetric, middle-weighted spread over whichever difficulties a
    generator actually supports — not a random or uniform pick. Mirrors the
    shape elevenplus_data/CLAUDE.md's own suggested per-batch spread
    describes (light at the extremes, heaviest in the middle), computed
    generically from how many bands are available rather than hardcoded per
    generator, since generators support different, uneven difficulty
    ranges (e.g. (2,3,4) vs (1,2,3,4,5))."""
    curves = {1: [1], 2: [1, 1], 3: [1, 2, 1], 4: [1, 2, 2, 1], 5: [1, 2, 3, 2, 1]}
    weights = curves[len(available)]
    total = sum(weights)
    return {d: w / total for d, w in zip(available, weights)}


def counts_from_weights(n, weights_by_key):
    """Turn {key: weight} (weights summing to ~1) into {key: integer count}
    summing to exactly n, largest-remainder method (no key silently drops
    to 0 due to rounding if n is at least len(weights_by_key))."""
    raw = {k: n * w for k, w in weights_by_key.items()}
    counts = {k: int(v) for k, v in raw.items()}
    remainder = n - sum(counts.values())
    order = sorted(raw, key=lambda k: raw[k] - counts[k], reverse=True)
    for k in order[:remainder]:
        counts[k] += 1
    return counts


def item_to_question_dict(item, gen, ref, number):
    """catalog.generators.Item -> the pack-JSON question shape
    elevenplus_data/CLAUDE.md defines. Every VR generator today only ever
    produces MCQ output (item.kind is None on all of them — confirmed by
    generate_bank.py only ever writing Kind.MCQ), so `kind` is omitted
    (mcq is the pack schema's own default) rather than hardcoded — a future
    generator that sets item.kind will carry it through correctly here."""
    options = []
    for text, is_correct in ((o[0], o[1]) for o in item.options):
        opt = {"text": text}
        if is_correct:
            opt["correct"] = True
        misc = item.misconceptions.get(text)
        if misc:
            opt["misconception"] = misc
        options.append(opt)
    q = {
        "ref": ref,
        "number": str(number),
        "subtopic": gen.subtopic,
        "difficulty": item.difficulty,
        "stem": item.stem,
        "options": options,
    }
    if item.question_type:
        q["question_type"] = item.question_type
    if item.kind:
        q["kind"] = item.kind
    if item.explanation:
        q["explanation"] = item.explanation
    return q


def gen_key_of(item, gen):
    return item.key(gen.slug, gen.template_id)


def draw_candidates(gen, difficulty, n, avoid_stems, rng, max_attempts=None):
    """Up to n distinct items at one difficulty, skipping anything whose
    rendered stem is already in avoid_stems (candidates already sitting in
    the staging file — the only cross-run identity pack-JSON can carry,
    since it has no item.params/gen_key) and anything that duplicates
    another draw in this same call (by gen_key, the real identity). Stops
    early and reports the shortfall honestly on pool exhaustion (RuntimeError,
    or too many consecutive already-seen/None draws) rather than padding with
    duplicates — the same posture generate_bank.py's own _fill_module already
    takes for a finite pool."""
    if max_attempts is None:
        max_attempts = max(500, n * 40)
    got = []
    seen_keys = set()
    attempts = 0
    while len(got) < n and attempts < max_attempts:
        attempts += 1
        try:
            item = gen.build(rng, difficulty)
        except RuntimeError:
            break
        if item is None:
            continue
        if item.stem in avoid_stems:
            continue
        key = gen_key_of(item, gen)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        got.append(item)
    return got


def load_candidates_file(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def existing_keys_by_subtopic(pack, gen_by_subtopic):
    """gen_keys already sitting in a candidates file, so re-running
    `generate` never hands back an exact duplicate of something still
    there (accepted or not-yet-rejected)."""
    keys = {}
    if not pack:
        return keys
    for q in pack.get("questions", []):
        subtopic = q.get("subtopic")
        gen = gen_by_subtopic.get(subtopic)
        if gen is None:
            continue
        # Re-derive params the same way the generator would identify this
        # question — we don't have item.params in pack JSON, so approximate
        # identity by (subtopic, stem) instead; good enough to stop an
        # immediate re-draw of literally the same rendered question.
        keys.setdefault(subtopic, set()).add(q.get("stem"))
    return keys


def cmd_generate(args):
    gen_by_subtopic = registry_for_section(args.section)
    taxonomy = load_taxonomy()
    section_subtopics = {
        s["name"] for s in taxonomy["sections"][args.section]["subtopics"]
    }

    specs = []  # (subtopic, count)
    if args.subtopic:
        if len(args.subtopic) != len(args.count):
            sys.exit("Error: pass one --count for every --subtopic, in order.")
        specs = list(zip(args.subtopic, args.count))
    elif args.spread:
        available = sorted(gen_by_subtopic)
        if not available:
            sys.exit(f"Error: no registered generators for section {args.section}.")
        counts = counts_from_weights(args.spread, {s: 1 / len(available) for s in available})
        specs = [(s, c) for s, c in counts.items() if c > 0]
    else:
        sys.exit("Error: pass either --spread N, or one or more --subtopic/--count pairs.")

    for subtopic, _ in specs:
        if subtopic not in section_subtopics:
            sys.exit(f"Error: {subtopic!r} is not a canonical {args.section} subtopic "
                      f"(check elevenplus_data/taxonomy_lookup.py {args.section}).")
        if subtopic not in gen_by_subtopic:
            print(f"NOTE: {subtopic!r} has no registered generator — skipping. "
                  f"This subtopic needs manual authoring (see Step 6 of the workflow).")

    out_path = args.out or os.path.join(
        os.path.dirname(__file__), f"_candidates_{args.handle}_{args.section.lower()}.json")
    existing = load_candidates_file(out_path)
    if existing is None:
        existing = {
            "section": {"code": args.section, "name": section_name(args.section),
                        "source": args.source or f"CONTRIB-{args.handle.upper()}-CANDIDATES",
                        "is_placeholder": False},
            "questions": [],
            "_draw_count": 0,
        }
    avoid_by_subtopic = existing_keys_by_subtopic(existing, gen_by_subtopic)

    # Regenerating (re-running `generate` for a subtopic after deleting the
    # candidates that were rejected) must not just reproduce those same
    # rejected candidates with the same seed -- but a rejected candidate is,
    # by design, gone from the file with nothing left to avoid it by (that
    # is what "reject needs no code" means). `_draw_count` is the fix: a
    # persistent, monotonically-increasing counter (never reset by deleting
    # questions, unlike len(questions)) that salts the seed, so every
    # `generate` call against an existing file explores a fresh part of the
    # random stream even when the file's content has shrunk back to what it
    # was before. A brand-new file starts at 0, so first-run determinism
    # (same command on a fresh file -> same output) is unaffected.
    draw_count = existing.get("_draw_count", 0)
    existing["_draw_count"] = draw_count + 1
    rng = random.Random((args.seed, draw_count))
    next_number = len(existing["questions"]) + 1
    diff_range = None
    if args.difficulty:
        lo, hi = (int(x) for x in args.difficulty.split("-"))
        diff_range = set(range(lo, hi + 1))

    report = []
    for subtopic, count in specs:
        gen = gen_by_subtopic.get(subtopic)
        if gen is None or count <= 0:
            continue
        available = [d for d in gen.difficulties if diff_range is None or d in diff_range]
        if not available:
            report.append((subtopic, 0, count,
                            f"none of {gen.difficulties} fall inside --difficulty {args.difficulty}"))
            continue
        weights = difficulty_weights(available)
        per_difficulty = counts_from_weights(count, weights)

        got_total = 0
        avoid_stems = avoid_by_subtopic.get(subtopic, set())
        for difficulty, n in per_difficulty.items():
            if n <= 0:
                continue
            fresh = draw_candidates(gen, difficulty, n, avoid_stems, rng)
            for item in fresh:
                q = item_to_question_dict(
                    item, gen, f"GEN-{args.section}-{next_number:04d}", next_number)
                existing["questions"].append(q)
                avoid_stems.add(item.stem)
                next_number += 1
                got_total += 1
        if got_total < count:
            report.append((subtopic, got_total, count,
                            "pool ran out — this generator can't produce that many "
                            "distinct questions at the requested difficulty spread"))
        else:
            report.append((subtopic, got_total, count, None))

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Wrote {out_path}")
    print(f"{len(existing['questions'])} candidates total in the file.\n")
    for subtopic, got, wanted, note in report:
        status = "OK" if got == wanted else "SHORT"
        line = f"  [{status}] {subtopic}: {got}/{wanted}"
        if note:
            line += f"  ({note})"
        print(line)
    print(f"\nReview: python3 elevenplus_data/preview_questions.py {out_path}")
    print(f"Then:   python3 elevenplus_data/generate_candidates.py accept "
          f"--candidates {out_path} --into <your contrib pack> --all")


def next_ref_number(pack, handle, section):
    prefix = f"{handle.upper()}-{section}-"
    best = 0
    for q in pack.get("questions", []):
        ref = q.get("ref", "")
        if ref.startswith(prefix):
            try:
                best = max(best, int(ref[len(prefix):]))
            except ValueError:
                pass
    return best + 1


def cmd_accept(args):
    with open(args.candidates, encoding="utf-8") as f:
        candidates = json.load(f)

    if os.path.exists(args.into):
        with open(args.into, encoding="utf-8") as f:
            target = json.load(f)
    else:
        sys.exit(f"Error: {args.into} does not exist yet — create it from "
                 f"_TEMPLATE.question_pack.json first (Step 2 of the workflow), "
                 f"so its section/source header is set deliberately, not guessed here.")

    section_code = target["section"]["code"]
    handle = args.handle or target["section"]["source"].split("-")[1].lower()

    wanted_refs = None if args.all else set(args.refs)
    remaining = []
    accepted = []
    for q in candidates["questions"]:
        if wanted_refs is None or q["ref"] in wanted_refs:
            accepted.append(q)
        else:
            remaining.append(q)

    if wanted_refs is not None:
        missing = wanted_refs - {q["ref"] for q in accepted}
        if missing:
            sys.exit(f"Error: ref(s) not found in {args.candidates}: {sorted(missing)}")

    n = next_ref_number(target, handle, section_code)
    for q in accepted:
        q["ref"] = f"{handle.upper()}-{section_code}-{n:04d}"
        q["number"] = str(len(target["questions"]) + 1)
        target["questions"].append(q)
        n += 1

    candidates["questions"] = remaining

    with open(args.into, "w", encoding="utf-8") as f:
        json.dump(target, f, indent=2, ensure_ascii=False)
        f.write("\n")
    with open(args.candidates, "w", encoding="utf-8") as f:
        json.dump(candidates, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Accepted {len(accepted)} question(s) into {args.into} "
          f"(now {len(target['questions'])} total).")
    print(f"{len(remaining)} candidate(s) left in {args.candidates}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="draw candidates into a staging file")
    g.add_argument("section", choices=["ENG", "MAT", "VR", "NVR"])
    g.add_argument("--handle", required=True)
    g.add_argument("--subtopic", action="append", default=[],
                    help="repeatable; pair with --count in the same order")
    g.add_argument("--count", action="append", type=int, default=[],
                    help="repeatable; pair with --subtopic in the same order")
    g.add_argument("--spread", type=int,
                    help="general/balanced mode: total questions split evenly "
                         "across every generator the section has")
    g.add_argument("--difficulty", help="e.g. 3-5; restricts to this band where "
                                          "the generator supports it")
    g.add_argument("--seed", type=int, default=0)
    g.add_argument("--source", help="defaults to CONTRIB-<HANDLE>-CANDIDATES")
    g.add_argument("--out", help="defaults to _candidates_<handle>_<section>.json")
    g.set_defaults(func=cmd_generate)

    a = sub.add_parser("accept", help="move selected candidates into a real pack")
    a.add_argument("--candidates", required=True)
    a.add_argument("--into", required=True)
    a.add_argument("--handle", help="defaults to the target pack's own source handle")
    group = a.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true")
    group.add_argument("--refs", nargs="+")
    a.set_defaults(func=cmd_accept)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
