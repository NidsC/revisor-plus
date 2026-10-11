"""Who may act on whose account: the tutor-side ownership guards, in one place.

Moved verbatim from tutoring/views.py so goals/views.py stops importing
private names from a views module.
"""
from django.core.exceptions import PermissionDenied

from .models import TutorStudent


def require_tutor(request):
    if not request.user.is_tutor:
        raise PermissionDenied("Tutors only.")


def owned_link(request, student_id):
    """Authorization boundary: a tutor may only access their own students."""
    link = TutorStudent.objects.filter(
        tutor=request.user, student_id=student_id, active=True
    ).select_related("student").first()
    if not link:
        raise PermissionDenied("This student is not linked to you.")
    return link


def owned_student(request, student_id):
    return owned_link(request, student_id).student
