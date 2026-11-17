"""The Terms agreement a parent or tutor gives: recorded on the user row, never only ticked."""
from django.utils import timezone

CURRENT_TERMS_VERSION = "1.0"


def record_acceptance(user, *, commit=True):
    user.terms_accepted_at = timezone.now()
    user.terms_version = CURRENT_TERMS_VERSION
    if commit:
        user.save(update_fields=["terms_accepted_at", "terms_version"])
    return user


def needs_acceptance(user):
    """Parents and tutors must have agreed to the current Terms; pupils never need to
    (the parent agrees on their behalf, Terms section 2)."""
    return user.role in (user.Role.PARENT, user.Role.TUTOR) and user.terms_version != CURRENT_TERMS_VERSION
