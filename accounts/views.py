from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import password_validation
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date

from analytics.readiness import compute_readiness
from analytics.services import compute_progress, compute_subject_summary
from assignments.models import Assignment
from billing.models import Subscription
from catalog.models import Subtopic
from tutoring.models import TutorMessage, TutorStudent

from .models import User


def _require_parent(request):
    if not request.user.is_parent:
        raise PermissionDenied("Parents only.")


def _owned_child(request, pupil_id):
    """Authorization boundary: a parent may only access their own children."""
    _require_parent(request)
    pupil = get_object_or_404(User, pk=pupil_id, role=User.Role.STUDENT)
    if pupil.parent_id != request.user.id:
        raise PermissionDenied("This child is not linked to your account.")
    return pupil


@login_required
def home(request):
    """List of a parent's children with plan status, and the add-child form."""
    _require_parent(request)

    children = (
        User.objects.filter(role=User.Role.STUDENT, parent=request.user)
        .select_related("subscription")
        .order_by("full_name", "username")
    )
    return render(request, "accounts/home.html", {"children": children})


@login_required
def add_child(request):
    """POST: display name, username, password.

    Creates a student user owned by the current parent, with no email
    (pupils never self-register and have no third-party identity), and a
    Subscription row so every pupil has one, exactly as seed_demo does.
    """
    _require_parent(request)
    if request.method != "POST":
        return redirect("family:home")

    full_name = (request.POST.get("full_name") or "").strip()
    username = (request.POST.get("username") or "").strip()
    password = request.POST.get("password") or ""

    errors = []
    if not full_name:
        errors.append("Enter the child's name.")
    if not username:
        errors.append("Choose a username.")
    elif User.objects.filter(username=username).exists():
        errors.append(f'The username "{username}" is already taken.')

    # Not User.objects.create_user(): its normalize_email() turns email=None
    # into "", and multiple pupils with "" collide on the unique constraint
    # where multiple NULLs would not.
    pupil = User(
        username=username,
        email=None,
        full_name=full_name,
        role=User.Role.STUDENT,
        parent=request.user,
    )

    if not errors:
        try:
            password_validation.validate_password(password, user=pupil)
        except ValidationError as exc:
            errors.extend(exc.messages)

    if errors:
        for error in errors:
            messages.error(request, error)
        return redirect("family:home")

    try:
        with transaction.atomic():
            pupil.set_password(password)
            pupil.save()
            Subscription.objects.get_or_create(user=pupil)
    except IntegrityError:
        messages.error(request, f'The username "{username}" is already taken.')
        return redirect("family:home")

    messages.success(request, f"{full_name} can now log in as {username}.")
    return redirect("family:home")


@login_required
def reset_child_password(request, pupil_id):
    pupil = _owned_child(request, pupil_id)
    if request.method != "POST":
        return redirect("family:child", pupil_id=pupil.id)

    password = request.POST.get("password") or ""
    try:
        password_validation.validate_password(password, user=pupil)
    except ValidationError as exc:
        for error in exc.messages:
            messages.error(request, error)
        return redirect("family:child", pupil_id=pupil.id)

    pupil.set_password(password)
    pupil.save(update_fields=["password"])
    messages.success(request, f"{pupil.full_name}'s password has been reset.")
    return redirect("family:child", pupil_id=pupil.id)


def _child_dashboard_action(request, pupil):
    """Handle parent actions on a child's dashboard without extra pages."""
    action = request.POST.get("action", "")

    if action == "send_tutor_message":
        tutor_link = (
            TutorStudent.objects
            .filter(student=pupil, active=True)
            .select_related("tutor")
            .order_by("created_at")
            .first()
        )
        if tutor_link is None:
            messages.error(request, "No tutor is linked to this account yet.")
            return HttpResponseRedirect(f"{reverse('family:child', args=[pupil.id])}#tutor-chat")

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

        return HttpResponseRedirect(f"{reverse('family:child', args=[pupil.id])}#tutor-chat")

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
            student=pupil,
            subtopic=subtopic,
            target_count=target_count,
            due_date=due_date,
        )
        messages.success(
            request,
            f"Homework added: {subtopic.name} · {target_count} questions."
        )
        return redirect("family:child", pupil_id=pupil.id)

    if action == "delete_homework":
        assignment = get_object_or_404(
            Assignment,
            pk=request.POST.get("assignment_id"),
            student=pupil,
            tutor=request.user,
            status=Assignment.Status.ASSIGNED,
        )
        assignment.delete()
        messages.success(request, "Parent-set homework removed.")
        return redirect("family:child", pupil_id=pupil.id)

    return None


def _child_subjects(pupil, data):
    """Per-subject summary with focus topics, for the parent-facing child page.

    Moved from practice/views.py dashboard (was `parent_subjects`, computed for
    the pupil dashboard's now-deleted "Parent summary" tab): the accuracy and
    topic breakdown per subject, ranked so the lowest-performing topics surface
    first. Prefer topics with at least three attempts; for a new pupil, fall
    back to whatever evidence exists so the panel remains useful instead of
    appearing broken.
    """
    progress_by_code = {s["code"]: s for s in data["sections"]}
    chip_codes = {"ENG": "EN", "MAT": "MA", "VR": "VR", "NVR": "NVR"}
    subjects = [
        dict({k: v for k, v in s.items() if k != "weekly_avg"},
             chip=chip_codes.get(s["code"], s["code"]),
             key=chip_codes.get(s["code"], s["code"]).lower())
        for s in compute_subject_summary(pupil)
    ]

    child_subjects = []
    for subject in subjects:
        code = subject["code"]
        section_progress = progress_by_code.get(code)
        topic_rows = [row.copy() for row in data["subtopics"] if row["section"] == code]
        evidenced = [row for row in topic_rows if row["total"] >= 3]
        ranked = sorted(evidenced or topic_rows, key=lambda row: (row["accuracy"], -row["total"]))
        for row in ranked:
            if row["total"] < 3:
                row["status"] = "Building data"
                row["status_key"] = "none"
            elif row["accuracy"] >= 75:
                row["status"] = "Strong"
                row["status_key"] = "good"
            elif row["accuracy"] >= 60:
                row["status"] = "Developing"
                row["status_key"] = "mid"
            else:
                row["status"] = "Needs focus"
                row["status_key"] = "low"
        focus_topics = ranked[:4]
        child_subjects.append({
            **subject,
            "accuracy": section_progress["accuracy"] if section_progress else None,
            "attempts": section_progress["total"] if section_progress else 0,
            "focus_topics": focus_topics,
            "primary_focus": focus_topics[0] if focus_topics else None,
        })
    order = {"MAT": 0, "ENG": 1, "VR": 2, "NVR": 3}
    child_subjects.sort(key=lambda subject: order.get(subject["code"], 99))
    return child_subjects


@login_required
def child(request, pupil_id):
    """Parent-facing progress, focus, per-subject summary and homework page
    for one child. Moved from the practice app's old pupil-side parent view,
    which used to render this to the pupil's own login."""
    pupil = _owned_child(request, pupil_id)

    if request.method == "POST":
        result = _child_dashboard_action(request, pupil)
        if result is not None:
            return result

    data = compute_progress(pupil)

    section_names = {section["code"]: section["name"] for section in data["sections"]}
    for weakness in data["weak"]:
        weakness["section_name"] = section_names.get(
            weakness["section"], weakness["section"]
        )

    assignments = Assignment.objects.filter(student=pupil).select_related(
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

    measured_sections = [s for s in data["sections"] if s["total"] > 0]
    strongest_section = max(measured_sections, key=lambda s: s["accuracy"], default=None)
    focus_section = min(measured_sections, key=lambda s: s["accuracy"], default=None)

    readiness = compute_readiness(pupil, progress=data)

    homework_subtopics = (
        Subtopic.objects
        .select_related("section")
        .order_by("section__order", "topic_order", "order", "name")
    )

    tomorrow = timezone.localdate() + timedelta(days=1)
    default_due = timezone.localdate() + timedelta(days=7)

    tutor_link = (
        TutorStudent.objects
        .filter(student=pupil, active=True)
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

    return render(
        request,
        "accounts/child.html",
        {
            "pupil": pupil,
            "data": data,
            "pending_assignments": pending_assignments,
            "parent_assignments": parent_assignments,
            "homework_count": len(pending_assignments),
            "section_by_code": {
                section["code"]: section for section in data["sections"]
            },
            "strongest_section": strongest_section,
            "focus_section": focus_section,
            "readiness": readiness,
            "overall_accuracy": data["overall"],
            "questions_done": data["total"],
            "child_subjects": _child_subjects(pupil, data),
            "homework_subtopics": homework_subtopics,
            "tomorrow": tomorrow,
            "default_due": default_due,
            "tutor_link": tutor_link,
            "tutor_conversation": tutor_conversation,
        },
    )
