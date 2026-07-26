from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.shortcuts import redirect, render


def landing_stats():
    """Live figures for the landing page.

    Counted from the database rather than typed into the template. The previous
    landing page and the pricing page both advertised a "20,000+ question bank"
    that was never true of this product; a number that can go stale by being
    copied is a number that eventually lies. Cached briefly because this is the
    one page anonymous traffic hits.
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


# The exams the same engine is intended to cover next. Rendered as explicitly
# "in development" cards: they ship no content and no Section rows, so the page
# must never imply a pupil could start one today.
TRACK_ROADMAP = [
    ("GCSE", "Core subjects, same targets-and-tracking engine."),
    ("A-level", "Subject papers with grade boundaries as the target."),
    ("UCAT", "Medical admissions — the platform this one was forked from."),
]


def landing(request):
    return render(request, "pages/landing.html", {
        "stats": landing_stats(),
        "price_gbp": int(settings.STRIPE_PRICE_GBP) / 100,
        "track_roadmap": TRACK_ROADMAP,
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
