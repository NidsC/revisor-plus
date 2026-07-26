"""End-to-end smoke test via Django's test client (no browser needed)."""
from django.test import Client

from accounts.models import User
from catalog.models import Question, Subtopic

BACKEND = "django.contrib.auth.backends.ModelBackend"
fails = []


def check(resp, label, expect=(200, 302)):
    ok = resp.status_code in expect
    print(f"  [{'OK ' if ok else 'FAIL'}] {label}: {resp.status_code}")
    if not ok:
        fails.append(label)
    return resp


print("== Anonymous ==")
c = Client(SERVER_NAME="localhost")
check(c.get("/"), "landing")
check(c.get("/accounts/login/"), "login page")
check(c.get("/dashboard/"), "dashboard redirects anon", expect=(302,))

print("== Student flow ==")
student = User.objects.get(email="student@revisorplus.test")
c.force_login(student, backend=BACKEND)
check(c.get("/after-login/"), "after-login -> student home", expect=(302,))
check(c.get("/dashboard/"), "student dashboard")
check(c.get("/practice/"), "practice choose")
sub = Subtopic.objects.filter(questions__isnull=False).distinct().first()
check(c.get(f"/practice/start/{sub.id}/"), "start practice", expect=(302,))
check(c.get("/practice/question/"), "question page")
deck = c.session["deck"]
q = Question.objects.get(pk=deck["qids"][deck["idx"]])
# The bank holds MCQ and typed-answer questions, and a deck can serve either, so
# submit whichever this one wants. Posting an option id for a numeric question
# used to blow up here on `None.id` depending purely on the shuffle.
if q.kind == q.Kind.MCQ:
    payload = {"option": q.options.first().id, "time_ms": 5000}
else:
    payload = {"answer": q.answer_text, "time_ms": 5000}
check(c.post("/practice/answer/", payload), f"submit answer ({q.kind})")
check(c.get("/practice/next/"), "next question", expect=(302,))
check(c.get("/billing/"), "pricing")
check(c.post("/billing/checkout/"), "checkout (simulated)", expect=(302,))
check(c.get("/billing/success/"), "billing success")
student.refresh_from_db()
print(f"  subscription active: {student.subscription.is_active}")

print("== Tutor flow ==")
tutor = User.objects.get(email="tutor@revisorplus.test")
tc = Client(SERVER_NAME="localhost")
tc.force_login(tutor, backend=BACKEND)
check(tc.get("/after-login/"), "after-login -> tutor home", expect=(302,))
check(tc.get("/tutor/"), "tutor dashboard")
check(tc.get(f"/tutor/student/{student.id}/"), "student detail (owned)")
check(tc.post(f"/tutor/student/{student.id}/assign/",
              {"subtopic": sub.id, "target_count": 5, "due_days": 5}),
      "assign homework", expect=(302,))

print("== Goal tracker ==")
from datetime import timedelta

from django.utils import timezone

from goals.models import Goal, School

exam = (timezone.localdate() + timedelta(weeks=12)).isoformat()
check(c.get("/goal/"), "goal detail (pupil has a seeded goal)")
check(c.get("/goal/set/"), "goal setup form")
school = School.objects.filter(active=True).first()
r = check(c.post("/goal/set/", {
    "school": school.id, "school_note": "", "exam_date": exam,
    "target_overall": 82, "target_hours": 65, "weekly_hours_available": 4,
    "target_ENG": 84, "target_MAT": 86,
}), "save goal", expect=(302,))
g = Goal.objects.filter(student=student, is_active=True).first()
ok = g and g.target_overall == 82 and g.section_targets.count() == 2
print(f"  [{'OK ' if ok else 'FAIL'}] goal saved with 2 paper targets, blanks skipped")
if not ok:
    fails.append("goal save")
check(c.get("/dashboard/"), "dashboard renders WITH a goal")

# The dashboard must survive a pupil with no target at all — onboarding is a
# prompt, not a gate, so this is a state real users will be in.
Goal.objects.filter(student=student).delete()
check(c.get("/dashboard/"), "dashboard renders WITHOUT a goal")
check(c.get("/goal/"), "goal detail without a goal")
check(c.get("/after-login/"), "after-login nudges to goal setup", expect=(302,))
check(c.get("/goal/skip/"), "skip onboarding", expect=(302,))

print("== Authorization boundary ==")
other = User.objects.create_user(username="other_tmp", email="other_tmp@x.test",
                                 password="x", role=User.Role.STUDENT)
r = tc.get(f"/tutor/student/{other.id}/")
ok = r.status_code == 403
print(f"  [{'OK ' if ok else 'FAIL'}] tutor blocked from non-owned student: {r.status_code} (expect 403)")
if not ok:
    fails.append("AUTHZ BOUNDARY")

# A target is a claim about someone else's child — the same ownership rule has to
# hold on the goal endpoints, not just the tutoring ones.
for label, resp in [
    ("tutor GET goal-set for non-owned student", tc.get(f"/goal/set/{other.id}/")),
    ("tutor POST goal-set for non-owned student", tc.post(f"/goal/set/{other.id}/", {
        "exam_date": exam, "target_overall": 90, "target_hours": 50,
        "weekly_hours_available": 3})),
    ("pupil POST goal-set for another pupil", c.post(f"/goal/set/{other.id}/", {
        "exam_date": exam, "target_overall": 90, "target_hours": 50,
        "weekly_hours_available": 3})),
]:
    ok = resp.status_code == 403
    print(f"  [{'OK ' if ok else 'FAIL'}] {label}: {resp.status_code} (expect 403)")
    if not ok:
        fails.append(label)
leaked = Goal.objects.filter(student=other).exists()
print(f"  [{'OK ' if not leaked else 'FAIL'}] no goal written to the non-owned student")
if leaked:
    fails.append("goal leaked across ownership boundary")

# Tutor setting a target for their OWN pupil must work, and be attributed to them.
r = tc.post(f"/goal/set/{student.id}/", {
    "school": school.id, "school_note": "", "exam_date": exam,
    "target_overall": 88, "target_hours": 80, "weekly_hours_available": 5,
    "target_ENG": 88, "target_MAT": 90})
g = Goal.objects.filter(student=student, is_active=True).first()
ok = r.status_code == 302 and g and g.set_by == Goal.SetBy.TUTOR
print(f"  [{'OK ' if ok else 'FAIL'}] tutor sets own pupil's target, recorded as set_by=tutor")
if not ok:
    fails.append("tutor goal set")
other.delete()

print()
print("RESULT:", "ALL PASSED" if not fails else f"FAILURES: {fails}")
