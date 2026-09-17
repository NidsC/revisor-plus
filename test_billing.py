"""
Checks Phase B of the Stripe/entitlements plan (docs/plans/2026-09-16-stripe-
subscriptions-and-google-auth.md): billing/entitlements.py's branches, the
practice cap, the mock gate, and the locked panels on the pupil and parent
dashboards.

Run:  python main.py seed_demo
      python main.py shell < test_billing.py

PREMIUM_GATES_ENABLED is forced on for the whole script — it defaults off in
settings so Phases A and B can deploy without locking anyone out, but every
check here is about what happens once the owner switches it on.

`main.py shell` exits 0 whatever this prints; CI greps for RESULT: ALL PASSED.
"""
from datetime import timedelta

from django.conf import settings
from django.contrib.messages import get_messages
from django.test import Client
from django.test.utils import setup_test_environment, teardown_test_environment
from django.urls import reverse
from django.utils import timezone

# Not running under Django's own test runner, so the template_rendered signal
# django.test.Client relies on for response.context is never connected unless
# this is called explicitly — without it every response.context is None.
setup_test_environment()

from accounts.models import User
from analytics.services import compute_progress
from assignments.models import Assignment
from billing.entitlements import (
    FREE_QUESTIONS_PER_PAPER, free_questions_left, free_questions_used,
    is_premium, practice_allowed,
)
from billing.models import Subscription
from catalog.models import Question, Section, Subtopic
from practice.models import Attempt, TestSession
from tutoring.models import TutorMessage, TutorStudent

results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(("PASS " if ok else "FAIL ") + name + (f" -- {detail}" if detail else ""))


if "testserver" not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS.append("testserver")

settings.PREMIUM_GATES_ENABLED = True

parent = User.objects.get(email="parent@revisorplus.test")
tutor = User.objects.get(email="tutor@revisorplus.test")
# The showcase pupil (seed_demo.SHOWCASE_EMAIL): the one seeded with
# tier="premium" history and an active Subscription.
showcase = User.objects.get(email="nideesh@revisorplus.test")

created_users = []
created_sessions = []


def make_pupil(tag):
    """A fresh, owned probe pupil, no Subscription row yet (free tier)."""
    pupil = User(
        username=f"probe_billing_{tag}", email=None, full_name=f"Probe {tag}",
        role=User.Role.STUDENT, parent=parent,
    )
    pupil.set_password("probeword12345")
    pupil.save()
    created_users.append(pupil)
    return pupil


def _answerable_subtopic(section):
    """A subtopic in `section` with at least one question practice's own
    start() can actually serve — active, not a container part, not
    rubric-marked (mirrors practice.views.answerable())."""
    question = (
        Question.objects.filter(
            subtopic__section=section, active=True, parts__isnull=True,
        )
        .exclude(marking=Question.Marking.RUBRIC)
        .select_related("subtopic")
        .first()
    )
    return question.subtopic, question


def give_attempts(pupil, section, n, tier=Attempt.Tier.FREE, mode=TestSession.Mode.PRACTICE,
                   correct=False):
    subtopic, question = _answerable_subtopic(section)
    session = TestSession.objects.create(student=pupil, subtopic=subtopic, mode=mode)
    created_sessions.append(session)
    rows = [
        Attempt(
            session=session, student=pupil, question=question, subtopic=subtopic,
            is_correct=correct, marks_earned=1 if correct else 0, marks_available=1,
            tier=tier, source=Attempt.Source.PRACTICE,
        )
        for _ in range(n)
    ]
    Attempt.objects.bulk_create(rows)
    return subtopic, question


MAT = Section.objects.get(code="MAT")
ENG = Section.objects.get(code="ENG")

# ---------------------------------------------------------------------------
print("== is_premium branches ==")

flagged_pupil = make_pupil("flag")
settings.PREMIUM_GATES_ENABLED = False
check("flag off: pupil with no Subscription row is Premium for everyone",
      is_premium(flagged_pupil) is True)
settings.PREMIUM_GATES_ENABLED = True

check("no Subscription row: free, no exception", is_premium(flagged_pupil) is False)

sub, _ = Subscription.objects.get_or_create(user=flagged_pupil)
sub.status = Subscription.Status.ACTIVE
sub.save(update_fields=["status"])
check("active: Premium", is_premium(flagged_pupil) is True)

sub.status = Subscription.Status.PAST_DUE
sub.save(update_fields=["status"])
check("past_due: Premium (Smart Retry window)", is_premium(flagged_pupil) is True)

sub.status = Subscription.Status.CANCELED
sub.current_period_end = timezone.now() + timedelta(days=3)
sub.save(update_fields=["status", "current_period_end"])
check("canceled, period end in the future: still Premium", is_premium(flagged_pupil) is True)

sub.current_period_end = timezone.now() - timedelta(days=1)
sub.save(update_fields=["current_period_end"])
check("canceled, period end in the past: free", is_premium(flagged_pupil) is False)

# ---------------------------------------------------------------------------
print("== the free cap is lifetime, not tier-filtered [C-10] ==")

lifetime_pupil = make_pupil("lifetime")
give_attempts(lifetime_pupil, MAT, FREE_QUESTIONS_PER_PAPER, tier=Attempt.Tier.PREMIUM)
check("100 premium-tier attempts, no active subscription -> free_questions_left == 0, not 100",
      free_questions_left(lifetime_pupil, MAT) == 0,
      f"got {free_questions_left(lifetime_pupil, MAT)}")
check("practice_allowed is False once the lifetime cap is used up",
      practice_allowed(lifetime_pupil, MAT) is False)
check("free_questions_used counts the premium-tier rows too",
      free_questions_used(lifetime_pupil, MAT) == FREE_QUESTIONS_PER_PAPER)

# A mock attempt must never count against the cap.
mock_pupil = make_pupil("mockcap")
give_attempts(mock_pupil, MAT, 5, tier=Attempt.Tier.PREMIUM, mode=TestSession.Mode.MOCK)
check("mock attempts don't count toward the free cap",
      free_questions_used(mock_pupil, MAT) == 0, f"got {free_questions_used(mock_pupil, MAT)}")

# ---------------------------------------------------------------------------
print("== compute_progress(student, tier=...) ==")

tier_pupil = make_pupil("tierdata")
give_attempts(tier_pupil, MAT, 6, tier=Attempt.Tier.FREE, correct=True)
give_attempts(tier_pupil, ENG, 4, tier=Attempt.Tier.PREMIUM, correct=False)
free_total = compute_progress(tier_pupil, tier="free")["total"]
check("compute_progress(tier='free')['total'] equals the free-tier row count",
      free_total == 6, f"got {free_total}")
unfiltered = compute_progress(showcase)
check("compute_progress(tier=None) matches the untouched, unfiltered call",
      compute_progress(showcase, tier=None) == unfiltered)
check("compute_progress(tier=None)['total'] equals every attempt on the pupil",
      unfiltered["total"] == Attempt.objects.filter(student=showcase).count())

# ---------------------------------------------------------------------------
print("== the practice cap, through real requests ==")

cap_pupil = make_pupil("cap")
subtopic99, _cap_q = give_attempts(cap_pupil, MAT, 99, tier=Attempt.Tier.FREE)

client = Client(raise_request_exception=False)
client.force_login(cap_pupil)

r = client.get(reverse("practice:start", args=[subtopic99.id]) + "?count=5")
deck = client.session.get("deck")
check("99 attempts in: a ?count=5 request starts a 1-question deck",
      deck is not None and len(deck["qids"]) == 1, f"deck={deck}")

# Finish that deck so its TestSession is no longer "in progress" for the next
# start(), then top the pupil up to exactly the cap.
client.session.pop("deck", None)
client.session.save()
give_attempts(cap_pupil, MAT, 1, tier=Attempt.Tier.FREE)  # now at 100

sessions_before = TestSession.objects.filter(student=cap_pupil).count()
r = client.get(reverse("practice:start", args=[subtopic99.id]) + "?count=1")
check("at 100: start() redirects to choose with the cap message",
      r.status_code == 302 and r.url == reverse("practice:choose"), f"status={r.status_code} url={r.url}")
msgs = [str(m) for m in get_messages(r.wsgi_request)]
check("... and the cap message is queued", any("free" in m.lower() for m in msgs), f"messages={msgs}")
check("... no new TestSession was created",
      TestSession.objects.filter(student=cap_pupil).count() == sessions_before)

r = client.get(reverse("practice:start_subject", args=["MAT"]) + "?count=1")
check("at 100: start_subject() also redirects to choose",
      r.status_code == 302 and r.url == reverse("practice:choose"))

# answer() belt-and-braces: start a deck just under the cap, then let another
# tab use up the last free answer before this one is submitted.
cap_pupil2 = make_pupil("cap2")
give_attempts(cap_pupil2, MAT, 99, tier=Attempt.Tier.FREE)
client2 = Client(raise_request_exception=False)
client2.force_login(cap_pupil2)
r = client2.get(reverse("practice:start", args=[subtopic99.id]) + "?count=1")
deck2 = client2.session.get("deck")
check("cap_pupil2 got a 1-question deck at 99/100", deck2 is not None and len(deck2["qids"]) == 1)

give_attempts(cap_pupil2, MAT, 1, tier=Attempt.Tier.FREE)  # now at 100, deck already open

question_obj = Question.objects.get(pk=deck2["qids"][0])
option = question_obj.options.filter(is_correct=True).first() or question_obj.options.first()
attempts_before = Attempt.objects.filter(session_id=deck2["session_id"]).count()
r = client2.post(reverse("practice:answer"), {"qid": question_obj.id, "option": option.id if option else ""})
check("answer() refuses the 101st: redirects to summary",
      r.status_code == 302 and r.url == reverse("practice:summary"), f"status={r.status_code} url={r.url}")
check("... and no Attempt was created for that submission",
      Attempt.objects.filter(session_id=deck2["session_id"]).count() == attempts_before)

# ---------------------------------------------------------------------------
print("== the deck-size slider agrees with the cap [C-2] ==")

slider_pupil = make_pupil("slider")
give_attempts(slider_pupil, ENG, FREE_QUESTIONS_PER_PAPER - 3, tier=Attempt.Tier.FREE)
check("slider_pupil has exactly 3 free ENG answers left",
      free_questions_left(slider_pupil, ENG) == 3, f"got {free_questions_left(slider_pupil, ENG)}")
sclient = Client(raise_request_exception=False)
sclient.force_login(slider_pupil)
r = sclient.get(reverse("practice:choose"))
html = r.content.decode()
check("choose page's ENG slider is capped: shows the 3-free-left label",
      "free left" in html and 'data-free-left="3"' in html)
check("... and the label reads 3 questions, not the default 10",
      "3 question" in html)

# ---------------------------------------------------------------------------
print("== mock gate ==")

mock_free_pupil = make_pupil("mockfree")
Subscription.objects.get_or_create(user=mock_free_pupil)  # every real pupil has one (add_child)
mclient = Client(raise_request_exception=False)
mclient.force_login(mock_free_pupil)

r = mclient.get(reverse("practice:mock_start", args=[MAT.id]))
check("non-premium GET /mocks/start/<id>/ -> 302 to /mocks/",
      r.status_code == 302 and r.url == reverse("practice:mock_choose"))
check("... no TestSession was created",
      not TestSession.objects.filter(student=mock_free_pupil, mode=TestSession.Mode.MOCK).exists())
mock_sub = Subscription.objects.get(user=mock_free_pupil)
check("... last_mock_blocked_at was stamped", mock_sub.last_mock_blocked_at is not None)

r = mclient.get(reverse("practice:mock_start_targeted"))
check("non-premium GET /mocks/targeted/ -> 302 to /mocks/",
      r.status_code == 302 and r.url == reverse("practice:mock_choose"))
check("... still no TestSession",
      not TestSession.objects.filter(student=mock_free_pupil, mode=TestSession.Mode.MOCK).exists())

mock_premium_pupil = make_pupil("mockpremium")
psub, _ = Subscription.objects.get_or_create(user=mock_premium_pupil)
psub.status = Subscription.Status.ACTIVE
psub.current_period_end = timezone.now() + timedelta(days=30)
psub.save(update_fields=["status", "current_period_end"])
pclient = Client(raise_request_exception=False)
pclient.force_login(mock_premium_pupil)
r = pclient.get(reverse("practice:mock_start", args=[MAT.id]))
check("premium pupil GET /mocks/start/<id>/ -> 302 to /practice/question/",
      r.status_code == 302 and r.url == reverse("practice:question"), f"status={r.status_code} url={r.url}")

r = mclient.get(reverse("practice:mock_choose"))
html = r.content.decode()
check("/mocks/ for a non-premium pupil has the locked marker",
      "data-rp-locked" in html)
check("... and no /mocks/start/ links",
      "/mocks/start/" not in html)

r = pclient.get(reverse("practice:mock_choose"))
html = r.content.decode()
check("/mocks/ for a premium pupil has no locked marker",
      "data-rp-locked" not in html)
check("... and does have /mocks/start/ links",
      "/mocks/start/" in html)

# ---------------------------------------------------------------------------
print("== pupil dashboard: free-tier charts and the locked focus teaser ==")

dash_pupil = make_pupil("dash")
weak_subtopic, _q = give_attempts(dash_pupil, MAT, 10, tier=Attempt.Tier.FREE, correct=False)
give_attempts(dash_pupil, ENG, 10, tier=Attempt.Tier.PREMIUM, correct=True)

dclient = Client(raise_request_exception=False)
dclient.force_login(dash_pupil)
r = dclient.get(reverse("practice:dashboard"))
html = r.content.decode()
expected_free = compute_progress(dash_pupil, tier="free")
check("non-premium dashboard chart data equals compute_progress(tier='free')",
      r.context["data"]["total"] == expected_free["total"]
      and r.context["data"]["overall"] == expected_free["overall"],
      f"got total={r.context['data']['total']} want={expected_free['total']}")
check("... has the locked focus marker", "data-rp-locked" in html)
check("... no 'Worth some practice' rows", "Worth some practice" not in html)
check("... suggested_topics is empty", r.context["suggested_topics"] == [])

dsub, _ = Subscription.objects.get_or_create(user=dash_pupil)
dsub.status = Subscription.Status.ACTIVE
dsub.current_period_end = timezone.now() + timedelta(days=30)
dsub.save(update_fields=["status", "current_period_end"])

r = dclient.get(reverse("practice:dashboard"))
html = r.content.decode()
expected_full = compute_progress(dash_pupil)
check("premium dashboard chart data equals the unfiltered compute_progress",
      r.context["data"]["total"] == expected_full["total"], f"got {r.context['data']['total']}")
check("... suggested rows are back (a weak MAT topic exists)",
      len(r.context["suggested_topics"]) > 0, f"suggested={r.context['suggested_topics']}")

# ---------------------------------------------------------------------------
print("== parent's child page: locked panel vs full focus markup ==")

child_pupil = make_pupil("child")
give_attempts(child_pupil, MAT, 10, tier=Attempt.Tier.FREE, correct=False)
tutor_link = TutorStudent.objects.create(tutor=tutor, student=child_pupil, active=True)
TutorMessage.objects.create(link=tutor_link, sender=tutor, body="Probe tutor message for test_billing.")
hw_subtopic = Subtopic.objects.filter(section=ENG, questions__active=True).first()
Assignment.objects.create(
    tutor=tutor, student=child_pupil, subtopic=hw_subtopic,
    target_count=5, due_date=timezone.localdate() + timedelta(days=7),
)

pcclient = Client(raise_request_exception=False)
pcclient.force_login(parent)
r = pcclient.get(reverse("family:child", args=[child_pupil.id]))
html = r.content.decode()
check("non-premium child page: 200", r.status_code == 200)
check("... has the locked panel marker", "data-rp-locked" in html)
check("... links to /billing/", reverse("billing:pricing") in html)
check("... no focus-primary / per-subject breakdown markup",
      "rp-parent__focus-primary" not in html and "rp-parent__subject-block" not in html)
check("... homework markup is present", hw_subtopic.name in html)
check("... tutor chat markup is present", "Probe tutor message for test_billing." in html)

csub, _ = Subscription.objects.get_or_create(user=child_pupil)
csub.status = Subscription.Status.ACTIVE
csub.current_period_end = timezone.now() + timedelta(days=30)
csub.save(update_fields=["status", "current_period_end"])

r = pcclient.get(reverse("family:child", args=[child_pupil.id]))
html = r.content.decode()
check("premium child page: focus markup is present",
      "rp-parent__focus-primary" in html or "rp-parent__subject-block" in html)
check("... homework markup is still present", hw_subtopic.name in html)
check("... tutor chat markup is still present", "Probe tutor message for test_billing." in html)

# ---------------------------------------------------------------------------
# Cleanup — probe users, their sessions/attempts (cascade) and the Assignment/
# TutorStudent/TutorMessage rows created above.
TutorMessage.objects.filter(link=tutor_link).delete()
tutor_link.delete()
Assignment.objects.filter(student=child_pupil, tutor=tutor).delete()
for u in created_users:
    User.objects.filter(pk=u.pk).delete()

teardown_test_environment()

print()
print("RESULT: ALL PASSED" if all(results) else f"RESULT: {results.count(False)} FAILED")
