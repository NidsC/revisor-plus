from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import password_validation
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.http import url_has_allowed_host_and_scheme

from analytics.readiness import compute_readiness
from analytics.services import compute_progress, compute_subject_detail, subject_cards
from assignments.models import Assignment
from billing.entitlements import (
    FREE_QUESTIONS_PER_PAPER,
    free_questions_used_by_section,
    is_premium,
)
from billing.models import ReferralReward, Subscription
from billing.status import plan_status, stripe_ready
from billing.views import format_price_gbp
from catalog.models import Section, Subtopic
from tutoring.models import TutorMessage, TutorStudent
from vocab.services import summary as vocab_summary

from .consent import record_acceptance
from .forms import AcceptTermsForm
from .models import User
from .permissions import owned_child, require_parent


@login_required
def accept_terms(request):
    """Parents and tutors from before the Terms were published agree once, here, before
    they can subscribe (billing.views.checkout sends them). Pupils never agree: the parent does."""
    if request.user.is_student:
        return redirect("practice:dashboard")
    form = AcceptTermsForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        record_acceptance(request.user)
        messages.success(request, "Thank you. You have agreed to the Terms of Service.")
        next_url = request.POST.get("next") or request.GET.get("next") or ""
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
            return HttpResponseRedirect(next_url)
        return redirect("tutoring:dashboard" if request.user.is_tutor else "family:home")
    return render(request, "accounts/accept_terms.html", {"form": form, "next": request.GET.get("next", "")})


@login_required
def home(request):
    """List of a parent's children with plan status and the demand signal
    [C-4], and the add-child form."""
    require_parent(request)

    children = list(
        User.objects.filter(role=User.Role.STUDENT, parent=request.user)
        .select_related("subscription")
        .order_by("full_name", "username")
    )
    sections = list(Section.objects.all())
    used = None  # one grouped query for every child, fetched only if someone is non-premium
    child_rows = []
    paying = False
    for pupil in children:
        sub = getattr(pupil, "subscription", None)
        if sub is not None and sub.status == Subscription.Status.ACTIVE and sub.payer_id == request.user.id:
            paying = True
        demand = []
        if not is_premium(pupil, subscription=sub):
            if used is None:
                used = free_questions_used_by_section([c.pk for c in children])
            for section in sections:
                if used.get((pupil.pk, section.pk), 0) >= FREE_QUESTIONS_PER_PAPER:
                    demand.append(f"Used all {FREE_QUESTIONS_PER_PAPER} free {section.name} answers")
            if sub and sub.last_mock_blocked_at:
                demand.append(f"Tried a mock paper on {sub.last_mock_blocked_at:%-d %b}")
            demand = demand[:2]
        child_rows.append({"pupil": pupil, "status": plan_status(sub), "demand": demand,
                           "wiz": vocab_summary(pupil),
                           "setup_needed": not pupil.has_usable_password()})

    # getattr with a default: the reverse one-to-one raises a DoesNotExist (an AttributeError) when absent.
    referral = getattr(request.user, "referral", None)
    referral_granted = (
        referral.rewards.filter(status=ReferralReward.Status.GRANTED).count() if referral is not None else 0
    )
    friend_discount = settings.REFERRAL_FRIEND_DISCOUNT_GBP
    referral_link = f"{settings.SITE_URL.rstrip('/')}/offer/{referral.code}/" if referral is not None else ""
    return render(request, "accounts/home.html", {
        "children": child_rows,
        "stripe_ready": stripe_ready(),
        "referral_enabled": settings.REFERRAL_ENABLED and (paying or referral is not None),
        "referral": referral,
        "referral_link": referral_link,
        "referral_granted": referral_granted,
        "referral_cap": settings.REFERRAL_CAP_PER_YEAR,
        "friend_discount": friend_discount,
        "credit": format_price_gbp(settings.STRIPE_PRICE_GBP),
        "referral_share_text": (
            f"Try RevisorPlus for 11+ practice — my code gives you {friend_discount} "
            f"off the first month: {referral_link}"
        ),
    })


def validate_child_fields(full_name, username, password, pupil):
    """The error messages for a child's nickname, username and password, in the order the
    add-child form has always shown them. `pupil` is the unsaved (or placeholder) row, so
    the username check skips its own pk (None on a new row) and the password validators
    can compare against it."""
    errors = []
    if not full_name:
        errors.append("Enter the child's name.")
    if not username:
        errors.append("Choose a username.")
    elif User.objects.filter(username=username).exclude(pk=pupil.pk).exists():
        errors.append(f'The username "{username}" is already taken.')

    if not errors:
        try:
            password_validation.validate_password(password, user=pupil)
        except ValidationError as exc:
            errors.extend(exc.messages)
    return errors


def create_placeholder_pupil(parent):
    """The child row the offer funnel creates before payment so Stripe has a pupil to
    attach the subscription to. The parent names it and sets its password afterwards
    (setup_child); until then it has an unusable password and cannot log in."""
    n = 1
    username = f"child-{parent.pk}"
    while User.objects.filter(username=username).exists():
        n += 1
        username = f"child-{parent.pk}-{n}"
    pupil = User(
        username=username,
        email=None,
        full_name="Your child",
        role=User.Role.STUDENT,
        parent=parent,
    )
    pupil.set_unusable_password()
    pupil.save()
    Subscription.objects.get_or_create(user=pupil)
    return pupil


@login_required
def setup_child(request, pupil_id):
    """Finish a funnel placeholder pupil: nickname, username and password, once."""
    pupil = owned_child(request, pupil_id)
    if pupil.has_usable_password():
        raise Http404
    if request.method != "POST":
        # The pixel is on this page (the parent's, before the pupil has a password) and fires the
        # queued Purchase once: offer_success left it in the session only for a consenting parent.
        return render(request, "accounts/setup_child.html", {
            "pupil": pupil, "errors": [], "values": {},
            "track_pixel": True, "meta_events": request.session.pop("meta_events", None) or [],
        })

    full_name = (request.POST.get("full_name") or "").strip()
    username = (request.POST.get("username") or "").strip()
    password = request.POST.get("password") or ""
    pupil.full_name = full_name
    pupil.username = username
    errors = validate_child_fields(full_name, username, password, pupil)
    if not errors:
        try:
            with transaction.atomic():
                pupil.set_password(password)
                pupil.save()
        except IntegrityError:
            errors.append(f'The username "{username}" is already taken.')
    if errors:
        return render(request, "accounts/setup_child.html", {
            "pupil": pupil, "errors": errors, "values": {"full_name": full_name, "username": username},
            "track_pixel": True,
        })
    return render(request, "accounts/setup_child_done.html", {"pupil": pupil, "track_pixel": True})


@login_required
def add_child(request):
    """POST: nickname (display name), username, password.

    Creates a student user owned by the current parent, with no email
    (pupils never self-register and have no third-party identity), and a
    Subscription row so every pupil has one, exactly as seed_demo does.
    """
    require_parent(request)
    if request.method != "POST":
        return redirect("family:home")

    full_name = (request.POST.get("full_name") or "").strip()
    username = (request.POST.get("username") or "").strip()
    password = request.POST.get("password") or ""

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
    errors = validate_child_fields(full_name, username, password, pupil)

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
    pupil = owned_child(request, pupil_id)
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


def _child_dashboard_action(request, pupil, parent_page="overview"):
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
            return redirect('family:child_messages', pupil_id=pupil.id)

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

        return redirect('family:child_messages', pupil_id=pupil.id)

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
        return redirect("family:child_homework", pupil_id=pupil.id)

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
        return redirect("family:child_homework", pupil_id=pupil.id)

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
    subjects = subject_cards(pupil)

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
def child(request, pupil_id, parent_page="overview"):
    """Parent-facing progress, focus, per-subject summary and homework page
    for one child. Moved from the practice app's old pupil-side parent view,
    which used to render this to the pupil's own login."""
    pupil = owned_child(request, pupil_id)
    premium = is_premium(pupil)
    if parent_page not in {"overview", "subjects", "homework", "messages"}:
        parent_page = "overview"

    if request.method == "POST":
        result = _child_dashboard_action(request, pupil, parent_page)
        if result is not None:
            return result

    data = compute_progress(pupil)

    section_names = {section["code"]: section["name"] for section in data["sections"]}
    for weakness in data["weak"]:
        weakness["section_name"] = section_names.get(
            weakness["section"], weakness["section"]
        )

    assignments = Assignment.with_progress(
        Assignment.objects.filter(student=pupil).select_related(
            "subtopic", "subtopic__section", "tutor"
        )
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
    if tutor_link is not None and parent_page == "messages":
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
            "parent_page": parent_page,
            "premium": premium,
            "stripe_ready": stripe_ready(),
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
            "wiz": vocab_summary(pupil),
        },
    )


@login_required
def child_subject(request, pupil_id, code):
    """Show the selected child's progress without starting a pupil session."""
    pupil = owned_child(request, pupil_id)
    if not is_premium(pupil):
        messages.info(request, "Detailed subject progress is part of Premium.")
        return redirect("family:child", pupil_id=pupil.id)
    section = get_object_or_404(Section, code=code.upper())
    context = compute_subject_detail(pupil, section)
    context.update({
        "pupil": pupil, "read_only": True, "premium": True,
        "free_left": None,
        "back_url": reverse("family:child_subjects", args=[pupil.id]),
        "back_label": f"← {pupil.full_name or pupil.username}'s dashboard",
    })
    return render(request, "practice/subject.html", context)
