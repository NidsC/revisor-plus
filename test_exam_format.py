"""
Checks School.exam_format and the school seed that fills it in.

Run:  python main.py shell < test_exam_format.py

exam_format is what the vocab trainer will use to choose a pupil's word pack,
so a school filed under the wrong format quietly gives its pupils the wrong
words. The expected values below are the agreed list, written out again here
on purpose: a test that read them back from SCHOOLS would pass whatever SCHOOLS
said.

It also checks the one behaviour seed_schools() adds: a blank fact in SCHOOLS
does not overwrite what has been entered in admin since. The one value this
test changes is put back in a `finally`, so a failure part-way leaves nothing
behind.
"""
import sys

from catalog.management.commands.seed_demo import SCHOOLS, seed_schools
from goals.models import School

fails = []


def ck(label, cond, extra=""):
    print(f"  [{'OK  ' if cond else 'FAIL'}] {label}" + (f" — {extra}" if extra else ""))
    if not cond:
        fails.append(label)


EXPECTED = {
    "wilsons": "set", "sutton-grammar": "set", "wallington-county": "set",
    "newstead-wood": "gl", "ilford-county-high": "gl", "woodford-county-high": "gl",
    "tiffin": "bespoke", "tiffin-girls": "bespoke", "queen-elizabeths-barnet": "bespoke",
    "henrietta-barnett": "bespoke", "st-olaves": "bespoke",
    "colchester-royal": "", "altrincham-boys": "", "reading-school": "", "kendrick": "",
}
NEW = ("newstead-wood", "ilford-county-high", "woodford-county-high", "tiffin-girls")

print("== the field ==")
field = School._meta.get_field("exam_format")
ck("values are exactly gl, set, bespoke",
   sorted(v for v, _ in field.choices) == ["bespoke", "gl", "set"], str(field.choices))
ck("blank is allowed (not recorded)", field.blank)

print("\n== the seed list ==")
seeded = {row[0]: row[6] for row in SCHOOLS}
ck("every slug appears once", len(seeded) == len(SCHOOLS))
ck("the seed list is exactly the agreed schools", set(seeded) == set(EXPECTED),
   f"extra {sorted(set(seeded) - set(EXPECTED))}, missing {sorted(set(EXPECTED) - set(seeded))}")
wrong = {s: (seeded.get(s), f) for s, f in EXPECTED.items() if seeded.get(s) != f}
ck("each school has its agreed format", not wrong, str(wrong))
blank_facts = [row[0] for row in SCHOOLS if row[0] in NEW and any(row[i] for i in (2, 3, 4, 5))]
ck("the four new schools carry no facts beyond name and format", not blank_facts, str(blank_facts))

print("\n== seeding the database ==")
seed_schools()
in_db = dict(School.objects.filter(slug__in=EXPECTED).values_list("slug", "exam_format"))
ck("all agreed schools are in the database", set(in_db) == set(EXPECTED),
   str(sorted(set(EXPECTED) - set(in_db))))
ck("each has its agreed format in the database",
   all(in_db.get(s) == f for s, f in EXPECTED.items()))
new_rows = School.objects.filter(slug__in=NEW)
ck("the new schools are unverified", not new_rows.filter(verified=True).exists())
ck("the new schools are active", new_rows.filter(active=True).count() == len(NEW))
wilsons = School.objects.get(slug="wilsons")
ck("existing facts are still written", wilsons.area == "Sutton" and wilsons.papers.count() == 2)

print("\n== a blank in SCHOOLS does not overwrite admin ==")
school = School.objects.get(slug="tiffin-girls")
before = (school.area, school.test_window)
try:
    school.area, school.test_window = "Kingston upon Thames", "September, Year 6"
    school.save(update_fields=["area", "test_window"])
    seed_schools()
    school.refresh_from_db()
    ck("an area entered in admin survives a reseed", school.area == "Kingston upon Thames")
    ck("a test window entered in admin survives a reseed", school.test_window == "September, Year 6")
    ck("the format is still written", school.exam_format == "bespoke")
finally:
    School.objects.filter(pk=school.pk).update(area=before[0], test_window=before[1])

if fails:
    print("\nRESULT: FAILURES:", fails)
    sys.exit(1)
print("\nRESULT: ALL PASSED")
