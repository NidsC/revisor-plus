"""Progress analytics computed over the Attempt table (the analytics spine)."""
from collections import defaultdict
from datetime import timedelta

from django.utils import timezone

from practice.models import Attempt


def compute_progress(student):
    attempts = list(
        Attempt.objects.filter(student=student).select_related("subtopic", "subtopic__section")
    )
    total = len(attempts)
    correct = sum(1 for a in attempts if a.is_correct)
    overall = round(100 * correct / total) if total else 0

    # by subtopic
    sub_stats = {}
    for a in attempts:
        s = sub_stats.setdefault(
            a.subtopic_id,
            {"id": a.subtopic_id, "name": a.subtopic.name, "section": a.subtopic.section.code,
             "total": 0, "correct": 0},
        )
        s["total"] += 1
        s["correct"] += 1 if a.is_correct else 0
    subtopics = []
    for s in sub_stats.values():
        s["accuracy"] = round(100 * s["correct"] / s["total"]) if s["total"] else 0
        subtopics.append(s)
    subtopics.sort(key=lambda x: x["accuracy"])

    # by section
    sec_stats = {}
    for a in attempts:
        code = a.subtopic.section.code
        s = sec_stats.setdefault(
            code, {"code": code, "name": a.subtopic.section.name, "total": 0, "correct": 0}
        )
        s["total"] += 1
        s["correct"] += 1 if a.is_correct else 0
    sections = []
    for s in sec_stats.values():
        s["accuracy"] = round(100 * s["correct"] / s["total"]) if s["total"] else 0
        sections.append(s)
    sections.sort(key=lambda x: x["code"])

    # Minimum sample before a subtopic can be called a weakness. At 3 attempts a
    # single unlucky run reads as 0%, which is noise presented as a diagnosis —
    # and it is what a tutor would action first. Fall back to the looser floor
    # only for pupils too new to clear the higher one, so their panel is not empty.
    weak = [s for s in subtopics if s["total"] >= 8][:4]
    if not weak:
        weak = [s for s in subtopics if s["total"] >= 3][:4]

    # trend: accuracy per day
    day_stats = defaultdict(lambda: [0, 0])
    for a in attempts:
        d = a.created_at.date()
        day_stats[d][0] += 1
        day_stats[d][1] += 1 if a.is_correct else 0
    trend = sorted(day_stats.items())

    # A rolling accuracy alongside the daily one. A single day holds only a
    # handful of questions, so day-to-day accuracy swings between 0% and 100% and
    # the chart reads as noise — a pupil who climbed from 59% to 82% over four
    # months could not see it. Summed correct over summed attempts across the
    # window, not a mean of the daily percentages, so a day with three questions
    # does not count the same as one with forty.
    WINDOW = 7
    trend_rolling = []
    for i in range(len(trend)):
        window = trend[max(0, i - WINDOW + 1):i + 1]
        seen = sum(t for _, (t, _c) in window)
        got = sum(c for _, (_t, c) in window)
        trend_rolling.append(round(100 * got / seen) if seen else 0)

    return {
        "total": total,
        "correct": correct,
        "overall": overall,
        "subtopics": subtopics,
        "sections": sections,
        "weak": weak,
        "trend_labels": [d.strftime("%d %b") for d, _ in trend],
        "trend_values": [round(100 * c / t) if t else 0 for _, (t, c) in trend],
        "trend_rolling": trend_rolling,
        "section_labels": [s["code"] for s in sections],
        "section_values": [s["accuracy"] for s in sections],
    }


WEEKLY_WINDOW_DAYS = 7

# The per-subject band on the dashboard is a judgement about a pupil, so it is
# read over a longer window than WEEKLY_WINDOW_DAYS: a week of a couple of
# evenings is a handful of questions, and a band drawn from those swings between
# "Strong" and "Keep practising" on one bad session.
BAND_WINDOW_DAYS = 30
# Below this many attempts in the window there is no band at all. A pupil who
# answered four questions gets a blank row, not a verdict drawn from four rows.
BAND_MIN_ATTEMPTS = 20
# Accuracy floors, in percent. Strong at 75 and up, Getting there from 55, and
# anything under 55 is Keep practising.
BAND_STRONG_PCT = 75
BAND_GETTING_THERE_PCT = 55
# Label (pupil-facing wording) paired with a stable level key. Templates switch
# on the level, never on the label — the wording here is still open (the parent
# side says Secure / Developing / Needs work) and changing it should not mean
# rewriting the markup that colours the row.
BAND_STRONG = ("Strong", "good")
BAND_GETTING_THERE = ("Getting there", "mid")
BAND_KEEP_PRACTISING = ("Keep practising", "low")


def _band(attempts, correct):
    """(label, level) for a subject row, or (None, None) when the window holds
    too little to say anything. Compared before rounding, so 74.6% is Getting
    there rather than being rounded up over the Strong line."""
    if attempts < BAND_MIN_ATTEMPTS:
        return None, None
    pct = 100 * correct / attempts
    if pct >= BAND_STRONG_PCT:
        return BAND_STRONG
    if pct >= BAND_GETTING_THERE_PCT:
        return BAND_GETTING_THERE
    return BAND_KEEP_PRACTISING


def compute_subject_summary(student):
    """Per-section (subject) completion, trailing-week accuracy and dashboard
    band. Always returns all four sections, even for a brand-new student with no
    attempts, so the cards never render blank.
    """
    from catalog.models import Question, Section

    now = timezone.now()
    cutoff = now - timedelta(days=WEEKLY_WINDOW_DAYS)
    band_cutoff = now - timedelta(days=BAND_WINDOW_DAYS)

    # `parts` is the reverse side of Question.parent (a container's children),
    # not a field readable off a row — so "answerable" has to be resolved as a
    # set of ids up front, the same way answerable() does it as a queryset,
    # rather than re-checked per attempt in Python.
    answerable_section = {}  # question id -> section id, for answerable questions only
    bank_by_section = defaultdict(int)
    for qid, section_id in (
        Question.objects.filter(active=True, parts__isnull=True)
        .exclude(marking=Question.Marking.RUBRIC)
        .values_list("id", "subtopic__section_id")
    ):
        answerable_section[qid] = section_id
        bank_by_section[section_id] += 1

    # completed: distinct answerable questions ever attempted, per section.
    # weekly: [attempts, correct] in the trailing window, per section.
    # banded: [attempts, correct] over the band window, per section — restricted
    # to answerable questions, so the band is scored over the same bank the row's
    # completion figure counts against. Rubric answers in particular are recorded
    # is_correct=False until a marker sees them, and letting those into the band
    # would read as a pupil getting them wrong.
    completed = defaultdict(set)
    weekly = defaultdict(lambda: [0, 0])
    banded = defaultdict(lambda: [0, 0])
    for qid, section_id, is_correct, created_at in Attempt.objects.filter(
        student=student
    ).values_list("question_id", "subtopic__section_id", "is_correct", "created_at"):
        is_answerable = qid in answerable_section
        if is_answerable:
            completed[section_id].add(qid)
        if created_at >= cutoff:
            weekly[section_id][0] += 1
            weekly[section_id][1] += 1 if is_correct else 0
        if is_answerable and created_at >= band_cutoff:
            banded[section_id][0] += 1
            banded[section_id][1] += 1 if is_correct else 0

    out = []
    for section in Section.objects.order_by("order"):
        total = bank_by_section.get(section.id, 0)
        n_done = len(completed.get(section.id, ()))
        w_total, w_correct = weekly.get(section.id, (0, 0))
        b_total, b_correct = banded.get(section.id, (0, 0))
        band, band_level = _band(b_total, b_correct)
        out.append({
            "code": section.code,
            "name": section.name,
            "completed": n_done,
            "total": total,
            "pct_complete": round(100 * n_done / total) if total else 0,
            "weekly_avg": round(100 * w_correct / w_total) if w_total else None,
            "band": band,
            "band_level": band_level,
        })
    return out


def compute_coverage(student):
    """How much of the bank this student has seen: distinct ANSWERABLE questions
    attempted, over the whole answerable bank. `None` when the bank is empty.

    The single definition of coverage. The dashboard header and
    `compute_readiness`'s `coverage` key both call this, because two coverage
    figures that disagree by a few questions is exactly the contradiction the
    dashboard is trying to remove — they used to differ, this one filtering to
    answerable questions and readiness's counting every attempt.

    Availability, NOT completion. With a bank of a few dozen this read ~100% and
    looked like "you're done"; with a generated bank of 1,000+ the same fraction
    reads ~2% and looks like failure. Neither is a fact about the pupil — nobody
    is expected to answer every question — so it is reported as how much material
    is there, with `pct` kept only for the "you've seen nearly all of it" nudge.
    """
    from catalog.models import Question

    answerable = (
        Question.objects.filter(active=True, parts__isnull=True)
        .exclude(marking=Question.Marking.RUBRIC)
    )
    bank = answerable.count()
    if not bank:
        return None
    # Restricted to `answerable`, so `seen` can never exceed `bank` and the
    # percentage needs no clamp.
    seen = (
        Attempt.objects.filter(student=student, question__in=answerable)
        .values("question").distinct().count()
    )
    return {"seen": seen, "bank": bank, "pct": round(100 * seen / bank)}
