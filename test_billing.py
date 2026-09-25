"""
Checks Phases B and C of the Stripe/entitlements plan (docs/plans/2026-09-16-
stripe-subscriptions-and-google-auth.md): billing/entitlements.py's branches,
the practice cap, the mock gate, the locked panels on the pupil and parent
dashboards (Phase B), and Checkout, the success page, the signed webhook and
the Customer Portal, all against monkeypatched Stripe calls — no real Stripe
key or network call is ever used (Phase C).

Run:  python main.py seed_demo
      python main.py shell < test_billing.py

PREMIUM_GATES_ENABLED is forced on for the whole script — it defaults off in
settings so Phases A and B can deploy without locking anyone out, but every
check here is about what happens once the owner switches it on.

`main.py shell` exits 0 whatever this prints; CI greps for RESULT: ALL PASSED.
"""
import json
from datetime import timedelta

import stripe
from django.conf import settings
from django.contrib.messages import get_messages
from django.test import Client
from django.test.utils import setup_test_environment, teardown_test_environment
from django.urls import reverse
from django.utils import timezone

import billing.views as billing_views

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
from billing.models import StripeEvent, Subscription
from billing.status import plan_status
from billing.stripe_sync import apply_subscription
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

# A pupil under the cap but at/above SIZES[0] (5): the *old* bug was that the
# subject-level slider (default count 10) rendered its normal, uncapped
# branch whenever free_left >= count wasn't true — i.e. whenever free_left
# was, say, 20: below 30 (the top of SIZES) but still bigger than 5, so the
# slider offered 25 and 30 and a pupil could pick more than they had left.
# The fix is client-side JS (choose.html's on-load clamp of the range's max
# and sync()'s Math.min), which this shell script cannot execute — so this
# only asserts the server-rendered half of the fix: the control still carries
# data-free-left even though it's well above the fixed-single-value cutoff,
# which is what the script needs to find and clamp on load.
slider_pupil20 = make_pupil("slider20")
give_attempts(slider_pupil20, ENG, FREE_QUESTIONS_PER_PAPER - 20, tier=Attempt.Tier.FREE)
check("slider_pupil20 has exactly 20 free ENG answers left",
      free_questions_left(slider_pupil20, ENG) == 20, f"got {free_questions_left(slider_pupil20, ENG)}")
sclient20 = Client(raise_request_exception=False)
sclient20.force_login(slider_pupil20)
r = sclient20.get(reverse("practice:choose"))
html = r.content.decode()
check("choose page's ENG control (20 free left, above SIZES[0]) still carries "
      "data-free-left, for the on-load JS clamp to find (JS itself not testable here)",
      'data-free-left="20"' in html)

# ---------------------------------------------------------------------------
print("== the practice-count modal agrees with the cap [C-2] ==")

modal_capped_pupil = make_pupil("modalcap")
give_attempts(modal_capped_pupil, MAT, FREE_QUESTIONS_PER_PAPER - 3, tier=Attempt.Tier.FREE)
check("modal_capped_pupil has exactly 3 free MAT answers left",
      free_questions_left(modal_capped_pupil, MAT) == 3, f"got {free_questions_left(modal_capped_pupil, MAT)}")
mcclient = Client(raise_request_exception=False)
mcclient.force_login(modal_capped_pupil)
r = mcclient.get(reverse("practice:subject_detail", args=["MAT"]))
html = r.content.decode()
check('non-premium, 3 left: #practiceCount has max="3"', 'max="3"' in html)
check("... and the hint reads 1–3 questions", "1–3 questions" in html)

modal_premium_pupil = make_pupil("modalpremium")
mpsub, _ = Subscription.objects.get_or_create(user=modal_premium_pupil)
mpsub.status = Subscription.Status.ACTIVE
mpsub.current_period_end = timezone.now() + timedelta(days=30)
mpsub.save(update_fields=["status", "current_period_end"])
mpclient = Client(raise_request_exception=False)
mpclient.force_login(modal_premium_pupil)
r = mpclient.get(reverse("practice:subject_detail", args=["MAT"]))
html = r.content.decode()
check('premium pupil: #practiceCount has max="40"', 'max="40"' in html)

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
check("... no raw template comment leaked onto the page",
      "{#" not in html and "{% comment" not in html)

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
print("== [Phase C] apply_subscription: the single writer ==")


def sub_fixture(pupil_id, status, period_end_dt, cancel_at_period_end=False,
                 sub_id="sub_fixture_1", parent_id=None, top_level_period_end=False):
    """A plain dict shaped like a Stripe Subscription — everything
    apply_subscription and the webhook handler see is a plain dict, since
    as_dict() converts any real Stripe SDK object (which supports
    __getitem__ but NOT .get(), verified in this venv) at the point it
    leaves the SDK. Puts current_period_end on the item by default (API
    2025+); top_level_period_end=True puts it at the top level instead, for
    the fallback-read check."""
    unix = int(period_end_dt.timestamp()) if period_end_dt else None
    sub = {
        "id": sub_id,
        "status": status,
        "cancel_at_period_end": cancel_at_period_end,
        "metadata": {"pupil_id": str(pupil_id)} if pupil_id else {},
    }
    if parent_id:
        sub["metadata"]["parent_id"] = str(parent_id)
    if top_level_period_end:
        sub["items"] = {"data": []}
        sub["current_period_end"] = unix
    else:
        sub["items"] = {"data": [{"current_period_end": unix}]}
    return sub


apply_pupil = make_pupil("apply")
Subscription.objects.get_or_create(user=apply_pupil)
t0 = timezone.now()

active_fx = sub_fixture(apply_pupil.id, "active", t0 + timedelta(days=30))
row = apply_subscription(active_fx, event_created=t0)
check("in-order: active applied", row.status == Subscription.Status.ACTIVE)

future_end = (t0 + timedelta(days=5)).replace(microsecond=0)
canceled_fx = sub_fixture(apply_pupil.id, "canceled", future_end)
row = apply_subscription(canceled_fx, event_created=t0 + timedelta(seconds=10))
check("in-order: canceled-with-future-period-end applied after active",
      row.status == Subscription.Status.CANCELED and row.current_period_end == future_end)

# Same two fixtures, now posted OUT of order: the older (active) event
# arrives after the newer (canceled) one has already been applied. The row
# must stay canceled — last_event_created wins, not arrival order.
apply_pupil2 = make_pupil("apply2")
Subscription.objects.get_or_create(user=apply_pupil2)
later_created = t0 + timedelta(seconds=10)
earlier_created = t0
canceled_fx2 = sub_fixture(apply_pupil2.id, "canceled", future_end, sub_id="sub_fixture_2")
active_fx2 = sub_fixture(apply_pupil2.id, "active", t0 + timedelta(days=30), sub_id="sub_fixture_2")
apply_subscription(canceled_fx2, event_created=later_created)
row = apply_subscription(active_fx2, event_created=earlier_created)
check("out-of-order: the later-created event wins regardless of arrival order",
      row.status == Subscription.Status.CANCELED, f"got {row.status}")

# No metadata, no matching local row.
orphan_fx = sub_fixture(None, "active", t0 + timedelta(days=30), sub_id="sub_orphan")
result = apply_subscription(orphan_fx, event_created=t0)
check("no pupil_id metadata and no matching row -> None, nothing changed", result is None)

# Top-level current_period_end fallback.
top_end = (t0 + timedelta(days=14)).replace(microsecond=0)
top_fx = sub_fixture(apply_pupil.id, "active", top_end, sub_id="sub_fixture_1",
                      top_level_period_end=True)
row = apply_subscription(top_fx, event_created=t0 + timedelta(seconds=20))
check("period end read from the top-level field when items.data is empty",
      row.current_period_end == top_end, f"got {row.current_period_end}")

# ---------------------------------------------------------------------------
print("== [Phase C] checkout view ==")

settings.STRIPE_SECRET_KEY = ""
settings.STRIPE_PRICE_ID = ""

checkout_pupil = make_pupil("checkout")
Subscription.objects.get_or_create(user=checkout_pupil)

other_parent = User(
    username="probe_other_parent", email="probe_other_parent@revisorplus.test",
    full_name="Other Parent", role=User.Role.PARENT,
)
other_parent.set_password("otherparent12345")
other_parent.save()
created_users.append(other_parent)
other_pupil = make_pupil("other")
other_pupil.parent = other_parent
other_pupil.save(update_fields=["parent"])
Subscription.objects.get_or_create(user=other_pupil)

pupil_client = Client(raise_request_exception=False)
pupil_client.force_login(checkout_pupil)
r = pupil_client.post(reverse("billing:checkout"), {"pupil_id": checkout_pupil.id})
check("pupil POST /billing/checkout/ -> 403", r.status_code == 403, f"status={r.status_code}")

tutor_client = Client(raise_request_exception=False)
tutor_client.force_login(tutor)
r = tutor_client.post(reverse("billing:checkout"), {"pupil_id": checkout_pupil.id})
check("tutor POST /billing/checkout/ -> 403", r.status_code == 403, f"status={r.status_code}")

parent_client = Client(raise_request_exception=False)
parent_client.force_login(parent)
r = parent_client.post(reverse("billing:checkout"), {"pupil_id": other_pupil.id})
check("parent POST for another parent's pupil -> 403", r.status_code == 403, f"status={r.status_code}")

_orig_customer_create = stripe.Customer.create
_orig_session_create = stripe.checkout.Session.create
_customer_create_called = []
_session_create_called = []


def _fake_customer_create(**kwargs):
    _customer_create_called.append(kwargs)
    return {"id": "cus_fake_123"}


def _fake_session_create(**kwargs):
    _session_create_called.append(kwargs)

    class _FakeSession:
        url = "https://checkout.stripe.com/pay/cs_fake_123"
    return _FakeSession()


r = parent_client.post(reverse("billing:checkout"), {"pupil_id": checkout_pupil.id})
check("parent POST with no Stripe keys -> redirected to the child page",
      r.status_code == 302 and r.url == reverse("family:child", args=[checkout_pupil.id]),
      f"status={r.status_code} url={r.url}")
msgs = [str(m) for m in get_messages(r.wsgi_request)]
check("... 'Payments are not configured' is queued",
      any("not configured" in m for m in msgs), f"messages={msgs}")
check("... no Stripe call was made",
      not _customer_create_called and not _session_create_called)

settings.STRIPE_SECRET_KEY = "sk_test_dummy"
settings.STRIPE_PRICE_ID = "price_dummy"
stripe.Customer.create = _fake_customer_create
stripe.checkout.Session.create = _fake_session_create

r = parent_client.post(reverse("billing:checkout"), {"pupil_id": checkout_pupil.id})
check("parent POST with keys set -> 302 to the fake Checkout url",
      r.status_code == 302 and r.url == "https://checkout.stripe.com/pay/cs_fake_123",
      f"status={r.status_code} url={r.url}")
check("... exactly one Session.create call", len(_session_create_called) == 1)
call_kwargs = _session_create_called[0] if _session_create_called else {}
check("... mode is subscription", call_kwargs.get("mode") == "subscription")
check("... price id is passed", call_kwargs.get("line_items") == [{"price": "price_dummy", "quantity": 1}])
check("... subscription metadata carries pupil and parent ids",
      call_kwargs.get("subscription_data", {}).get("metadata")
      == {"pupil_id": str(checkout_pupil.id), "parent_id": str(parent.id)})
check("... client_reference_id is the pupil id",
      call_kwargs.get("client_reference_id") == str(checkout_pupil.id))
parent.refresh_from_db()
check("... the parent's stripe_customer_id was saved",
      parent.stripe_customer_id == "cus_fake_123", f"got {parent.stripe_customer_id!r}")

r = parent_client.post(reverse("billing:checkout"), {"pupil_id": showcase.id})
check("second POST for the already-active showcase pupil is refused",
      r.status_code == 302 and r.url == reverse("family:child", args=[showcase.id]))
msgs = [str(m) for m in get_messages(r.wsgi_request)]
check("... 'already has Premium' is queued", any("already has Premium" in m for m in msgs), f"messages={msgs}")
check("... still exactly one Session.create call overall (no new Stripe call)",
      len(_session_create_called) == 1)

stripe.Customer.create = _orig_customer_create
stripe.checkout.Session.create = _orig_session_create
parent.stripe_customer_id = ""
parent.save(update_fields=["stripe_customer_id"])

# ---------------------------------------------------------------------------
print("== [Phase C] success view ==")

success_pupil = make_pupil("success")
Subscription.objects.get_or_create(user=success_pupil)
parent.stripe_customer_id = "cus_success_parent"
parent.save(update_fields=["stripe_customer_id"])

_orig_session_retrieve = stripe.checkout.Session.retrieve
success_end = (timezone.now() + timedelta(days=30)).replace(microsecond=0)


def _fake_session_retrieve_matching(session_id, expand=None):
    return {
        "customer": "cus_success_parent",
        "client_reference_id": str(success_pupil.id),
        "subscription": sub_fixture(success_pupil.id, "active", success_end,
                                     sub_id="sub_success_1", parent_id=parent.id),
    }


stripe.checkout.Session.retrieve = _fake_session_retrieve_matching
r = parent_client.get(reverse("billing:success") + "?session_id=cs_fake_success")
check("success: matching customer -> 200", r.status_code == 200, f"status={r.status_code}")
success_sub = Subscription.objects.get(user=success_pupil)
check("... the pupil's row flipped to active with the fixture's period end",
      success_sub.status == Subscription.Status.ACTIVE and success_sub.current_period_end == success_end)


def _fake_session_retrieve_foreign(session_id, expand=None):
    return {
        "customer": "cus_someone_else",
        "client_reference_id": str(success_pupil.id),
        "subscription": sub_fixture(success_pupil.id, "canceled", None, sub_id="sub_should_not_apply"),
    }


stripe.checkout.Session.retrieve = _fake_session_retrieve_foreign
before_status = Subscription.objects.get(user=success_pupil).status
r = parent_client.get(reverse("billing:success") + "?session_id=cs_fake_foreign")
check("success: foreign customer -> 403", r.status_code == 403, f"status={r.status_code}")
after_status = Subscription.objects.get(user=success_pupil).status
check("... no row changed", before_status == after_status)

stripe.checkout.Session.retrieve = _orig_session_retrieve
r = parent_client.get(reverse("billing:success"))
check("success: no session_id -> redirected, no row changed",
      r.status_code == 302 and Subscription.objects.get(user=success_pupil).status == after_status)

# ---------------------------------------------------------------------------
print("== [Phase C] signed webhook [C-8] ==")

settings.STRIPE_WEBHOOK_SECRET = "whsec_test_dummy"

if not hasattr(stripe, "WebhookSignature"):
    check("stripe private signing helper still exists", False)


def sign(payload_bytes, secret):
    t = str(int(timezone.now().timestamp()))
    signed_payload = f"{t}.{payload_bytes.decode()}"
    v1 = stripe.WebhookSignature._compute_signature(signed_payload, secret)
    return f"t={t},v1={v1}"


def post_event(event_dict, secret=None):
    payload = json.dumps(event_dict).encode()
    sig = sign(payload, secret if secret is not None else settings.STRIPE_WEBHOOK_SECRET)
    return webhook_client.generic(
        "POST", reverse("billing:webhook"), data=payload,
        content_type="application/json", HTTP_STRIPE_SIGNATURE=sig,
    )


def make_event(event_id, event_type, obj, created):
    # "object": "event" is the envelope discriminator stripe.Webhook.
    # construct_event itself reads (stripe/_webhook.py) before this script's
    # own code ever sees the event — without it, construct_event raises
    # before signature verification even happens.
    return {
        "id": event_id, "object": "event", "type": event_type,
        "created": created, "data": {"object": obj},
    }


webhook_client = Client(raise_request_exception=False)

wh_pupil = make_pupil("webhook")
Subscription.objects.get_or_create(user=wh_pupil)
now_unix = int(timezone.now().timestamp())

active_obj = sub_fixture(wh_pupil.id, "active", timezone.now() + timedelta(days=30), sub_id="sub_wh_1")
event1 = make_event("evt_wh_1", "customer.subscription.updated", active_obj, now_unix)
r = post_event(event1)
check("valid signed customer.subscription.updated -> 200", r.status_code == 200, f"status={r.status_code}")
wh_sub = Subscription.objects.get(user=wh_pupil)
check("... the row was updated", wh_sub.status == Subscription.Status.ACTIVE)
evt_row = StripeEvent.objects.filter(event_id="evt_wh_1").first()
check("... a StripeEvent row exists with processed_at set",
      evt_row is not None and evt_row.processed_at is not None)

# Tampered body: same signature header, one byte changed in the payload.
events_before_tamper = StripeEvent.objects.count()
payload2 = json.dumps(event1).encode()
sig2 = sign(payload2, settings.STRIPE_WEBHOOK_SECRET)
tampered = payload2.replace(b"active", b"activf", 1)
r = webhook_client.generic("POST", reverse("billing:webhook"), data=tampered,
                            content_type="application/json", HTTP_STRIPE_SIGNATURE=sig2)
check("tampered body -> 400", r.status_code == 400, f"status={r.status_code}")
check("... no StripeEvent row was written for the tampered payload",
      StripeEvent.objects.count() == events_before_tamper,
      f"before={events_before_tamper} after={StripeEvent.objects.count()}")

updated_at_before = Subscription.objects.get(user=wh_pupil).updated_at
r = post_event(event1)
check("same event posted twice -> second returns 200", r.status_code == 200, f"status={r.status_code}")
updated_at_after = Subscription.objects.get(user=wh_pupil).updated_at
check("... and changes nothing", updated_at_before == updated_at_after)

# Handler raises -> 500, no processed_at; same event again with the patch
# removed -> 200 and the row updated.
_orig_apply_subscription = billing_views.apply_subscription


def _raising_apply_subscription(*a, **kw):
    raise RuntimeError("probe failure")


billing_views.apply_subscription = _raising_apply_subscription
canceled_obj = sub_fixture(wh_pupil.id, "canceled", None, sub_id="sub_wh_1")
event_fail = make_event("evt_wh_fail", "customer.subscription.updated", canceled_obj, now_unix)
r = post_event(event_fail)
check("handler raising -> 500", r.status_code == 500, f"status={r.status_code}")
check("... no StripeEvent with processed_at for that event id",
      not StripeEvent.objects.filter(event_id="evt_wh_fail", processed_at__isnull=False).exists())

billing_views.apply_subscription = _orig_apply_subscription
r = post_event(event_fail)
check("retry after the patch is removed -> 200", r.status_code == 200, f"status={r.status_code}")
check("... the row was updated on retry",
      Subscription.objects.get(user=wh_pupil).status == Subscription.Status.CANCELED)

# Out-of-order pair: the later-created event (canceled, future period end)
# arrives FIRST, then the earlier-created (active) event arrives second —
# the row must stay canceled.
wh_pupil2 = make_pupil("webhook2")
Subscription.objects.get_or_create(user=wh_pupil2)
later_unix = now_unix + 100
earlier_unix = now_unix
future = timezone.now() + timedelta(days=10)
later_obj = sub_fixture(wh_pupil2.id, "canceled", future, sub_id="sub_wh_2")
earlier_obj = sub_fixture(wh_pupil2.id, "active", timezone.now() + timedelta(days=30), sub_id="sub_wh_2")
post_event(make_event("evt_wh_2_later", "customer.subscription.updated", later_obj, later_unix))
post_event(make_event("evt_wh_2_earlier", "customer.subscription.updated", earlier_obj, earlier_unix))
check("out-of-order webhook pair: the row stays canceled",
      Subscription.objects.get(user=wh_pupil2).status == Subscription.Status.CANCELED)

# invoice.paid with stripe.Subscription.retrieve monkeypatched.
_orig_subscription_retrieve = stripe.Subscription.retrieve
invoice_obj = sub_fixture(wh_pupil.id, "active", timezone.now() + timedelta(days=30), sub_id="sub_wh_invoice")


def _fake_subscription_retrieve(sub_id):
    return invoice_obj


stripe.Subscription.retrieve = _fake_subscription_retrieve
invoice_event = make_event("evt_wh_invoice", "invoice.paid", {"subscription": "sub_wh_invoice"}, now_unix)
r = post_event(invoice_event)
check("invoice.paid (Subscription.retrieve monkeypatched) -> applied",
      r.status_code == 200 and Subscription.objects.get(user=wh_pupil).stripe_subscription_id == "sub_wh_invoice")
stripe.Subscription.retrieve = _orig_subscription_retrieve

# Unknown event type -> 200 and a processed marker, no row touched.
unknown_event = make_event("evt_wh_unknown", "some.unknown.event", {}, now_unix)
r = post_event(unknown_event)
check("unknown event type -> 200", r.status_code == 200, f"status={r.status_code}")
check("... and it's marked processed",
      StripeEvent.objects.filter(event_id="evt_wh_unknown", processed_at__isnull=False).exists())

# ---------------------------------------------------------------------------
print("== [Phase C] Customer Portal ==")

_orig_portal_create = stripe.billing_portal.Session.create


def _fake_portal_create(**kwargs):
    class _FakePortalSession:
        url = "https://billing.stripe.com/session/fake_123"
    return _FakePortalSession()


stripe.billing_portal.Session.create = _fake_portal_create
r = parent_client.post(reverse("billing:portal"))
check("portal: parent POST -> 302 to the fake Portal url",
      r.status_code == 302 and r.url == "https://billing.stripe.com/session/fake_123",
      f"status={r.status_code} url={r.url}")
stripe.billing_portal.Session.create = _orig_portal_create

r = pupil_client.post(reverse("billing:portal"))
check("portal: pupil POST -> 403", r.status_code == 403, f"status={r.status_code}")

parent.stripe_customer_id = ""
parent.save(update_fields=["stripe_customer_id"])
home_html = parent_client.get(reverse("family:home")).content.decode()
check("no customer id: no Manage billing button", reverse("billing:portal") not in home_html)

parent.stripe_customer_id = "cus_success_parent"
parent.save(update_fields=["stripe_customer_id"])
home_html = parent_client.get(reverse("family:home")).content.decode()
check("with a customer id and stripe_ready: the Manage billing button is present",
      reverse("billing:portal") in home_html)
check("family:home with dummy keys: no raw template comment leaked onto the page",
      "{#" not in home_html and "{% comment" not in home_html)

# ---------------------------------------------------------------------------
print("== [Phase C] pricing page ==")

pricing_a = make_pupil("pricinga")
pricing_b = make_pupil("pricingb")
pbsub, _ = Subscription.objects.get_or_create(user=pricing_b)
pbsub.status = Subscription.Status.ACTIVE
pbsub.current_period_end = timezone.now() + timedelta(days=30)
pbsub.save(update_fields=["status", "current_period_end"])

r = parent_client.get(reverse("billing:pricing"))
html = r.content.decode()
check("with keys set: parent with two children (one active) sees exactly one subscribe button",
      html.count('name="pupil_id" value="%s"' % pricing_a.id) == 1
      and html.count('name="pupil_id" value="%s"' % pricing_b.id) == 0,
      f"count_a={html.count('name=\"pupil_id\" value=\"%s\"' % pricing_a.id)}")
check("pricing page with keys set: no raw template comment leaked onto the page",
      "{#" not in html and "{% comment" not in html)

settings.STRIPE_SECRET_KEY = ""
settings.STRIPE_PRICE_ID = ""
r = parent_client.get(reverse("billing:pricing"))
html = r.content.decode()
check("without keys: no subscribe buttons at all", 'name="pupil_id"' not in html)

subs_before = Subscription.objects.filter(user=checkout_pupil).count()
r = pupil_client.get(reverse("billing:pricing"))
check("pupil GET pricing -> 200, no button", r.status_code == 200 and 'name="pupil_id"' not in r.content.decode())
check("... and no new Subscription row was created for the pupil",
      Subscription.objects.filter(user=checkout_pupil).count() == subs_before)

no_children_parent = User(
    username="probe_no_children_parent", email="probe_no_children_parent@revisorplus.test",
    full_name="Probe Parentless", role=User.Role.PARENT,
)
no_children_parent.set_password("probeparent12345")
no_children_parent.save()
created_users.append(no_children_parent)
ncp_client = Client(raise_request_exception=False)
ncp_client.force_login(no_children_parent)
r = ncp_client.get(reverse("billing:pricing"))
check("parent with no children sees 'Add a child first'", "Add a child first" in r.content.decode())

settings.STRIPE_SECRET_KEY = "sk_test_dummy"
settings.STRIPE_PRICE_ID = "price_dummy"

# ---------------------------------------------------------------------------
print("== [Phase C] plan_status and the demand signal on family:home [C-4] ==")

demand_pupil = make_pupil("demand")
give_attempts(demand_pupil, MAT, FREE_QUESTIONS_PER_PAPER, tier=Attempt.Tier.FREE)
dmsub, _ = Subscription.objects.get_or_create(user=demand_pupil)
dmsub.last_mock_blocked_at = timezone.now()
dmsub.save(update_fields=["last_mock_blocked_at"])

r = parent_client.get(reverse("family:home"))
html = r.content.decode()
check("demand child: 'Used all 100 free' line shown", "Used all 100 free Maths answers" in html, )
check("... and the 'Tried a mock paper' line is shown", "Tried a mock paper on" in html)
check("... and exactly one subscribe button for this pupil is shown "
      "(one per child, not one per demand line)",
      html.count(f'name="pupil_id" value="{demand_pupil.id}"') == 1,
      f"count={html.count(f'name=\"pupil_id\" value=\"{demand_pupil.id}\"')}")

pd_sub, _ = Subscription.objects.get_or_create(user=make_pupil("pastdue"))
pd_pupil = pd_sub.user
pd_sub.status = Subscription.Status.PAST_DUE
pd_sub.save(update_fields=["status"])
check("plan_status: past_due -> payment-problem label",
      plan_status(pd_sub) == ("Payment problem, update your card", "warn"))

cw_sub, _ = Subscription.objects.get_or_create(user=make_pupil("cancelwarn"))
cw_sub.status = Subscription.Status.CANCELED
cw_sub.current_period_end = timezone.now() + timedelta(days=9)
cw_sub.save(update_fields=["status", "current_period_end"])
label, kind = plan_status(cw_sub)
check("plan_status: canceled with future period end -> 'Premium until'",
      label.startswith("Premium until") and kind == "ok", f"got {(label, kind)}")

check("plan_status: showcase pupil (active) -> Premium",
      plan_status(showcase.subscription) == ("Premium", "ok"))

# ---------------------------------------------------------------------------
# Cleanup — probe users, their sessions/attempts (cascade) and the Assignment/
# TutorStudent/TutorMessage rows created above, plus settings and the
# parent's stripe_customer_id this script changed at runtime.
TutorMessage.objects.filter(link=tutor_link).delete()
tutor_link.delete()
Assignment.objects.filter(student=child_pupil, tutor=tutor).delete()
for u in created_users:
    User.objects.filter(pk=u.pk).delete()

StripeEvent.objects.filter(event_id__startswith="evt_wh_").delete()
parent.stripe_customer_id = ""
parent.save(update_fields=["stripe_customer_id"])
settings.STRIPE_SECRET_KEY = ""
settings.STRIPE_PRICE_ID = ""
settings.STRIPE_WEBHOOK_SECRET = ""

teardown_test_environment()

print()
print("RESULT: ALL PASSED" if all(results) else f"RESULT: {results.count(False)} FAILED")
