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


def compute_subject_summary(student):
    """Per-section (subject) completion and trailing-week accuracy, for the
    dashboard's subject cards. Always returns all four sections, even for a
    brand-new student with no attempts, so the cards never render blank.
    """
    from catalog.models import Question, Section

    now = timezone.now()
    cutoff = now - timedelta(days=WEEKLY_WINDOW_DAYS)

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
    completed = defaultdict(set)
    weekly = defaultdict(lambda: [0, 0])
    for qid, section_id, is_correct, created_at in Attempt.objects.filter(
        student=student
    ).values_list("question_id", "subtopic__section_id", "is_correct", "created_at"):
        if qid in answerable_section:
            completed[section_id].add(qid)
        if created_at >= cutoff:
            weekly[section_id][0] += 1
            weekly[section_id][1] += 1 if is_correct else 0

    out = []
    for section in Section.objects.order_by("order"):
        total = bank_by_section.get(section.id, 0)
        n_done = len(completed.get(section.id, ()))
        w_total, w_correct = weekly.get(section.id, (0, 0))
        out.append({
            "code": section.code,
            "name": section.name,
            "completed": n_done,
            "total": total,
            "pct_complete": round(100 * n_done / total) if total else 0,
            "weekly_avg": round(100 * w_correct / w_total) if w_total else None,
        })
    return out
