#!/usr/bin/env python3
"""
Print the part of the taxonomy an authoring session actually needs.

`taxonomy.json` is over 1,200 lines. A `/questions` session needs a handful of
them: the subtopics for one section, and the question types for one subtopic.
Reading the whole file to find them costs a large slice of the session's context
and gives the model 1,200 lines of things it is not authoring, which is how a
question ends up filed under a plausible-looking slug from the wrong subtopic.

So this prints the slice. It is a lookup, not a source of truth — `taxonomy.json`
is the source of truth and this only ever reads it.

Run:
  python3 elevenplus_data/taxonomy_lookup.py MAT
        every subtopic in Maths, with how many question types each has

  python3 elevenplus_data/taxonomy_lookup.py MAT "Algebra & Sequences"
        every question type for that subtopic, with its provenance

  python3 elevenplus_data/taxonomy_lookup.py --sections
        the four section codes and whether each is rebuilt

  python3 elevenplus_data/taxonomy_lookup.py MAT --search angle
        subtopics and question types matching a word, when you know the maths
        but not what the taxonomy calls it

Stdlib only, reads one file, writes nothing.
"""
import json
import sys
from pathlib import Path

TAXONOMY = Path(__file__).resolve().parent / "taxonomy.json"


def load():
    if not TAXONOMY.exists():
        sys.exit(f"taxonomy not found at {TAXONOMY}")
    return json.loads(TAXONOMY.read_text())


def subtopics(sec):
    return [s for s in sec.get("subtopics", []) if isinstance(s, dict)]


def find_subtopic(sec, wanted):
    """Match on canonical name or slug, case-insensitively.

    Authors type what they remember, and ENG/VR subtopics have two names — a
    display name and a snake_case slug. Both resolve here for the same reason
    the validator accepts both.
    """
    w = wanted.strip().lower()
    for s in subtopics(sec):
        if s["name"].lower() == w or (s.get("slug") or "").lower() == w:
            return s
    return None


def print_sections(data):
    print("Section codes:\n")
    for code, sec in data["sections"].items():
        subs = subtopics(sec)
        n_types = sum(len(s.get("question_types", [])) for s in subs)
        rebuilt = sec.get("rebuilt")
        # The rebuilt flag is the one that changes what an author must write:
        # a rebuilt section requires question_type, a non-rebuilt one forbids it.
        note = ("question_type REQUIRED" if rebuilt
                else "not rebuilt — question_type must be OMITTED")
        print(f"  {code:4s} {sec.get('name',''):22s} "
              f"{len(subs):3d} subtopics, {n_types:3d} question types   [{note}]")
    print(f"\ntaxonomy version {data.get('version')}")


def print_subtopics(code, sec):
    subs = subtopics(sec)
    rebuilt = sec.get("rebuilt")
    print(f"{code} — {sec.get('name','')}: {len(subs)} subtopics"
          f"{'' if rebuilt else '   (NOT rebuilt: omit question_type)'}\n")
    topic = None
    for s in sorted(subs, key=lambda s: (s.get("topic_order", 0), s.get("order", 0))):
        if s.get("topic") != topic:
            topic = s.get("topic")
            if topic:
                print(f"  {topic}")
        types = s.get("question_types", [])
        slug = f"   [{s['slug']}]" if s.get("slug") else ""
        target = s.get("target_questions")
        tgt = f"  target {target}" if target else ""
        print(f"    {s['name']}{slug}  — {len(types)} types{tgt}")
    print("\nUse the name exactly as printed. For the question types of one "
          f"subtopic:\n  python3 elevenplus_data/taxonomy_lookup.py {code} "
          "\"<subtopic name>\"")


def print_types(code, sec, s):
    types = s.get("question_types", [])
    print(f"{code} / {s['name']}"
          + (f"  [slug: {s['slug']}]" if s.get("slug") else "")
          + f" — {len(types)} question types\n")
    if not types:
        print("  none — this section is not rebuilt, so omit 'question_type'.")
        return
    for t in types:
        if isinstance(t, str):
            print(f"    {t}")
            continue
        # Provenance matters when authoring: an `authored` type was confirmed
        # against a real paper, a `proposed` one is a considered guess. An author
        # writing to a proposed type should expect it to move.
        prov = t.get("provenance") or ""
        mark = {"authored": "*", "proposed": "?"}.get(prov, " ")
        print(f"  {mark} {t.get('slug','')}")
        if t.get("name"):
            print(f"      {t['name']}")
        if t.get("evidence"):
            print(f"      evidence: {t['evidence']}")
    if any(isinstance(t, dict) for t in types):
        print("\n  * confirmed against a real paper   ? proposed, not yet confirmed")
    if s.get("axes"):
        print(f"\n  This subtopic is a grid, not a list. Axes: {s['axes']}")
        print("  File the harder half as question_type and the other in also_tests.")


def search(code, sec, term):
    t = term.lower()
    hits = 0
    for s in subtopics(sec):
        if t in s["name"].lower() or t in (s.get("slug") or "").lower():
            print(f"  subtopic  {s['name']}")
            hits += 1
        for q in s.get("question_types", []):
            slug = q if isinstance(q, str) else q.get("slug", "")
            name = "" if isinstance(q, str) else (q.get("name") or "")
            if t in slug.lower() or t in name.lower():
                print(f"  type      {s['name']}  >  {slug}")
                hits += 1
    if not hits:
        print(f"  nothing in {code} matches {term!r}. Try a broader word, or list "
              f"the subtopics:\n    python3 elevenplus_data/taxonomy_lookup.py {code}")


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    data = load()
    if argv[0] == "--sections":
        print_sections(data)
        return 0

    code = argv[0].upper()
    sec = data["sections"].get(code)
    if not sec:
        sys.exit(f"unknown section {code!r}. One of: "
                 f"{', '.join(data['sections'])}")

    rest = argv[1:]
    if rest and rest[0] == "--search":
        if len(rest) < 2:
            sys.exit("--search needs a word")
        search(code, sec, rest[1])
        return 0
    if not rest:
        print_subtopics(code, sec)
        return 0

    s = find_subtopic(sec, rest[0])
    if not s:
        print(f"{rest[0]!r} is not a {code} subtopic.\n")
        print_subtopics(code, sec)
        return 1
    print_types(code, sec, s)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
