"""
The vocab trainer's JSON API. The pupil pages and the later canvas game are
both clients of this; neither does any marking of its own.

    GET  /vocab/api/me/              the pupil's pack, XP, level and streak
    GET  /vocab/api/round/           the unfinished round, or {"round": null}
    POST /vocab/api/round/           start a round, or resume the unfinished one
                                     body: {"kind": "mixed"} (optional; the default)
    POST /vocab/api/answer/          answer one item
                                     body: {"item": <id>, "choice": 0-3}
    GET  /vocab/api/round/<id>/      a round with its answered items, and its
                                     result once finished

Rules every endpoint keeps:
  * JSON in both directions, errors included: {"error": code, "message": text}.
    Not logged in is 401, not a redirect to the login page, so a script can
    tell what happened.
  * Pupils only (403 for parents, tutors and admins). A pupil only ever sees
    their own rounds; anyone else's is 404, not 403, so ids reveal nothing.
  * An item's answer is never sent before that item is answered.
  * POSTs need the CSRF token in an X-CSRFToken header, as for any form here.
"""
import json
from functools import wraps

from django.http import JsonResponse
from billing.entitlements import vocab_allowed

from . import services
from .models import Round, RoundItem, VocabProfile

PROMPTS = {
    Round.Kind.SYNONYM: "Which word means the same as “{word}”?",
    Round.Kind.ODD_ONE_OUT: "Which word is the odd one out?",
    Round.Kind.GAP: "Which word best fills the gap?",
}


def error(status, code, message):
    return JsonResponse({"error": code, "message": message}, status=status)


class BadRequest(Exception):
    pass


def pupil_api(*methods):
    """Login, pupil-only and method checks, answered in JSON."""
    def decorate(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return error(401, "login_required", "Log in to use the trainer.")
            if not request.user.is_student:
                return error(403, "pupils_only", "The trainer is for pupils' own accounts.")
            if request.method not in methods:
                response = error(405, "method_not_allowed", f"Use {' or '.join(methods)}.")
                response["Allow"] = ", ".join(methods)
                return response
            try:
                return view(request, *args, **kwargs)
            except BadRequest as exc:
                return error(400, "bad_request", str(exc))
            except services.VocabUnavailable:
                return error(503, "unavailable", "The word lists are not available yet.")
        return wrapper
    return decorate


def body(request):
    if not request.body:
        return {}
    try:
        data = json.loads(request.body)
    except ValueError:
        raise BadRequest("The request body is not valid JSON.")
    if not isinstance(data, dict):
        raise BadRequest("The request body must be a JSON object.")
    return data


# --------------------------------------------------------------------------
# What the client sees
# --------------------------------------------------------------------------

def item_json(item):
    """One item. Its answer is included only once it has been answered."""
    data = {
        "id": item.pk,
        "number": item.position + 1,
        "kind": item.kind,
        "prompt": PROMPTS[item.kind].format(word=item.word.headword),
        # The word being asked about is shown only where that does not give
        # the answer away: in fill the gap it IS the answer, and in odd one
        # out it is one of the three that belong.
        "target": item.word.headword if item.kind == Round.Kind.SYNONYM else None,
        "sentence": item.word.gap_frame if item.kind == Round.Kind.GAP else None,
        "options": item.options,
        "answered": item.chosen_index is not None,
    }
    if item.chosen_index is not None:
        w = item.word
        data.update({
            "chosen_index": item.chosen_index,
            "answer_index": item.answer_index,
            "correct": item.correct,
            "word": {"headword": w.headword, "pos": w.pos, "definition": w.definition,
                     "synonyms": w.synonyms, "example": w.example},
        })
    return data


def round_json(round_):
    items = list(round_.items.select_related("word"))
    upcoming = next((i for i in items if i.chosen_index is None), None)
    return {
        "id": round_.pk,
        "kind": round_.kind,
        "pack": {"slug": round_.pack.slug, "title": round_.pack.title},
        "total": len(items),
        "answered": sum(i.chosen_index is not None for i in items),
        "correct": sum(bool(i.correct) for i in items),
        # XP earned so far: the final figure (with any perfect-round bonus)
        # comes in the finish summary.
        "xp": round_.xp_awarded if round_.finished_at else
              sum(bool(i.correct) for i in items) * services.XP_PER_CORRECT,
        # One entry per item, in order: true, false, or null if not answered.
        "progress": [i.correct if i.chosen_index is not None else None for i in items],
        "finished": round_.finished_at is not None,
        "item": item_json(upcoming) if upcoming else None,
    }


def own_round(request, round_id):
    return (Round.objects.select_related("pack")
            .filter(pk=round_id, pupil=request.user).first())


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------

@pupil_api("GET")
def me(request):
    return JsonResponse({**services.summary(request.user), "allowed": vocab_allowed(request.user)})


@pupil_api("GET", "POST")
def round_view(request):
    pupil = request.user
    if request.method == "GET":
        current = services.current_round(pupil)
        return JsonResponse({"round": round_json(current) if current else None})

    kind = body(request).get("kind", Round.Kind.MIXED)
    if kind not in Round.Kind.values:
        raise BadRequest(f"kind must be one of {', '.join(Round.Kind.values)}.")
    resuming = services.current_round(pupil)
    if not resuming and not vocab_allowed(pupil):
        return error(403, "not_allowed", "Rounds are not available on this account.")
    round_, resumed = services.start_round(pupil, kind=kind)
    return JsonResponse({"round": round_json(round_), "resumed": resumed},
                        status=200 if resumed else 201)


@pupil_api("POST")
def answer(request):
    data = body(request)
    item_id, choice = data.get("item"), data.get("choice")
    if type(item_id) is not int or type(choice) is not int:
        raise BadRequest("Send {\"item\": <item id>, \"choice\": <0-3>} as whole numbers.")
    if choice not in range(services.OPTIONS):
        raise BadRequest(f"choice must be 0-{services.OPTIONS - 1}.")
    try:
        result = services.answer_item(request.user, item_id, choice)
    except RoundItem.DoesNotExist:
        return error(404, "not_found", "No such question in your rounds.")
    item = result["item"]
    finished = result["finished"]
    round_ = Round.objects.select_related("pack").get(pk=item.round_id)
    return JsonResponse({
        "result": {**item_json(item), "already_answered": result["already_answered"]},
        "round": round_json(round_),
        "finished": finished,
    })


@pupil_api("GET")
def round_detail(request, round_id):
    round_ = own_round(request, round_id)
    if round_ is None:
        return error(404, "not_found", "No such round.")
    items = list(round_.items.select_related("word"))
    data = {
        "round": round_json(round_),
        "items": [item_json(i) for i in items if i.chosen_index is not None],
        "summary": None,
    }
    if round_.finished_at:
        profile = VocabProfile.objects.filter(pupil=request.user).first()
        data["summary"] = {
            "correct": sum(bool(i.correct) for i in items), "total": len(items),
            "xp": round_.xp_awarded, "total_xp": profile.xp if profile else 0,
            "level": services.level_for(profile.xp if profile else 0),
            "streak": services.streak_for(profile),
        }
    return JsonResponse(data)
