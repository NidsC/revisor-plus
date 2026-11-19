from django.conf import settings

from .consent import consent_choice


def consent(request):
    """Cookie-choice facts for base.html. Adding them to every template is harmless: base.html
    renders the pixel and the banner only for views that set `track_pixel` (the public pages and
    the parent's funnel pages), so a pupil's pages never carry either."""
    choice = consent_choice(request)
    return {
        "consent_yes": choice == "yes",
        "consent_choice": choice,
        "meta_pixel_id": settings.META_PIXEL_ID,
        "meta_enabled": settings.META_ENABLED,
    }
