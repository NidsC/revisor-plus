"""Progress analytics computed over the Attempt table (the analytics spine)."""
from collections import defaultdict

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
