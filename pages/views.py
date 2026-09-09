from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.shortcuts import redirect, render


def landing_stats():
    """Live figures for the pricing page.

    Counted from the database rather than typed into the template. The previous
    landing page and the pricing page both advertised a "20,000+ question bank"
    that was never true of this product; a number that can go stale by being
    copied is a number that eventually lies.

    Named for the landing page, which is where it started and which no longer
    shows any of it — the redesign has no stats card. billing.views.pricing is
    the only caller now. Kept cached anyway: it counts the whole question bank.
    """
    stats = cache.get("landing_stats")
    if stats is None:
        from catalog.models import Question, Section, Subtopic
        from goals.models import School

        answerable = (Question.objects
                      .filter(active=True, parts__isnull=True)
                      .exclude(marking=Question.Marking.RUBRIC))
        stats = {
            "questions": answerable.count(),
            "subtopics": Subtopic.objects.count(),
            "papers": Section.objects.count(),
            "bands": answerable.values("difficulty").distinct().count(),
            "schools": School.objects.count(),
        }
        cache.set("landing_stats", stats, 300)
    return stats


# How many target schools the landing page lists. The section is a sample, not
# a directory — "Find a school" goes to the real chooser.
LANDING_SCHOOLS = 6


def landing(request):
    """The public landing page.

    The school list is read from the database rather than typed into the
    template, for the same reason landing_stats() exists: these are real
    schools, and a hardcoded admissions detail next to a real school's name is
    a claim that goes stale silently. goals.models.School is explicit that its
    seeded assessment details are unchecked until someone verifies them, so the
    template carries the same "not yet verified" note goals/detail.html does
    whenever an unverified row is on show.

    `stats`, `price_gbp` and `track_roadmap` are gone: the template rendered
    none of the three, and the redesign has no stats card, no price and no
    roadmap. landing_stats() itself stays — billing.views imports it for the
    pricing page.
    """
    from goals.models import School

    schools = list(
        School.objects.filter(active=True).order_by("area", "name")[:LANDING_SCHOOLS]
    )
    return render(request, "pages/landing.html", {
        "schools": schools,
        "schools_unverified": any(not s.verified for s in schools),
    })


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
