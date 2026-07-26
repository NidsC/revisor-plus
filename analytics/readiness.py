"""
Readiness against a target: am I on track, and how many hours a week do I need?

Modelled on Kaplan Schweser's study-plan indicator, with one deliberate
difference in how the hours figure is derived.

    required h/wk = (target_hours - hours actually done) / weeks remaining

`hours actually done` is MEASURED, summed from Attempt.time_taken_ms. The only
assumption in the whole calculation is `Goal.target_hours`, and that lives in a
single editable field a human owns rather than being buried in a coefficient
here. Schweser can drive its number off content coverage because its content is
finite and large; ours is not yet — a pupil has currently seen every question in
the bank, so "content remaining" would report zero work and zero hours. Revisit
`coverage` below as the primary driver once the bank is big enough to mean
something.

ATTAINMENT IS KEPT SEPARATE FROM PACE, ON PURPOSE. Hours put in and marks
achieved are different things, and blending them into one score would let a
pupil who has ground through their hours without improving read as "ready".
`overall_status` therefore reports the worse of the two and only ever says ready
when the attainment targets are actually met.
"""
from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone

from analytics.services import compute_progress
from practice.models import Attempt

# Status values, worst-first. Order matters: `_worst` relies on it.
BEHIND = "behind"
AT_RISK = "at_risk"
ON_TRACK = "on_track"
READY = "ready"
_SEVERITY = [BEHIND, AT_RISK, ON_TRACK, READY]

# Distinct non-judgemental states. Each means "we cannot say", and each needs its
# own message rather than being flattened into a misleading number.
NO_GOAL = "no_goal"
NOT_STARTED = "not_started"
EXAM_PASSED = "exam_passed"

STATUS_LABEL = {
    BEHIND: "Behind",
    AT_RISK: "At risk",
    ON_TRACK: "On track",
    READY: "On target",
    NO_GOAL: "No target set",
    NOT_STARTED: "Not started",
    EXAM_PASSED: "Exam date passed",
}

# A pupil hitting 90% of the hours they need is on track; below 60%, behind.
PACE_ON_TRACK = 0.9
PACE_AT_RISK = 0.6
# Within 5 points of a target counts as at risk rather than behind — inside the
# noise of a few hundred attempts, not a comfortable pass.
ATTAINMENT_NEAR_MISS = 5
RECENT_WINDOW_DAYS = 28


def _worst(statuses):
    known = [s for s in statuses if s in _SEVERITY]
    return min(known, key=_SEVERITY.index) if known else None


def _hours(qs):
    return (qs.aggregate(t=Sum("time_taken_ms"))["t"] or 0) / 3_600_000


def active_goal(student):
    return (
        student.goals.filter(is_active=True)
        .select_related("school")
        .prefetch_related("section_targets__section", "school__papers")
        .first()
    )


def compute_readiness(student, progress=None):
    """Readiness dict for templates. Pass `progress` to reuse an existing
    compute_progress() call rather than paying for the queries twice."""
    goal = active_goal(student)
    if progress is None:
        progress = compute_progress(student)

    out = {
        "goal": goal,
        "status": NO_GOAL,
        "status_label": STATUS_LABEL[NO_GOAL],
        "pace_status": None,
        "attainment_status": None,
        "section_gaps": [],
        "readiness_pct": 0,
        "hours_done": 0.0,
        "recent_hours_per_week": 0.0,
        "required_hours_per_week": 0.0,
        "hours_remaining": 0.0,
        "weeks_remaining": 0.0,
        "days_remaining": 0,
        "target_met": False,
        "projected_overall": None,
        "coverage": None,
    }
    if goal is None:
        return out

    now = timezone.now()
    days = goal.days_remaining
    out["days_remaining"] = days

    # --- effort, measured ------------------------------------------------
    attempts = Attempt.objects.filter(student=student)
    hours_done = _hours(attempts)
    recent = _hours(attempts.filter(created_at__gte=now - timedelta(days=RECENT_WINDOW_DAYS)))
    out["hours_done"] = round(hours_done, 1)
    out["recent_hours_per_week"] = round(recent / (RECENT_WINDOW_DAYS / 7), 2)
    out["hours_remaining"] = round(max(0.0, goal.target_hours - hours_done), 1)

    # Never divide by zero, and never imply a whole week is left on exam eve.
    # Half a week is the floor: it keeps the number finite and honestly urgent.
    weeks = max(0.5, days / 7)
    out["weeks_remaining"] = round(weeks, 1)
    out["required_hours_per_week"] = round(out["hours_remaining"] / weeks, 2)

    # --- attainment, measured -------------------------------------------
    by_code = {s["code"]: s for s in progress["sections"]}
    targets = {t.section.code: t for t in goal.section_targets.all()}
    required = goal.required_sections()
    # Fall back to whatever has an explicit target, then to the overall figure,
    # so a goal with no per-paper detail still produces a usable read.
    codes = [s.code for s in required] or list(targets)

    gaps = []
    for code in codes:
        target = targets[code].target_accuracy if code in targets else goal.target_overall
        section = by_code.get(code)
        current = section["accuracy"] if section else None
        attempted = section["total"] if section else 0
        if current is None:
            status = NOT_STARTED
            gap = None
        else:
            gap = current - target
            if gap >= 0:
                status = READY
            elif gap >= -ATTAINMENT_NEAR_MISS:
                status = AT_RISK
            else:
                status = BEHIND
        gaps.append({
            "code": code,
            "name": section["name"] if section else code,
            "current": current,
            "target": target,
            "gap": gap,
            "attempted": attempted,
            "status": status,
            "status_label": STATUS_LABEL[status],
            # Progress-bar width: how far to target, capped so an over-performing
            # paper does not overflow the bar.
            "pct_of_target": min(100, round(100 * current / target)) if current and target else 0,
        })
    out["section_gaps"] = gaps

    scored = [g for g in gaps if g["current"] is not None and g["target"]]
    if scored:
        out["readiness_pct"] = round(
            100 * sum(min(1.0, g["current"] / g["target"]) for g in scored) / len(scored)
        )
        out["attainment_status"] = _worst([g["status"] for g in scored])
    out["target_met"] = bool(scored) and all(g["status"] == READY for g in scored)

    # --- pace ------------------------------------------------------------
    if out["required_hours_per_week"] <= 0:
        # Planned hours are done. That is not the same as being ready, so pace is
        # only "on track" here — attainment decides the headline below.
        out["pace_status"] = ON_TRACK
    else:
        ratio = out["recent_hours_per_week"] / out["required_hours_per_week"]
        out["pace_status"] = (
            ON_TRACK if ratio >= PACE_ON_TRACK
            else AT_RISK if ratio >= PACE_AT_RISK
            else BEHIND
        )

    # --- trend projection (directional only, labelled as such in the UI) --
    values = progress.get("trend_values") or []
    if len(values) >= 6 and days > 0:
        half = len(values) // 2
        early = sum(values[:half]) / half
        late = sum(values[half:]) / len(values[half:])
        per_day = (late - early) / max(1, len(values) / 2)
        out["projected_overall"] = max(0, min(100, round(progress["overall"] + per_day * days)))

    # --- how much of the bank has been seen (secondary indicator) ---------
    from catalog.models import Question

    bank = Question.objects.filter(active=True, parts__isnull=True).count()
    seen = attempts.values("question").distinct().count()
    if bank:
        out["coverage"] = {"seen": seen, "bank": bank, "pct": round(100 * min(seen, bank) / bank)}

    # --- headline --------------------------------------------------------
    if progress["total"] == 0:
        out["status"] = NOT_STARTED
    elif days < 0:
        out["status"] = EXAM_PASSED
    else:
        combined = _worst([out["pace_status"], out["attainment_status"]])
        # READY is earned by ATTAINMENT, gated on not being behind on the hours.
        # Hours alone can never earn it, however diligently they were logged —
        # that is what keeps a pupil who has ground out the time without
        # improving from being told they are on target.
        if out["target_met"] and out["pace_status"] in (ON_TRACK, READY):
            combined = READY
        elif combined == READY and not out["target_met"]:
            combined = ON_TRACK
        out["status"] = combined or NOT_STARTED
    out["status_label"] = STATUS_LABEL[out["status"]]
    return out
