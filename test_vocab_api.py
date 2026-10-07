"""
Checks the vocab trainer's JSON API (vocab/api.py) through real HTTP requests.

Run:  python main.py load_vocab
      python main.py shell < test_vocab_api.py

The API is what the pupil pages and the later canvas game are built on, so
this pins its contract: who may call it, the shape of every response, that an
answer never reaches the client before the pupil commits, and that a double
submit scores once.

Every case runs inside a transaction that is always rolled back.
"""
import json
import logging
import sys
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import Client
from django.test.utils import setup_test_environment

from vocab.models import Round, RoundItem, VocabProfile, WordPack

# Lets the test client's "testserver" host through ALLOWED_HOSTS.
setup_test_environment()
# Every 4xx this script provokes on purpose would otherwise print a warning.
logging.getLogger("django.request").setLevel(logging.ERROR)

fails = []


def ck(label, cond, extra=""):
    print(f"  [{'OK  ' if cond else 'FAIL'}] {label}" + (f" — {extra}" if extra else ""))
    if not cond:
        fails.append(label)


class Rollback(Exception):
    pass


def case(fn):
    try:
        with transaction.atomic():
            fn()
            raise Rollback
    except Rollback:
        pass
    return fn


User = get_user_model()
_n = [0]


def user(role=User.Role.STUDENT):
    _n[0] += 1
    return User.objects.create_user(username=f"vocabapi_{_n[0]}", email=f"vocabapi_{_n[0]}@x.test",
                                    password="x", role=role)


def client_for(u, csrf=False):
    c = Client(enforce_csrf_checks=csrf)
    c.force_login(u)
    return c


def post(c, url, data=None, **extra):
    return c.post(url, json.dumps(data) if data is not None else "",
                  content_type="application/json", **extra)


ME, ROUND, ANSWER = "/vocab/api/me/", "/vocab/api/round/", "/vocab/api/answer/"


def detail(rid):
    return f"/vocab/api/round/{rid}/"


def play_out(c, start_kind="mixed"):
    """Start a round and answer every item right. Returns the last response JSON."""
    data = post(c, ROUND, {"kind": start_kind}).json()
    last = None
    while data["round"]["item"]:
        item = data["round"]["item"]
        # The client never knows the answer, so find it the way a test may: on the server.
        right = RoundItem.objects.get(pk=item["id"]).answer_index
        last = post(c, ANSWER, {"item": item["id"], "choice": right}).json()
        data = last
    return last


if not WordPack.objects.filter(slug="general").exists():
    print("  [FAIL] packs not loaded: run python main.py load_vocab first")
    sys.exit(1)

print("== who may call it ==")


@case
def access():
    anon = Client()
    for method, url in (("get", ME), ("get", ROUND), ("post", ROUND), ("post", ANSWER), ("get", detail(1))):
        r = getattr(anon, method)(url)
        ck(f"logged out {method.upper()} {url} -> 401 JSON, not a redirect",
           r.status_code == 401 and r.json()["error"] == "login_required", str(r.status_code))
    for role in (User.Role.PARENT, User.Role.TUTOR, User.Role.ADMIN):
        r = client_for(user(role)).get(ME)
        ck(f"a {role} -> 403 pupils_only", r.status_code == 403 and r.json()["error"] == "pupils_only")
    c = client_for(user())
    r = c.get(ANSWER)
    ck("GET on the answer endpoint -> 405 with Allow: POST",
       r.status_code == 405 and r["Allow"] == "POST")
    r = c.delete(ROUND)
    ck("DELETE on round -> 405", r.status_code == 405 and r["Allow"] == "GET, POST")


@case
def csrf():
    p = user()
    c = client_for(p, csrf=True)
    r = post(c, ROUND, {})
    ck("a POST without the CSRF token is refused", r.status_code == 403)
    # The token a browser would hold in its csrftoken cookie, sent back in the header.
    from django.middleware.csrf import _get_new_csrf_string, _mask_cipher_secret
    secret = _get_new_csrf_string()
    c.cookies["csrftoken"] = secret
    r = post(c, ROUND, {}, HTTP_X_CSRFTOKEN=_mask_cipher_secret(secret))
    ck("...and accepted with the token in X-CSRFToken", r.status_code == 201, str(r.status_code))


print("\n== starting and resuming ==")


@case
def start_and_resume():
    p = user()
    c = client_for(p)
    r = c.get(ROUND)
    ck("no round yet -> {\"round\": null}", r.status_code == 200 and r.json() == {"round": None})
    r = post(c, ROUND)
    data = r.json()
    rnd = data["round"]
    ck("POST with no body starts a mixed round -> 201", r.status_code == 201 and rnd["kind"] == "mixed")
    ck("not resumed", data["resumed"] is False)
    ck("round shape", set(rnd) == {"id", "kind", "pack", "total", "answered", "correct",
                                   "progress", "finished", "item"}, str(sorted(rnd)))
    ck("ten items, none answered", rnd["total"] == 10 and rnd["answered"] == 0
       and rnd["progress"] == [None] * 10)
    ck("pack is general for a pupil with no goal", rnd["pack"]["slug"] == "general")
    item = rnd["item"]
    ck("the first item is number 1", item["number"] == 1)
    ck("item shape before answering", set(item) == {"id", "number", "kind", "prompt", "target",
                                                   "sentence", "options", "answered"}, str(sorted(item)))
    r2 = post(c, ROUND, {"kind": "gap"})
    ck("POST again resumes the same round -> 200", r2.status_code == 200
       and r2.json()["resumed"] is True and r2.json()["round"]["id"] == rnd["id"])
    ck("GET returns the unfinished round", c.get(ROUND).json()["round"]["id"] == rnd["id"])
    r = post(client_for(user()), ROUND, {"kind": "spelling"})
    ck("an unknown kind -> 400", r.status_code == 400 and r.json()["error"] == "bad_request")
    r = client_for(user()).post(ROUND, "not json", content_type="application/json")
    ck("a body that is not JSON -> 400", r.status_code == 400)
    r = post(client_for(user()), ROUND, ["mixed"])
    ck("a JSON body that is not an object -> 400", r.status_code == 400)


print("\n== nothing gives the answer away ==")


@case
def no_leaks():
    for kind in ("synonym", "odd_one_out", "gap"):
        p = user()
        c = client_for(p)
        rnd = post(c, ROUND, {"kind": kind}).json()["round"]
        item = rnd["item"]
        db = RoundItem.objects.select_related("word").get(pk=item["id"])
        text = json.dumps(c.get(ROUND).json())
        ck(f"{kind}: no answer_index, chosen_index or correct before answering",
           all(k not in text for k in ('"answer_index"', '"chosen_index"', '"correct": true')))
        ck(f"{kind}: no definition or example before answering",
           db.word.definition not in text and db.word.example not in text)
        if kind == "gap":
            ck("gap: the headword (the answer) appears only as one of the options",
               text.count(f'"{db.word.headword}"') == 1 and item["target"] is None
               and "___" in item["sentence"])
        if kind == "synonym":
            ck("synonym: shows the word being asked about", item["target"] == db.word.headword
               and db.word.headword in item["prompt"])
        if kind == "odd_one_out":
            ck("odd one out: shows no target", item["target"] is None and item["sentence"] is None)


print("\n== answering ==")


@case
def answering():
    p = user()
    c = client_for(p)
    rnd = post(c, ROUND).json()["round"]
    item = rnd["item"]
    right = RoundItem.objects.get(pk=item["id"]).answer_index
    wrong = (right + 1) % 4
    r = post(c, ANSWER, {"item": item["id"], "choice": wrong})
    data = r.json()
    res = data["result"]
    ck("answer -> 200", r.status_code == 200)
    ck("marked wrong, with the right answer and the word revealed",
       res["correct"] is False and res["chosen_index"] == wrong and res["answer_index"] == right
       and set(res["word"]) == {"headword", "pos", "definition", "synonyms", "example"})
    ck("the round moves on to item 2", data["round"]["item"]["number"] == 2
       and data["round"]["progress"][0] is False and data["round"]["answered"] == 1)
    ck("not finished yet", data["finished"] is None)
    again = post(c, ANSWER, {"item": item["id"], "choice": right}).json()
    ck("answering the same item again changes nothing and says so",
       again["result"]["already_answered"] is True and again["result"]["correct"] is False
       and again["round"]["answered"] == 1)
    for bad, label in (({"item": item["id"]}, "missing choice"),
                       ({"item": str(item["id"]), "choice": 0}, "item as a string"),
                       ({"item": item["id"], "choice": True}, "choice as true"),
                       ({"item": item["id"], "choice": 4}, "choice 4"),
                       ({"item": item["id"], "choice": -1}, "choice -1")):
        r = post(c, ANSWER, bad)
        ck(f"{label} -> 400", r.status_code == 400, str(r.status_code))
    r = post(client_for(user()), ANSWER, {"item": rnd["item"]["id"] + 1, "choice": 0})
    ck("another pupil's item -> 404, and it is not answered",
       r.status_code == 404 and RoundItem.objects.get(pk=rnd["item"]["id"] + 1).chosen_index is None)
    r = post(c, ANSWER, {"item": 10**9, "choice": 0})
    ck("an item that does not exist -> 404", r.status_code == 404)


print("\n== finishing ==")


@case
def finishing():
    p = user()
    c = client_for(p)
    last = play_out(c)
    fin = last["finished"]
    ck("the last answer returns the result", fin is not None and fin["correct"] == 10 and fin["xp"] == 120)
    ck("...with level, streak and whether they levelled up",
       fin["level"]["level"] == 2 and fin["streak"] == 1 and fin["levelled_up"] is True)
    ck("...and the round is finished with no next item",
       last["round"]["finished"] is True and last["round"]["item"] is None)
    rid = last["round"]["id"]
    ck("GET round is null again once finished", c.get(ROUND).json() == {"round": None})
    d = c.get(detail(rid)).json()
    ck("round detail lists all ten answered items, each with its word",
       len(d["items"]) == 10 and all("word" in i and i["answered"] for i in d["items"]))
    ck("round detail has the summary", d["summary"]["xp"] == 120 and d["summary"]["total"] == 10)
    ck("another pupil cannot see it -> 404", client_for(user()).get(detail(rid)).status_code == 404)
    item_id = d["items"][0]["id"]
    r = post(c, ANSWER, {"item": item_id, "choice": 0}).json()
    ck("answering in a finished round changes nothing", r["result"]["already_answered"] is True)
    ck("XP was awarded once", VocabProfile.objects.get(pupil=p).xp == 120)
    unfinished = post(client_for(p), ROUND).json()["round"]
    d = c.get(detail(unfinished["id"])).json()
    ck("an unfinished round's detail has no summary and no unanswered items",
       d["summary"] is None and d["items"] == [])


print("\n== the pupil's totals ==")


@case
def me():
    p = user()
    c = client_for(p)
    m = c.get(ME).json()
    ck("before playing: no XP, level 1, no streak, general pack",
       m["xp"] == 0 and m["level"]["level"] == 1 and m["streak"]["current"] == 0
       and m["pack"]["slug"] == "general" and m["pack_size"] == 50 and m["allowed"] is True)
    play_out(c)
    m = c.get(ME).json()
    ck("after a perfect round: 120 XP, level 2, streak 1, played today",
       m["xp"] == 120 and m["level"]["level"] == 2 and m["streak"]["current"] == 1
       and m["streak"]["played_today"] is True, json.dumps(m["streak"]))
    ck("ten words met, none mastered yet, none due today",
       m["words_met"] == 10 and m["words_mastered"] == 0 and m["due_today"] == 0, str(m))
    ck("no current round", m["current_round"] is None)


@case
def unavailable_and_gated():
    p = user()
    c = client_for(p)
    with mock.patch("vocab.api.vocab_allowed", return_value=False):
        r = post(c, ROUND)
        ck("vocab_allowed False -> 403 not_allowed", r.status_code == 403
           and r.json()["error"] == "not_allowed")
        ck("...and no round was made", not Round.objects.filter(pupil=p).exists())
    rid = post(c, ROUND).json()["round"]["id"]
    with mock.patch("vocab.api.vocab_allowed", return_value=False):
        r = post(c, ROUND)
        ck("...but an unfinished round can still be resumed", r.status_code == 200
           and r.json()["round"]["id"] == rid)
    q = user()
    with mock.patch("vocab.services.pack_for", return_value=None):
        r = post(client_for(q), ROUND)
        ck("packs not loaded -> 503 unavailable", r.status_code == 503
           and r.json()["error"] == "unavailable")
        m = client_for(q).get(ME).json()
        ck("...and me still answers, with no pack", m["pack"] is None and m["pack_size"] == 0)


print("\n== nothing left behind ==")
ck("no test users remain", not User.objects.filter(username__startswith="vocabapi_").exists())

if fails:
    print("\nRESULT: FAILURES:", fails)
    sys.exit(1)
print("\nRESULT: ALL PASSED")
