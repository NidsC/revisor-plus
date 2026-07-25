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
student = User.objects.get(email="student@medrevisor.test")
c.force_login(student, backend=BACKEND)
check(c.get("/after-login/"), "after-login -> student home", expect=(302,))
check(c.get("/dashboard/"), "student dashboard")
check(c.get("/practice/"), "practice choose")
sub = Subtopic.objects.filter(questions__isnull=False).distinct().first()
check(c.get(f"/practice/start/{sub.id}/"), "start practice", expect=(302,))
check(c.get("/practice/question/"), "question page")
deck = c.session["deck"]
q = Question.objects.get(pk=deck["qids"][deck["idx"]])
opt = q.options.first()
check(c.post("/practice/answer/", {"option": opt.id, "time_ms": 5000}), "submit answer")
check(c.get("/practice/next/"), "next question", expect=(302,))
check(c.get("/billing/"), "pricing")
check(c.post("/billing/checkout/"), "checkout (simulated)", expect=(302,))
check(c.get("/billing/success/"), "billing success")
student.refresh_from_db()
print(f"  subscription active: {student.subscription.is_active}")

print("== Tutor flow ==")
tutor = User.objects.get(email="tutor@medrevisor.test")
tc = Client(SERVER_NAME="localhost")
tc.force_login(tutor, backend=BACKEND)
check(tc.get("/after-login/"), "after-login -> tutor home", expect=(302,))
check(tc.get("/tutor/"), "tutor dashboard")
check(tc.get(f"/tutor/student/{student.id}/"), "student detail (owned)")
check(tc.post(f"/tutor/student/{student.id}/assign/",
              {"subtopic": sub.id, "target_count": 5, "due_days": 5}),
      "assign homework", expect=(302,))

print("== Authorization boundary ==")
other = User.objects.create_user(username="other_tmp", email="other_tmp@x.test",
                                 password="x", role=User.Role.STUDENT)
r = tc.get(f"/tutor/student/{other.id}/")
ok = r.status_code == 403
print(f"  [{'OK ' if ok else 'FAIL'}] tutor blocked from non-owned student: {r.status_code} (expect 403)")
if not ok:
    fails.append("AUTHZ BOUNDARY")
other.delete()

print()
print("RESULT:", "ALL PASSED" if not fails else f"FAILURES: {fails}")
