from __future__ import annotations

import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from school_onboarding.models import School


OPEN_STATUSES = {"Open", "Open, but proposed to close"}


def _text(row, *keys):
    for key in keys:
        value = row.get(key)
        if value is not None:
            return str(value).strip()
    return ""


def _int(value):
    try:
        text = str(value).strip()
        if not text:
            return None
        return int(float(text))
    except (TypeError, ValueError):
        return None


class Command(BaseCommand):
    help = "Import open secondary-age schools from a DfE GIAS Establishment fields CSV."

    def add_arguments(self, parser):
        parser.add_argument("csv_file", type=str)
        parser.add_argument(
            "--all-open",
            action="store_true",
            help="Import every open establishment instead of only secondary-age establishments.",
        )
        parser.add_argument(
            "--keep-missing-coordinates",
            action="store_true",
            help="Keep rows without Easting/Northing. They can be found by name but not postcode distance.",
        )

    def handle(self, *args, **options):
        path = Path(options["csv_file"]).expanduser().resolve()
        if not path.exists():
            raise CommandError(f"File not found: {path}")

        created = updated = skipped = 0
        batch = []

        # GIAS downloads are commonly Windows-1252/latin-1 compatible.
        try:
            fh = path.open("r", encoding="utf-8-sig", newline="")
            fh.read(4096)
            fh.seek(0)
        except UnicodeDecodeError:
            fh = path.open("r", encoding="latin-1", newline="")

        with fh:
            reader = csv.DictReader(fh)
            required = {"URN", "EstablishmentName", "EstablishmentStatus (name)", "Postcode"}
            missing = required.difference(reader.fieldnames or [])
            if missing:
                raise CommandError(
                    "This does not look like the GIAS Establishment fields CSV. "
                    f"Missing columns: {', '.join(sorted(missing))}"
                )

            for row in reader:
                urn = _text(row, "URN")
                name = _text(row, "EstablishmentName")
                status = _text(row, "EstablishmentStatus (name)")
                if not urn or not name or status not in OPEN_STATUSES:
                    skipped += 1
                    continue

                low_age = _int(_text(row, "StatutoryLowAge"))
                high_age = _int(_text(row, "StatutoryHighAge"))

                # Covers secondary, all-through and independent secondary-age schools
                # without relying on one particular GIAS phase label.
                if not options["all_open"]:
                    if high_age is None or high_age < 16:
                        skipped += 1
                        continue
                    if low_age is not None and low_age > 13:
                        skipped += 1
                        continue

                easting = _int(_text(row, "Easting"))
                northing = _int(_text(row, "Northing"))
                if not options["keep_missing_coordinates"] and (easting is None or northing is None):
                    skipped += 1
                    continue

                defaults = {
                    "name": name,
                    "postcode": _text(row, "Postcode").upper(),
                    "town": _text(row, "Town"),
                    "county": _text(row, "County (name)", "County"),
                    "establishment_type": _text(row, "TypeOfEstablishment (name)"),
                    "admissions_policy": _text(row, "AdmissionsPolicy (name)"),
                    "gender": _text(row, "Gender (name)"),
                    "phase": _text(row, "PhaseOfEducation (name)"),
                    "status": status,
                    "statutory_low_age": low_age,
                    "statutory_high_age": high_age,
                    "easting": easting,
                    "northing": northing,
                }
                _, was_created = School.objects.update_or_create(urn=urn, defaults=defaults)
                if was_created:
                    created += 1
                else:
                    updated += 1

                if (created + updated) % 1000 == 0:
                    self.stdout.write(f"Processed {created + updated:,} schools...")

        self.stdout.write(self.style.SUCCESS(
            f"GIAS import complete: {created:,} created, {updated:,} updated, {skipped:,} skipped."
        ))
