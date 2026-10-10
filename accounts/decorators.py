from functools import wraps

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def pupils_only(view):
    """Logged-in pupils only; anyone else goes to their own home page.

    Explicit, and shared: practice and Word Wizard both gate their pages with it.
    """
    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_student:
            return redirect("after_login")
        return view(request, *args, **kwargs)
    return wrapper
