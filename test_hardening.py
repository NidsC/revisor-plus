"""
Checks three request-handling fixes stay fixed: the parent dashboard renders for a
tutor-linked pupil, the tutor's homework form survives bad numbers, and sign-up
passwords are held to Django's standard validators.

Run:  python main.py seed_demo
      python main.py shell < test_hardening.py

Each of these was a live defect on 2026-09-15:

- `/parent/` returned 500 for every pupil with an active TutorStudent link: the
  template applied the list filter `first` to a User object. Every seeded demo
  pupil is tutor-linked, so the page never worked with demo data.
- `tutoring.views.assign_homework` fed the raw POST values straight into `int()`.
  A non-number crashed the request; a negative count failed the model's CHECK
  constraint (also a 500); a huge count or due-date offset was stored as sent.
  `practice.parent_views` already guarded and clamped the same field, so the
  two forms disagreed about what a valid homework was.
- AUTH_PASSWORD_VALIDATORS listed only the 6-character minimum, so "password1",
  an all-digit password, or the pupil's own name were all accepted at sign-up.

`main.py shell` exits 0 whatever this prints; CI greps for RESULT: ALL PASSED.
"""
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from assignments.models import Assignment
from catalog.models import Subtopic

results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(("PASS " if ok else "FAIL ") + name + (f" -- {detail}" if detail else ""))


# The test client calls itself "testserver", which the real settings do not list.
if "testserver" not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS.append("testserver")

student = User.objects.get(email="student@revisorplus.test")
tutor = User.objects.get(email="tutor@revisorplus.test")

print("== /parent/ renders for a tutor-linked pupil ==")
pupil = Client(raise_request_exception=False)
pupil.force_login(student)
r = pupil.get("/parent/")
check("GET /parent/ is 200", r.status_code == 200, f"status {r.status_code}")
if r.status_code == 200:
    html = r.content.decode()
    initial = (tutor.full_name or tutor.email)[:1].upper()
    check("tutor avatar shows the tutor's initial",
          f'rp-parent__tutor-avatar">{initial}<' in html, f"expected {initial!r}")

print("== tutor homework form tolerates bad numbers ==")
subtopic = Subtopic.objects.order_by("pk").first()
assign_url = reverse("tutoring:assign", args=[student.id])
tutor_client = Client(raise_request_exception=False)
tutor_client.force_login(tutor)
start_id = Assignment.objects.order_by("-id").values_list("id", flat=True).first() or 0


def assign(target_count, due_days):
    r = tutor_client.post(assign_url, {
        "subtopic": subtopic.pk, "target_count": target_count, "due_days": due_days,
    })
    return r.status_code, Assignment.objects.filter(id__gt=start_id).order_by("-id").first()


def due_in(days):
    return (timezone.now() + timedelta(days=days)).date()


for sent, expected in [("abc", 5), ("-5", 1), ("9999", 40), ("7", 7), ("", 5)]:
    status, a = assign(sent, "5")
    check(f"target_count={sent!r} -> redirect, stored {expected}",
          status == 302 and a is not None and a.target_count == expected,
          f"status {status}, stored {getattr(a, 'target_count', None)}")
for sent, expected_days in [("abc", 5), ("99999", 365), ("0", 1), ("", 5)]:
    status, a = assign("5", sent)
    check(f"due_days={sent!r} -> redirect, due in {expected_days} days",
          status == 302 and a is not None and a.due_date == due_in(expected_days),
          f"status {status}, due {getattr(a, 'due_date', None)}")
removed, _ = Assignment.objects.filter(id__gt=start_id).delete()
print(f"   removed {removed} probe assignment(s)")

print("== sign-up passwords face Django's standard validators ==")
# Unrelated username/email and full name, so each rejection can be attributed.
probe = User(username="pupil42", email="pupil42@example.test", full_name="Jane Smith")


def verdict(password):
    try:
        validate_password(password, probe)
    except ValidationError as e:
        return True, "; ".join(e.messages)
    return False, "accepted"


for password, why in [
    ("password1", "common"),
    ("12345678", "numeric"),
    ("abcde", "too short"),
    ("janesmith2", "similar to full_name"),
    ("pupil42x", "similar to username/email"),
]:
    rejected, msg = verdict(password)
    check(f"rejects {password!r} ({why})", rejected, msg)
rejected, msg = verdict("Kestrel7!x")
check("accepts an ordinary strong password", not rejected, msg)
names = sorted(v["NAME"].rsplit(".", 1)[-1] for v in settings.AUTH_PASSWORD_VALIDATORS)
check("all four validators are configured", names == sorted([
    "UserAttributeSimilarityValidator", "MinimumLengthValidator",
    "CommonPasswordValidator", "NumericPasswordValidator"]), str(names))

print()
print("RESULT: ALL PASSED" if all(results) else f"RESULT: {results.count(False)} FAILED")
