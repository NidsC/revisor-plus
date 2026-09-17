from django.conf import settings

from .entitlements import is_premium


def subscription_flags(request):
    """Expose {{ is_subscribed }} and {{ premium_gates_enabled }} to all
    templates. `is_subscribed` means "is this pupil Premium" for a pupil, or
    "does any child have Premium" for a parent — the nav badge these feed is
    a single yes/no, not a per-pupil detail.
    """
    is_subscribed = False
    user = request.user
    if user.is_authenticated:
        if user.is_student:
            is_subscribed = is_premium(user)
        elif user.is_parent:
            is_subscribed = any(is_premium(child) for child in user.children.all())
    return {
        "is_subscribed": is_subscribed,
        "premium_gates_enabled": settings.PREMIUM_GATES_ENABLED,
    }
