"""The advertising-cookie choice: one cookie, "yes" or "no", set from the banner or /consent/.

Nothing optional is set, loaded or sent until the cookie says yes. The cookie is readable by
the page (httponly False) because the templates read it; the Meta pixel itself never does.
"""
from django.conf import settings

CONSENT_COOKIE = settings.CONSENT_COOKIE
CHOICES = ("yes", "no")


def consent_choice(request):
    """The stored choice: "yes", "no", or "" when none has been made (or the value is junk)."""
    value = request.COOKIES.get(CONSENT_COOKIE, "")
    return value if value in CHOICES else ""


def set_consent(response, choice):
    response.set_cookie(
        CONSENT_COOKIE, choice,
        max_age=settings.CONSENT_MAX_AGE, samesite="Lax",
        secure=not settings.DEBUG, httponly=False,
    )
    return response
