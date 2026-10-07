"""
Checks Word Wizard's parent and tutor panels.

Run:  python main.py load_vocab
      python main.py shell < test_vocab_panels.py

The panels add a pupil's vocab progress to three pages that already decide who
may see that pupil: the family home and child page (accounts.views, by
_owned_child / the parent link) and the tutor's student page (tutoring.views,
by an active TutorStudent link). The panels add no page and no URL of their
own, so the thing to prove is that they appear where they should, say what the
pupil has done, and never appear for someone else's child.

Every case runs inside a transaction that is always rolled back.
"""
import logging
import random
import sys

from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import Client
from django.test.utils import setup_test_environment

from tutoring.models import TutorStudent
from vocab import services
from vocab.models import WordProgress

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


def user(role=User.Role.STUDENT, parent=None, name=None):
    _n[0] += 1
    return User.objects.create_user(username=f"vocabpanel_{_n[0]}", email=f"vocabpanel_{_n[0]}@x.test",
                                    password="x", role=role, parent=parent,
                                    full_name=name or f"Test {_n[0]}")


def client_for(u):
    c = Client()
    c.force_login(u)
    return c


def play(pupil, right, seed=0):
    """One finished round with `right` answers correct."""
    r, _ = services.start_round(pupil, rng=random.Random(seed))
    for n, item in enumerate(r.items.all()):
        services.answer_item(pupil, item.pk, item.answer_index if n < right else (item.answer_index + 1) % 4)


def family():
    parent = user(User.Role.PARENT)
    child = user(parent=parent, name="Wizard Child")
    return parent, child


print("== services.adult_summary ==")


@case
def adult_summary():
    _, child = family()
    s = services.adult_summary(child)
    ck("not played: no rounds, nothing to practise", s["rounds_played"] == 0 and s["practise"] == []
       and s["last_played_on"] is None)
    play(child, right=3)
    s = services.adult_summary(child)
    ck("after a round: one round, played today", s["rounds_played"] == 1
       and s["last_played_on"] is not None and s["streak"]["played_today"])
    ck("the seven missed words are the ones to practise (top five shown)",
       len(s["practise"]) == 5 and set(s["practise"]) <= set(
           WordProgress.objects.filter(pupil=child, times_correct=0)
           .values_list("word__headword", flat=True)), str(s["practise"]))
    hard = WordProgress.objects.filter(pupil=child, times_correct=0).first()
    hard.times_seen, hard.box = 4, 1
    hard.save()
    ck("the most-missed word comes first", services.practise_words(child)[0] == hard.word.headword)
    hard.times_correct, hard.box = 3, 4
    hard.save()
    ck("a word since mastered drops off the list",
       hard.word.headword not in services.practise_words(child))


print("\n== the parent's pages ==")


@case
def parent_pages():
    parent, child = family()
    c = client_for(parent)
    html = c.get("/family/").content.decode()
    ck("family home: one line per child, 'not played yet'",
       "<strong>Word Wizard:</strong>" in html and "not played yet" in html)
    play(child, right=7)
    html = c.get("/family/").content.decode()
    ck("family home: rank, streak and words mastered once they have played",
       "Apprentice, level 1" in html and "1-day streak" in html and "0 words mastered" in html)
    html = c.get(f"/family/child/{child.pk}/").content.decode()
    ck("child page: a Word Wizard section", "rp-parent__wiz-card" in html and "<h2>Word Wizard</h2>" in html)
    ck("...with rank, XP and rounds", "Apprentice · Level 1" in html and "70 XP from 1 round" in html)
    ck("...streak played today", "1 day, played today" in html)
    ck("...words mastered against the pupil's list", "0 of 50 on the General list (10 met so far)" in html)
    ck("...but NOT the words they are finding hard: that list is for tutors",
       'class="wiz-adult__words"' not in html and "Finding hard" not in html)
    ck("...and their wizard, as he looks at their rank", 'class="wiz-char' in html and "wc--lv1" in html)
    ck("...and wizard.css is loaded", "vocab/wizard.css" in html)
    ck("no play button for a parent", "/vocab/play/" not in html)


@case
def not_your_child():
    parent, child = family()
    play(child, right=5)
    stranger = user(User.Role.PARENT)
    r = client_for(stranger).get(f"/family/child/{child.pk}/")
    ck("another parent cannot open the child page at all", r.status_code in (403, 404), str(r.status_code))
    html = client_for(stranger).get("/family/").content.decode()
    ck("...and their family home shows none of this child's Word Wizard",
       "Wizard Child" not in html and "Apprentice, level" not in html)


print("\n== the tutor's page ==")


@case
def tutor_page():
    parent, child = family()
    tutor = user(User.Role.TUTOR)
    TutorStudent.objects.create(tutor=tutor, student=child, active=True)
    play(child, right=4)
    html = client_for(tutor).get(f"/tutor/student/{child.pk}/").content.decode()
    ck("tutor student page: a Word Wizard card", "<h2 class=\"h6\">Word Wizard</h2>" in html)
    ck("...with the same figures as the parent sees", "40 XP from 1 round" in html
       and "0 of 50 on the General list" in html)
    ck("...and the hard words, for planning", 'class="wiz-adult__words"' in html and "Finding hard" in html)
    ck("no play button for a tutor", "/vocab/play/" not in html)
    other = user(User.Role.TUTOR)
    r = client_for(other).get(f"/tutor/student/{child.pk}/")
    ck("a tutor without a link cannot see it", r.status_code in (403, 404), str(r.status_code))
    TutorStudent.objects.filter(tutor=tutor, student=child).update(active=False)
    r = client_for(tutor).get(f"/tutor/student/{child.pk}/")
    ck("...nor can one whose link is no longer active", r.status_code in (403, 404), str(r.status_code))


print("\n== nothing left behind ==")
ck("no test users remain", not User.objects.filter(username__startswith="vocabpanel_").exists())

if fails:
    print("\nRESULT: FAILURES:", fails)
    sys.exit(1)
print("\nRESULT: ALL PASSED")
