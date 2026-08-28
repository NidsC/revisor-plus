"""
Checks that a non-verbal question survives the whole pipeline onto the page.

Run:  python manage.py shell < test_nvr_page.py

`test_figures.py` checks the drawing; this checks everything between the drawing
and a pupil. It goes through the real view and the real template rather than
calling the renderer, because the failures that live in that gap are invisible to
a unit test of `catalog/figures`:

  * a template tag that forgets `mark_safe`, so the pupil is shown SVG source as
    text — `catalog/figures` deliberately returns plain strings so the
    contributor preview can share it, which puts that risk on the tag
  * the option-tile branch never firing, so picture answers fall through to the
    ordinary list and render as four rows reading "A", "B", "C", "D"
  * a figure reaching the question but not the answers, or the reverse
  * anything storing generated markup in the database, which is the thing this
    whole package exists not to do

It needs a database with content: migrate, sync_taxonomy, seed_demo,
import_pack of _EXAMPLE.nvr_figures.json, and generate_bank.

Also checks that every generated NVR question's `question_type` is one the
rebuilt taxonomy actually lists for its subtopic — the check that would have
caught `catalog/generators/nonverbal.py` silently writing `question_type=""`
when NVR moved from `rebuilt: false` to `rebuilt: true` (see taxonomy.json v6
and pending_issues.md), since nothing on the generate_bank write path runs
validate_questions.py. And a non-blocking content-balance report, so any one
NVR subtopic silently climbing past half the module stays visible.

And that every active NVR question, from any source, has a figure — no
exception exists in the taxonomy, so this is a hard failure, not a report.
This is deliberately DB-wide rather than scoped to the example pack, because
the render check below deterministically targets one known-good question and
would not by itself catch a *different* source (a pack, a generator, or
seed_demo) quietly introducing a non-figured one — see pending_issues.md,
"seed_demo files a text-only NVR placeholder inside a fully-figured subtopic".

Writes the rendered page to nvr-question.html so it can be looked at.
"""
import re
import sys

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client

from catalog.management.commands.generate_bank import SOURCE as GENERATED
from catalog.models import AnswerOption, Question

sys.path.insert(0, "elevenplus_data")
from taxonomy_lookup import load as load_taxonomy  # noqa: E402

# The test client calls itself "testserver", which the real settings do not list.
if "testserver" not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS.append("testserver")

problems = []


def check(condition, message):
    if not condition:
        problems.append(message)
    return condition


student = get_user_model().objects.filter(email="student@revisorplus.test").first()
check(student is not None, "no seeded student to render as")

# An authored question (from the example pack) and a generated one, because they
# arrive by different importers and only one of them was ever exercised.
authored = Question.objects.filter(source="EXAMPLE-NVR-FIGURES").order_by("order")
generated = Question.objects.filter(
    subtopic__section__code="NVR", source=GENERATED
).exclude(options__figure=None).distinct()

print(f"authored NVR questions: {authored.count()}")
print(f"generated NVR questions with option figures: {generated.count()}")
check(authored.count() == 5, "the example pack did not import 5 questions")
check(generated.exists(), "no generated NVR question carries option figures")

for question in list(authored):
    options = list(question.options.all())
    with_figures = [o for o in options if o.figure]
    labels = [o.label for o in options]
    print(f"  {question.stem[:46]:<46} options={len(options)} "
          f"with figures={len(with_figures)} labels={labels} "
          f"stem figure={'yes' if question.figure else 'no'}")
    check(len(with_figures) == len(options),
          f"{question.stem[:30]}: only {len(with_figures)}/{len(options)} options have figures")
    check(question.has_figure_options,
          f"{question.stem[:30]}: has_figure_options is False")
    check(all(labels), f"{question.stem[:30]}: an option has no letter")

# The whole point of storing data rather than markup: nothing in the database
# contains any.
print("\nNothing stored is markup:")
stored = list(Question.objects.exclude(figure=None).values_list("figure", flat=True))
stored += list(AnswerOption.objects.exclude(figure=None).values_list("figure", flat=True))
check(not any("<" in repr(f) for f in stored),
      "a stored figure contains markup — this package stores data, not SVG")
print(f"  checked {len(stored)} stored figures, none contain '<'")

# Every active NVR question must be figure-based — no exception exists anywhere
# in the rebuilt taxonomy (every question_type in every NVR subtopic is
# spatial/diagram). This is the invariant that failed, invisibly, for a
# seed_demo item this check used to tolerate: catches a non-figured NVR
# question from ANY source — a pack, a generator, or seed_demo again — at the
# point it's introduced, rather than only sometimes surfacing when start()'s
# random deck sample happens to draw it into an unrelated PR's CI run.
print("\nEvery active NVR question is figure-based:")
all_active_nvr = Question.objects.filter(
    subtopic__section__code="NVR", active=True, parts__isnull=True)
non_figured = [q for q in all_active_nvr if not q.has_figure_options]
print(f"  checked {all_active_nvr.count()} active NVR questions")
for q in non_figured[:10]:
    print(f"  ! {q.source}: {q.stem[:60]!r} (subtopic={q.subtopic.name}) has no figure")
check(not non_figured,
      f"{len(non_figured)} active NVR question(s) have no figure at all — "
      f"every NVR question must be a picture, see catalog/figures")

# Generator-taxonomy conformance: every generated NVR question must carry a
# question_type the rebuilt taxonomy lists for its subtopic. taxonomy.json is
# read fresh each run (not hardcoded here) so this stays correct across future
# rebuilds with no maintenance.
print("\nGenerated NVR questions carry a valid question_type:")
nvr_section = load_taxonomy()["sections"]["NVR"]
valid_by_subtopic = {
    sub["name"]: {t["slug"] for t in sub.get("question_types", []) if isinstance(t, dict)}
    for sub in nvr_section["subtopics"]
}
all_generated_nvr = list(Question.objects.filter(subtopic__section__code="NVR", source=GENERATED))
print(f"  generated NVR questions total: {len(all_generated_nvr)}")
missing, invalid = {}, {}
for q in all_generated_nvr:
    valid = valid_by_subtopic.get(q.subtopic.name, set())
    if not q.question_type:
        missing[q.subtopic.name] = missing.get(q.subtopic.name, 0) + 1
    elif q.question_type not in valid:
        key = (q.subtopic.name, q.question_type)
        invalid[key] = invalid.get(key, 0) + 1
for name, n in sorted(missing.items()):
    print(f"  ! {name}: {n} generated questions have no question_type")
for (name, qtype), n in sorted(invalid.items()):
    print(f"  ! {name}: {n} generated questions carry question_type={qtype!r}, "
          f"not a valid slug for this subtopic")
check(not missing, f"{sum(missing.values())} generated NVR questions have no "
                    f"question_type — the rebuilt taxonomy requires one on every "
                    f"NVR question")
check(not invalid, f"{sum(invalid.values())} generated NVR questions carry a "
                    f"question_type that is not in taxonomy.json for their subtopic")

# Content-balance report: non-blocking, since the current concentration is a
# known, already-tracked condition (pending_issues.md, "Five subtopics can
# never be filled once generation is frozen") rather than a new regression.
# This just keeps the number visible as content lands, rather than only living
# in a comment someone has to remember to reread.
print("\nNVR content balance by subtopic (all sources, not just generated):")
all_nvr = Question.objects.filter(subtopic__section__code="NVR")
total_nvr = all_nvr.count()
if total_nvr:
    by_subtopic = {}
    for name in all_nvr.values_list("subtopic__name", flat=True):
        by_subtopic[name] = by_subtopic.get(name, 0) + 1
    for name, n in sorted(by_subtopic.items(), key=lambda kv: -kv[1]):
        share = n / total_nvr
        flag = "  WARN >50% of the module" if share > 0.5 else ""
        print(f"  {name:24s} {n:5d}  ({share:5.1%}){flag}")

client = Client()
client.force_login(student)
# Deterministically render the first authored example question, rather than
# trusting practice.views.start()'s unseeded random deck sample to happen to
# include a figured question — see pending_issues.md, "seed_demo files a
# text-only NVR placeholder inside a fully-figured subtopic". start() is still
# called first, for its TestSession/session-key side effects; only the deck's
# question order is pinned afterwards.
target = authored.first()
client.get(f"/practice/start/{target.subtopic_id}/", follow=True)
session = client.session
deck = session["deck"]
deck["qids"], deck["idx"] = [target.id], 0
session["deck"] = deck
session.save()
html = client.get("/practice/question/", follow=True).content.decode()

print("\nRendered page:")
check("nvr-option" in html, "no option tiles in the rendered page")
check("<svg" in html, "no SVG in the rendered page")
check("&lt;svg" not in html,
      "the SVG came out ESCAPED — a template tag is missing mark_safe, and the "
      "pupil sees the markup as text")
check("var(--fig-scale,1)" in html,
      "the figures do not size through --fig-scale")
tiles = len(re.findall(r'class="nvr-option[ "]', html))
svgs = len(re.findall(r"<svg", html))
radios = len(re.findall(r'type="radio"', html))
print(f"  option tiles: {tiles}   svg elements: {svgs}   radio inputs: {radios}")
check(tiles >= 3, f"only {tiles} option tiles rendered")
check(tiles == radios, f"{tiles} tiles but {radios} radios — every tile needs its own control")
# The letters must be page text, not drawing.
check("nvr-option-letter" in html, "no HTML letter on the option tiles")
in_figure_text = re.findall(r"<text[^>]*>([A-E])</text>", html)
check(not in_figure_text,
      f"letters {in_figure_text} are drawn INSIDE the SVG, where they scale with "
      f"the figure — that is the arrangement this replaced")

with open("nvr-question.html", "w") as handle:
    handle.write(html)
print("  wrote nvr-question.html")

print("\n" + "=" * 66)
if problems:
    for problem in problems:
        print("FAIL ", problem)
    print(f"\nRESULT: {len(problems)} FAILED")
else:
    print("RESULT: ALL PASSED")
