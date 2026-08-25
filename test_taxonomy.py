"""
Checks that everything which files a question agrees with the taxonomy.

Run:  python manage.py shell < test_taxonomy.py

`taxonomy.json` is the single source of truth, but nothing in the codebase is
obliged to agree with it. A generator, a seeder or a paper importer reaches a
subtopic through `get_or_create(name=...)`, so a name that is not in the taxonomy
does not raise — it creates a second subtopic beside the real one and files its
questions there. Practice decks, subtopic counts and the weakness profile then
treat the two as unrelated areas, and nothing anywhere errors.

That is not hypothetical. When the Maths taxonomy was rebuilt from 8 subtopics to
17, six generators kept pointing at the three retired names and held 469 questions
between them; rebuilding English and VR took it to 21 across three sections. It was
found by hand, months later. This is the check that would have caught it the same
day.

It deliberately does NOT check the reverse direction. A taxonomy subtopic with no
generator is fine and expected — most of them are meant to be filled by authored
packs, not generated ones.
"""
import json
from pathlib import Path

from django.conf import settings

from catalog.generators import load_all
from catalog.management.commands.import_paper import TOPIC_MAP

TAXONOMY = Path(settings.BASE_DIR) / "elevenplus_data" / "taxonomy.json"

fails = []


def ck(label, cond, extra=""):
    print(f"  [{'OK  ' if cond else 'FAIL'}] {label}" + (f" — {extra}" if extra else ""))
    if not cond:
        fails.append(label)


data = json.loads(TAXONOMY.read_text())
canonical = {}
for code, sec in data["sections"].items():
    names = set()
    for s in sec.get("subtopics", []):
        if isinstance(s, dict):
            names.add(s["name"])
            if s.get("slug"):
                names.add(s["slug"])
    canonical[code] = names

print("== every generator declares a canonical subtopic ==")
# load_all(), not REGISTRY: the registrations only run when the four generator
# modules are imported, so reading REGISTRY directly reports an empty list and
# passes vacuously — which it did, on the first version of this check.
gens = load_all()
assert gens, "no generators loaded — load_all() returned nothing, the check would pass vacuously"
orphans = []
for g in gens:
    code = getattr(g, "section", None)
    sub = getattr(g, "subtopic", None)
    if not code or not sub:
        continue
    if sub not in canonical.get(code, set()):
        orphans.append(f"{getattr(g, 'slug', g)} -> {code} / {sub}")
ck(f"{len(gens)} generators, none orphaned", not orphans,
   "; ".join(orphans) if orphans else "")

print("\n== the paper importer maps onto canonical subtopics ==")
# import_paper reaches subtopics by name too. It errors on an unmapped *topic*
# rather than inventing a subtopic — good design — but nothing stops the name it
# maps TO from falling out of the taxonomy, which is a different failure.
bad = sorted({f"{code} / {sub}" for code, sub, _qt in TOPIC_MAP.values()
              if sub not in canonical.get(code, set())})
ck(f"import_paper TOPIC_MAP: {len(TOPIC_MAP)} topics, all canonical", not bad,
   "; ".join(bad))

# The question types it declares must be real too — a paper question filed under a
# type that no longer exists is invisible to every per-type report.
types_by_sub = {}
for code, sec in data["sections"].items():
    for s in sec.get("subtopics", []):
        if isinstance(s, dict):
            slugs = {t if isinstance(t, str) else t.get("slug")
                     for t in s.get("question_types", [])}
            types_by_sub[(code, s["name"])] = slugs
bad_t = sorted({f"{code}/{sub}/{qt}" for code, sub, qt in TOPIC_MAP.values()
                if qt and qt not in types_by_sub.get((code, sub), set())})
ck("import_paper TOPIC_MAP: every declared question_type exists", not bad_t,
   "; ".join(bad_t))

print("\n== the taxonomy itself is well formed ==")
for code, sec in data["sections"].items():
    subs = [s for s in sec.get("subtopics", []) if isinstance(s, dict)]
    names = [s["name"] for s in subs]
    ck(f"{code}: no duplicate subtopic names", len(names) == len(set(names)))
    rebuilt = sec.get("rebuilt")
    n_types = sum(len(s.get("question_types", [])) for s in subs)
    # A rebuilt section is one whose questions must carry a question_type. If it
    # has no types to choose from, every pack for it fails on every question.
    ck(f"{code}: rebuilt={bool(rebuilt)} is consistent with {n_types} question types",
       (not rebuilt) or n_types > 0)

print()
print("RESULT: " + ("ALL PASSED" if not fails else f"{len(fails)} FAILED"))
for f in fails:
    print("  - " + f)
