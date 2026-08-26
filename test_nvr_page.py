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

Writes the rendered page to nvr-question.html so it can be looked at.
"""
import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client

from catalog.management.commands.generate_bank import SOURCE as GENERATED
from catalog.models import AnswerOption, Question

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

client = Client()
client.force_login(student)
# Start a practice deck on the subtopic the example pack filled, so the page
# under test is an authored question rather than a generated one.
target = authored.first().subtopic
client.get(f"/practice/start/{target.id}/", follow=True)
html = ""
for _ in range(12):
    response = client.get("/practice/question/", follow=True)
    html = response.content.decode()
    if "nvr-option" in html:
        break
    # Answer whatever came up so the deck advances to the next question.
    match = re.search(r'name="option" value="(\d+)"', html)
    qid = re.search(r'name="qid" value="(\d+)"', html)
    if not match or not qid:
        break
    client.post("/practice/answer/",
                {"option": match.group(1), "qid": qid.group(1), "time_ms": 1000},
                follow=True)
    client.get("/practice/next/", follow=True)

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
