"""
Checks three request-handling fixes stay fixed: the parent dashboard renders for a
tutor-linked pupil, the tutor's homework form survives bad numbers, and sign-up
passwords are held to Django's standard validators.

Run:  python main.py seed_demo
      python main.py shell < test_hardening.py

Each of these was a live defect on 2026-09-15:

- `/parent/` (now `/family/child/<id>/`, on the parent's own login since the
  parent-accounts change) returned 500 for every pupil with an active
  TutorStudent link: the template applied the list filter `first` to a User
  object. Every seeded demo pupil is tutor-linked, so the page never worked
  with demo data.
- `tutoring.views.assign_homework` fed the raw POST values straight into `int()`.
  A non-number crashed the request; a negative count failed the model's CHECK
  constraint (also a 500); a huge count or due-date offset was stored as sent.
  The parent-facing homework form in `accounts.views` already guarded and
  clamped the same field, so the two forms disagreed about what a valid
  homework was.
- AUTH_PASSWORD_VALIDATORS listed only the 6-character minimum, so "password1",
  an all-digit password, or the pupil's own name were all accepted at sign-up.

`main.py shell` exits 0 whatever this prints; CI greps for RESULT: ALL PASSED.
"""
import re
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from assignments.models import Assignment
from billing.models import Subscription
from catalog.models import Subtopic

results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(("PASS " if ok else "FAIL ") + name + (f" -- {detail}" if detail else ""))


# Progress-bar helpers for the accessibility section: the opening <div> tags carrying a class,
# and those of them missing the progressbar role, its value or its label.
bars = lambda html, cls: re.findall(r'<div[^>]*class="[^"]*' + cls + r'[^"]*"[^>]*>', html)
unlabelled = lambda tags: [t for t in tags if 'role="progressbar"' not in t
                           or 'aria-valuenow="' not in t or 'aria-label="' not in t]

# The test client calls itself "testserver", which the real settings do not list.
if "testserver" not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS.append("testserver")

student = User.objects.get(email="student@revisorplus.test")
tutor = User.objects.get(email="tutor@revisorplus.test")
parent = User.objects.get(email="parent@revisorplus.test")

print("== /family/child/<id>/ renders for a tutor-linked pupil ==")
parent_client = Client(raise_request_exception=False)
parent_client.force_login(parent)
r = parent_client.get(f"/family/child/{student.id}/")
check("GET /family/child/<id>/ is 200", r.status_code == 200, f"status {r.status_code}")

msg_r = parent_client.get(f"/family/child/{student.id}/messages/")
if msg_r.status_code == 200:
    msg_html = msg_r.content.decode()
    initial = (tutor.full_name or tutor.email)[:1].upper()
    check("tutor avatar shows the tutor's initial",
          f'rp-parent__tutor-avatar" aria-hidden="true">{initial}<' in msg_html, f"expected {initial!r}")

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

print("== parent accounts: /family/ access control ==")
parent2 = User.objects.create_user(
    username="probe_parent2", email="probe_parent2@example.test",
    password="Kestrel7!x", full_name="Probe Parent Two", role=User.Role.PARENT,
)
other_pupil = User(
    username="probe_other_pupil", email=None,
    full_name="Probe Other Pupil", role=User.Role.STUDENT, parent=parent2,
)
other_pupil.set_password("Kestrel7!x")
other_pupil.save()

r = parent_client.get("/family/")
check("GET /family/ is 200 for a parent", r.status_code == 200, f"status {r.status_code}")

tutor_family = Client(raise_request_exception=False)
tutor_family.force_login(tutor)
r = tutor_family.get("/family/")
check("GET /family/ is 403 for a tutor", r.status_code == 403, f"status {r.status_code}")

pupil_family = Client(raise_request_exception=False)
pupil_family.force_login(student)
r = pupil_family.get("/family/")
check("GET /family/ is 403 for a pupil", r.status_code == 403, f"status {r.status_code}")

r = parent_client.get(f"/family/child/{other_pupil.id}/")
check("GET /family/child/<other parent's pupil>/ is 403", r.status_code == 403, f"status {r.status_code}")

r = tutor_client.get(f"/tutor/student/{other_pupil.id}/")
check("GET /tutor/student/<a pupil not linked to this tutor>/ is 403", r.status_code == 403, f"status {r.status_code}")

r = parent_client.get("/parent/")
check("GET /parent/ is 404 (route removed)", r.status_code == 404, f"status {r.status_code}")

parent_html = parent_client.get(f"/family/child/{student.id}/").content.decode()
# The nav is rendered on any page through base.html; the dashboard is a cheap one to check.
parent_nav = parent_client.get("/dashboard/", follow=True)
pupil_nav = pupil_family.get("/dashboard/", follow=True)
check("pupil's nav has no /family/ link", '/family/' not in pupil_nav.content.decode())
check("pupil's nav has no /billing/ link", '/billing/' not in pupil_nav.content.decode())
check("parent's nav has a /family/ link", '/family/' in parent_nav.content.decode())
check("parent's nav has a /billing/ link", '/billing/' in parent_nav.content.decode())

r = parent_client.post("/family/add-child/", {
    "full_name": "Probe Child", "username": "probe_child_1",
    "password": "Kestrel7!x",
})
new_pupil = User.objects.filter(username="probe_child_1").first()
check("add_child created the pupil", new_pupil is not None)
if new_pupil is not None:
    check("add_child gave the pupil a Subscription row",
          Subscription.objects.filter(user=new_pupil).exists())
    fresh_client = Client(raise_request_exception=False)
    logged_in = fresh_client.login(username="probe_child_1", password="Kestrel7!x")
    check("the new pupil can log in with the parent-set password", logged_in)

r = parent_client.post("/family/add-child/", {
    "full_name": "Probe Child Two", "username": "probe_child_2",
    "password": "probechildtwo1",
})
check("add_child rejects a password too similar to the child's own name/username",
      not User.objects.filter(username="probe_child_2").exists())

print("== sign-up chooses parent or tutor, never pupil ==")


def signup(email, username, account_type=None):
    payload = {
        "email": email, "username": username,
        "password1": "Kestrel7!x", "password2": "Kestrel7!x",
    }
    if account_type is not None:
        payload["account_type"] = account_type
    Client(raise_request_exception=False).post("/accounts/signup/", payload)
    return User.objects.filter(email=email).first()


created = signup("probe_signup_default@example.test", "probe_signup_default")
check("signup with no account_type creates a parent",
      created is not None and created.role == User.Role.PARENT,
      f"role={getattr(created, 'role', None)}")

created = signup("probe_signup_tutor@example.test", "probe_signup_tutor", "tutor")
check("signup with account_type=tutor creates a tutor",
      created is not None and created.role == User.Role.TUTOR,
      f"role={getattr(created, 'role', None)}")

created = signup("probe_signup_student@example.test", "probe_signup_student", "student")
check("signup with account_type=student is rejected (no account created)", created is None)

Subscription.objects.filter(user__in=[other_pupil, new_pupil]).delete()
User.objects.filter(id__in=[u.id for u in [parent2, other_pupil, new_pupil] if u]).delete()
User.objects.filter(email__in=[
    "probe_signup_default@example.test", "probe_signup_tutor@example.test",
]).delete()

print("== PR C: practice routes are pupils-only ==")
from django.core.cache import cache
from catalog.marking import mark
from catalog.models import Question, Section
from practice.models import Attempt, TestSession

after_login_url = reverse("after_login")
gate_urls = [reverse(n) for n in
             ("practice:choose", "practice:question", "practice:mock_choose", "practice:dashboard")]
for who, user in [("parent", parent), ("tutor", tutor)]:
    c = Client(raise_request_exception=False)
    c.force_login(user)
    for url in gate_urls:
        r = c.get(url)
        check(f"{who} GET {url} -> 302 to after_login",
              r.status_code == 302 and r["Location"] == after_login_url,
              f"status {r.status_code}, Location {r.get('Location')}")
c = Client(raise_request_exception=False)
c.force_login(parent)
r = c.get(reverse("vocab:home"))
check("parent GET vocab:home still -> 302 to after_login (decorator moved to accounts.decorators)",
      r.status_code == 302 and r["Location"] == after_login_url, f"status {r.status_code}")

pupil_client = Client(raise_request_exception=False)
pupil_client.force_login(student)
for url in gate_urls:
    r = pupil_client.get(url)
    check(f"pupil GET {url} is not turned away to after_login",
          r.status_code in (200, 302) and r.get("Location") != after_login_url,
          f"status {r.status_code}, Location {r.get('Location')}")

print("== PR C: a timed-out question is recorded as a deliberate wrong answer ==")
attempt_floor = Attempt.objects.order_by("-id").values_list("id", flat=True).first() or 0
session_floor = TestSession.objects.order_by("-id").values_list("id", flat=True).first() or 0
section = Section.objects.order_by("order").first()
r = pupil_client.get(reverse("practice:start_subject", args=[section.code]) + "?mode=test&count=5")
check("timed deck starts through start_subject?mode=test", r.status_code == 302, f"status {r.status_code}")
deck = pupil_client.session.get("deck") or {}
check("deck is a timed (test-mode) deck", deck.get("mode") == "test", f"mode {deck.get('mode')}")
r = pupil_client.get(reverse("practice:question"))
check("timed question page renders", r.status_code == 200, f"status {r.status_code}")
check("question form carries the hidden timed_out input",
      'name="timed_out"' in r.content.decode())
qid = deck["qids"][0]
r = pupil_client.post(reverse("practice:answer"), {"qid": qid, "timed_out": "1", "time_ms": "90000"})
att = Attempt.objects.filter(id__gt=attempt_floor, question_id=qid).first()
check("timed_out answer with nothing chosen -> 200", r.status_code == 200, f"status {r.status_code}")
check("an Attempt exists, is_correct False, selected_option None",
      att is not None and att.is_correct is False and att.selected_option is None
      and att.answer_given == "",
      f"attempt {att and (att.is_correct, att.selected_option, att.answer_given)}")
check("feedback says \"Time's up\"", "Time's up" in r.content.decode())

print("== PR C: mark() with empty inputs, per kind in the bank ==")
for kind in Question.objects.order_by().values_list("kind", flat=True).distinct():
    q = Question.objects.filter(kind=kind).first()
    try:
        res = mark(q, given="", option=None, options=[])
        ok = res.correct in (False, None)
        detail = f"correct={res.correct} marks={res.marks}/{res.available} awaiting={res.awaiting_marking}"
    except Exception as e:  # noqa: BLE001 - the point is to see any failure
        ok, detail = False, f"RAISED {e!r}"
    check(f"mark(empty) for kind {kind!r} does not raise and is not correct", ok, detail)

print("== PR C: mock paper timer ==")
r = pupil_client.get(reverse("practice:mock_start", args=[section.id]))
r = pupil_client.get(reverse("practice:question"))
html = r.content.decode()
check("mock question page renders with #paper-timer carrying data-remaining",
      r.status_code == 200 and 'id="paper-timer"' in html and "data-remaining=" in html,
      f"status {r.status_code}")
with open(settings.BASE_DIR / "templates" / "practice" / "question.html") as fh:
    tpl = fh.read()
check("template submits a pending answer when the paper clock hits zero",
      "hasPendingAnswer(f)" in tpl and "f.submit();" in tpl
      and tpl.index("hasPendingAnswer(f)") < tpl.index("practice:mock_result' %}\";"))

print("== PR C: login is rate limited (allauth login_failed) ==")
cache.clear()
rl = Client(raise_request_exception=False)
login_url = reverse("account_login")
codes, bodies = [], []
for i in range(6):
    r = rl.post(login_url, {"login": "parent@revisorplus.test", "password": f"wrong-pw-{i}"})
    codes.append(r.status_code)
    bodies.append(r.content.decode())
check("first five wrong passwords are ordinary failures (no lockout message)",
      not any("Too many failed login attempts" in b for b in bodies[:5]), f"statuses {codes[:5]}")
check("6th wrong password is throttled (allauth returns a 200 form error, not a 429)",
      "Too many failed login attempts" in bodies[5], f"6th status {codes[5]}")
r = rl.post(login_url, {"login": "parent@revisorplus.test", "password": "demo12345"})
check("while throttled, even the correct password is refused",
      "Too many failed login attempts" in r.content.decode() and "_auth_user_id" not in rl.session,
      f"status {r.status_code}")
cache.clear()
check("setting is explicit in settings",
      settings.ACCOUNT_RATE_LIMITS == {"login_failed": "10/m/ip,5/300s/key"})

print("== hotfix: My target with and without a goal ==")
from goals.models import Goal

goal_pupil = User(
    username="probe_goal_pupil", email=None,
    full_name="Probe Goal Pupil", role=User.Role.STUDENT, parent=parent,
)
goal_pupil.set_password("Kestrel7!x")
goal_pupil.save()
goal_client = Client(raise_request_exception=False)
goal_client.force_login(goal_pupil)

r = goal_client.get("/goal/")
check("GET /goal/ with no Goal is 200 and carries the goals:setup link for the script",
      r.status_code == 200 and reverse("goals:setup") in r.content.decode(),
      f"status {r.status_code}")

Goal.objects.create(student=goal_pupil, exam_date=timezone.now().date() + timedelta(days=120))
r = goal_client.get("/goal/")
check("GET /goal/ with a Goal is 200 and offers Change target",
      r.status_code == 200 and "Change target" in r.content.decode(),
      f"status {r.status_code}")
Goal.objects.filter(student=goal_pupil).delete()
goal_pupil.delete()

print("\n== accessibility: headings, roving tabindex, progressbars, labels ==")
from catalog.models import Question

q = Question.objects.filter(source="EXAMPLE-SHARED-PASSAGE", parent__isnull=False).order_by("id").first()
if q is None:
    print("  (skipped — import elevenplus_data/_EXAMPLE.shared_passage.json first)")
else:
    pupil_client.get(f"/practice/start/{q.subtopic_id}/")
    sess = pupil_client.session
    sess["deck"]["qids"], sess["deck"]["idx"] = [q.id], 0
    sess.save()
    html = pupil_client.get("/practice/question/").content.decode()
    main = html[html.index("<main"):html.index("</main>")]
    check("no h2 before the h1 on the question page", "<h2" not in main[:main.index("<h1")])
    check("the passage is a landmarked section",
          '<section class="p-3 mb-3 bg-light rounded rp-passage" aria-label="Passage: Down the Rabbit-Hole">' in main)
    check("the passage title is still shown", "Down the Rabbit-Hole" in main)
    check("the passage title keeps its heading look via a class, not a heading tag",
          '<p class="h6 mb-2 text-center rp-passage__title">Down the Rabbit-Hole</p>' in main)

r = pupil_client.get("/practice/subject/ENG/")
radios = re.findall(r'<button[^>]*role="radio"[^>]*>', r.content.decode())
check("the Timed/Untimed modal has two radios", r.status_code == 200 and len(radios) == 2, f"{len(radios)}")
check("exactly one role=radio is a tab stop", sum('tabindex="0"' in t for t in radios) == 1)
check("the other role=radio is tabindex -1", sum('tabindex="-1"' in t for t in radios) == 1)

# /goal/ draws bars only for a pupil with attempts, so the seeded student gets a Goal for this check.
had_goal = Goal.objects.filter(student=student).exists()
if not had_goal:
    Goal.objects.create(student=student, exam_date=timezone.now().date() + timedelta(days=120))
html = pupil_client.get("/goal/").content.decode()
tags = bars(html, "progress-bar")
check("every by-paper bar on /goal/ is a labelled progressbar",
      bool(tags) and not unlabelled(tags), f"{len(tags)} bar(s)")
if not had_goal:
    Goal.objects.filter(student=student).delete()

html = tutor_client.get(f"/tutor/student/{student.id}/").content.decode()
tags = bars(html, "progress-bar")
check("every subtopic bar on the tutor page is a labelled progressbar",
      bool(tags) and not unlabelled(tags), f"{len(tags)} bar(s)")
check("the section chart has a text label",
      '<canvas id="sectionChart" role="img" aria-label="Accuracy by section: ' in html)
for i in ("assign-subtopic", "assign-target-count", "assign-due-days"):
    check(f"assign-homework control {i} is labelled", f'for="{i}"' in html and f'id="{i}"' in html)

html = parent_client.get(f"/family/child/{student.id}/").content.decode()
tags = bars(html, "rp-parent__subject-track")
check("the four subject tracks are labelled progressbars", len(tags) == 4 and not unlabelled(tags), f"{len(tags)}")
tags = bars(html, "rp-parent__track")
check("the readiness track, when shown, is a labelled progressbar", not unlabelled(tags), f"{len(tags)}")
html = parent_client.get(f"/family/child/{student.id}/homework/").content.decode()
tags = bars(html, "rp-parent__mini-track")
check("every homework mini-track is a labelled progressbar", not unlabelled(tags), f"{len(tags)}")
check("the homework empty-state glyph is hidden from assistive tech",
      "rp-parent__homework-empty-icon" not in html or 'rp-parent__homework-empty-icon" aria-hidden="true"' in html)
html = parent_client.get(f"/family/child/{student.id}/messages/").content.decode()
check("tutor avatar initial is hidden from assistive tech",
      bool(re.search(r'<span class="rp-parent__tutor-avatar" aria-hidden="true">', html)))

# The mock result page draws a section bar only once something is answered.
from catalog.models import Question, Section
mat = Section.objects.get(code="MAT")
pupil_client.get(reverse("practice:mock_start", args=[mat.id]))
deck = pupil_client.session.get("deck") or {}
first_q = Question.objects.get(pk=deck["qids"][0])
opt = first_q.options.first()
# The answer view marks the deck's current question whatever its kind; a question
# without options (numeric, short text) is answered with free text instead.
pupil_client.post(reverse("practice:answer"),
                  {"option": opt.id, "time_ms": 1500} if opt else {"answer": "1", "time_ms": 1500})
html = pupil_client.get(reverse("practice:mock_result")).content.decode()
tags = bars(html, "progress-bar")
check("every by-section bar on the mock result page is a labelled progressbar",
      bool(tags) and not unlabelled(tags), f"{len(tags)} bar(s)")

print("== app-code dedup: one home for guards, progress, cards, seeding ==")
import accounts.permissions, accounts.views, goals.views, tutoring.permissions, tutoring.views
from django.db import connection
from django.test.utils import CaptureQueriesContext

from analytics.services import subject_cards
from catalog.management.commands.seed_demo import SHOWCASE_EMAIL

check("the old underscore guards are gone from the views modules",
      not any(hasattr(accounts.views, n) for n in ("_owned_child", "_require_parent"))
      and not any(hasattr(tutoring.views, n) for n in ("_owned_student", "_require_tutor", "_owned_link")))
check("accounts.permissions has owned_child and require_parent",
      hasattr(accounts.permissions, "owned_child") and hasattr(accounts.permissions, "require_parent"))
check("tutoring.permissions has require_tutor, owned_link and owned_student",
      all(hasattr(tutoring.permissions, n) for n in ("require_tutor", "owned_link", "owned_student")))
check("goals.views uses tutoring.permissions.owned_student",
      goals.views.owned_student is tutoring.permissions.owned_student)

# with_progress: probe_a's created_at is moved back to the student's earliest attempt on its
# subtopic, so it has done >= 1 against a target of 1; probe_b has a target of 0.
first_attempt = Attempt.objects.filter(student=student).order_by("created_at").first()
probe_a = Assignment.objects.create(
    tutor=tutor, student=student, subtopic_id=first_attempt.subtopic_id,
    target_count=1, due_date=due_in(7))
Assignment.objects.filter(pk=probe_a.pk).update(created_at=first_attempt.created_at)
probe_a.refresh_from_db()
probe_b = Assignment.objects.create(
    tutor=tutor, student=student, subtopic_id=first_attempt.subtopic_id,
    target_count=0, due_date=due_in(7))
with CaptureQueriesContext(connection) as ctx:
    rows = Assignment.with_progress(Assignment.objects.filter(pk__in=[probe_a.pk, probe_b.pk]).order_by("pk"))
by_pk = {a.pk: a for a in rows}
counts = [q for q in ctx.captured_queries if "COUNT(" in q["sql"] and "practice_attempt" in q["sql"]]
check("with_progress returns a list of both assignments", isinstance(rows, list) and len(rows) == 2)
check("with_progress: done >= 1, pct_done capped at 100, status completed",
      by_pk[probe_a.pk].done >= 1 and by_pk[probe_a.pk].pct_done == 100
      and by_pk[probe_a.pk].status == Assignment.Status.COMPLETED,
      f"done {by_pk[probe_a.pk].done}, pct {by_pk[probe_a.pk].pct_done}")
check("with_progress: target_count 0 reads 100% and done is an int",
      by_pk[probe_b.pk].pct_done == 100 and isinstance(by_pk[probe_b.pk].done, int))
check("with_progress issues exactly one attempt COUNT per assignment",
      len(counts) == 2, f"{len(counts)} COUNT(s)")
Assignment.objects.filter(pk__in=[probe_a.pk, probe_b.pk]).delete()

cards = subject_cards(student)
check("subject_cards: four rows, each with chip and key, none with weekly_avg",
      len(cards) == 4 and all("chip" in c and "key" in c and "weekly_avg" not in c for c in cards))
check("subject_cards: chips are EN/MA/VR/NVR and key is the lowercase chip",
      sorted(c["chip"] for c in cards) == ["EN", "MA", "NVR", "VR"]
      and all(c["key"] == c["chip"].lower() for c in cards))


def with_progress_calls(client, url):
    """How many times a GET of `url` goes through Assignment.with_progress."""
    calls = []
    orig = Assignment.with_progress.__func__
    Assignment.with_progress = classmethod(lambda cls, qs: calls.append(1) or orig(cls, qs))
    try:
        client.get(url)
    finally:
        Assignment.with_progress = classmethod(orig)
    return calls


pupil_client = Client(raise_request_exception=False)
pupil_client.force_login(student)
check("the tutor page builds its assignments through with_progress",
      with_progress_calls(tutor_client, f"/tutor/student/{student.id}/") == [1])
check("the pupil dashboard builds its assignments through with_progress",
      with_progress_calls(pupil_client, "/dashboard/") == [1])
check("the parent's child page builds its assignments through with_progress",
      with_progress_calls(parent_client, f"/family/child/{student.id}/") == [1])

# Holds on a DB seeded by this branch (the CI mirror's), not one seeded before it:
# seed_demo now writes the showcase row through apply_subscription.
showcase = User.objects.get(email=SHOWCASE_EMAIL)
showcase_sub = showcase.subscription
check("seeded showcase subscription is ACTIVE, paid by the demo parent, with the demo id",
      showcase_sub.status == Subscription.Status.ACTIVE and showcase_sub.payer_id == parent.id
      and showcase_sub.stripe_subscription_id == "sub_demo_showcase",
      f"{showcase_sub.status}, payer {showcase_sub.payer_id}, {showcase_sub.stripe_subscription_id!r}")
check("every pupil has a Subscription row (C-7)",
      Subscription.objects.filter(user__role="student").count() == User.objects.filter(role="student").count())

print("== launch gates: nickname label and the inactivity purge ==")
import re as _re
from io import StringIO
from django.core.management import call_command
from catalog.models import Question
from goals.models import Goal
from vocab.models import VocabProfile

lp_parent = User.objects.create_user(username="probe_lp", email="probe_purge_parent@example.test",
                                     password="x", role=User.Role.PARENT)
lp_client = Client(raise_request_exception=False)
lp_client.force_login(lp_parent)
lp_html = lp_client.get("/family/").content.decode()
check("the add-child form is labelled Nickname, with the full-name warning",
      ">Nickname<" in lp_html and "Please do not enter your child's full name" in lp_html
      and "Child's name" not in lp_html)

lp_now = timezone.now()
lp_q = Question.objects.filter(is_active=True).first() if hasattr(Question, "is_active") else Question.objects.first()


def lp_pupil(name, joined_days_ago, login_days_ago, attempt_days_ago=None, vocab_days_ago=None,
             status=Subscription.Status.INACTIVE, email=None, parent=None):
    u = User.objects.create(username=f"probe_lp_{name}", role=User.Role.STUDENT, email=email,
                            parent=parent or lp_parent)
    u.set_password("x")
    u.save()
    User.objects.filter(pk=u.pk).update(
        date_joined=lp_now - timedelta(days=joined_days_ago),
        last_login=None if login_days_ago is None else lp_now - timedelta(days=login_days_ago))
    if attempt_days_ago is not None:
        sess = TestSession.objects.create(student=u)
        att = Attempt.objects.create(session=sess, student=u, question=lp_q, subtopic=lp_q.subtopic)
        Attempt.objects.filter(pk=att.pk).update(created_at=lp_now - timedelta(days=attempt_days_ago))
    if vocab_days_ago is not None:
        VocabProfile.objects.create(pupil=u, last_played_on=(lp_now - timedelta(days=vocab_days_ago)).date())
    sub, _ = Subscription.objects.get_or_create(user=u)
    Subscription.objects.filter(pk=sub.pk).update(status=status)
    return User.objects.get(pk=u.pk)


lp_old = lp_pupil("old", 400, 400, 400, 400)
lp_recent = lp_pupil("recent", 400, None, 10)
lp_paid = lp_pupil("paid", 400, 400, 400, 400, status=Subscription.Status.ACTIVE)
lp_young = lp_pupil("young", 5, None)
# Old enough to be selected on activity alone, so only the demo-domain guards keep them out
# (the freshly seeded demo pupils are also protected by date_joined, which would mask a broken guard).
lp_demo_parent = User.objects.create_user(username="probe_lp_demo_parent", email="probe_lp_demo_parent@revisorplus.test",
                                          password="x", role=User.Role.PARENT)
lp_demo_own = lp_pupil("demo_own", 400, 400, 400, email="probe_lp_demo_own@revisorplus.test")
lp_demo_child = lp_pupil("demo_child", 400, 400, 400, parent=lp_demo_parent)
lp_old_id = lp_old.pk

out = StringIO()
call_command("purge_inactive_pupils", days=365, dry_run=True, stdout=out)
lp_text = out.getvalue()
lp_line = next((ln for ln in lp_text.splitlines() if ln.startswith(lp_old.username)), "")
print("   " + lp_line)
check("dry run selects only the 400-day pupil",
      lp_old.username in lp_text and not any(p.username in lp_text for p in (lp_recent, lp_paid, lp_young)))
check("dry run never names a seeded demo pupil, nor an old pupil with a demo-domain email or parent",
      student.username not in lp_text and User.objects.get(email=SHOWCASE_EMAIL).username not in lp_text
      and lp_demo_own.username not in lp_text and lp_demo_child.username not in lp_text)
check("a pupil joined 5 days ago with no activity is not selected", lp_young.username not in lp_text)
check("dry run summary is '1 selected, 0 deleted'",
      "purge_inactive_pupils: 1 selected, 0 deleted" in lp_text, lp_text.splitlines()[-1])
check("dry run deletes nothing", User.objects.filter(pk=lp_old_id).exists())
check("the per-pupil line carries attempts=1 and subscription=1",
      "attempts=1" in lp_line and "subscription=1" in lp_line, lp_line)

out2 = StringIO()
call_command("purge_inactive_pupils", days=365, stdout=out2)
check("live run deletes the old pupil and every row of theirs",
      not User.objects.filter(pk=lp_old_id).exists()
      and not Attempt.objects.filter(student_id=lp_old_id).exists()
      and not TestSession.objects.filter(student_id=lp_old_id).exists()
      and not VocabProfile.objects.filter(pupil_id=lp_old_id).exists()
      and not Subscription.objects.filter(user_id=lp_old_id).exists())
check("live run leaves recent, paid, young and the demo pupils (with their attempts)",
      all(User.objects.filter(pk=p.pk).exists() for p in (lp_recent, lp_paid, lp_young, student))
      and User.objects.filter(email=SHOWCASE_EMAIL).exists()
      and Attempt.objects.filter(student=lp_recent).count() == 1
      and Attempt.objects.filter(student=student).exists())
check("live run summary is '1 selected, 1 deleted'",
      "purge_inactive_pupils: 1 selected, 1 deleted" in out2.getvalue(), out2.getvalue().splitlines()[-1])

out3 = StringIO()
call_command("purge_inactive_pupils", days=7, dry_run=True, stdout=out3)
check("the window is the --days argument (7 days selects recent, not young)",
      lp_recent.username in out3.getvalue() and lp_young.username not in out3.getvalue()
      and lp_paid.username not in out3.getvalue(), out3.getvalue().splitlines()[-1])

from django.core.management.base import CommandError
lp_pupils_before = User.objects.filter(role=User.Role.STUDENT).count()
try:
    call_command("purge_inactive_pupils", days=0, stdout=StringIO())
    lp_refused = False
except CommandError:
    lp_refused = True
check("a live run with --days below 30 is refused and deletes nothing",
      lp_refused and User.objects.filter(role=User.Role.STUDENT).count() == lp_pupils_before
      and all(User.objects.filter(pk=p.pk).exists() for p in (lp_recent, lp_paid, lp_young)))
out4 = StringIO()
call_command("purge_inactive_pupils", days=0, dry_run=True, stdout=out4)
check("--days 0 still runs under --dry-run",
      _re.search(r"^purge_inactive_pupils: \d+ selected, 0 deleted$", out4.getvalue(), _re.M) is not None,
      out4.getvalue().splitlines()[-1])

lp_parent.delete()
lp_demo_parent.delete()
check("probe parent and pupils removed", not User.objects.filter(username__startswith="probe_lp").exists())

Attempt.objects.filter(id__gt=attempt_floor, student=student).delete()
TestSession.objects.filter(id__gt=session_floor, student=student).delete()

print()
print("RESULT: ALL PASSED" if all(results) else f"RESULT: {results.count(False)} FAILED")
