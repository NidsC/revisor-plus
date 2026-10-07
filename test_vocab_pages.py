"""
Checks Word Wizard's pages, its nav link and its dashboard panel.

Run:  python main.py load_vocab
      python main.py shell < test_vocab_pages.py

The play page itself is JavaScript on the JSON API (test_vocab_api.py covers
that); this checks the server-rendered side, and the constraints the trainer
was built under: pupils only, nothing styled .stat (base.html animates those
up from zero), no data-rp-mode (portals.js rewrites pages that have one), and
no panel on the goal page.

Every case runs inside a transaction that is always rolled back.
"""
import logging
import re
import sys
from pathlib import Path

from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import Client
from django.test.utils import setup_test_environment

from vocab import services

setup_test_environment()
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
    return User.objects.create_user(username=f"vocabpage_{_n[0]}", email=f"vocabpage_{_n[0]}@x.test",
                                    password="x", role=role, full_name=f"Test {_n[0]}")


def client_for(u):
    c = Client()
    c.force_login(u)
    return c


def wiz_markup(html):
    """Only the Word Wizard parts of a page: the .wiz page or the .wiz-panel."""
    m = re.search(r'<div class="(?:wiz|wiz wiz--play)">.*', html, re.S) or \
        re.search(r'<div class="kid-dash__panel wiz-panel">.*?\n</div>', html, re.S)
    return m.group(0) if m else ""


print("== who may open the pages ==")


@case
def access():
    for path in ("/vocab/", "/vocab/play/"):
        r = Client().get(path)
        ck(f"logged out {path} -> login page", r.status_code == 302 and "/accounts/login/" in r["Location"])
        for role in (User.Role.PARENT, User.Role.TUTOR):
            r = client_for(user(role)).get(path)
            ck(f"a {role} opening {path} is sent to their own home",
               r.status_code == 302 and r["Location"] == "/after-login/", r.get("Location"))
        ck(f"a pupil opens {path}", client_for(user()).get(path).status_code == 200)


print("\n== the home page ==")


@case
def home():
    p = user()
    html = client_for(p).get("/vocab/").content.decode()
    ck("named Word Wizard, with its premise", "Word Wizard" in html and services.RANKS[0] in html
       and "level up from Apprentice to Grand Wizard" in html)
    ck("uses the shared page header", 'class="rp-page-head"' in html)
    ck("a new pupil is offered 'Play a round', mixed", "Play a round" in html
       and 'href="/vocab/play/"' in html)
    ck("and the three single types", all(f"/vocab/play/?kind={k}" in html
                                         for k in ("synonym", "odd_one_out", "gap")))
    ck("shows the general list for a pupil with no goal", "General list, 50 words" in html)
    ck("the wizard, large and idle", 'wiz-char wiz-char--idle wiz-char--lg' in html)
    ck("...and his next look as a locked silhouette, with what it unlocks",
       "wiz-char--locked" in html and "Level 2: Spell Reader." in html and "a pointed hat" in html)
    services.start_round(p)
    html = client_for(p).get("/vocab/").content.decode()
    ck("with a round under way it offers 'Carry on'", "Carry on" in html and "a round waiting" in html)
    ck("...and greys out the other types", html.count('aria-disabled="true"') == 3)


@case
def unavailable():
    from unittest import mock
    with mock.patch("vocab.services.pack_for", return_value=None):
        html = client_for(user()).get("/vocab/").content.decode()
    ck("no packs loaded: says so, offers no play button",
       "aren't ready yet" in html and "Play a round" not in html)


print("\n== the play page ==")


@case
def play():
    c = client_for(user())
    html = c.get("/vocab/play/").content.decode()
    ck("an empty frame for play.js, defaulting to mixed",
       'id="wiz-play"' in html and 'data-kind="mixed"' in html and "vocab/play.js" in html)
    ck("it carries the API URLs", 'data-api-round="/vocab/api/round/"' in html
       and 'data-api-answer="/vocab/api/answer/"' in html)
    ck("?kind=gap asks for a gap round", 'data-kind="gap"' in c.get("/vocab/play/?kind=gap").content.decode())
    ck("an unknown kind falls back to mixed", 'data-kind="mixed"' in c.get("/vocab/play/?kind=x").content.decode())
    ck("a noscript message instead of a frame that never fills", "<noscript>" in html)
    ck("the page carries the wizard now, larger, and at the next level for a level-up",
       '<template id="wiz-now">' in html and '<template id="wiz-now-lg">' in html
       and '<template id="wiz-next">' in html and "wc--lv2" in html)
    ck("...with what the next level unlocks", 'data-next-new="a pointed hat' in html)
    frame = html[html.index('id="wiz-play"'):html.index("</noscript>")]
    ck("...outside the frame play.js empties, so they survive the first screen",
       "<template" not in frame)
    fresh = client_for(user())
    r = fresh.get("/vocab/play/")
    ck("the play page sets the CSRF cookie, so a browser without one can still answer",
       "csrftoken" in r.cookies)
    ck("...and carries the token in the page as a fallback",
       re.search(r'data-csrf="[A-Za-z0-9]{32,}"', r.content.decode()) is not None)


print("\n== nav and dashboard ==")


@case
def nav_and_panel():
    p = user()
    html = client_for(p).get("/dashboard/").content.decode()
    ck("pupils have a Word Wizard nav link", '<a class="nav-link" href="/vocab/">Word Wizard</a>' in html)
    panel = wiz_markup(html)
    ck("the pupil dashboard has the Word Wizard panel", 'wiz-panel' in html and "Apprentice · Level 1" in html)
    ck("the panel sits inside .kid-dash__shell, before the Today/Mocks columns",
       html.index("wiz-panel") < html.index('class="kid-dash__cols"')
       and html.index('class="kid-dash__shell"') < html.index("wiz-panel"))
    ck("the dashboard loads wizard.css", "vocab/wizard.css" in html)
    parent = user(User.Role.PARENT)
    html = client_for(parent).get("/family/").content.decode()
    ck("a parent has no Word Wizard nav link", "Word Wizard</a>" not in html)


print("\n== the constraints ==")
root = Path(".")
wiz_templates = sorted((root / "templates/vocab").glob("*.html"))
text = {p.name: p.read_text() for p in wiz_templates}
css = (root / "static/vocab/wizard.css").read_text()
js = (root / "static/vocab/play.js").read_text()
ck("no Word Wizard template uses .stat",
   not any(re.search(r'class="[^"]*\bstat\b', t) for t in text.values()), str(list(text)))
ck("play.js never sets a .stat class", not re.search(r'["\s]stat["\s]', js))
ck("no Word Wizard template uses .card", not any(re.search(r'class="[^"]*\bcard\b', t) for t in text.values()))
ck("no data-rp-mode on any Word Wizard page", not any("data-rp-mode=" in t for t in text.values()))
ck("goals/detail.html has nothing from Word Wizard",
   not re.search(r"vocab|wiz", (root / "templates/goals/detail.html").read_text()))
ck("wizard.css reads base.html tokens (--measure, --gutter, --subj-ma)",
   all(t in css for t in ("var(--measure)", "var(--gutter)", "var(--subj-ma-deep)")))
ck("answer buttons are at least 3.5rem (56px) tall", "--wiz-tap: 3.5rem" in css
   and "min-height: var(--wiz-tap)" in css)
ck("play.js reloads on a CSRF 403 at most once, never in a loop",
   "reloadOnce()" in js and "window.location.reload()" in js and js.count("location.reload") == 1)
ck("play.js puts server text in with textContent, never innerHTML",
   not re.search(r"\.(inner|outer)HTML\s*=|insertAdjacentHTML", js))

print("\n== nothing left behind ==")
ck("no test users remain", not User.objects.filter(username__startswith="vocabpage_").exists())

if fails:
    print("\nRESULT: FAILURES:", fails)
    sys.exit(1)
print("\nRESULT: ALL PASSED")
