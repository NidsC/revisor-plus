from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, F
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from analytics.readiness import compute_readiness
from analytics.services import compute_progress, compute_progress_many
from assignments.models import Assignment
from catalog.models import Subtopic
from vocab.services import adult_summary

from .models import TutorMessage, TutorStudent
from .permissions import owned_link, owned_student, require_tutor


@login_required
def dashboard(request):
    require_tutor(request)
    links = list(
        TutorStudent.objects.filter(tutor=request.user, active=True).select_related("student")
    )
    progress = compute_progress_many([link.student_id for link in links])
    open_hw = dict(
        Assignment.objects.filter(
            tutor=request.user, student_id__in=[link.student_id for link in links],
            status="assigned",
        ).order_by().values_list("student_id").annotate(n=Count("id"))
    )
    unread = dict(
        TutorMessage.objects.filter(
            link__in=links, sender_id=F("link__student__parent_id"), read_at__isnull=True,
        ).order_by().values_list("link_id").annotate(n=Count("id"))
    )
    roster = []
    for link in links:
        p = progress[link.student_id]
        roster.append({
            "student": link.student,
            "overall": p["overall"],
            "total": p["total"],
            "weakest": p["weak"][0] if p["weak"] else None,
            "open_hw": open_hw.get(link.student_id, 0),
            # Pass the progress we already have so readiness doesn't re-query it.
            "readiness": compute_readiness(link.student, progress=p),
            "unread_messages": unread.get(link.pk, 0),
        })
    # Worst first: the pupils a tutor needs to act on should not be buried at the
    # bottom of an alphabetical list.
    order = {"behind": 0, "at_risk": 1, "not_started": 2, "on_track": 3,
             "ready": 4, "exam_passed": 5, "no_goal": 6}
    roster.sort(key=lambda r: (order.get(r["readiness"]["status"], 9), -r["total"]))
    return render(request, "tutoring/tutor_dashboard.html", {"roster": roster})


@login_required
def student_detail(request, student_id):
    require_tutor(request)
    link = owned_link(request, student_id)
    student = link.student

    if request.method == "POST" and request.POST.get("action") == "send_parent_message":
        body = (request.POST.get("message") or "").strip()
        if not body:
            messages.error(request, "Write a message before sending.")
        elif len(body) > 2000:
            messages.error(request, "Messages can be up to 2,000 characters.")
        else:
            TutorMessage.objects.create(link=link, sender=request.user, body=body)
            messages.success(request, "Reply sent to the parent dashboard.")
        return HttpResponseRedirect(
            f"{reverse('tutoring:student_detail', args=[student.id])}#parent-messages"
        )

    TutorMessage.objects.filter(
        link=link,
        sender=student.parent,
        read_at__isnull=True,
    ).update(read_at=timezone.now())

    newest_messages = list(
        TutorMessage.objects
        .filter(link=link)
        .select_related("sender")
        .order_by("-created_at", "-id")[:60]
    )
    conversation = list(reversed(newest_messages))

    data = compute_progress(student)
    assignments = Assignment.with_progress(
        Assignment.objects.filter(student=student).select_related("subtopic", "tutor")
    )
    return render(request, "tutoring/student_detail.html", {
        "student": student, "data": data,
        "subtopics": Subtopic.objects.select_related("section").all(),
        "assignments": assignments,
        "readiness": compute_readiness(student, progress=data),
        "conversation": conversation,
        "wiz": adult_summary(student),
    })


@login_required
def assign_homework(request, student_id):
    require_tutor(request)
    student = owned_student(request, student_id)
    if request.method == "POST":
        subtopic = get_object_or_404(Subtopic, pk=request.POST.get("subtopic"))
        try:
            target_count = int(request.POST.get("target_count") or 5)
        except (TypeError, ValueError):
            target_count = 5
        target_count = max(1, min(target_count, 40))
        try:
            due_days = int(request.POST.get("due_days") or 5)
        except (TypeError, ValueError):
            due_days = 5
        due_days = max(1, min(due_days, 365))
        Assignment.objects.create(
            tutor=request.user, student=student, subtopic=subtopic,
            target_count=target_count,
            due_date=(timezone.now() + timedelta(days=due_days)).date(),
        )
        messages.success(request, f"Assigned '{subtopic.name}' to {student.full_name}.")
    return redirect("tutoring:student_detail", student_id=student.id)
