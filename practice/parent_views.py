import re
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date

from analytics.readiness import compute_readiness
from analytics.services import compute_progress
from assignments.models import Assignment
from catalog.models import Subtopic
from tutoring.models import TutorMessage, TutorStudent

from . import views


def _add_parent_nav(response):
    """Keep the Parent link visible in the shared top navigation."""
    if getattr(response, "status_code", None) != 200:
        return response

    content_type = response.get("Content-Type", "")
    if "text/html" not in content_type:
        return response

    charset = getattr(response, "charset", None) or "utf-8"
    html = response.content.decode(charset)

    if 'href="/parent/"' not in html:
        parent_link = '<a class="nav-link d-inline" href="/parent/">Parent</a>'
        html = re.sub(
            r'(<a[^>]*>\s*My target\s*</a>)',
            r"\1\n        " + parent_link,
            html,
            count=1,
            flags=re.IGNORECASE,
        )

    response.content = html.encode(charset)
    return response


@login_required
def dashboard(request):
    """
    Keep the student dashboard student-focused while preserving the original
    dashboard view and its existing data.
    """
    response = views.dashboard(request)

    if getattr(response, "status_code", None) != 200:
        return response

    content_type = response.get("Content-Type", "")
    if "text/html" not in content_type:
        return response

    charset = getattr(response, "charset", None) or "utf-8"
    html = response.content.decode(charset)

    # Remove only the old student/parent tab switch from the rendered dashboard.
    html = re.sub(
        r'\s*<div class="kid-dash__tabs"[^>]*>.*?</div>\s*',
        "\n",
        html,
        count=1,
        flags=re.DOTALL | re.IGNORECASE,
    )

    response.content = html.encode(charset)
    return _add_parent_nav(response)


def _parent_dashboard_action(request):
    """Handle parent actions without splitting the dashboard into extra pages."""
    action = request.POST.get("action", "")

    if action == "send_tutor_message":
        tutor_link = (
            TutorStudent.objects
            .filter(student=request.user, active=True)
            .select_related("tutor")
            .order_by("created_at")
            .first()
        )
        if tutor_link is None:
            messages.error(request, "No tutor is linked to this account yet.")
            return HttpResponseRedirect(f"{reverse('practice:parent_dashboard')}#tutor-chat")

        body = (request.POST.get("message") or "").strip()
        if not body:
            messages.error(request, "Write a message before sending.")
        elif len(body) > 2000:
            messages.error(request, "Messages can be up to 2,000 characters.")
        else:
            TutorMessage.objects.create(
                link=tutor_link,
                sender=request.user,
                body=body,
            )
            messages.success(request, f"Message sent to {tutor_link.tutor}.")

        return HttpResponseRedirect(f"{reverse('practice:parent_dashboard')}#tutor-chat")

    if action == "add_homework":
        subtopic = get_object_or_404(
            Subtopic.objects.select_related("section"),
            pk=request.POST.get("subtopic"),
        )

        try:
            target_count = int(request.POST.get("target_count") or 10)
        except (TypeError, ValueError):
            target_count = 10
        target_count = max(1, min(target_count, 40))

        due_date = parse_date(request.POST.get("due_date") or "")
        if due_date is None:
            due_date = (timezone.localdate() + timedelta(days=7))

        Assignment.objects.create(
            tutor=request.user,
            student=request.user,
            subtopic=subtopic,
            target_count=target_count,
            due_date=due_date,
        )
        messages.success(
            request,
            f"Homework added: {subtopic.name} · {target_count} questions."
        )
        return redirect("practice:parent_dashboard")

    if action == "delete_homework":
        assignment = get_object_or_404(
            Assignment,
            pk=request.POST.get("assignment_id"),
            student=request.user,
            tutor=request.user,
            status=Assignment.Status.ASSIGNED,
        )
        assignment.delete()
        messages.success(request, "Parent-set homework removed.")
        return redirect("practice:parent_dashboard")

    return None


@login_required
def parent_dashboard(request):
    """Dedicated parent-facing progress, focus and homework dashboard."""
    if request.method == "POST":
        result = _parent_dashboard_action(request)
        if result is not None:
            return result

    data = compute_progress(request.user)

    section_names = {section["code"]: section["name"] for section in data["sections"]}
    for weakness in data["weak"]:
        weakness["section_name"] = section_names.get(
            weakness["section"], weakness["section"]
        )

    assignments = Assignment.objects.filter(student=request.user).select_related(
        "subtopic", "subtopic__section", "tutor"
    )
    for assignment in assignments:
        assignment.refresh_status()
        assignment.done = assignment.progress_count()
        assignment.pct_done = (
            min(100, round(100 * assignment.done / assignment.target_count))
            if assignment.target_count
            else 100
        )

    pending_assignments = [
        assignment
        for assignment in assignments
        if assignment.status == Assignment.Status.ASSIGNED
    ]

    parent_assignments = [
        assignment for assignment in pending_assignments
        if assignment.tutor_id == request.user.id
    ]

    strongest_section = max(
        (section for section in data["sections"] if section["total"] > 0),
        key=lambda section: section["accuracy"],
        default=None,
    )

    readiness = compute_readiness(request.user, progress=data)

    homework_subtopics = (
        Subtopic.objects
        .select_related("section")
        .order_by("section__order", "topic_order", "order", "name")
    )

    tomorrow = timezone.localdate() + timedelta(days=1)
    default_due = timezone.localdate() + timedelta(days=7)

    tutor_link = (
        TutorStudent.objects
        .filter(student=request.user, active=True)
        .select_related("tutor")
        .order_by("created_at")
        .first()
    )
    tutor_conversation = []
    if tutor_link is not None:
        TutorMessage.objects.filter(
            link=tutor_link,
            read_at__isnull=True,
        ).exclude(sender=request.user).update(read_at=timezone.now())

        newest_messages = list(
            TutorMessage.objects
            .filter(link=tutor_link)
            .select_related("sender")
            .order_by("-created_at", "-id")[:60]
        )
        tutor_conversation = list(reversed(newest_messages))

    response = render(
        request,
        "practice/parent_dashboard.html",
        {
            "data": data,
            "pending_assignments": pending_assignments,
            "parent_assignments": parent_assignments,
            "homework_count": len(pending_assignments),
            "section_by_code": {
                section["code"]: section for section in data["sections"]
            },
            "strongest_section": strongest_section,
            "readiness": readiness,
            "overall_accuracy": data["overall"],
            "questions_done": data["total"],
            "homework_subtopics": homework_subtopics,
            "tomorrow": tomorrow,
            "default_due": default_due,
            "tutor_link": tutor_link,
            "tutor_conversation": tutor_conversation,
        },
    )
    return _add_parent_nav(response)
