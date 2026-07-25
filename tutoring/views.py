from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from analytics.services import compute_progress
from assignments.models import Assignment
from catalog.models import Subtopic

from .models import TutorStudent


def _require_tutor(request):
    if not request.user.is_tutor:
        raise PermissionDenied("Tutors only.")


def _owned_student(request, student_id):
    """Authorization boundary: a tutor may only access their own students."""
    link = TutorStudent.objects.filter(
        tutor=request.user, student_id=student_id, active=True
    ).select_related("student").first()
    if not link:
        raise PermissionDenied("This student is not linked to you.")
    return link.student


@login_required
def dashboard(request):
    _require_tutor(request)
    links = TutorStudent.objects.filter(tutor=request.user, active=True).select_related("student")
    roster = []
    for link in links:
        p = compute_progress(link.student)
        roster.append({
            "student": link.student,
            "overall": p["overall"],
            "total": p["total"],
            "weakest": p["weak"][0] if p["weak"] else None,
            "open_hw": Assignment.objects.filter(
                tutor=request.user, student=link.student, status="assigned"
            ).count(),
        })
    return render(request, "tutoring/tutor_dashboard.html", {"roster": roster})


@login_required
def student_detail(request, student_id):
    _require_tutor(request)
    student = _owned_student(request, student_id)
    data = compute_progress(student)
    assignments = Assignment.objects.filter(student=student).select_related("subtopic")
    for a in assignments:
        a.refresh_status()
        a.done = a.progress_count()
    return render(request, "tutoring/student_detail.html", {
        "student": student, "data": data,
        "subtopics": Subtopic.objects.select_related("section").all(),
        "assignments": assignments,
    })


@login_required
def assign_homework(request, student_id):
    _require_tutor(request)
    student = _owned_student(request, student_id)
    if request.method == "POST":
        subtopic = get_object_or_404(Subtopic, pk=request.POST.get("subtopic"))
        Assignment.objects.create(
            tutor=request.user, student=student, subtopic=subtopic,
            target_count=int(request.POST.get("target_count") or 5),
            due_date=(timezone.now() + timedelta(days=int(request.POST.get("due_days") or 5))).date(),
        )
        messages.success(request, f"Assigned '{subtopic.name}' to {student.full_name}.")
    return redirect("tutoring:student_detail", student_id=student.id)
