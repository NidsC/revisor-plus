"""
Edge-case checks for the new subject dashboard (compute_subject_summary) and the
practice-setup modal's question-count handling (practice.views.start).

Run:  python main.py shell < test_subject_dashboard.py

Same convention as test_readiness.py — no test runner needed. Everything happens
on a throwaway pupil that is deleted at the end, so this never disturbs the
seeded demo data.
"""
from datetime import timedelta

from django.test import Client
from django.utils import timezone

from accounts.models import User
from analytics.services import compute_subject_summary
from catalog.models import Question, Section
from practice.models import Attempt, TestSession

fails = []


def check(label, cond, detail=""):
    print(f"  [{'OK  ' if cond else 'FAIL'}] {label}{(' — ' + str(detail)) if detail else ''}")
    if not cond:
        fails.append(label)


now = timezone.now()
pupil = User.objects.create_user(username="subjdash_tmp", email="subjdash_tmp@x.test",
                                 password="x", role=User.Role.STUDENT)
eng = Section.objects.get(code="ENG")

try:
    print("== 1. brand-new pupil: all four sections present, nothing crashes ==")
    rows = compute_subject_summary(pupil)
    codes = sorted(r["code"] for r in rows)
    check("all four sections returned", codes == ["ENG", "MAT", "NVR", "VR"], codes)
    eng_row = next(r for r in rows if r["code"] == "ENG")
    check("completed is 0", eng_row["completed"] == 0, eng_row["completed"])
    check("total is the ENG bank size, not 0", eng_row["total"] > 0, eng_row["total"])
    check("pct_complete is 0", eng_row["pct_complete"] == 0, eng_row["pct_complete"])
    check("weekly_avg is None, not 0", eng_row["weekly_avg"] is None, eng_row["weekly_avg"])

    eng_qs = list(Question.objects.filter(subtopic__section=eng, active=True, parts__isnull=True)[:3])
    if len(eng_qs) >= 2:
        session = TestSession.objects.create(student=pupil, subtopic=eng_qs[0].subtopic)

        print("== 2. attempts inside the last 7 days count toward completion + weekly_avg ==")
        recent = [
            Attempt(session=session, student=pupil, question=eng_qs[0], subtopic=eng_qs[0].subtopic,
                    is_correct=True, marks_earned=1, marks_available=1, time_taken_ms=1000,
                    source=Attempt.Source.PRACTICE, created_at=now - timedelta(days=1)),
            Attempt(session=session, student=pupil, question=eng_qs[1], subtopic=eng_qs[1].subtopic,
                    is_correct=False, marks_earned=0, marks_available=1, time_taken_ms=1000,
                    source=Attempt.Source.PRACTICE, created_at=now - timedelta(days=2)),
        ]
        Attempt.objects.bulk_create(recent)
        rows = compute_subject_summary(pupil)
        eng_row = next(r for r in rows if r["code"] == "ENG")
        check("completed counts 2 distinct questions", eng_row["completed"] == 2, eng_row["completed"])
        check("weekly_avg is 50% (1 of 2 correct)", eng_row["weekly_avg"] == 50, eng_row["weekly_avg"])

        print("== 3. an attempt older than 7 days adds to completion but not weekly_avg ==")
        Attempt.objects.create(
            session=session, student=pupil, question=eng_qs[2], subtopic=eng_qs[2].subtopic,
            is_correct=True, marks_earned=1, marks_available=1, time_taken_ms=1000,
            source=Attempt.Source.PRACTICE, created_at=now - timedelta(days=30),
        )
        rows = compute_subject_summary(pupil)
        eng_row = next(r for r in rows if r["code"] == "ENG")
        check("completed now counts 3 distinct questions", eng_row["completed"] == 3, eng_row["completed"])
        check("weekly_avg unchanged by the old attempt", eng_row["weekly_avg"] == 50, eng_row["weekly_avg"])

        print("== 4. start() honours a valid ?count=, clamps invalid ones, never crashes ==")
        client = Client(SERVER_NAME="localhost")  # ALLOWED_HOSTS doesn't include the Client default "testserver"
        client.force_login(pupil)
        subtopic_id = eng_qs[0].subtopic_id

        resp = client.get(f"/practice/start/{subtopic_id}/?count=3")
        deck = client.session.get("deck")
        check("count=3 deals exactly 3 questions", deck is not None and len(deck["qids"]) == 3,
              deck and len(deck["qids"]))

        resp = client.get(f"/practice/start/{subtopic_id}/?count=0")
        deck = client.session.get("deck")
        check("count=0 floors at 1, not an empty deck",
              deck is not None and len(deck["qids"]) == 1, deck and len(deck["qids"]))

        resp = client.get(f"/practice/start/{subtopic_id}/?count=-4")
        deck = client.session.get("deck")
        check("negative count also floors at 1", deck is not None and len(deck["qids"]) == 1,
              deck and len(deck["qids"]))

        resp = client.get(f"/practice/start/{subtopic_id}/?count=notanumber")
        deck = client.session.get("deck")
        check("non-numeric count falls back to the default", deck is not None and len(deck["qids"]) == 5,
              deck and len(deck["qids"]))

        resp = client.get(f"/practice/start/{subtopic_id}/?count=999")
        deck = client.session.get("deck")
        check("an absurd count is clamped to the ceiling (40)",
              deck is not None and len(deck["qids"]) == 40, deck and len(deck["qids"]))

        resp = client.get(f"/practice/start/{subtopic_id}/?count=7&mode=test")
        deck = client.session.get("deck")
        check("mode=test still honoured alongside count", deck is not None and deck["mode"] == "test",
              deck and deck.get("mode"))
    else:
        print("== (skipped 2-4: fewer than 3 answerable ENG questions in this database) ==")
finally:
    Attempt.objects.filter(student=pupil).delete()
    TestSession.objects.filter(student=pupil).delete()
    pupil.delete()

print()
print("RESULT:", "ALL PASSED" if not fails else f"FAILURES: {fails}")
