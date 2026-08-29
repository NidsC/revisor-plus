"""
Checks for the paper importer and the typed-answer flow.

Run:  python main.py shell < test_papers.py
      (after: python main.py import_paper elevenplus_data/revisor-maths-paper-01_2.json)

Covers the parts of this feature that fail quietly rather than loudly: a deck
serving a question nobody can answer, a lenient answer being marked wrong, or a
multi-mark question scoring one.
"""
from django.test import Client

from accounts.models import User
from catalog.marking import mark, parse_number
from catalog.models import Question
from practice.models import Attempt
from practice.views import answerable

SRC = "PAPER-RVSR-MATHS-01"
fails = []


def ck(label, cond, detail=""):
    print(f"  [{'OK  ' if cond else 'FAIL'}] {label}{(' — ' + str(detail)) if detail else ''}")
    if not cond:
        fails.append(label)


if not Question.objects.filter(source=SRC).exists():
    print(f"SKIPPED: {SRC} not imported. Run:")
    print("  python main.py import_paper elevenplus_data/revisor-maths-paper-01_2.json")
else:
    print("== import shape ==")
    qs = Question.objects.filter(source=SRC)
    parents = qs.filter(parent__isnull=True)
    parts = qs.filter(parent__isnull=False)
    ck("26 parent questions", parents.count() == 26, parents.count())
    ck("47 answerable parts", parts.count() == 47, parts.count())
    ck("marks total matches the paper's 59",
       sum(p.marks for p in parts) == 59, sum(p.marks for p in parts))
    ck("every part is numeric entry",
       set(parts.values_list("kind", flat=True)) == {"numeric"},
       set(parts.values_list("kind", flat=True)))
    ck("6 figures attached", qs.exclude(figure=None).count() == 6,
       qs.exclude(figure=None).count())

    print("== deck selection cannot serve a dead end ==")
    containers = set(qs.filter(parts__isnull=False).values_list("id", flat=True))
    rubric = set(Question.objects.filter(marking=Question.Marking.RUBRIC)
                 .values_list("id", flat=True))
    pooled = set()
    for sub_id in qs.values_list("subtopic_id", flat=True).distinct():
        pooled |= set(answerable(Question.objects.get(
            pk=qs.filter(subtopic_id=sub_id).first().pk).subtopic).values_list("id", flat=True))
    ck("no container questions in any deck pool", not (pooled & containers),
       f"{len(containers)} containers exist")
    ck("no rubric-marked questions in any deck pool", not (pooled & rubric),
       f"{len(rubric)} rubric items exist")

    print("== number parsing is lenient about presentation, strict about value ==")
    for raw, want in [("380", 380.0), (" 380 ", 380.0), ("£25", 25.0), ("25 cm", 25.0),
                      ("1,240", 1240.0), ("47°", 47.0), ("1/2", 0.5), ("-3", -3.0),
                      ("eleven", 11.0), ("the seventh", 7.0), ("twenty five", 25.0),
                      ("", None), ("banana", None)]:
        got = parse_number(raw)
        ck(f"parse {raw!r} -> {want}", got == want, got)

    print("== marking real imported questions ==")
    q = Question.objects.get(source=SRC, stem="382 to the nearest 10")
    for given, want in [("380", True), ("380 ", True), ("381", False), ("", False)]:
        ck(f"'{given}' marked {'correct' if want else 'wrong'}",
           mark(q, given=given).correct == want)

    perim = Question.objects.get(source=SRC, stem="Work out the perimeter, in cm.")
    for given, want in [("56", True), ("56cm", True), ("56 cm", True), ("55", False)]:
        ck(f"perimeter '{given}' marked {'correct' if want else 'wrong'}",
           mark(perim, given=given).correct == want)
    r = mark(perim, given="56")
    ck("a 2-mark question awards 2, not 1", (r.marks, r.available) == (2, 2),
       f"{r.marks}/{r.available}")

    print("== end-to-end through the real view ==")
    student = User.objects.filter(role=User.Role.STUDENT).first()
    c = Client(SERVER_NAME="localhost")
    c.force_login(student, backend="django.contrib.auth.backends.ModelBackend")
    c.get(f"/practice/start/{perim.subtopic_id}/")
    sess = c.session
    deck = sess["deck"]
    deck["qids"], deck["idx"] = [perim.id], 0
    sess["deck"] = deck
    sess.save()

    html = c.get("/practice/question/").content.decode()
    ck("renders a typed-answer input", 'name="answer"' in html)
    ck("renders no radio buttons", 'type="radio"' not in html)
    ck("renders the generated SVG inline", "<svg" in html and "L-shaped figure" in html)
    ck("shows the parent's shared stem", "Find the perimeter of the L-shape" in html)
    ck("shows the unit", ">cm<" in html)

    resp = c.post("/practice/answer/", {"answer": "56 cm", "time_ms": 4200})
    ck("unit-suffixed answer marked correct", b"Correct!" in resp.content)
    ck("marks shown as 2/2", b"2/2 marks" in resp.content)
    a = Attempt.objects.filter(student=student).order_by("-id").first()
    ck("attempt stores 2 of 2 marks", (a.marks_earned, a.marks_available) == (2, 2),
       f"{a.marks_earned}/{a.marks_available}")
    ck("attempt stores the raw answer", a.answer_given == "56 cm", a.answer_given)
    ck("attempt not flagged for marking", a.awaiting_marking is False)

print()
print("RESULT:", "ALL PASSED" if not fails else f"FAILURES: {fails}")
