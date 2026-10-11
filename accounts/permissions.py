"""Who may act on whose account: the parent-side ownership guards, in one place.

Moved verbatim from accounts/views.py so billing/views.py (checkout, portal)
stops importing private names from a views module.
"""
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from .models import User


def require_parent(request):
    if not request.user.is_parent:
        raise PermissionDenied("Parents only.")


def owned_child(request, pupil_id):
    """Authorization boundary: a parent may only access their own children."""
    require_parent(request)
    pupil = get_object_or_404(User, pk=pupil_id, role=User.Role.STUDENT)
    if pupil.parent_id != request.user.id:
        raise PermissionDenied("This child is not linked to your account.")
    return pupil
