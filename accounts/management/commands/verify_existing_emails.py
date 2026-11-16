"""
Mark the email addresses of older parents and tutors as verified.

Email verification became mandatory on 2026-11-04 (ACCOUNT_EMAIL_VERIFICATION). A parent or
tutor who signed up before then has no verified EmailAddress row, so on their next login
allauth would hold them at the verification page. This command vouches for those accounts:
every parent or tutor who joined before the --before date and has an email gets a verified,
primary EmailAddress row (created if missing). Pupils have no email and are never selected;
nor is anyone who joined on or after the --before date.

--before must be a past date (before today), so the command can never vouch for accounts
that signed up under the verification rule. Without --apply it is a dry run and changes
nothing. Only the @domain of each address is printed, never the full address.

Run:  python main.py verify_existing_emails --before <YYYY-MM-DD>
      python main.py verify_existing_emails --before <YYYY-MM-DD> --apply
(the date verification went live; must be before today)
"""
from datetime import datetime

from allauth.account.models import EmailAddress
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import User


def _parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise CommandError(f"--before must be a date written YYYY-MM-DD, got {value!r}")


class Command(BaseCommand):
    help = "Mark pre-verification parent and tutor email addresses as verified (dry run unless --apply)."

    def add_arguments(self, parser):
        parser.add_argument("--before", required=True, type=_parse_date,
                            help="Only accounts that joined before this date, YYYY-MM-DD (must be in the past).")
        parser.add_argument("--apply", action="store_true",
                            help="Write the changes. Without it nothing is changed.")

    def handle(self, *args, before, apply, **options):
        if before >= timezone.localdate():
            raise CommandError("--before must be earlier than today.")
        cutoff = timezone.make_aware(datetime.combine(before, datetime.min.time()))
        users = list(
            User.objects.filter(role__in=[User.Role.PARENT, User.Role.TUTOR], date_joined__lt=cutoff)
            .exclude(email__isnull=True).exclude(email="").order_by("pk")
        )
        verified = 0
        with transaction.atomic():
            for user in users:
                outcome = self._handle_user(user, apply)
                if outcome == "verified":
                    verified += 1
                domain = user.email.rsplit("@", 1)[-1]
                self.stdout.write(f"{user.role} @{domain}: {outcome}")
        if not apply:
            self.stdout.write("dry run: nothing changed")
        self.stdout.write(f"verify_existing_emails: {len(users)} selected, {verified} verified")

    def _handle_user(self, user, apply):
        row = EmailAddress.objects.filter(user=user, email__iexact=user.email).first()
        if row is not None and row.verified:
            return "already verified"
        if not apply:
            return "would verify"
        if row is None:
            row = EmailAddress(user=user, email=user.email)
        row.verified = True
        if not EmailAddress.objects.filter(user=user, primary=True).exclude(pk=row.pk).exists():
            row.primary = True
        row.save()
        return "verified"
