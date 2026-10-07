"""
Checks the vocab trainer's game logic in vocab/services.py.

Run:  python main.py load_vocab
      python main.py shell < test_vocab.py

Round building, marking, the spaced-repetition schedule, XP, levels and the
streak — including the edges that are easy to get wrong and hard to notice: a
double submit, the day boundary in BST, a missed day, a pupil with no goal.

Every case runs inside a transaction that is always rolled back, so nothing is
left in the database even if the script fails part way.
"""
import random
import sys
from datetime import date, datetime, timedelta, timezone as dt_tz

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from vocab import services as s
from vocab.models import Round, VocabProfile, Word, WordPack, WordProgress

fails = []


def ck(label, cond, extra=""):
    print(f"  [{'OK  ' if cond else 'FAIL'}] {label}" + (f" — {extra}" if extra else ""))
    if not cond:
        fails.append(label)


class Rollback(Exception):
    pass


def case(fn):
    """Run one case in a transaction that is always undone."""
    try:
        with transaction.atomic():
            fn()
            raise Rollback
    except Rollback:
        pass
    return fn


User = get_user_model()
_n = [0]


def pupil():
    _n[0] += 1
    return User.objects.create_user(username=f"vocabgame_{_n[0]}", email=f"vocabgame_{_n[0]}@x.test",
                                    password="x", role=User.Role.STUDENT)


def london(y, m, d, hh, mm):
    """An aware datetime for a UK wall-clock time."""
    return timezone.make_aware(datetime(y, m, d, hh, mm))


def play(p, right=True, now=None, kind=Round.Kind.MIXED, seed=0):
    """Start (or resume) a round and answer every item. Returns the finish summary."""
    r, _ = s.start_round(p, kind=kind, now=now, rng=random.Random(seed))
    summary = None
    while (item := s.next_item(r)) is not None:
        choice = item.answer_index if right else (item.answer_index + 1) % s.OPTIONS
        summary = s.answer_item(p, item.pk, choice, now=now)["finished"] or summary
    return summary


GENERAL = WordPack.objects.filter(slug="general").first()
if GENERAL is None or not GENERAL.words.exists():
    print("  [FAIL] packs not loaded: run python main.py load_vocab first")
    sys.exit(1)

print("== building a round ==")


@case
def first_round_is_mixed():
    p = pupil()
    r, resumed = s.start_round(p, rng=random.Random(1))
    items = list(r.items.all())
    ck("a new round, not a resumed one", not resumed)
    ck("defaults to mixed", r.kind == Round.Kind.MIXED)
    ck("ten items", len(items) == 10)
    ck("from the general pack (no goal)", r.pack.slug == "general")
    kinds = sorted(i.kind for i in items)
    ck("mixed is an even spread of the three kinds (4/3/3)",
       sorted([kinds.count(k) for k in s.ITEM_KINDS]) == [3, 3, 4], str(kinds))
    ck("ten different words", len({i.word_id for i in items}) == 10)
    ck("a new pupil gets the easiest year first",
       all(i.word.year == 5 for i in items), str(sorted(i.word.year for i in items)))
    ck("every item has four different options",
       all(len(i.options) == 4 and len(set(i.options)) == 4 for i in items))


def check_item(i):
    """Problems with one item, judged from the word data. [] if it is sound."""
    w, ans = i.word, i.options[i.answer_index]
    wrong = [o for k, o in enumerate(i.options) if k != i.answer_index]
    own = {w.headword, *w.synonyms}
    group_terms = set()
    for g in Word.objects.filter(group=w.group):
        group_terms |= {g.headword, *g.synonyms}
    term_owner = {}
    for o in Word.objects.all():
        for t in (o.headword, *o.synonyms):
            term_owner[t] = o
    problems = []
    if i.kind == "gap":
        if ans != w.headword or wrong != [d for d in i.options if d in w.gap_distractors]:
            problems.append("gap answer is not the word, or options not its distractors")
    elif i.kind == "synonym":
        if ans not in w.synonyms:
            problems.append(f"answer {ans!r} is not a synonym")
        for o in wrong:
            if o in group_terms:
                problems.append(f"wrong option {o!r} is in the word's group")
            elif term_owner[o].pos != w.pos:
                problems.append(f"wrong option {o!r} is a {term_owner[o].pos}")
        if len({term_owner[o].group for o in wrong}) != 3:
            problems.append("two wrong options from one group")
    elif i.kind == "odd_one_out":
        if ans in group_terms:
            problems.append(f"odd one out {ans!r} is in the word's group")
        if term_owner[ans].pos != w.pos:
            problems.append(f"odd one out {ans!r} is a different part of speech")
        if not set(wrong) <= own or w.headword not in wrong:
            problems.append("the three that belong are not the word and two synonyms")
    return problems


@case
def items_are_sound_over_many_rounds():
    # 60 rounds of each kind over both packs, answered right so new words keep
    # coming in: every item judged against the word data.
    bad, seen = [], {k: 0 for k in s.ITEM_KINDS}
    for slug in ("general", "gl"):
        for kind in s.ITEM_KINDS:
            p = pupil()
            if slug == "gl":
                from goals.models import Goal, School
                school = School.objects.create(slug=f"vocabgame-{kind}", name="GL test", exam_format="gl")
                Goal.objects.create(student=p, school=school, exam_date=date.today() + timedelta(days=99))
            for n in range(10):
                r, _ = s.start_round(p, kind=kind, rng=random.Random(n))
                for i in r.items.all():
                    seen[i.kind] += 1
                    bad += [f"{slug}/{i.word.headword}/{i.kind}: {m}" for m in check_item(i)]
                    s.answer_item(p, i.pk, i.answer_index)
    ck("every item built is sound", not bad, "; ".join(bad[:5]))
    ck("each kind was really built, not swapped for gap",
       seen["synonym"] >= 190 and seen["odd_one_out"] >= 190, str(seen))


@case
def single_kind_rounds():
    for kind in s.ITEM_KINDS:
        p = pupil()
        r, _ = s.start_round(p, kind=kind, rng=random.Random(2))
        ck(f"a {kind} round is all {kind}", set(r.items.values_list("kind", flat=True)) == {kind})


@case
def unknown_kind():
    try:
        s.start_round(pupil(), kind="spelling")
        ck("an unknown kind is refused", False)
    except ValueError:
        ck("an unknown kind is refused", True)


@case
def resume():
    p = pupil()
    r, _ = s.start_round(p, kind=Round.Kind.GAP)
    first = r.items.first()
    s.answer_item(p, first.pk, first.answer_index)
    again, resumed = s.start_round(p, kind=Round.Kind.SYNONYM)
    ck("an unfinished round is resumed", resumed and again.pk == r.pk)
    ck("...even when a different kind is asked for", again.kind == Round.Kind.GAP)
    ck("...at the first unanswered item", s.next_item(again).position == 1)
    ck("only one unfinished round exists", Round.objects.filter(pupil=p, finished_at=None).count() == 1)


print("\n== what goes into a round ==")


@case
def due_words_first():
    p = pupil()
    today = timezone.localdate()
    due = list(GENERAL.words.filter(year=6)[:8])
    for k, w in enumerate(due):
        WordProgress.objects.create(pupil=p, word=w, box=2, due_on=today - timedelta(days=k))
    r, _ = s.start_round(p, rng=random.Random(3))
    ids = set(r.items.values_list("word_id", flat=True))
    ck("all eight due words are in the round", {w.pk for w in due} <= ids)
    ck("the other two are new words",
       not WordProgress.objects.filter(pupil=p, word_id__in=ids - {w.pk for w in due}).exists())


@case
def too_many_due():
    p = pupil()
    today = timezone.localdate()
    words = list(GENERAL.words.all()[:14])
    for k, w in enumerate(words):
        WordProgress.objects.create(pupil=p, word=w, box=1, due_on=today - timedelta(days=k))
    r, _ = s.start_round(p, rng=random.Random(4))
    ids = set(r.items.values_list("word_id", flat=True))
    most_overdue = {w.pk for w in words[4:]}
    ck("with 14 due, the 10 most overdue are asked", ids == most_overdue)


@case
def new_word_cap():
    p = pupil()
    today = timezone.localdate()
    later = list(GENERAL.words.all()[:5])
    for w in later:
        WordProgress.objects.create(pupil=p, word=w, box=3, due_on=today + timedelta(days=3))
    r, _ = s.start_round(p, rng=random.Random(5))
    ids = set(r.items.values_list("word_id", flat=True))
    new = ids - {w.pk for w in later}
    ck("reviews not yet due are used before a fifth new word",
       {w.pk for w in later} <= ids and len(new) == 5, f"{len(new)} new")


@case
def retired_words_are_left_out():
    p = pupil()
    keep = set(GENERAL.words.values_list("pk", flat=True)[:10])
    Word.objects.filter(packs=GENERAL).exclude(pk__in=keep).update(active=False)
    WordProgress.objects.create(pupil=p, word_id=sorted(keep)[0], due_on=timezone.localdate())
    retired = Word.objects.filter(packs=GENERAL, active=False).first()
    WordProgress.objects.create(pupil=p, word=retired, due_on=timezone.localdate() - timedelta(days=9))
    r, _ = s.start_round(p, rng=random.Random(6))
    ck("an inactive word is never asked, even when overdue",
       retired.pk not in set(r.items.values_list("word_id", flat=True)))


@case
def no_pack():
    p = pupil()
    WordPack.objects.filter(slug="general").delete()
    try:
        s.start_round(p)
        ck("no pack loaded -> VocabUnavailable", False)
    except s.VocabUnavailable:
        ck("no pack loaded -> VocabUnavailable", True)


print("\n== marking ==")


@case
def marking():
    p = pupil()
    now = london(2026, 3, 10, 16, 0)
    r, _ = s.start_round(p, now=now, rng=random.Random(7))
    a, b = list(r.items.all()[:2])
    res = s.answer_item(p, a.pk, a.answer_index, now=now)
    pa = WordProgress.objects.get(pupil=p, word=a.word)
    ck("right answer is marked right", res["correct"] and not res["already_answered"])
    ck("a new word answered right goes to box 2, due in 2 days",
       pa.box == 2 and pa.due_on == date(2026, 3, 12), f"box {pa.box} due {pa.due_on}")
    wrong = (b.answer_index + 1) % 4
    res = s.answer_item(p, b.pk, wrong, now=now)
    pb = WordProgress.objects.get(pupil=p, word=b.word)
    ck("wrong answer is marked wrong, and says what was right",
       not res["correct"] and res["answer"] == b.options[b.answer_index])
    ck("a word answered wrong is box 1, due tomorrow",
       pb.box == 1 and pb.due_on == date(2026, 3, 11), f"box {pb.box} due {pb.due_on}")
    again = s.answer_item(p, b.pk, b.answer_index, now=now)
    pb.refresh_from_db()
    ck("a second answer to the same item changes nothing",
       again["already_answered"] and not again["correct"] and pb.times_seen == 1 and pb.box == 1)
    try:
        s.answer_item(p, a.pk, 4)
        ck("an option number outside 0-3 is refused", False)
    except ValueError:
        ck("an option number outside 0-3 is refused", True)
    try:
        s.answer_item(pupil(), r.items.last().pk, 0)
        ck("another pupil cannot answer this round", False)
    except r.items.model.DoesNotExist:
        ck("another pupil cannot answer this round", True)


ck("schedule: right moves up a box", s.schedule(2, True, date(2026, 1, 1)) == (3, date(2026, 1, 5)))
ck("schedule: the top box stays the top box, 16 days",
   s.schedule(5, True, date(2026, 1, 1)) == (5, date(2026, 1, 17)))
ck("schedule: wrong from any box goes back to box 1",
   s.schedule(5, False, date(2026, 1, 1)) == (1, date(2026, 1, 2)))

print("\n== finishing, XP and levels ==")


@case
def finishing():
    p = pupil()
    summary = play(p, right=True)
    profile = VocabProfile.objects.get(pupil=p)
    ck("a perfect round is 10 x 10 + 20 bonus = 120 XP", summary["xp"] == 120 and profile.xp == 120)
    ck("the round is closed", Round.objects.filter(pupil=p, finished_at__isnull=False).count() == 1)
    ck("reaching 100 XP is level 2", summary["level"]["level"] == 2 and summary["levelled_up"])
    summary = play(p, right=False, seed=1)
    ck("an all-wrong round is 0 XP", summary["xp"] == 0 and summary["correct"] == 0)
    r = Round.objects.filter(pupil=p).first()
    ck("finishing twice does nothing the second time", s.finish_round(r) is None)
    ck("...and does not add XP again", VocabProfile.objects.get(pupil=p).xp == 120)


ck("XP: 7 of 10 is 70, no bonus", s.round_xp(7, 10) == 70)
ck("levels: 0 XP is level 1", s.level_for(0)["level"] == 1)
ck("levels: 99 is still 1, one short", s.level_for(99) == {
    "level": 1, "rank": "Apprentice", "xp_into_level": 99, "xp_for_level": 100, "xp_to_next": 1})
ck("ranks: level 2 is Spell Reader, 9 and beyond Grand Wizard",
   [s.level_for(s.level_threshold(n))["rank"] for n in (2, 9, 15)]
   == ["Spell Reader", "Grand Wizard", "Grand Wizard"])
ck("levels: thresholds 100, 300, 600, 1000",
   [s.level_for(x)["level"] for x in (100, 299, 300, 600, 1000)] == [2, 2, 3, 4, 5])

print("\n== the streak ==")


@case
def streak():
    p = pupil()
    d1 = london(2026, 6, 10, 9, 0)
    ck("first round: streak 1", play(p, now=d1)["streak"] == 1)
    ck("second round the same day: still 1", play(p, now=d1 + timedelta(hours=5), seed=1)["streak"] == 1)
    ck("next day: 2", play(p, now=d1 + timedelta(days=1), seed=2)["streak"] == 2)
    ck("the day after: 3", play(p, now=d1 + timedelta(days=2), seed=3)["streak"] == 3)
    summary = play(p, now=d1 + timedelta(days=4), seed=4)
    ck("after a missed day: back to 1, best stays 3",
       summary["streak"] == 1 and summary["best_streak"] == 3, str(summary))


@case
def streak_bst_boundary():
    # 22:30 UTC on 10 June is 23:30 in London (BST); 23:30 UTC is 00:30 on 11 June.
    p = pupil()
    late = datetime(2026, 6, 10, 22, 30, tzinfo=dt_tz.utc)
    after_midnight = datetime(2026, 6, 10, 23, 30, tzinfo=dt_tz.utc)
    play(p, now=late)
    summary = play(p, now=after_midnight, seed=1)
    ck("in BST, 00:30 London is the next day even though UTC says the same day",
       summary["streak"] == 2, str(summary["streak"]))
    ck("...and last_played_on is the London date",
       VocabProfile.objects.get(pupil=p).last_played_on == date(2026, 6, 11))


@case
def streak_gmt_boundary():
    # In winter London is on GMT: 23:30 UTC on 10 Dec is still 10 Dec there.
    p = pupil()
    play(p, now=datetime(2026, 12, 10, 12, 0, tzinfo=dt_tz.utc))
    summary = play(p, now=datetime(2026, 12, 10, 23, 30, tzinfo=dt_tz.utc), seed=1)
    ck("in GMT, 23:30 UTC is the same day: no extra streak", summary["streak"] == 1)


@case
def streak_display():
    p = pupil()
    profile = VocabProfile.objects.create(pupil=p, current_streak=5, best_streak=7,
                                          last_played_on=date(2026, 6, 10))
    at = lambda d: london(2026, 6, d, 12, 0)
    ck("played today: shows 5", s.streak_for(profile, at(10)) ==
       {"current": 5, "best": 7, "played_today": True, "at_risk": False})
    ck("played yesterday: shows 5, at risk", s.streak_for(profile, at(11)) ==
       {"current": 5, "best": 7, "played_today": False, "at_risk": True})
    ck("missed a day: shows 0, though 5 is still stored", s.streak_for(profile, at(12))["current"] == 0)
    ck("never played: all zero", s.streak_for(None)["current"] == 0)


print("\n== nothing left behind ==")
ck("no test pupils remain", not User.objects.filter(username__startswith="vocabgame_").exists())

if fails:
    print("\nRESULT: FAILURES:", fails)
    sys.exit(1)
print("\nRESULT: ALL PASSED")
