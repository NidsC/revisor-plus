"""
Checks that every answer kind survives the whole pipeline.

Run:  python manage.py import_pack elevenplus_data/_EXAMPLE.answer_kinds.json
      python manage.py import_pack elevenplus_data/_EXAMPLE.shared_passage.json
      python manage.py import_pack elevenplus_data/_EXAMPLE.vr_shapes.json
      python manage.py shell < test_kinds.py

A kind is only usable when four things agree: the model stores it, the validator
admits it, the importer carries its fields, and the marking engine scores it.
They have disagreed before — `extended_text` sat in the model and the marking
engine for months while the validator refused it, and the importer threw away the
rubric of anything human-marked. Both failures were silent. This checks all four
for all eight kinds, and checks the pupil-facing rendering too, because a
spot-the-error question that marks correctly and renders as a list of answers is
still wrong.

Seven of the eight are demonstrated by _EXAMPLE.answer_kinds.json. The eighth,
`grouped_options`, is in _EXAMPLE.vr_shapes.json instead — it is a verbal
reasoning shape, and putting a bracketed pair in an English pack to keep the
kinds in one file would model something no GL English paper does. That pack also
carries the other two things a VR paper needs and a pack could not express: a
shared instruction with a worked example, and a shared code table.
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

# ---------------------------------------------------------------------------
# The three shapes a GL verbal reasoning paper needs.
#
# The eighth kind lives in the VR pack rather than in _EXAMPLE.answer_kinds.json
# with the other seven, because it is a VR shape: GL English does not print
# bracketed pairs, and adding one to an English pack to keep the kinds in one
# file would model something no paper does.
# ---------------------------------------------------------------------------
print("\n== a shared instruction, a shared table, and one word from each bracket ==")
vr = Question.objects.filter(source="EXAMPLE-VR-SHAPES")
if not vr.exists():
    print("  (skipped — import elevenplus_data/_EXAMPLE.vr_shapes.json first)")
else:
    by_ref = {q.stem: q for q in vr}
    grouped = [q for q in vr if q.kind == "grouped_options"]
    ck("the eighth kind survives import", len(grouped) == 2, len(grouped))

    g = next(q for q in grouped if q.stem.startswith("Petal"))
    ck("its words are split into brackets, in order",
       [(n, [o.text for o in opts]) for n, opts in g.option_groups]
       == [(1, ["stem", "flower", "leaf"]), (2, ["beak", "nest", "bird"])])
    ck("each bracket has exactly one key",
       all(sum(1 for o in opts if o.is_correct) == 1 for _, opts in g.option_groups))
    # Not cosmetic: the mock review page shows answer_text for every kind that is
    # not plain multiple choice, so without this a pupil reviewing a paper would
    # be told what they answered and never what was right.
    ck("the pair is stored as readable text for the review page",
       g.answer_text == "flower, bird", repr(g.answer_text))

    print("\n  -- marking is all-or-nothing, one mark --")
    picks = {n: opts for n, opts in g.option_groups}
    right = [next(o for o in opts if o.is_correct) for _, opts in g.option_groups]
    r = mark(g, options=right)
    ck("both brackets right scores the mark", r.correct and r.marks == r.available)
    half = [right[0], next(o for o in picks[2] if not o.is_correct)]
    r = mark(g, options=half)
    ck("one bracket wrong scores nothing", not r.correct and r.marks == 0)
    # Half a pair is not half an analogy, and partial credit would reward
    # guessing: two brackets of three are half-right by chance one time in two.
    ck("and it names which bracket was wrong", r.detail == ["bracket 2"], r.detail)
    r = mark(g, options=[right[0]])
    ck("a bracket left blank is wrong, with nothing to say about it",
       not r.correct and r.detail == [])
    ck("nothing picked at all is wrong", not mark(g, options=[]).correct)

    print("\n  -- the instruction and worked example ride along --")
    ck("every question in a block carries its instruction",
       all(q.instruction for q in vr if not q.is_container))
    ins = next(q for q in vr if q.stem.startswith("for ("))
    ck("the worked example is carried too, not just the instruction",
       "car ( PET ) al" in ins.worked_example, ins.worked_example[:40])
    ck("a different block gets a different instruction",
       ins.instruction != g.instruction)

    print("\n  -- the shared code table --")
    coded = [q for q in vr if q.figure]
    ck("both questions in the code block get the table", len(coded) == 2, len(coded))
    fig = coded[0].figure
    ck("it is the figure shape catalog/figures.py already draws",
       fig.get("kind") == "table" and "headers" in fig["data"])
    blanks = [c for row in fig["data"]["rows"] for c in row if c is None]
    ck("exactly one cell is withheld, as None rather than an empty string",
       len(blanks) == 1, len(blanks))

    print("\n  -- a question can need a passage AND an instruction --")
    # This is the case that forced groups and tables to be copied onto each
    # question rather than held on a container row: `parent` is a single FK.
    both = next(q for q in vr if q.parent_id and not q.is_container)
    ck("it hangs off the passage container", bool(both.context_passage))
    ck("and still carries its own instruction", bool(both.instruction))
    ck("the table questions carry a figure and an instruction at once",
       all(q.figure and q.instruction for q in coded))

    print("\n  -- what the pupil sees --")
    html = show(g)
    ck("each bracket is its own radio group",
       'name="bracket_1"' in html and 'name="bracket_2"' in html)
    ck("every word is offered", all(o.text in html for _, opts in g.option_groups
                                    for o in opts))
    ck("the stem is shown once, with its brackets", html.count(g.stem) == 1)
    ck("the instruction is printed above it", g.instruction[:40] in html)
    ck("so is the worked example", "spider is to" in html)

    html = show(coded[0])
    ck("the code table is rendered as a table, not an image",
       "<table" in html and "DBU" in html)
    ck("the withheld cell is blank rather than the word None", "None" not in html)

    print("\n  -- answers submitted through the real view --")
    for want in (True, False):
        Attempt.objects.filter(student=student).delete()
        show(g)
        if want:
            post = {f"bracket_{n}": next(o for o in opts if o.is_correct).id
                    for n, opts in g.option_groups}
        else:
            post = {f"bracket_{n}": next(o for o in opts if not o.is_correct).id
                    for n, opts in g.option_groups}
        post["time_ms"] = 4000
        body = c.post("/practice/answer/", post).content.decode()
        a = Attempt.objects.filter(student=student).order_by("-id").first()
        ck(f"grouped_options: a {'right' if want else 'wrong'} pair is marked and stored",
           ("Correct!" in body if want else "Not quite" in body)
           and a is not None and a.is_correct is want)
        # One ForeignKey cannot hold two picks, so the words go into
        # answer_given — which is what the review page already falls back to.
        ck(f"  the words picked are recorded ({'right' if want else 'wrong'})",
           a is not None and a.selected_option is None and " | " in (a.answer_given or ""),
           a.answer_given if a else None)

print()
print("RESULT:", "ALL PASSED" if not fails else f"FAILURES: {fails}")
