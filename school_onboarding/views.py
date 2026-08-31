from __future__ import annotations

import json
import math
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Case, IntegerField, Q, Value, When
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .models import School, SchoolOnboardingState, StudentTargetSchool
from .postcodes import PostcodeLookupError, bulk_lookup, lookup_postcode, normalise_postcode

RESULT_LIMIT = 30
NEARBY_RADIUS_METRES = 60_000


def _school_payload(school: School, distance_km: float | None = None) -> dict:
    return {
        "id": school.id,
        "urn": school.urn,
        "name": school.name,
        "postcode": school.postcode,
        "town": school.town,
        "county": school.county,
        "type": school.establishment_type,
        "admissions_policy": school.admissions_policy,
        "gender": school.gender,
        "phase": school.phase,
        "latitude": school.latitude,
        "longitude": school.longitude,
        "distance_km": round(distance_km, 1) if distance_km is not None else None,
    }


def _cache_lat_lng(schools: list[School]) -> None:
    missing = [s for s in schools if s.postcode and (s.latitude is None or s.longitude is None)]
    if not missing:
        return

    try:
        lookup = bulk_lookup([s.postcode for s in missing])
    except PostcodeLookupError:
        return

    updates = []
    for school in missing:
        point = lookup.get(normalise_postcode(school.postcode))
        if not point:
            continue
        lat = point.get("latitude")
        lng = point.get("longitude")
        if lat is None or lng is None:
            continue
        school.latitude = float(lat)
        school.longitude = float(lng)
        updates.append(school)

    if updates:
        School.objects.bulk_update(updates, ["latitude", "longitude"])


def _default_return_url(request) -> str:
    candidate = request.GET.get("next") or request.session.get("school_onboarding_next")
    if candidate and isinstance(candidate, str) and candidate.startswith("/") and not candidate.startswith("//"):
        return candidate
    return "/"


@login_required
@require_GET
def onboarding(request):
    if request.user.is_staff or request.user.is_superuser:
        return redirect("/")

    state, _ = SchoolOnboardingState.objects.get_or_create(user=request.user)
    if request.GET.get("reset") != "1" and state.is_finished:
        return redirect(_default_return_url(request))

    if request.GET.get("next"):
        request.session["school_onboarding_next"] = _default_return_url(request)

    selections = list(
        School.objects.filter(student_targets__user=request.user)
        .distinct()
        .order_by("student_targets__created_at", "name")
    )
    _cache_lat_lng(selections)

    context = {
        "initial_schools_json": json.dumps([_school_payload(s) for s in selections]),
        "last_postcode": state.last_postcode,
        "search_url": reverse("school_onboarding:search"),
        "save_url": reverse("school_onboarding:save"),
        "skip_url": reverse("school_onboarding:skip"),
        "next_url": _default_return_url(request),
    }
    return render(request, "school_onboarding/onboarding.html", context)


@login_required
@require_GET
def search_schools(request):
    query = (request.GET.get("q") or "").strip()
    postcode = (request.GET.get("postcode") or "").strip()

    if postcode:
        return _search_by_postcode(postcode)
    if len(query) < 2:
        return JsonResponse({"schools": [], "message": "Type at least 2 characters."})

    qs = (
        School.objects.filter(status__iexact="Open")
        .filter(
            Q(name__icontains=query)
            | Q(postcode__icontains=query)
            | Q(town__icontains=query)
            | Q(urn__icontains=query)
        )
        .annotate(
            match_rank=Case(
                When(name__iexact=query, then=Value(0)),
                When(name__istartswith=query, then=Value(1)),
                When(postcode__iexact=normalise_postcode(query), then=Value(2)),
                default=Value(3),
                output_field=IntegerField(),
            )
        )
        .order_by("match_rank", "name")[:RESULT_LIMIT]
    )
    schools = list(qs)
    _cache_lat_lng(schools)
    return JsonResponse({"schools": [_school_payload(s) for s in schools]})


def _search_by_postcode(postcode: str):
    try:
        location = lookup_postcode(postcode)
    except PostcodeLookupError as exc:
        return JsonResponse({"schools": [], "error": str(exc)}, status=400)

    easting = location.get("eastings")
    northing = location.get("northings")
    if easting is None or northing is None:
        return JsonResponse(
            {"schools": [], "error": "We found the postcode but could not map its location."},
            status=400,
        )

    # Use a bounding box in British National Grid metres first, then calculate
    # exact straight-line distance in Python. This stays database-agnostic.
    candidates = list(
        School.objects.filter(
            status__iexact="Open",
            easting__isnull=False,
            northing__isnull=False,
            easting__gte=int(easting) - NEARBY_RADIUS_METRES,
            easting__lte=int(easting) + NEARBY_RADIUS_METRES,
            northing__gte=int(northing) - NEARBY_RADIUS_METRES,
            northing__lte=int(northing) + NEARBY_RADIUS_METRES,
        )
    )

    ranked = []
    for school in candidates:
        dx = school.easting - int(easting)
        dy = school.northing - int(northing)
        distance_m = math.sqrt(dx * dx + dy * dy)
        if distance_m <= NEARBY_RADIUS_METRES:
            ranked.append((distance_m, school))

    ranked.sort(key=lambda pair: (pair[0], pair[1].name.lower()))
    ranked = ranked[:RESULT_LIMIT]
    schools = [school for _, school in ranked]
    _cache_lat_lng(schools)

    by_id = {school.id: school for school in schools}
    payload = [
        _school_payload(by_id[school.id], distance_m / 1000)
        for distance_m, school in ranked
        if school.id in by_id
    ]

    return JsonResponse(
        {
            "schools": payload,
            "postcode": normalise_postcode(postcode),
            "centre": {
                "latitude": location.get("latitude"),
                "longitude": location.get("longitude"),
            },
        }
    )


@login_required
@require_POST
def save_selection(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid request."}, status=400)

    raw_ids = payload.get("school_ids") or []
    if not isinstance(raw_ids, list):
        return JsonResponse({"error": "Invalid school selection."}, status=400)

    try:
        school_ids = list(dict.fromkeys(int(value) for value in raw_ids))
    except (TypeError, ValueError):
        return JsonResponse({"error": "Invalid school selection."}, status=400)

    if not school_ids:
        return JsonResponse({"error": "Choose at least one school to continue."}, status=400)
    if len(school_ids) > 20:
        return JsonResponse({"error": "You can choose up to 20 schools."}, status=400)

    valid_ids = set(School.objects.filter(id__in=school_ids, status__iexact="Open").values_list("id", flat=True))
    if len(valid_ids) != len(school_ids):
        return JsonResponse({"error": "One or more selected schools are unavailable."}, status=400)

    postcode = normalise_postcode(str(payload.get("postcode") or ""))[:12]
    with transaction.atomic():
        StudentTargetSchool.objects.filter(user=request.user).exclude(school_id__in=valid_ids).delete()
        existing = set(
            StudentTargetSchool.objects.filter(user=request.user, school_id__in=valid_ids)
            .values_list("school_id", flat=True)
        )
        StudentTargetSchool.objects.bulk_create(
            [
                StudentTargetSchool(user=request.user, school_id=school_id)
                for school_id in school_ids
                if school_id not in existing
            ],
            ignore_conflicts=True,
        )
        state, _ = SchoolOnboardingState.objects.get_or_create(user=request.user)
        state.completed_at = timezone.now()
        state.skipped_at = None
        state.last_postcode = postcode
        state.save(update_fields=["completed_at", "skipped_at", "last_postcode", "updated_at"])

    redirect_url = payload.get("next") or "/"
    if not isinstance(redirect_url, str) or not redirect_url.startswith("/") or redirect_url.startswith("//"):
        redirect_url = "/"
    request.session.pop("school_onboarding_next", None)
    return JsonResponse({"ok": True, "redirect": redirect_url})


@login_required
@require_POST
def skip_onboarding(request):
    state, _ = SchoolOnboardingState.objects.get_or_create(user=request.user)
    state.skipped_at = timezone.now()
    state.completed_at = None
    state.save(update_fields=["skipped_at", "completed_at", "updated_at"])
    request.session.pop("school_onboarding_next", None)
    return JsonResponse({"ok": True, "redirect": "/"})
