"""
Delete pupils who have been inactive for 12 months, with all their history.

This is the Privacy Policy's retention rule (section 8: a pupil's account, attempts,
progress, targets, homework and vocabulary history are deleted after 12 months without
any login or activity).

The rule: a pupil (role=student) is inactive when ALL of `User.last_login`, the newest
`practice.Attempt.created_at` and `vocab.VocabProfile.last_played_on` are older than the
cutoff (`now - N days`) or absent. `last_played_on` is a DateField, so it is compared
against `cutoff.date()`. Never selected: a pupil whose `Subscription.status` is ACTIVE or
PAST_DUE; any pupil whose own email or whose parent's email ends with `@revisorplus.test`
(the seeded demo family); a pupil whose `date_joined` is within the last N days. The owner
may refine what counts as activity later; this is the rule as decided on 2026-10-11.

What a deletion takes with it (all `on_delete=CASCADE` from the pupil): TestSession and its
Attempt rows, Goal and its SectionTarget rows, Assignment, Subscription, VocabProfile,
WordProgress, Round and its RoundItem rows, and the pupil's TutorStudent links with the
TutorMessage rows on those links. The messages are the one thing that is not literally the
pupil's own: they were sent by the tutor or the parent, but they hang off the pupil's link and
the policy deletes messages with the accounts they belong to, so they are in scope. A pupil is
never a tutor or a message sender, and never a Subscription payer (that is SET_NULL anyway).

Each selected pupil is printed with those counts. Before anything is deleted the real cascade
is built with `NestedObjects`, tallied per model and compared with the printed counts; a
mismatch, or a model outside the expected set, raises CommandError, and in a live run that
rolls the whole transaction back. `delete()`'s own per-model return is compared the same way.

A live run refuses a window shorter than 30 days; short windows are for dry runs only.

Run:  python main.py purge_inactive_pupils --dry-run
      python main.py purge_inactive_pupils
      python main.py purge_inactive_pupils --days 400
"""
from datetime import timedelta

from django.contrib.admin.utils import NestedObjects
from django.core.management.base import BaseCommand, CommandError
from django.db import router, transaction
from django.db.models import Max
from django.utils import timezone

from accounts.models import User
from assignments.models import Assignment
from billing.models import Subscription
from goals.models import Goal, SectionTarget
from practice.models import Attempt, TestSession
from tutoring.models import TutorMessage, TutorStudent
from vocab.models import Round, RoundItem, VocabProfile, WordProgress

DEMO_DOMAIN = "@revisorplus.test"
PAID = [Subscription.Status.ACTIVE, Subscription.Status.PAST_DUE]
# Every model a pupil's deletion may reach; anything else is a surprise and stops the run.
ALLOWED_MODELS = {
    "User", "TestSession", "Attempt", "Goal", "SectionTarget", "Assignment", "TutorStudent",
    "TutorMessage", "Subscription", "VocabProfile", "WordProgress", "Round", "RoundItem",
}


def _vocab_profile(user):
    try:
        return user.vocab_profile
    except VocabProfile.DoesNotExist:
        return None


def _last_activity(user, cutoff):
    """(newest of the three signals or None, whether any of them is inside the window)."""
    profile = _vocab_profile(user)
    played = profile.last_played_on if profile else None
    signals = [
        user.last_login.date() if user.last_login else None,
        user.last_attempt.date() if user.last_attempt else None,
        played,
    ]
    present = [s for s in signals if s is not None]
    recent = (
        (user.last_login is not None and user.last_login >= cutoff)
        or (user.last_attempt is not None and user.last_attempt >= cutoff)
        or (played is not None and played >= cutoff.date())
    )
    return (max(present) if present else None), recent


def _expected_counts(user):
    """Rows the pupil's deletion should remove, by model name, from explicit queries."""
    profile = 1 if _vocab_profile(user) else 0
    counts = {
        "User": 1,
        "TestSession": TestSession.objects.filter(student=user).count(),
        "Attempt": Attempt.objects.filter(student=user).count(),
        "Goal": Goal.objects.filter(student=user).count(),
        "SectionTarget": SectionTarget.objects.filter(goal__student=user).count(),
        "Assignment": Assignment.objects.filter(student=user).count(),
        "TutorStudent": TutorStudent.objects.filter(student=user).count(),
        "TutorMessage": TutorMessage.objects.filter(link__student=user).count(),
        "Subscription": Subscription.objects.filter(user=user).count(),
        "VocabProfile": profile,
        "WordProgress": WordProgress.objects.filter(pupil=user).count(),
        "Round": Round.objects.filter(pupil=user).count(),
        "RoundItem": RoundItem.objects.filter(round__pupil=user).count(),
    }
    return {k: v for k, v in counts.items() if v}


def _cascade_tally(user):
    collector = NestedObjects(using=router.db_for_write(User))
    collector.collect([user])
    tally = {}
    for objs in collector.data.values():
        for obj in objs:
            name = type(obj).__name__
            tally[name] = tally.get(name, 0) + 1
    return tally


def _compare(user, actual, expected, source):
    unexpected = set(actual) - ALLOWED_MODELS
    if unexpected:
        raise CommandError(f"MISMATCH: {user.username}: {source} reaches unexpected model(s) {sorted(unexpected)}")
    if actual != expected:
        raise CommandError(f"MISMATCH: {user.username}: {source} {actual} does not match the counts {expected}")


class Command(BaseCommand):
    help = "Delete pupils with no login, attempt or vocab play for --days days (default 365), with their history."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=365, help="inactivity window in days (default 365); 0 selects every pupil with no activity "
                 "whatsoever that is not otherwise guarded")
        parser.add_argument("--dry-run", action="store_true", help="list and verify, delete nothing")

    def _select(self, cutoff, verbosity):
        pupils = User.objects.filter(role=User.Role.STUDENT)
        total = pupils.count()
        guards = [
            ("demo email", pupils.filter(email__iendswith=DEMO_DOMAIN)),
            ("demo parent", pupils.filter(parent__email__iendswith=DEMO_DOMAIN)),
            ("joined within window", pupils.filter(date_joined__gte=cutoff)),
            ("paid subscription", pupils.filter(subscription__status__in=PAID)),
        ]
        candidates = (
            pupils.exclude(email__iendswith=DEMO_DOMAIN)
            .exclude(parent__email__iendswith=DEMO_DOMAIN)
            .exclude(date_joined__gte=cutoff)
            .exclude(subscription__status__in=PAID)
            .annotate(last_attempt=Max("attempts__created_at"))
            .select_related("parent", "vocab_profile")
            .order_by("pk")
        )
        selected = [u for u in candidates if not _last_activity(u, cutoff)[1]]
        if verbosity >= 2:
            self.stdout.write(f"cutoff: {cutoff.isoformat()}  pupils: {total}")
            for label, qs in guards:
                self.stdout.write(f"skipped by guard ({label}): {qs.count()}")
            self.stdout.write(f"skipped as recently active: {len(candidates) - len(selected)}")
        return selected

    def _line(self, user, cutoff, counts):
        last, _ = _last_activity(user, cutoff)
        vocab = sum(counts.get(k, 0) for k in ("VocabProfile", "WordProgress", "Round", "RoundItem"))
        return (
            f"{user.username}  parent={user.parent.email if user.parent and user.parent.email else '-'}"
            f"  last_activity={last.isoformat() if last else 'never'}"
            f"  sessions={counts.get('TestSession', 0)} attempts={counts.get('Attempt', 0)}"
            f" goals={counts.get('Goal', 0)} targets={counts.get('SectionTarget', 0)}"
            f" assignments={counts.get('Assignment', 0)} links={counts.get('TutorStudent', 0)}"
            f" messages={counts.get('TutorMessage', 0)} vocab={vocab}"
            f" subscription={counts.get('Subscription', 0)}"
        )

    def _purge_one(self, user, expected):
        _, deleted = user.delete()
        returned = {label.split(".")[-1]: n for label, n in deleted.items() if n}
        _compare(user, returned, expected, "delete()")

    def handle(self, *args, **opts):
        days, dry_run, verbosity = opts["days"], opts["dry_run"], opts["verbosity"]
        if days < 0:
            raise CommandError("--days must be 0 or more")
        if days < 30 and not dry_run:
            raise CommandError("--days below 30 is allowed only with --dry-run")
        cutoff = timezone.now() - timedelta(days=days)
        selected = self._select(cutoff, verbosity)
        plan = [(u, _expected_counts(u)) for u in selected]
        for user, expected in plan:
            _compare(user, _cascade_tally(user), expected, "the cascade")
            if verbosity >= 1:
                self.stdout.write(self._line(user, cutoff, expected))
        deleted = 0
        if not dry_run:
            with transaction.atomic():
                for user, expected in plan:
                    self._purge_one(user, expected)
                    deleted += 1
        self.stdout.write(f"purge_inactive_pupils: {len(plan)} selected, {deleted} deleted")
