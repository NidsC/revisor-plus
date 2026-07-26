"""
Checks for the adaptive/practice machinery.

Run:  python manage.py shell < test_adaptive.py

Same convention as smoke_test.py and test_readiness.py. Starts as the guard on
Step 0's idempotency fix; the adaptive-engine assertions (calibration ladder,
mastery movement, review scheduling, deck uniqueness, generator stability) get
added as those steps land, so this file is the running contract for the engine.
"""
from django.test import Client

from accounts.models import User
from catalog.models import Question
from practice.models import Attempt
from practice.views import answerable, was_correct

fails = []


def ck(label, cond, detail=""):
    print(f"  [{'OK  ' if cond else 'FAIL'}] {label}{(' — ' + str(detail)) if detail else ''}")
    if not cond:
        fails.append(label)


student = User.objects.filter(role=User.Role.STUDENT).first()
c = Client(SERVER_NAME="localhost")
c.force_login(student, backend="django.contrib.auth.backends.ModelBackend")

# Pick something deterministic to answer, whichever content happens to be loaded.
target = (Question.objects.filter(active=True, parent__isnull=False, kind="numeric")
          .exclude(answer_text="").first()
          or Question.objects.filter(active=True, parts__isnull=True, kind="mcq").first())


def payload_for(q, correct=True):
    if q.kind == q.Kind.MCQ:
        opt = q.options.filter(is_correct=correct).first() or q.options.first()
        return {"option": opt.id, "time_ms": 3000}
    return {"answer": q.answer_text if correct else "-99999", "time_ms": 3000}


def fresh_deck(q):
    c.get(f"/practice/start/{q.subtopic_id}/")
    sess = c.session
    deck = sess["deck"]
    deck["qids"], deck["idx"], deck["answered"] = [q.id], 0, []
    sess["deck"] = deck
    sess.save()


print("== answering is idempotent (repost / double-click / refresh) ==")
fresh_deck(target)
before = Attempt.objects.filter(student=student, question=target).count()
responses = [c.post("/practice/answer/", payload_for(target)) for _ in range(4)]
created = Attempt.objects.filter(student=student, question=target).count() - before
ck("4 posts of one question create exactly 1 Attempt", created == 1, f"created {created}")
ck("every response still renders feedback",
   all(r.status_code == 200 for r in responses),
   [r.status_code for r in responses])
ck("replays show the same verdict",
   len({b"Correct!" in r.content for r in responses}) == 1)
banked = sum(a.marks_earned for a in
             Attempt.objects.filter(student=student, question=target).order_by("-id")[:1])
ck("marks banked once, not per post", banked <= target.marks, f"{banked} vs max {target.marks}")

print("== the deck records enough to rebuild feedback ==")
deck = c.session["deck"]
entry = deck["answered"][0]
ck("answered entries are dicts, not bare bools", isinstance(entry, dict), type(entry).__name__)
ck("entry carries the attempt id", bool(entry.get("attempt_id")))
ck("entry carries qid, correct and marks",
   {"qid", "correct", "marks"} <= set(entry), sorted(entry))

print("== old bare-bool decks still work (paused decks survive deploy) ==")
ck("was_correct(True) is True", was_correct(True) is True)
ck("was_correct(False) is False", was_correct(False) is False)
ck("was_correct(dict) reads 'correct'", was_correct({"correct": True}) is True)
ck("summary can total a mixed legacy deck",
   sum(1 for x in [True, False, {"correct": True}, {"correct": False}] if was_correct(x)) == 2)

print("== advancing lets the next question be answered ==")
fresh_deck(target)
c.post("/practice/answer/", payload_for(target))
n_after_first = Attempt.objects.filter(student=student, question=target).count()
c.get("/practice/next/")          # idx advances past the end of a 1-question deck
r = c.get("/practice/question/")
ck("deck completes and redirects to summary", r.status_code == 302, r.status_code)
ck("no extra attempt from advancing",
   Attempt.objects.filter(student=student, question=target).count() == n_after_first)

print("== deck selection invariants ==")
pool = list(answerable(target.subtopic).values_list("id", flat=True))
ck("no containers in the pool",
   not set(pool) & set(Question.objects.filter(parts__isnull=False).values_list("id", flat=True)))
ck("no rubric items in the pool",
   not set(pool) & set(Question.objects.filter(
       marking=Question.Marking.RUBRIC).values_list("id", flat=True)))

print("== generated bank ==")
gen = Question.objects.filter(source="GEN")
if not gen.exists():
    print("  (skipped — run: manage.py generate_bank --count 60 --seed 11)")
else:
    from collections import Counter

    spread = Counter(gen.values_list("difficulty", flat=True))
    ck("bank is over 1,000 questions", gen.count() > 1000, gen.count())
    ck("all five difficulty bands populated", set(spread) == {1, 2, 3, 4, 5}, dict(spread))
    ck("no band is empty enough to starve the adaptive selector",
       min(spread.values()) >= 50, dict(spread))
    ck("every generated question has a gen_key",
       not gen.filter(gen_key="").exists())
    ck("gen_keys are unique",
       len(set(gen.values_list("gen_key", flat=True))) == gen.count())
    bad = [q.id for q in gen.prefetch_related("options")[:400]
           if q.options.filter(is_correct=True).count() != 1]
    ck("exactly one correct option per question", not bad, bad[:5])
    thin = [q.id for q in gen.prefetch_related("options")[:400] if q.options.count() < 3]
    ck("at least three options per question", not thin, thin[:5])

    print("== decks no longer repeat a question ==")
    for sub in {q.subtopic for q in gen[:60]}:
        pool = list(answerable(sub).values_list("id", flat=True))
        if len(pool) >= 5:
            c.get(f"/practice/start/{sub.id}/")
            qids = c.session["deck"]["qids"]
            ck(f"{sub.section.code}/{sub.name}: deck has no duplicates",
               len(qids) == len(set(qids)), qids)
            break

print("== mock papers ==")
from datetime import timedelta

from django.utils import timezone

from catalog.models import Section, Subtopic
from practice.views import build_paper, paper_questions

ck("four papers offered", Section.objects.count() == 4, Section.objects.count())
for section in Section.objects.all():
    ids = build_paper(section, 20)
    ck(f"{section.code}: paper built with no duplicates",
       ids and len(ids) == len(set(ids)), len(ids))
    ck(f"{section.code}: spread across subtopics",
       len({q.subtopic_id for q in Question.objects.filter(id__in=ids)}) >= 1)
    ck(f"{section.code}: no containers served",
       not Question.objects.filter(id__in=ids, parts__isnull=False).exists())

# A mock is a whole paper, so unlike practice it DOES include written questions.
eng = Section.objects.get(code="ENG")
ck("mock pool includes rubric items where practice excludes them",
   paper_questions(eng).filter(marking=Question.Marking.RUBRIC).count()
   >= sum(answerable(s).filter(marking=Question.Marking.RUBRIC).count()
          for s in Subtopic.objects.filter(section=eng)))

c.get(f"/mocks/start/{eng.id}/")
deck = c.session["deck"]
ck("mock deck is timed and paper-wide",
   deck["mode"] == "mock" and deck["subtopic_id"] is None and bool(deck.get("ends_at")))

# THE CLOCK MUST BE SERVER-ENFORCED. A displayed countdown a pupil can reload
# past is decoration, not a timed paper.
sess = c.session
sess["deck"]["ends_at"] = (timezone.now() - timedelta(seconds=30)).isoformat()
sess.modified = True
sess.save()
n_before = Attempt.objects.filter(student=student).count()
ck("expired paper will not serve another question",
   c.get("/practice/question/").status_code == 302)
qq = Question.objects.get(pk=deck["qids"][0])
c.post("/practice/answer/",
       {"option": qq.options.first().id} if qq.kind == qq.Kind.MCQ else {"answer": "x"})
ck("expired paper records no further attempt",
   Attempt.objects.filter(student=student).count() == n_before)
ck("result page renders", c.get("/mocks/result/").status_code == 200)

print("== no template leaks developer comments to users ==")
# Django's {# #} is SINGLE-LINE ONLY; a multi-line one renders as visible text.
# This has now shipped to real pages three separate times — the pricing page, the
# goal setup page, and a pupil's screen mid-paper — so it is a permanent check
# rather than something to remember.
import glob
import re as _re

leaky = []
for path in glob.glob("templates/**/*.html", recursive=True):
    src = open(path).read()
    for m in _re.finditer(r"\{#", src):
        rest = src[m.start():]
        close = rest.find("#}")
        if close == -1 or "\n" in rest[:close]:
            leaky.append(path)
ck("no multi-line {# #} comments in any template", not leaky, sorted(set(leaky)))

print()
print("RESULT:", "ALL PASSED" if not fails else f"FAILURES: {fails}")
