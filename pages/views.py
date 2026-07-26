from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render


def landing(request):
    return render(request, "pages/landing.html")


@login_required
def after_login(request):
    """Route users to the right home by role."""
    u = request.user
    if u.is_superuser or u.role == u.Role.ADMIN:
        return redirect("/admin/")
    if u.is_tutor:
        return redirect("tutoring:dashboard")
    # A pupil with no target lands on goal setup first — the tracker is the point
    # of the product, and it cannot say anything useful without one. Deliberately
    # a prompt and not a gate: setup is skippable, and the dashboard keeps a
    # set-a-target card visible afterwards.
    if not request.session.get("goal_prompt_skipped"):
        from analytics.readiness import active_goal

        if active_goal(u) is None:
            return redirect("goals:setup")
    return redirect("practice:dashboard")
