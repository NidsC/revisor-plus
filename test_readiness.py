"""
Edge-case checks for the readiness engine (analytics/readiness.py).

Run:  python manage.py shell < test_readiness.py

Same convention as smoke_test.py — no test runner needed. Everything happens on a
throwaway pupil that is deleted at the end, so this never disturbs the seeded
demo data. The cases here are the ones where a plausible-looking implementation
quietly says something false, so they are worth re-running after any change to
the engine.
"""
from datetime import timedelta

from django.utils import timezone

from accounts.models import User
from analytics.readiness import compute_readiness
from catalog.models import Question, Section
from goals.models import Goal, School, SectionTarget
from practice.models import Attempt, TestSession

fails = []


def check(label, cond, detail=""):
    print(f"  [{'OK  ' if cond else 'FAIL'}] {label}{(' — ' + str(detail)) if detail else ''}")
    if not cond:
        fails.append(label)


today = timezone.localdate()
now = timezone.now()
pupil = User.objects.create_user(username="readiness_tmp", email="readiness_tmp@x.test",
                                 password="x", role=User.Role.STUDENT)
school = School.objects.create(slug="readiness-tmp-school", name="Test School", area="Sutton")
eng, mat = Section.objects.get(code="ENG"), Section.objects.get(code="MAT")
school.papers.set([eng, mat])

try:
    print("== 1. no goal at all ==")
    r = compute_readiness(pupil)
    check("status is no_goal", r["status"] == "no_goal", r["status"])
    check("no divide-by-zero; hours are zero", r["required_hours_per_week"] == 0)

    print("== 2. goal but no attempts ==")
    goal = Goal.objects.create(student=pupil, school=school, target_hours=50,
                               exam_date=today + timedelta(weeks=10))
    SectionTarget.objects.create(goal=goal, section=eng, target_accuracy=80)
    SectionTarget.objects.create(goal=goal, section=mat, target_accuracy=80)
    r = compute_readiness(pupil)
    check("status is not_started", r["status"] == "not_started", r["status"])
    check("readiness_pct is 0", r["readiness_pct"] == 0)
    check("no crash on an empty trend", r["projected_overall"] is None)
    check("required h/wk uses the whole target", r["required_hours_per_week"] == 5.0,
          r["required_hours_per_week"])

    # Give the pupil a measurable record: 120 ENG attempts at 50%, 60s each = 2.0h.
    # Deliberately over two hours so case 7 can set an integer target_hours below it.
    eng_qs = list(Question.objects.filter(subtopic__section=eng, active=True)[:4])
    if eng_qs:
        session = TestSession.objects.create(student=pupil, subtopic=eng_qs[0].subtopic)
        rows = []
        for i in range(120):
            q = eng_qs[i % len(eng_qs)]
            correct = i % 2 == 0
            rows.append(Attempt(
                session=session, student=pupil, question=q, subtopic=q.subtopic,
                is_correct=correct, marks_earned=1 if correct else 0, marks_available=1,
                time_taken_ms=60_000, source=Attempt.Source.PRACTICE,
                created_at=now - timedelta(days=7),
            ))
        Attempt.objects.bulk_create(rows)

        print("== 3. hours are measured, not assumed ==")
        r = compute_readiness(pupil)
        check("120 x 60s reads as 2.0h", r["hours_done"] == 2.0, r["hours_done"])
        check("ENG accuracy measured at 50%",
              any(g["code"] == "ENG" and g["current"] == 50 for g in r["section_gaps"]),
              [(g["code"], g["current"]) for g in r["section_gaps"]])

        print("== 4. a paper with no attempts is 'not started', not 0% ==")
        m = next(g for g in r["section_gaps"] if g["code"] == "MAT")
        check("MAT current is None, not zero", m["current"] is None, m["current"])
        check("MAT status is not_started", m["status"] == "not_started", m["status"])

    print("== 5. exam date in the past ==")
    goal.exam_date = today - timedelta(days=3)
    goal.save()
    r = compute_readiness(pupil)
    check("status is exam_passed", r["status"] == "exam_passed", r["status"])
    check("days_remaining is negative", r["days_remaining"] < 0, r["days_remaining"])
    check("still no divide-by-zero", isinstance(r["required_hours_per_week"], float))

    print("== 6. exam in two days: weeks clamped, hours finite ==")
    goal.exam_date = today + timedelta(days=2)
    goal.save()
    r = compute_readiness(pupil)
    check("weeks_remaining floors at 0.5", r["weeks_remaining"] == 0.5, r["weeks_remaining"])
    check("required h/wk is finite and urgent", 0 < r["required_hours_per_week"] < 1e6,
          r["required_hours_per_week"])

    print("== 7. THE IMPORTANT ONE: hours done, marks short -> never 'ready' ==")
    goal.exam_date = today + timedelta(weeks=6)
    goal.target_hours = 1  # already exceeded
    goal.save()
    r = compute_readiness(pupil)
    check("no hours remaining", r["hours_remaining"] == 0)
    check("pace reads on_track", r["pace_status"] == "on_track", r["pace_status"])
    check("attainment still short", r["attainment_status"] in ("behind", "at_risk"),
          r["attainment_status"])
    check("HEADLINE IS NOT 'ready'", r["status"] != "ready", r["status"])
    check("target_met is False", r["target_met"] is False)

    print("== 8. attainment genuinely met -> ready ==")
    SectionTarget.objects.filter(goal=goal).update(target_accuracy=20)
    SectionTarget.objects.filter(goal=goal, section=mat).delete()
    school.papers.set([eng])
    r = compute_readiness(pupil)
    check("target_met is True", r["target_met"] is True)
    check("status is ready", r["status"] == "ready", r["status"])
    check("readiness_pct is 100", r["readiness_pct"] == 100, r["readiness_pct"])

    print("== 9. goal with no school and no paper targets ==")
    goal.school = None
    goal.save()
    SectionTarget.objects.filter(goal=goal).delete()
    r = compute_readiness(pupil)
    check("does not crash", r["status"] in
          ("not_started", "behind", "at_risk", "on_track", "ready"), r["status"])
    check("target_label falls back", goal.target_label == "a grammar school", goal.target_label)
finally:
    Attempt.objects.filter(student=pupil).delete()
    TestSession.objects.filter(student=pupil).delete()
    Goal.objects.filter(student=pupil).delete()
    pupil.delete()
    school.delete()

print()
print("RESULT:", "ALL PASSED" if not fails else f"FAILURES: {fails}")
