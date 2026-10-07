"""
The vocab trainer's logic. Views stay thin and call in here.

  * Which pack a pupil gets ............ pack_slug_for, pack_for
  * Building and resuming a round ...... start_round, current_round, next_item
  * Marking ............................ answer_item (finishes the round itself)
  * Spaced repetition .................. INTERVALS, schedule
  * XP, levels and the streak .......... round_xp, level_for, streak_for

"Today" is always timezone.localdate(now): UK time (settings.TIME_ZONE), so a
day turns over at midnight in London, BST included. Functions that depend on
the date take an optional `now` so that tests can pin it.
"""
import random
from datetime import timedelta

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from analytics.readiness import active_goal
from goals.models import School

from .models import Round, RoundItem, VocabProfile, Word, WordPack, WordProgress

GENERAL = "general"

# A school's entrance-test format -> the pack its pupils practise. The Sutton
# SET follows the GL format, so it gets the GL pack. Bespoke tests, schools with
# no format recorded, and pupils with no goal or no school all get GENERAL.
FORMAT_TO_PACK = {
    School.ExamFormat.GL: "gl",
    School.ExamFormat.SET: "gl",
}

ROUND_SIZE = 10
OPTIONS = 4
# New words allowed into a round while there are reviews to fit in. With no
# reviews to hand (a pupil's first rounds), new words fill the round instead,
# so the cap only ever decides between the two, never shortens a round.
MAX_NEW_WHEN_REVIEWING = 4

# Leitner boxes: days until a word is due again after an answer leaves it in
# that box. Right moves a word up one box (to at most the last); wrong sends it
# back to box 1, so it is due tomorrow.
INTERVALS = {1: 1, 2: 2, 3: 4, 4: 8, 5: 16}
MAX_BOX = max(INTERVALS)

XP_PER_CORRECT = 10
XP_PERFECT_BONUS = 20  # all ten right

ITEM_KINDS = [Round.Kind.SYNONYM, Round.Kind.ODD_ONE_OUT, Round.Kind.GAP]


class VocabUnavailable(Exception):
    """The pupil's word pack is not loaded (load_vocab has not run or failed)."""


# --------------------------------------------------------------------------
# Which pack
# --------------------------------------------------------------------------

def pack_slug_for(pupil):
    """The slug of the pack this pupil should practise."""
    goal = active_goal(pupil)
    exam_format = goal.school.exam_format if goal and goal.school else ""
    return FORMAT_TO_PACK.get(exam_format, GENERAL)


def pack_for(pupil):
    """This pupil's WordPack, or None if the packs have not been loaded.

    None rather than an exception: a deploy whose load_vocab failed should show
    the pupil "not available yet", not a server error.
    """
    return WordPack.objects.filter(slug=pack_slug_for(pupil)).first()


# --------------------------------------------------------------------------
# Building a round
# --------------------------------------------------------------------------

def current_round(pupil):
    """The pupil's unfinished round, if they have one."""
    return Round.objects.filter(pupil=pupil, finished_at__isnull=True).first()


def next_item(round_):
    """The first unanswered item, or None once every item is answered."""
    return round_.items.filter(chosen_index__isnull=True).order_by("position").first()


def start_round(pupil, kind=Round.Kind.MIXED, now=None, rng=None):
    """Resume the pupil's unfinished round, or build a new one.

    An unfinished round is always resumed, whatever `kind` asks for: otherwise
    a pupil could skip a hard word by walking away and starting again.
    Returns (round, resumed).
    """
    if kind not in Round.Kind.values:
        raise ValueError(f"unknown round kind {kind!r}")
    existing = current_round(pupil)
    if existing:
        return existing, True

    pack = pack_for(pupil)
    if pack is None:
        raise VocabUnavailable(pack_slug_for(pupil))
    rng = rng or random.Random()
    today = timezone.localdate(now)
    pool = list(pack.words.filter(active=True))
    words = choose_words(pupil, pool, today, rng)
    if not words:
        raise VocabUnavailable(pack.slug)

    kinds = item_kinds(kind, len(words), rng)
    with transaction.atomic():
        round_ = Round.objects.create(pupil=pupil, pack=pack, kind=kind)
        for position, (word, item_kind) in enumerate(zip(words, kinds)):
            item_kind, options, answer = build_item(word, item_kind, pool, rng)
            RoundItem.objects.create(round=round_, position=position, word=word,
                                     kind=item_kind, options=options, answer_index=answer)
    return round_, False


def choose_words(pupil, pool, today, rng):
    """Up to ROUND_SIZE words from `pool`, in the order they will be asked.

    Priority: reviews that are due (most overdue first), then new words (easiest
    year first, at most MAX_NEW_WHEN_REVIEWING of them), then reviews not yet
    due (soonest first), then any further new words.
    """
    by_id = {w.pk: w for w in pool}
    progress = {p.word_id: p for p in WordProgress.objects.filter(pupil=pupil, word_id__in=by_id)}

    due = sorted((p for p in progress.values() if p.due_on <= today),
                 key=lambda p: (p.due_on, p.box))
    upcoming = sorted((p for p in progress.values() if p.due_on > today),
                      key=lambda p: (p.due_on, p.box))
    new = [w for w in pool if w.pk not in progress]
    rng.shuffle(new)
    new.sort(key=lambda w: w.year)  # stable: random order within each year

    chosen = [by_id[p.word_id] for p in due][:ROUND_SIZE]
    room = ROUND_SIZE - len(chosen)
    chosen += new[:min(room, MAX_NEW_WHEN_REVIEWING)]
    chosen += [by_id[p.word_id] for p in upcoming][:ROUND_SIZE - len(chosen)]
    taken = {w.pk for w in chosen}
    chosen += [w for w in new if w.pk not in taken][:ROUND_SIZE - len(chosen)]
    rng.shuffle(chosen)
    return chosen


def item_kinds(kind, n, rng):
    """The kind of each of n items: all one kind, or an even shuffled mix."""
    if kind != Round.Kind.MIXED:
        return [kind] * n
    kinds = (ITEM_KINDS * n)[:n]
    rng.shuffle(kinds)
    return kinds


def _others(word, pool):
    """Words a wrong option may come from: same part of speech, other group."""
    return [w for w in pool if w.pos == word.pos and w.group != word.group and w.pk != word.pk]


def build_item(word, kind, pool, rng):
    """(kind, options, answer_index) for one item.

    Falls back to fill the gap, which always works (its distractors are in the
    word itself), when the pack cannot supply enough same-class words from
    other groups for the kind asked for.
    """
    others = _others(word, pool)
    # One wrong option per group: words in one group may share synonyms, so two
    # from the same group could show the same option twice.
    groups = {}
    for o in others:
        groups.setdefault(o.group, []).append(o)
    if kind == Round.Kind.SYNONYM and len(groups) >= OPTIONS - 1:
        answer = rng.choice(word.synonyms)
        picks = [rng.choice(groups[g]) for g in rng.sample(sorted(groups), OPTIONS - 1)]
        wrong = [rng.choice([o.headword, *o.synonyms]) for o in picks]
    elif kind == Round.Kind.ODD_ONE_OUT and others and len(word.synonyms) >= 2:
        # Three that mean the same (the word and two synonyms); the odd one out
        # is from another group, so it cannot also be a fair match.
        outsider = rng.choice(others)
        answer = rng.choice([outsider.headword, *outsider.synonyms])
        wrong = [word.headword, *rng.sample(word.synonyms, 2)]
    else:
        kind = Round.Kind.GAP
        answer = word.headword
        wrong = list(word.gap_distractors)
    options = [answer, *wrong]
    rng.shuffle(options)
    return kind, options, options.index(answer)


# --------------------------------------------------------------------------
# Marking
# --------------------------------------------------------------------------

def schedule(box, correct, today):
    """(new box, due date) after one answer."""
    box = min(box + 1, MAX_BOX) if correct else 1
    return box, today + timedelta(days=INTERVALS[box])


def answer_item(pupil, item_id, chosen_index, now=None):
    """Mark one item and return a dict describing the result.

    Answering is once only. The write is a single conditional UPDATE on a row
    that is still unanswered, in an unfinished round, owned by this pupil, so
    a double submit — or two tabs — marks it once; the second call gets the
    first result back with "already_answered": True and changes nothing.
    Answering the last item finishes the round.
    """
    if chosen_index not in range(OPTIONS):
        raise ValueError(f"chosen_index must be 0-{OPTIONS - 1}")
    now = now or timezone.now()
    today = timezone.localdate(now)
    item = (RoundItem.objects.select_related("round", "word")
            .get(pk=item_id, round__pupil=pupil))
    correct = chosen_index == item.answer_index

    with transaction.atomic():
        marked = (RoundItem.objects
                  .filter(pk=item.pk, chosen_index__isnull=True, round__finished_at__isnull=True)
                  .update(chosen_index=chosen_index, correct=correct, answered_at=now))
        if marked:
            progress, _ = (WordProgress.objects.select_for_update()
                           .get_or_create(pupil=pupil, word=item.word, defaults={"due_on": today}))
            progress.box, progress.due_on = schedule(progress.box, correct, today)
            progress.times_seen = F("times_seen") + 1
            progress.times_correct = F("times_correct") + int(correct)
            progress.last_seen_at = now
            progress.save()

    item.refresh_from_db()
    result = {
        "item": item, "correct": bool(item.correct), "already_answered": not marked,
        "answer": item.options[item.answer_index], "finished": None,
    }
    if marked and next_item(item.round) is None:
        result["finished"] = finish_round(item.round, now=now)
    return result


# --------------------------------------------------------------------------
# Finishing: XP, levels, streak
# --------------------------------------------------------------------------

def round_xp(n_correct, n_items):
    return n_correct * XP_PER_CORRECT + (XP_PERFECT_BONUS if n_correct == n_items else 0)


def finish_round(round_, now=None):
    """Close a fully answered round, award XP and move the streak, once.

    Returns a summary dict, or None if the round was already finished (the
    conditional UPDATE lets exactly one caller through).
    """
    now = now or timezone.now()
    today = timezone.localdate(now)
    items = list(round_.items.all())
    if any(i.chosen_index is None for i in items):
        raise ValueError("round has unanswered items")
    n_correct = sum(bool(i.correct) for i in items)
    xp = round_xp(n_correct, len(items))

    with transaction.atomic():
        closed = (Round.objects.filter(pk=round_.pk, finished_at__isnull=True)
                  .update(finished_at=now, xp_awarded=xp))
        if not closed:
            return None
        profile, _ = VocabProfile.objects.select_for_update().get_or_create(pupil=round_.pupil)
        level_before = level_for(profile.xp)["level"]
        profile.xp += xp
        if profile.last_played_on == today:
            pass                                   # second round today: no change
        elif profile.last_played_on == today - timedelta(days=1):
            profile.current_streak += 1            # played yesterday: streak grows
        else:
            profile.current_streak = 1             # first round, or a day was missed
        profile.best_streak = max(profile.best_streak, profile.current_streak)
        profile.last_played_on = today
        profile.save()

    level = level_for(profile.xp)
    return {
        "correct": n_correct, "total": len(items), "xp": xp, "total_xp": profile.xp,
        "level": level, "levelled_up": level["level"] > level_before,
        "streak": profile.current_streak, "best_streak": profile.best_streak,
    }


def level_threshold(level):
    """Total XP needed to reach `level`. Level 1 is 0; 2 is 100; 3 is 300;
    4 is 600; 5 is 1,000 — each level needs 100 more XP than the last. A
    perfect round is 120 XP, so level 2 comes in the first round or two and
    level 10 after roughly forty."""
    return 50 * level * (level - 1)


def level_for(xp):
    level = 1
    while xp >= level_threshold(level + 1):
        level += 1
    start, end = level_threshold(level), level_threshold(level + 1)
    return {"level": level, "xp_into_level": xp - start, "xp_for_level": end - start,
            "xp_to_next": end - xp}


def streak_for(profile, now=None):
    """The streak as the pupil should see it today.

    The stored current_streak only changes when a round finishes, so it goes
    stale: a pupil who last played three days ago still has their old number
    stored. Shown here as 0, because the streak is already broken.
    `at_risk` means they played yesterday but not yet today.
    """
    if profile is None or profile.last_played_on is None:
        return {"current": 0, "best": 0, "played_today": False, "at_risk": False}
    today = timezone.localdate(now)
    days = (today - profile.last_played_on).days
    alive = days <= 1
    return {"current": profile.current_streak if alive else 0, "best": profile.best_streak,
            "played_today": days == 0, "at_risk": days == 1}
