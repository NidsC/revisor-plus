import random
from datetime import timedelta

from urllib.parse import urlparse

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from analytics.readiness import compute_readiness
from analytics.services import compute_coverage, compute_progress, compute_subject_summary
from assignments.models import Assignment
from billing.entitlements import (
    FREE_QUESTIONS_PER_PAPER, free_questions_left, is_premium, practice_allowed,
)
from billing.models import Subscription
from catalog.marking import Result, mark
from catalog.models import AnswerOption, Question, Section, Subtopic

from .models import Attempt, TestSession


def was_correct(entry):
    """Read one `deck["answered"]` entry.

    Entries became dicts when answers were made idempotent, but decks live in the
    session and in TestSession.deck_state, so paused decks written before that
    change are still out there carrying bare booleans. Tolerating both costs a
    line and avoids a 500 on resume after deploy.
    """
    return bool(entry.get("correct")) if isinstance(entry, dict) else bool(entry)


def answerable(subtopic):
    """Questions a pupil can actually be asked, and that we can actually mark.

    Excludes two things that would otherwise land in a deck as dead ends:
      - containers. A multi-part paper question is stored as a parent carrying the
        shared stem plus a child per part. Only the children are answerable.
      - rubric-marked items. A 4-mark "what impression do you get of Mr Ashby"
        cannot be marked by the engine, so serving it in self-study practice would
        take an answer and then have nothing to say about it.
    """
    return Question.objects.filter(
        subtopic=subtopic, active=True, parts__isnull=True
    ).exclude(marking=Question.Marking.RUBRIC)


# One mock per paper. Lengths are cut down from a real sitting (English is 60
# minutes, Maths 45) so a pupil can finish one in an evening, but they are long
# enough that the clock is the point.
#   code: (questions, minutes)
MOCK_PAPERS = {"ENG": (20, 30), "MAT": (25, 35), "VR": (25, 25), "NVR": (20, 25)}


def paper_questions(section):
    """The pool a mock draws from — deliberately NOT answerable().

    A mock is a whole paper, so it includes the written questions that only a
    person can mark. Practice excludes those because self-study needs an answer
    back immediately; a mock does not, and leaving them out would misrepresent
    what sitting the paper is actually like. Containers stay excluded either way,
    since only their parts carry an answer.
    """
    return Question.objects.filter(
        subtopic__section=section, active=True, parts__isnull=True
    ).select_related("subtopic")


def build_paper(section, count, rng=random):
    """Pick `count` questions spread across the paper, easiest first.

    Stratified rather than a flat random sample: Maths holds 8,350 questions but
    they are not evenly spread across its eight subtopics, so sampling the pool
    directly would hand a pupil a paper that is mostly place value. Round-robin
    across subtopics covers the syllabus the way a real paper does. Ordering by
    difficulty then gives the ramp a paper normally has.
    """
    by_sub = {}
    for q in paper_questions(section):
        by_sub.setdefault(q.subtopic_id, []).append(q)
    for pool in by_sub.values():
        rng.shuffle(pool)

    picked, subs = [], list(by_sub)
    rng.shuffle(subs)
    while len(picked) < count and any(by_sub[s] for s in subs):
        for s in subs:
            if by_sub[s] and len(picked) < count:
                picked.append(by_sub[s].pop())
    picked.sort(key=lambda q: (q.difficulty, q.id))
    return [q.id for q in picked]


# A paper built from the pupil's own record. NOT the Elo engine: there is no
# ability estimate and nothing updates mid-paper. What it does is real, though —
# it reads measured per-subtopic accuracy and changes both WHICH subtopics appear
# and HOW HARD the questions are. It re-reads that record every time a paper is
# built, so it shifts as the pupil shifts. Describe it as targeted, not as
# learning.
TARGETED_MINUTES = 30
TARGETED_QUESTIONS = 20
# Share of the paper drawn from the weakest areas; the rest keeps everything else
# ticking over, because a paper that only ever drills weaknesses stops being a
# paper and the pupil's strong topics quietly rot.
FOCUS_SHARE = 0.7
FOCUS_SUBTOPICS = 5
# Minimum answered questions before a subtopic's accuracy is trusted enough to
# steer the paper. Same floor the dashboard's weakness panel uses — below this a
# single unlucky run reads as a weakness.
EVIDENCE_FLOOR = 8


def target_difficulty(accuracy):
    """Pitch a question band just above demonstrated level.

    Slightly above, not at: the point is to stretch. A pupil at 54% gets band 2,
    where they should get most right but not all; one at 92% gets band 5.
    """
    if accuracy is None:
        return 3
    if accuracy < 45:
        return 1
    if accuracy < 60:
        return 2
    if accuracy < 75:
        return 3
    if accuracy < 88:
        return 4
    return 5


def weakness_profile(student, progress=None):
    """Per-subtopic accuracy with enough evidence behind it to act on."""
    progress = progress or compute_progress(student)
    rows = [s for s in progress["subtopics"] if s["total"] >= EVIDENCE_FLOOR]
    return sorted(rows, key=lambda s: s["accuracy"])


def build_targeted_paper(student, count=TARGETED_QUESTIONS, rng=random, progress=None):
    """(question ids, explanation rows) for a paper aimed at this pupil.

    Returns the reasoning alongside the questions so the UI can show WHY each
    subtopic is there — an opaque "personalised" paper is indistinguishable from
    a random one, and the pupil should be able to check our working.
    """
    rows = weakness_profile(student, progress)
    if not rows:
        return [], []

    focus = rows[:FOCUS_SUBTOPICS]
    rest = rows[FOCUS_SUBTOPICS:]
    n_focus = round(count * FOCUS_SHARE)

    # Weight by how far below 100% each area sits, so the weakest gets the most.
    weights = [max(5, 100 - s["accuracy"]) for s in focus]
    total_w = sum(weights) or 1
    plan = []
    for s, w in zip(focus, weights):
        plan.append([s, max(1, round(n_focus * w / total_w)), "weakest areas"])
    for s in rest[:count - n_focus]:
        plan.append([s, 1, "keeping the rest ticking over"])

    picked, explain = [], []
    for row, want, why in plan:
        if len(picked) >= count:
            break
        want = min(want, count - len(picked))
        band = target_difficulty(row["accuracy"])
        pool = []
        # Widen the band until there are enough questions: a thin subtopic
        # (Analogies has 29) simply may not hold `want` questions at one level.
        for spread in (0, 1, 2, 4):
            lo, hi = band - spread, band + spread
            pool = list(
                Question.objects.filter(
                    subtopic_id=row["id"], active=True, parts__isnull=True,
                    difficulty__gte=lo, difficulty__lte=hi,
                ).exclude(marking=Question.Marking.RUBRIC)
                .exclude(id__in=picked).values_list("id", flat=True)
            )
            if len(pool) >= want:
                break
        if not pool:
            continue
        rng.shuffle(pool)
        chosen = pool[:want]
        picked.extend(chosen)
        explain.append({
            "name": row["name"], "code": row["section"],
            "accuracy": row["accuracy"], "count": len(chosen),
            "band": band, "why": why,
        })

    # Easiest first, so the paper ramps the way a real one does.
    order = {q.id: q.difficulty for q in Question.objects.filter(id__in=picked)}
    picked.sort(key=lambda qid: (order.get(qid, 3), qid))
    return picked, explain


def _deck_deadline(deck):
    """Seconds left on a timed paper, or None if this deck is not timed."""
    if not deck.get("ends_at"):
        return None
    from django.utils.dateparse import parse_datetime

    ends = parse_datetime(deck["ends_at"])
    return int((ends - timezone.now()).total_seconds()) if ends else None


def _park_deck(request):
    """Persist the in-progress deck to its TestSession so it can be resumed later."""
    deck = request.session.pop("deck", None)
    if deck:
        TestSession.objects.filter(pk=deck["session_id"], student=request.user).update(deck_state=deck)


@login_required
def dashboard(request):
    premium = is_premium(request.user)
    # A non-premium pupil's charts and stat tiles are drawn only from their
    # free-tier activity — their Premium-era history, if any, comes back if
    # Premium does, but it isn't shown while lapsed (see Attempt.tier's
    # docstring and the plan's "Lapsed pupil's charts" edge case).
    data = compute_progress(request.user) if premium else compute_progress(request.user, tier="free")

    # Full section name for a `data["weak"]` entry's code (e.g. "MAT" -> "Maths"),
    # so the mission/topics panels can show a readable subject label without a
    # second query — `data["sections"]` already carries it.
    section_names = {s["code"]: s["name"] for s in data["sections"]}
    for w in data["weak"]:
        w["section_name"] = section_names.get(w["section"], w["section"])

    assignments = Assignment.objects.filter(student=request.user).select_related(
        "subtopic", "subtopic__section"
    )
    for a in assignments:
        a.refresh_status()
        a.done = a.progress_count()
        a.pct_done = min(100, round(100 * a.done / a.target_count)) if a.target_count else 100
    # "Waiting"/"left" language throughout the template means pending, not total —
    # completed homework shouldn't still count as something left to do.
    pending_assignments = [a for a in assignments if a.status == Assignment.Status.ASSIGNED]

    # The Today list merges homework with suggested topics, so the same subtopic
    # could appear twice — as a tutor task and again as a suggestion. Set
    # difference on subtopic id. `data["weak"]` itself is left alone: the parent
    # summary tab names the top two weaknesses from it, homework or not.
    homework_subtopic_ids = {a.subtopic_id for a in pending_assignments}
    # Focus-areas targeting is Premium (step 19): a non-premium pupil gets no
    # suggested rows here — the template renders a single locked teaser row
    # in their place — regardless of what data["weak"] (computed on free-tier
    # activity only, above) would otherwise suggest.
    suggested_topics = (
        [w for w in data["weak"] if w["id"] not in homework_subtopic_ids] if premium else []
    )

    paused = TestSession.objects.filter(
        student=request.user, finished_at__isnull=True, deck_state__isnull=False
    ).select_related("subtopic", "subtopic__section").order_by("-started_at")

    # The resume panel names what is half-finished and how far in the pupil got.
    # The position lives in the parked deck, not on the row.
    resume = None
    if paused:
        session = paused[0]
        deck = session.deck_state or {}
        done, total = deck.get("idx") or 0, len(deck.get("qids") or [])
        resume = {
            "id": session.id,
            "name": session.subtopic.name if session.subtopic else deck.get("paper", "Practice"),
            "section": session.subtopic.section.name if session.subtopic else "Mock paper",
            "done": done,
            "total": total,
        }

    # Mock papers, one row per paper. A mock TestSession carries no section — it
    # is created with subtopic=None — so the papers a pupil has sat are found
    # through the attempts those sessions produced.
    sat = dict(
        Attempt.objects.filter(
            student=request.user,
            session__mode=TestSession.Mode.MOCK,
            session__finished_at__isnull=False,
        ).values_list("subtopic__section_id").annotate(last=Max("session__finished_at"))
    )
    mock_papers = [
        {"section": section, "sat_on": sat.get(section.id)}
        for section in Section.objects.order_by("order")
    ]

    # Reuse the progress we already computed rather than querying twice.
    readiness = compute_readiness(request.user, progress=data)

    # The mockup's chips read EN / MA / VR / NVR; the Section codes are
    # ENG / MAT / VR / NVR. Mapped here rather than sliced in the template,
    # where NVR would come out as "NV".
    chip_codes = {"ENG": "EN", "MAT": "MA", "VR": "VR", "NVR": "NVR"}
    subjects = [
        dict({k: v for k, v in s.items() if k != "weekly_avg"},
             chip=chip_codes.get(s["code"], s["code"]),
             key=chip_codes.get(s["code"], s["code"]).lower())
        for s in compute_subject_summary(request.user)
    ]

    return render(request, "practice/dashboard.html", {
        "data": data, "assignments": assignments, "paused": paused,
        "pending_assignments": pending_assignments,
        "homework_count": len(pending_assignments),
        "suggested_topics": suggested_topics,
        "premium": premium,
        "section_by_code": {s["code"]: s for s in data["sections"]},
        "readiness": readiness,
        "subjects": subjects,
        "resume": resume,
        "mock_papers": mock_papers,
        # Back in the header: the target's subline is "18 of 4,185 questions
        # attempted", the same distinct-answerable pair the rows carry per
        # subject.
        "coverage": compute_coverage(request.user),
    })


# The question bank page states what each subject covers above its subtopics.
# Section carries no blurb field and doesn't want one — this is presentational
# copy for a single page, not taxonomy, and taxonomy.json is the only thing
# allowed to describe the syllabus.
SUBJECT_BLURBS = {
    "ENG": "Comprehension, grammar and vocabulary.",
    "MAT": "Number, shape, measure and reasoning.",
    "VR": "Words, letters, codes and logic.",
    "NVR": "Shapes, patterns and spatial puzzles.",
}


@login_required
def choose(request):
    """The question bank: every subject, its areas, and each area's topics.

    Three levels, matching docs/question-bank-target.html — subject, then the
    taxonomy's topic as an "area", then the subtopics inside it. Counts are
    answerable questions — the same filter `answerable()` uses — so the number
    on a row is the number a pupil can actually be asked, and one grouped query
    covers the whole bank rather than a count per subtopic.
    """
    totals_by_subtopic = dict(
        Question.objects.filter(active=True, parts__isnull=True)
        .exclude(marking=Question.Marking.RUBRIC)
        .values("subtopic_id").annotate(n=Count("id")).values_list("subtopic_id", "n")
    )

    # topic_order then order, so the group headings come out in the order the
    # taxonomy states rather than alphabetically. dicts keep insertion order,
    # which is what carries that ordering through to the template.
    grouped = {}
    for st in Subtopic.objects.order_by("section__order", "topic_order", "order"):
        groups = grouped.setdefault(st.section_id, {})
        groups.setdefault(st.topic or "Other", []).append({
            "id": st.id,
            "name": st.name,
            "total": totals_by_subtopic.get(st.id, 0),
        })

    premium = is_premium(request.user)
    subjects = []
    for section in Section.objects.order_by("order"):
        groups = grouped.get(section.id, {})
        areas = [
            {
                "name": name,
                "subtopics": rows,
                # Both numbers go in the area card's pill.
                "count": len(rows),
                "total": sum(row["total"] for row in rows),
            }
            for name, rows in groups.items()
        ]
        # None for a premium pupil — the slider and the cards show no cap.
        # For a non-premium pupil it's the number of free answers left in
        # this paper, which the deck-size slider (_qbank_controls.html) uses
        # to cut its offered sizes so what it offers agrees with the cap.
        free_left = None if premium else free_questions_left(request.user, section)
        subjects.append({
            "code": section.code,
            "slug": section.code.lower(),
            "name": section.name,
            "blurb": SUBJECT_BLURBS.get(section.code, ""),
            "total": sum(area["total"] for area in areas),
            "groups": areas,
            "free_left": free_left,
        })

    return render(request, "practice/choose.html", {
        "subjects": subjects, "premium": premium, "free_cap": FREE_QUESTIONS_PER_PAPER,
    })


@login_required
def subject_detail(request, code):
    section = get_object_or_404(Section, code=code.upper())
    progress = compute_progress(request.user)
    perf_by_subtopic = {s["id"]: s for s in progress["subtopics"]}

    # One grouped query for every subtopic's answerable count, instead of the
    # answerable(st).count() N+1 this used to run per subtopic (same filter as
    # answerable(), just grouped by subtopic rather than issued once per row).
    totals_by_subtopic = dict(
        Question.objects.filter(subtopic__section=section, active=True, parts__isnull=True)
        .exclude(marking=Question.Marking.RUBRIC)
        .values("subtopic_id").annotate(n=Count("id")).values_list("subtopic_id", "n")
    )

    subtopics = []
    for st in Subtopic.objects.filter(section=section):
        perf = perf_by_subtopic.get(st.id)
        subtopics.append({
            "id": st.id,
            "name": st.name,
            "topic": st.topic,
            "total": totals_by_subtopic.get(st.id, 0),
            "attempted": perf["total"] if perf else 0,
            "correct": perf["correct"] if perf else 0,
            "accuracy": perf["accuracy"] if perf else None,
        })

    summary = next(
        (s for s in compute_subject_summary(request.user) if s["code"] == section.code), None
    )

    premium = is_premium(request.user)
    free_left = None if premium else free_questions_left(request.user, section)
    # The practiceModal's number input agrees with the cap the same way the
    # question-bank slider does [C-2]: capped at the smaller of the usual
    # ceiling and what's actually left, so a non-premium pupil can never type
    # a number the server would then clamp down anyway.
    deck_max = MAX_PRACTICE_QUESTIONS if premium else min(MAX_PRACTICE_QUESTIONS, free_left)

    # "Back" should return the pupil to wherever they actually came from (e.g.
    # /practice/ or /dashboard/), not always to the dashboard. Only trust the
    # referrer when it resolves to this same site — never redirect off-site —
    # otherwise fall back to the dashboard as before. Label stays the specific
    # "Back to dashboard" only when that's genuinely where we're sending them;
    # any other internal origin gets the generic "Back" since we don't know
    # what page it names.
    dashboard_url = reverse("practice:dashboard")
    back_url = dashboard_url
    back_label = "‹ Back to dashboard"
    referer = request.META.get("HTTP_REFERER")
    if referer and url_has_allowed_host_and_scheme(
        referer, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        back_url = referer
        if urlparse(referer).path != dashboard_url:
            back_label = "‹ Back"

    return render(request, "practice/subject.html", {
        "section": section, "subtopics": subtopics, "summary": summary,
        "back_url": back_url, "back_label": back_label,
        "premium": premium, "free_left": free_left, "free_cap": FREE_QUESTIONS_PER_PAPER,
        "deck_max": deck_max,
    })


# Reasonable floor/ceiling on a pupil-chosen deck size, applied server-side
# regardless of what the client sent — the modal's own input mirrors this range
# (min="1" max="40"), but a crafted request bypassing the modal can still send
# anything, so this clamp is the actual enforcement.
MIN_PRACTICE_QUESTIONS = 1
MAX_PRACTICE_QUESTIONS = 40
DEFAULT_PRACTICE_QUESTIONS = 5


def _requested_count(request):
    """The pupil's chosen deck size, clamped. Shared by the subtopic and
    whole-subject starts so one crafted `?count=` can't slip past either."""
    try:
        count = int(request.GET.get("count", DEFAULT_PRACTICE_QUESTIONS))
    except (TypeError, ValueError):
        count = DEFAULT_PRACTICE_QUESTIONS
    return max(MIN_PRACTICE_QUESTIONS, min(count, MAX_PRACTICE_QUESTIONS))


def _free_cap_message(section):
    return (
        f"You've used your {FREE_QUESTIONS_PER_PAPER} free {section.name} questions. "
        "Ask your parent about Premium to keep practising."
    )


def _cap_deck_size(request, section, count):
    """Clamp a non-premium pupil's requested deck size to what's left of the
    free cap in this paper, or refuse to start at all once it's used up.
    Shared by start() and start_subject() so a deck never crosses the cap
    regardless of which one a pupil hit.

    Returns (count, redirect_response). `redirect_response` is None when the
    caller should go ahead and start a deck of the returned size.
    """
    if is_premium(request.user):
        return count, None
    if not practice_allowed(request.user, section):
        messages.info(request, _free_cap_message(section))
        return count, redirect("practice:choose")
    return min(count, free_questions_left(request.user, section)), None


def _mock_gate(request):
    """Refuse a mock paper to a non-premium pupil, and record the demand
    signal a parent's home page reads (last_mock_blocked_at). Shared by
    mock_start and mock_start_targeted so the two agree on how a blocked
    pupil is turned away."""
    if is_premium(request.user):
        return None
    Subscription.objects.filter(user=request.user).update(last_mock_blocked_at=timezone.now())
    messages.info(request, "Ask your parent to unlock mock papers.")
    return redirect("practice:mock_choose")


@login_required
def start(request, subtopic_id):
    _park_deck(request)  # don't destroy an in-progress deck — park it so it stays resumable
    subtopic = get_object_or_404(Subtopic, pk=subtopic_id)
    count = _requested_count(request)
    count, blocked = _cap_deck_size(request, subtopic.section, count)
    if blocked:
        return blocked
    qids = list(answerable(subtopic).values_list("id", flat=True))
    if not qids:
        # Nothing to answer — don't create a session that can only end 0/0.
        # The subject page hides/disables the Practice button for this case,
        # but this guard also covers a stale link, back-button, or a modal
        # start-url hit with a mistaken subtopic id.
        messages.info(
            request,
            f"There aren't any {subtopic.name} questions to practise yet — check back soon."
        )
        return redirect("practice:subject_detail", code=subtopic.section.code)
    random.shuffle(qids)
    qids = qids[:count]
    while qids and len(qids) < count:
        qids.append(random.choice(qids))  # top up short decks so practice feels full
    mode = "test" if request.GET.get("mode") == "test" else "practice"
    session = TestSession.objects.create(
        student=request.user, subtopic=subtopic, mode=mode,
        time_limit_seconds=90 if mode == "test" else 0,
    )
    request.session["deck"] = {
        "session_id": session.id, "subtopic_id": subtopic.id,
        "qids": qids, "idx": 0, "answered": [], "mode": mode,
    }
    return redirect("practice:question")


@login_required
def start_subject(request, code):
    """Practise a whole subject — a deck drawn from across its subtopics.

    The deck carries `subtopic_id: None` and a `section_id`, the shape
    mock_start already uses; TestSession.subtopic is nullable, each Attempt
    records the question's own subtopic, and summary tolerates a null subtopic,
    so a mixed deck lands in analytics exactly like a single-subtopic one.
    Sampling goes through build_paper() so the deck is spread across the
    subject's subtopics rather than dominated by whichever one is largest.
    """
    _park_deck(request)
    section = get_object_or_404(Section, code=code.upper())
    count = _requested_count(request)
    count, blocked = _cap_deck_size(request, section, count)
    if blocked:
        return blocked
    qids = build_paper(section, count)
    if not qids:
        messages.info(
            request,
            f"There aren't any {section.name} questions to practise yet — check back soon."
        )
        return redirect("practice:choose")
    mode = "test" if request.GET.get("mode") == "test" else "practice"
    session = TestSession.objects.create(
        student=request.user, subtopic=None, mode=mode,
        time_limit_seconds=90 if mode == "test" else 0,
    )
    request.session["deck"] = {
        "session_id": session.id, "subtopic_id": None, "section_id": section.id,
        "qids": qids, "idx": 0, "answered": [], "mode": mode,
        # Names the parked deck on the dashboard's "pick up where you left off"
        # row, which falls back to this when there's no subtopic to name.
        "paper": section.name,
    }
    return redirect("practice:question")


@login_required
def mock_choose(request):
    """The four papers, as four cards."""
    papers = []
    for section in Section.objects.order_by("order"):
        count, minutes = MOCK_PAPERS.get(section.code, (20, 30))
        available = paper_questions(section).count()
        papers.append({
            "section": section, "minutes": minutes,
            "questions": min(count, available), "available": available,
            "written": paper_questions(section).filter(
                marking=Question.Marking.RUBRIC).count(),
        })
    progress = compute_progress(request.user)
    _, targeted_plan = build_targeted_paper(request.user, progress=progress)
    return render(request, "practice/mock_choose.html", {
        "papers": papers,
        "targeted_plan": targeted_plan,
        "targeted_minutes": TARGETED_MINUTES,
        "targeted_total": sum(r["count"] for r in targeted_plan),
        "answered": progress["total"],
        "premium": is_premium(request.user),
    })


@login_required
def mock_start_targeted(request):
    blocked = _mock_gate(request)
    if blocked:
        return blocked
    _park_deck(request)
    qids, plan = build_targeted_paper(request.user)
    if not qids:
        messages.info(
            request,
            "Answer a few more questions first — a targeted paper needs enough of "
            "a record to aim at, and right now there isn't one."
        )
        return redirect("practice:mock_choose")

    session = TestSession.objects.create(
        student=request.user, subtopic=None, mode=TestSession.Mode.MOCK,
        time_limit_seconds=TARGETED_MINUTES * 60,
    )
    request.session["deck"] = {
        "session_id": session.id, "subtopic_id": None, "section_id": None,
        "qids": qids, "idx": 0, "answered": [], "mode": "mock",
        "ends_at": (timezone.now() + timedelta(minutes=TARGETED_MINUTES)).isoformat(),
        "paper": "Targeted paper", "minutes": TARGETED_MINUTES,
    }
    return redirect("practice:question")


@login_required
def mock_start(request, section_id):
    blocked = _mock_gate(request)
    if blocked:
        return blocked
    _park_deck(request)
    section = get_object_or_404(Section, pk=section_id)
    count, minutes = MOCK_PAPERS.get(section.code, (20, 30))
    qids = build_paper(section, count)
    if not qids:
        messages.warning(request, f"No questions available for {section.name} yet.")
        return redirect("practice:mock_choose")

    session = TestSession.objects.create(
        student=request.user, subtopic=None, mode=TestSession.Mode.MOCK,
        time_limit_seconds=minutes * 60,
    )
    request.session["deck"] = {
        "session_id": session.id, "subtopic_id": None, "section_id": section.id,
        "qids": qids, "idx": 0, "answered": [], "mode": "mock",
        # Absolute, not a duration: the clock has to keep running across page
        # loads and survive the pupil sitting on one question, which a
        # per-request countdown would not.
        "ends_at": (timezone.now() + timedelta(minutes=minutes)).isoformat(),
        "paper": section.name, "minutes": minutes,
    }
    return redirect("practice:question")


@login_required
def question(request):
    deck = request.session.get("deck")
    if not deck:
        return redirect("practice:choose")
    remaining = _deck_deadline(deck)
    if remaining is not None and remaining <= 0:
        return redirect("practice:mock_result")
    if deck["idx"] >= len(deck["qids"]):
        return redirect("practice:mock_result" if deck["mode"] == "mock"
                        else "practice:summary")
    q = get_object_or_404(Question, pk=deck["qids"][deck["idx"]])
    return render(request, "practice/question.html", {
        "q": q, "num": deck["idx"] + 1, "total": len(deck["qids"]),
        "mode": deck["mode"],
        "time_limit": 90 if deck["mode"] == "test" else 0,
        "paper_remaining": remaining, "paper_name": deck.get("paper"),
    })


@login_required
def answer(request):
    deck = request.session.get("deck")
    if not deck or request.method != "POST":
        return redirect("practice:choose")
    # A submission after the clock runs out is not recorded. 10 seconds of grace
    # so an answer already in flight when it expired still counts.
    remaining = _deck_deadline(deck)
    if remaining is not None and remaining < -10:
        return redirect("practice:mock_result")

    q = get_object_or_404(Question, pk=deck["qids"][deck["idx"]])

    # A mock advances on submit, so a stale form — from the back button, or a
    # resubmit after moving on — would otherwise record its answer against
    # whatever question is now current. The hidden qid pins each submission to
    # the question it was actually shown for.
    posted_qid = request.POST.get("qid")
    if posted_qid and str(q.id) != str(posted_qid):
        return redirect("practice:question")

    # Idempotency. `idx` only advances in next_q(), so a refresh, a double-click
    # or a back-then-resubmit lands here with the same idx and used to bank a
    # whole second Attempt: three posts of one 2-mark question stored 3 attempts
    # and 8 marks. Harmless-looking today, but the adaptive engine reads exactly
    # these rows, so each duplicate would become another ability update.
    if deck["idx"] < len(deck["answered"]):
        return _replay_feedback(request, deck, q)

    # Belt and braces against a deck started before the cap was reached (a
    # deck open in another tab, or one started just under the last answer
    # that used up the cap): a mock's deck["mode"] is always "mock" and mocks
    # are gated at the door instead (mock_start/_targeted, above), so this
    # only ever turns away practice or timed-practice submissions.
    if deck["mode"] != "mock" and not is_premium(request.user):
        section = q.subtopic.section
        if free_questions_left(request.user, section) <= 0:
            messages.info(request, _free_cap_message(section))
            deck["qids"] = deck["qids"][:deck["idx"]]
            request.session["deck"] = deck
            return redirect("practice:summary")

    selected = AnswerOption.objects.filter(pk=request.POST.get("option"), question=q).first()
    given = (request.POST.get("answer") or "").strip()

    # A grouped question posts one pick per bracket — `option` repeated — rather
    # than a single choice. `selected_option` stays null for these: it holds one
    # AnswerOption and there is no honest way to say which of two picks it is.
    # The words go into `answer_given`, which the review page already falls back
    # to, and `Attempt.is_correct` and the marks are what analytics reads anyway.
    #
    # The cost, stated: per-bracket `misconception` is not recorded. Recording it
    # means a many-to-many on the analytics spine, which is not worth adding
    # before anything reads it.
    picked = []
    if q.is_grouped:
        # Each bracket is its own radio group and so posts under its own name —
        # `bracket_1`, `bracket_2`. They cannot share one name: HTML would treat
        # them as a single group and let the pupil pick one word in total.
        ids = [request.POST.get(f"bracket_{n}") for n, _ in q.option_groups]
        picked = list(AnswerOption.objects.filter(
            pk__in=[i for i in ids if i], question=q
        ).order_by("order"))
        selected = None
        given = " | ".join(o.text for o in picked)

    result = mark(q, given=given, option=selected, options=picked)

    session = TestSession.objects.get(pk=deck["session_id"])
    # Mock attempts are always "premium": a free pupil cannot sit one
    # (mock_start/_targeted refuse them at the door), so an attempt reaching
    # here from a mock deck is, by construction, from a pupil with access.
    attempt_tier = (
        Attempt.Tier.PREMIUM if deck["mode"] == "mock" or is_premium(request.user)
        else Attempt.Tier.FREE
    )
    attempt = Attempt.objects.create(
        session=session, student=request.user, question=q, subtopic=q.subtopic,
        selected_option=selected, answer_given=given[:400],
        is_correct=result.correct,
        marks_earned=result.marks, marks_available=result.available,
        awaiting_marking=result.awaiting_marking,
        time_taken_ms=int(request.POST.get("time_ms") or 0),
        source=deck["mode"],
        tier=attempt_tier,
    )
    # Recorded per question rather than as a bare bool, so a replay can rebuild
    # the exact feedback and session review can show what was actually answered.
    deck["answered"].append({
        "qid": q.id, "attempt_id": attempt.id,
        "correct": result.correct, "marks": result.marks,
        "available": result.available,
        # Which words were picked from which brackets. `selected_option` cannot
        # hold more than one, so without this a refresh would replay a grouped
        # question with nothing shown as chosen.
        "picked": [o.id for o in picked],
    })
    # Homework auto-completes from attempts, not self-report
    for a in Assignment.objects.filter(student=request.user, subtopic=q.subtopic):
        a.refresh_status()

    # UNDER EXAM CONDITIONS THE PUPIL IS TOLD NOTHING. A mock exists to measure,
    # and feedback after each question changes what is being measured — it lets
    # them recalibrate mid-paper, which is not available in the hall. So a mock
    # advances straight to the next question and every answer is revealed
    # together on the report. Practice, which exists to teach, still marks
    # immediately.
    if deck["mode"] == "mock":
        deck["idx"] += 1
        request.session["deck"] = deck
        return redirect("practice:question")

    request.session["deck"] = deck
    return render(request, "practice/question.html", {
        "q": q, "num": deck["idx"] + 1, "total": len(deck["qids"]),
        "mode": deck["mode"], "selected": selected, "given": given,
        "picked_ids": [o.id for o in picked],
        "is_correct": result.correct, "result": result,
        "correct_opt": q.correct_option(), "feedback": True,
    })


def _replay_feedback(request, deck, q):
    """Re-render the feedback already earned, without recording anything."""
    entry = deck["answered"][deck["idx"]]
    attempt = Attempt.objects.filter(
        pk=entry.get("attempt_id") if isinstance(entry, dict) else None,
        student=request.user,
    ).select_related("selected_option").first()
    if attempt is None:
        # Pre-existing deck from before this shape change, or a deleted attempt.
        # Nothing to replay, so send them on rather than inventing feedback.
        return redirect("practice:question")
    result = Result(
        marks=attempt.marks_earned, available=attempt.marks_available,
        correct=attempt.is_correct, awaiting_marking=attempt.awaiting_marking,
    )
    return render(request, "practice/question.html", {
        "q": q, "num": deck["idx"] + 1, "total": len(deck["qids"]),
        "mode": deck["mode"], "selected": attempt.selected_option,
        "given": attempt.answer_given,
        # A grouped question's picks are not on the Attempt — one FK cannot hold
        # two — so the deck entry carries them for the length of the session.
        "picked_ids": entry.get("picked") or [],
        "is_correct": attempt.is_correct, "result": result,
        "correct_opt": q.correct_option(), "feedback": True,
    })


@login_required
def next_q(request):
    deck = request.session.get("deck")
    if not deck:
        return redirect("practice:choose")
    deck["idx"] += 1
    request.session["deck"] = deck
    return redirect("practice:question")


@login_required
def pause(request):
    _park_deck(request)
    messages.info(request, "Practice paused — resume it any time from your dashboard.")
    return redirect("practice:dashboard")


@login_required
def resume(request, session_id):
    session = get_object_or_404(
        TestSession, pk=session_id, student=request.user, finished_at__isnull=True
    )
    if not session.deck_state:
        return redirect("practice:choose")
    _park_deck(request)  # park whatever else is open before swapping decks
    request.session["deck"] = session.deck_state
    session.deck_state = None
    session.save(update_fields=["deck_state"])
    return redirect("practice:question")


@login_required
def summary(request):
    deck = request.session.get("deck")
    if not deck:
        return redirect("practice:choose")
    if deck.get("mode") == "mock":
        return redirect("practice:mock_result")
    answered = deck.get("answered", [])
    # A mock deck carries no subtopic, so this must tolerate None.
    subtopic = Subtopic.objects.filter(pk=deck.get("subtopic_id")).first() \
        if deck.get("subtopic_id") else None
    TestSession.objects.filter(pk=deck["session_id"]).update(
        finished_at=timezone.now(), deck_state=None
    )
    request.session.pop("deck", None)
    return render(request, "practice/summary.html", {
        "correct": sum(1 for x in answered if was_correct(x)),
        "total": len(answered), "subtopic": subtopic,
    })


@login_required
def mock_result(request):
    """Marked report for a finished paper.

    Reads the Attempt rows rather than the deck, so the page survives a refresh
    after the deck has been cleared — and so it reports what was actually
    recorded rather than what the session thought it recorded.
    """
    deck = request.session.get("deck")
    if deck and deck.get("mode") == "mock":
        TestSession.objects.filter(pk=deck["session_id"], student=request.user).update(
            finished_at=timezone.now(), deck_state=None
        )
        request.session["last_mock"] = deck["session_id"]
        request.session["last_mock_total"] = len(deck["qids"])
        # Kept so the report can list questions that were never reached, not just
        # the ones answered — running out of time is information too.
        request.session["last_mock_qids"] = deck["qids"]
        request.session.pop("deck", None)

    session_id = request.session.get("last_mock")
    if not session_id:
        return redirect("practice:mock_choose")
    session = get_object_or_404(TestSession, pk=session_id, student=request.user)
    attempts = list(
        Attempt.objects.filter(session=session)
        .select_related("subtopic", "subtopic__section", "question")
    )

    earned = sum(a.marks_earned for a in attempts)
    available = sum(a.marks_available for a in attempts)
    pending = [a for a in attempts if a.awaiting_marking]
    pending_marks = sum(a.marks_available for a in pending)

    # Per subtopic, so the report says WHERE the marks went rather than just how
    # many. Written questions are counted separately: folding an unmarked essay
    # in as zero would report a mark the pupil has not actually been given.
    by_sub = {}
    for a in attempts:
        s = by_sub.setdefault(a.subtopic_id, {
            "name": a.subtopic.name, "code": a.subtopic.section.code,
            "earned": 0, "available": 0, "pending": 0, "n": 0,
        })
        s["n"] += 1
        s["available"] += a.marks_available
        if a.awaiting_marking:
            s["pending"] += a.marks_available
        else:
            s["earned"] += a.marks_earned
    rows = sorted(by_sub.values(), key=lambda r: (r["code"], r["name"]))
    for r in rows:
        markable = r["available"] - r["pending"]
        r["pct"] = round(100 * r["earned"] / markable) if markable else None

    # Question-by-question review. This is the ONLY place a mock reveals answers,
    # which is the whole point of withholding them during the paper.
    by_question = {a.question_id: a for a in attempts}
    review = []
    for i, qid in enumerate(request.session.get("last_mock_qids") or
                            [a.question_id for a in attempts], start=1):
        a = by_question.get(qid)
        question = a.question if a else Question.objects.filter(pk=qid).first()
        if question is None:
            continue
        review.append({
            "n": i, "q": question, "attempt": a,
            "given": (a.selected_option.text if a and a.selected_option
                      else (a.answer_given if a else "")),
            "correct_answer": (question.correct_option().text
                               if question.kind == Question.Kind.MCQ
                               and question.correct_option()
                               else question.answer_text),
            "misconception": (a.selected_option.misconception_text
                              if a and a.selected_option else ""),
        })

    markable = available - pending_marks
    spent = sum(a.time_taken_ms for a in attempts) / 60000
    return render(request, "practice/mock_result.html", {
        "review": review,
        "session": session,
        "attempted": len(attempts),
        "total_questions": request.session.get("last_mock_total", len(attempts)),
        "earned": earned, "available": available,
        "markable": markable, "pending": pending, "pending_marks": pending_marks,
        "pct": round(100 * earned / markable) if markable else None,
        "rows": rows,
        "minutes_spent": round(spent),
        "minutes_allowed": round(session.time_limit_seconds / 60),
    })
