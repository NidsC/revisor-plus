import random

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from analytics.readiness import compute_readiness
from analytics.services import compute_progress
from assignments.models import Assignment
from catalog.marking import Result, mark
from catalog.models import AnswerOption, Question, Subtopic

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
def question(request):
    deck = request.session.get("deck")
    if not deck:
        return redirect("practice:choose")
    if deck["idx"] >= len(deck["qids"]):
        return redirect("practice:summary")
    q = get_object_or_404(Question, pk=deck["qids"][deck["idx"]])
    return render(request, "practice/question.html", {
        "q": q, "num": deck["idx"] + 1, "total": len(deck["qids"]),
        "mode": deck["mode"], "time_limit": 90 if deck["mode"] == "test" else 0,
    })


@login_required
def answer(request):
    deck = request.session.get("deck")
    if not deck or request.method != "POST":
        return redirect("practice:choose")
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
    answered = deck.get("answered", [])
    subtopic = Subtopic.objects.filter(pk=deck["subtopic_id"]).first()
    TestSession.objects.filter(pk=deck["session_id"]).update(
        finished_at=timezone.now(), deck_state=None
    )
    request.session.pop("deck", None)
    return render(request, "practice/summary.html", {
        "correct": sum(1 for x in answered if was_correct(x)),
        "total": len(answered), "subtopic": subtopic,
    })
