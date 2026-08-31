from django.conf import settings
from django.db import OperationalError, ProgrammingError
from django.shortcuts import redirect
from django.urls import NoReverseMatch, reverse
from urllib.parse import urlencode

from .models import School, SchoolOnboardingState


class SchoolOnboardingMiddleware:
    """Redirect signed-in students to school onboarding until handled once.

    Place this AFTER django.contrib.auth.middleware.AuthenticationMiddleware.
    Staff/superusers are ignored. The redirect activates only after at least one
    School has been imported, so deploying the code cannot lock users out.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated or user.is_staff or user.is_superuser:
            return self.get_response(request)

        path = request.path
        exempt_prefixes = list(
            getattr(
                settings,
                "SCHOOL_ONBOARDING_EXEMPT_PREFIXES",
                ["/admin/", "/accounts/", "/static/", "/media/", "/logout/"],
            )
        )

        try:
            onboarding_path = reverse("school_onboarding:onboarding")
            onboarding_prefix = onboarding_path.rstrip("/") + "/"
            if path == onboarding_path or path.startswith(onboarding_prefix):
                return self.get_response(request)
        except NoReverseMatch:
            return self.get_response(request)

        if any(path.startswith(prefix) for prefix in exempt_prefixes):
            return self.get_response(request)

        try:
            if not School.objects.exists():
                return self.get_response(request)
            state = SchoolOnboardingState.objects.filter(user=user).first()
        except (OperationalError, ProgrammingError):
            # Migrations may not have run yet during first deployment.
            return self.get_response(request)

        if state and state.is_finished:
            return self.get_response(request)

        next_path = request.get_full_path()
        request.session["school_onboarding_next"] = next_path
        return redirect(f"{onboarding_path}?{urlencode({'next': next_path})}")
