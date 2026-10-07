"""
Word Wizard's pages. Thin on purpose: every number comes from
services.summary, and the play page does all its work through the JSON API
in vocab/api.py, the same one the later canvas game will use.
"""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie

from billing.entitlements import vocab_allowed

from . import services
from .models import Round

NAME = "Word Wizard"
PREMISE = "Answer ten words a round, earn XP, and level up from Apprentice to Grand Wizard."

# The round types a pupil can choose, in the order the home page offers them.
# Mixed is first and is what "Play" starts, so a child who just hits play gets
# variety.
CHOICES = [
    (Round.Kind.MIXED, "Mixed", "A bit of everything"),
    (Round.Kind.SYNONYM, "Synonym match", "Find the word that means the same"),
    (Round.Kind.ODD_ONE_OUT, "Odd one out", "Spot the word that doesn't belong"),
    (Round.Kind.GAP, "Fill the gap", "Pick the word that fits the sentence"),
]


def pupils_only(view):
    """Logged-in pupils only; anyone else goes to their own home page.

    Explicit, unlike practice's views, which check only for a login.
    """
    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_student:
            return redirect("after_login")
        return view(request, *args, **kwargs)
    return wrapper


@pupils_only
def home(request):
    return render(request, "vocab/home.html", {
        "name": NAME, "premise": PREMISE,
        "wiz": services.summary(request.user),
        "choices": CHOICES,
        "allowed": vocab_allowed(request.user),
    })


@pupils_only
@ensure_csrf_cookie
def play(request):
    """The page play.js runs in. ensure_csrf_cookie because the page has no form:
    without it a pupil whose browser lacks a csrftoken cookie gets a CSRF 403
    on their first answer."""
    kind = request.GET.get("kind", Round.Kind.MIXED)
    if kind not in Round.Kind.values:
        kind = Round.Kind.MIXED
    return render(request, "vocab/play.html", {"name": NAME, "kind": kind})
