"""
Checks that every answer kind survives the whole pipeline.

Run:  python manage.py import_pack elevenplus_data/_EXAMPLE.answer_kinds.json
      python manage.py shell < test_kinds.py

A kind is only usable when four things agree: the model stores it, the validator
admits it, the importer carries its fields, and the marking engine scores it.
They have disagreed before — `extended_text` sat in the model and the marking
engine for months while the validator refused it, and the importer threw away the
rubric of anything human-marked. Both failures were silent. This checks all four
for all seven kinds, and checks the pupil-facing rendering too, because a
spot-the-error question that marks correctly and renders as a list of answers is
still wrong.
"""
from django.test import Client

from accounts.models import User
from catalog.marking import mark
from catalog.models import Question
from practice.models import Attempt

SOURCE = "EXAMPLE-ANSWER-KINDS"
fails = []


def ck(label, cond, extra=""):
    print(f"  [{'OK  ' if cond else 'FAIL'}] {label}" + (f" — {extra}" if extra else ""))
    if not cond:
        fails.append(label)


qs = {q.kind: q for q in Question.objects.filter(source=SOURCE)}
print("== the pack imported at all ==")
expected = {"mcq", "numeric", "short_text", "extended_text",
            "error_span", "select_word", "cloze_gap"}
ck("every kind is present", set(qs) == expected, sorted(set(qs) ^ expected) or "all seven")
if set(qs) != expected:
    print("\nRESULT: FAILURES:", fails)
    raise SystemExit(1)

print("\n== the importer kept what each kind needs ==")
es = qs["error_span"]
ck("segments stored in reading order",
   [o.label for o in es.selection_spans] == ["A", "B", "C", "D"])
ck("segments rejoin the stem exactly",
   "".join(o.text for o in es.selection_spans) == es.stem)
ck("the no-mistake answer is kept apart from the sentence",
   es.no_error_option is not None and es.no_error_option.label == "N")
ck("the right segment is the correct one",
   next(o for o in es.options.all() if o.is_correct).label == "B")

sw = qs["select_word"]
ck("click-the-word rejoins its stem too",
   "".join(o.text for o in sw.selection_spans) == sw.stem)

cz = qs["cloze_gap"]
ck("a cloze gap knows which gap it is", cz.gap_number == 1, cz.gap_number)
ck("a cloze gap keeps its passage", bool(cz.passage))

et = qs["extended_text"]
ck("a human-marked question keeps its rubric", isinstance(et.rubric, dict), et.rubric)
ck("a human-marked question keeps its model answer", bool(et.model_answer))
ck("a human-marked question keeps its marks", et.marks == 4, et.marks)
ck("a human-marked question is flagged for a marker",
   et.marking == Question.Marking.RUBRIC, et.marking)

print("\n== the marking engine scores each kind ==")
for kind in ("mcq", "error_span", "select_word", "cloze_gap"):
    q = qs[kind]
    right = mark(q, option=next(o for o in q.options.all() if o.is_correct))
    wrong = mark(q, option=next(o for o in q.options.all() if not o.is_correct))
    ck(f"{kind} marks a right answer right", right.correct and right.marks == right.available)
    ck(f"{kind} marks a wrong answer wrong", not wrong.correct)

for kind in ("numeric", "short_text"):
    q = qs[kind]
    ck(f"{kind} accepts its own canonical answer", mark(q, given=q.answer_text).correct,
       repr(q.answer_text))
    ck(f"{kind} rejects a wrong answer", not mark(q, given="definitely not that").correct)

st = qs["short_text"]
for alt in st.accepted_alternatives:
    ck(f"short_text accepts the alternative {alt!r}", mark(st, given=alt).correct)

ck("extended_text goes to a human rather than scoring 0",
   mark(et, given="Some writing.").awaiting_marking)

print("\n== the pupil sees the right thing ==")
student = User.objects.filter(role=User.Role.STUDENT).first()
c = Client(SERVER_NAME="localhost")
c.force_login(student, backend="django.contrib.auth.backends.ModelBackend")


def show(question):
    c.get(f"/practice/start/{question.subtopic_id}/")
    sess = c.session
    deck = sess["deck"]
    deck["qids"], deck["idx"] = [question.id], 0
    sess["deck"] = deck
    sess.save()
    return c.get("/practice/question/").content.decode()


html = show(es)
ck("spot-the-error renders the sentence as clickable spans", "selection-sentence" in html)
ck("spot-the-error letters each span", "selection-letter" in html)
ck("spot-the-error keeps the misspelling on screen", "definately" in html)
ck("spot-the-error offers the no-mistake answer", "No mistake" in html)
ck("spot-the-error does not print the sentence twice", html.count(es.stem) == 0)

html = show(cz)
ck("a cloze gap offers choices rather than a text box",
   'type="radio"' in html and 'id="answer"' not in html)

html = show(et)
ck("extended writing gets a textarea", "<textarea" in html)
ck("extended writing says a teacher will mark it", "teacher marks this one" in html)

print("\n== answers submitted through the real view ==")
for kind in ("error_span", "select_word", "cloze_gap"):
    q = qs[kind]
    for want in (True, False):
        Attempt.objects.filter(student=student).delete()
        show(q)
        opt = next(o for o in q.options.all() if o.is_correct is want)
        body = c.post("/practice/answer/",
                      {"option": opt.id, "time_ms": 3000}).content.decode()
        a = Attempt.objects.filter(student=student).order_by("-id").first()
        ck(f"{kind}: a {'right' if want else 'wrong'} answer is marked and stored",
           ("Correct!" in body if want else "Not quite" in body)
           and a is not None and a.is_correct is want)

Attempt.objects.filter(student=student).delete()
show(et)
c.post("/practice/answer/", {"answer": "The writer uses cold words.", "time_ms": 9000})
a = Attempt.objects.filter(student=student).order_by("-id").first()
ck("extended writing is held for a marker", a is not None and a.awaiting_marking)
ck("extended writing stores what the pupil wrote",
   a is not None and "cold words" in (a.answer_given or ""))

print("\n== a passage shared by several questions ==")
shared = Question.objects.filter(source="EXAMPLE-SHARED-PASSAGE")
if not shared.exists():
    print("  (skipped — import elevenplus_data/_EXAMPLE.shared_passage.json first)")
else:
    containers = [q for q in shared if q.is_container]
    parts = [q for q in shared if q.parent_id]
    ck("exactly one container holds the passage", len(containers) == 1, len(containers))
    ck("every other question hangs off it", len(parts) == shared.count() - 1)
    cont = containers[0]
    ck("the passage is stored once, not per question",
       sum(1 for q in shared if q.passage) == 1)
    ck("the container keeps the title", cont.passage_title == "Down the Rabbit-Hole")
    ck("the container keeps the source note", "Public domain" in cont.passage_source)
    ck("the container's stem is empty so it cannot prefix its parts",
       cont.stem == "")
    ck("parts inherit the passage", all(p.context_passage == cont.passage for p in parts))
    ck("parts inherit the title",
       all(p.context_passage_title == cont.passage_title for p in parts))
    ck("a part's displayed stem is its own question, not the passage title",
       all(not p.display_stem.startswith("Down the Rabbit-Hole") for p in parts))
    ck("cloze gaps keep their numbers",
       sorted(p.gap_number for p in parts if p.kind == "cloze_gap") == [1, 2])

    servable = Question.objects.filter(active=True, parts__isnull=True)
    ck("the container can never be served to a pupil", cont not in servable)
    ck("its questions can", all(p in servable for p in parts))

    html = show(parts[0])
    ck("the pupil sees the passage title", "Down the Rabbit-Hole" in html)
    ck("the pupil sees where the text came from", "Public domain" in html)
    ck("the passage is numbered", "passage-num" in html)

print()
print("RESULT:", "ALL PASSED" if not fails else f"FAILURES: {fails}")
