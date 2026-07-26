from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from analytics.readiness import active_goal, compute_readiness

from .forms import GoalForm
from .models import Goal


def _target_student(request, student_id):
    """Whose goal is being edited, with the ownership rule enforced.

    A pupil may only ever touch their own. A tutor may touch a pupil's only if
    that pupil is linked to them — reusing the same check as the rest of the
    tutoring app rather than inventing a second, subtly different one.
    """
    if student_id is None:
        return request.user, Goal.SetBy.STUDENT
    if str(student_id) == str(request.user.id):
        return request.user, Goal.SetBy.STUDENT
    if not request.user.is_tutor:
        raise PermissionDenied("You can only change your own target.")
    from tutoring.views import _owned_student

    return _owned_student(request, student_id), Goal.SetBy.TUTOR


@login_required
def setup(request, student_id=None):
    student, set_by = _target_student(request, student_id)
    goal = active_goal(student)

    if request.method == "POST":
        form = GoalForm(request.POST, instance=goal)
        if form.is_valid():
            goal = form.save(commit=False)
            goal.student = student
            goal.is_active = True
            form.instance = goal
            form.save(set_by=set_by)
            whose = "Target" if student == request.user else f"{student.full_name}'s target"
            messages.success(request, f"{whose} saved — {goal.target_label}, "
                                      f"{goal.exam_date:%d %b %Y}.")
            if set_by == Goal.SetBy.TUTOR:
                return redirect("tutoring:student_detail", student_id=student.id)
            return redirect("practice:dashboard")
    else:
        form = GoalForm(instance=goal)

    return render(request, "goals/setup.html", {
        "form": form, "goal": goal, "student": student,
        "editing_other": student != request.user,
        "readiness": compute_readiness(student) if goal else None,
    })


@login_required
def detail(request):
    """The pupil's own full tracker page."""
    return render(request, "goals/detail.html", {
        "readiness": compute_readiness(request.user),
        "goal": active_goal(request.user),
    })


@login_required
def skip(request):
    """Dismiss onboarding for this session.

    Onboarding is a prompt, not a gate: a pupil who wants to try a few questions
    before committing to a school should be able to. The dashboard keeps showing
    a set-a-target card, so the nudge is not lost.
    """
    request.session["goal_prompt_skipped"] = True
    return redirect("practice:dashboard")
