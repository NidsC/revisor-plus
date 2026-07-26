import random
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from analytics.readiness import compute_readiness
from analytics.services import compute_progress
from assignments.models import Assignment
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
    data = compute_progress(request.user)
    assignments = Assignment.objects.filter(student=request.user).select_related(
        "subtopic", "subtopic__section"
    )
    for a in assignments:
        a.refresh_status()
        a.done = a.progress_count()
    paused = TestSession.objects.filter(
        student=request.user, finished_at__isnull=True, deck_state__isnull=False
    ).select_related("subtopic", "subtopic__section").order_by("-started_at")
    return render(request, "practice/dashboard.html", {
        "data": data, "assignments": assignments, "paused": paused,
        # Reuse the progress we already computed rather than querying twice.
        "readiness": compute_readiness(request.user, progress=data),
    })


@login_required
def choose(request):
    subtopics = Subtopic.objects.select_related("section").all()
    return render(request, "practice/choose.html", {"subtopics": subtopics})


@login_required
def start(request, subtopic_id):
    _park_deck(request)  # don't destroy an in-progress deck — park it so it stays resumable
    subtopic = get_object_or_404(Subtopic, pk=subtopic_id)
    qids = list(answerable(subtopic).values_list("id", flat=True))
    random.shuffle(qids)
    qids = qids[:5]
    while qids and len(qids) < 5:
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
    })


@login_required
def mock_start_targeted(request):
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
        student=request.user, subtopic=None, mode=TestSession.Mode.TEST,
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
    _park_deck(request)
    section = get_object_or_404(Section, pk=section_id)
    count, minutes = MOCK_PAPERS.get(section.code, (20, 30))
    qids = build_paper(section, count)
    if not qids:
        messages.warning(request, f"No questions available for {section.name} yet.")
        return redirect("practice:mock_choose")

    session = TestSession.objects.create(
        student=request.user, subtopic=None, mode=TestSession.Mode.TEST,
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

    # Idempotency. `idx` only advances in next_q(), so a refresh, a double-click
    # or a back-then-resubmit lands here with the same idx and used to bank a
    # whole second Attempt: three posts of one 2-mark question stored 3 attempts
    # and 8 marks. Harmless-looking today, but the adaptive engine reads exactly
    # these rows, so each duplicate would become another ability update.
    if deck["idx"] < len(deck["answered"]):
        return _replay_feedback(request, deck, q)

    selected = AnswerOption.objects.filter(pk=request.POST.get("option"), question=q).first()
    given = (request.POST.get("answer") or "").strip()
    result = mark(q, given=given, option=selected)

    session = TestSession.objects.get(pk=deck["session_id"])
    attempt = Attempt.objects.create(
        session=session, student=request.user, question=q, subtopic=q.subtopic,
        selected_option=selected, answer_given=given[:400],
        is_correct=result.correct,
        marks_earned=result.marks, marks_available=result.available,
        awaiting_marking=result.awaiting_marking,
        time_taken_ms=int(request.POST.get("time_ms") or 0),
        source=deck["mode"],
    )
    # Recorded per question rather than as a bare bool, so a replay can rebuild
    # the exact feedback and session review can show what was actually answered.
    deck["answered"].append({
        "qid": q.id, "attempt_id": attempt.id,
        "correct": result.correct, "marks": result.marks,
        "available": result.available,
    })
    request.session["deck"] = deck
    # Homework auto-completes from attempts, not self-report
    for a in Assignment.objects.filter(student=request.user, subtopic=q.subtopic):
        a.refresh_status()
    return render(request, "practice/question.html", {
        "q": q, "num": deck["idx"] + 1, "total": len(deck["qids"]),
        "mode": deck["mode"], "selected": selected, "given": given,
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

    markable = available - pending_marks
    spent = sum(a.time_taken_ms for a in attempts) / 60000
    return render(request, "practice/mock_result.html", {
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
