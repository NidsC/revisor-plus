"""
Write elevenplus_data/taxonomy.json into the database.

Creates any missing Section and Subtopic rows and fixes their display order, so
the taxonomy in the JSON file is the taxonomy the app shows. Safe to re-run.

**This command never deletes anything.** Deleting a Subtopic cascades into
Attempt (practice/models.py), which would destroy pupils' answer history for
that area and every accuracy figure derived from it. So a subtopic that exists
in the database but not in taxonomy.json is *reported*, not removed. Retiring
one is a deliberate, separate act.

`--dry-run` writes nothing at all — not even the Section row it would need to hang
the rest of the report off. That is enforced twice over: every write is guarded by
the flag, and the whole dry pass runs in a transaction that is rolled back.

Run:  python main.py sync_taxonomy
      python main.py sync_taxonomy --section MAT
      python main.py sync_taxonomy --dry-run
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.models import Question, Section, Subtopic

TAXONOMY = Path("elevenplus_data/taxonomy.json")
SECTION_ORDER = {"ENG": 1, "MAT": 2, "VR": 3, "NVR": 4}


class _Rollback(Exception):
    """Raised at the end of a --dry-run pass to undo anything it touched."""


class Command(BaseCommand):
    help = "Sync sections and subtopics from elevenplus_data/taxonomy.json."

    def add_arguments(self, parser):
        parser.add_argument(
            "--section", help="Only sync this section code (ENG/MAT/VR/NVR).")
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report what would change without writing anything.")

    def handle(self, *args, **opts):
        if not TAXONOMY.exists():
            raise CommandError(f"{TAXONOMY} not found — run from the repo root.")
        data = json.loads(TAXONOMY.read_text())

        wanted = opts.get("section")
        sections = data["sections"]
        if wanted:
            if wanted not in sections:
                raise CommandError(
                    f"unknown section {wanted!r}; taxonomy has "
                    f"{', '.join(sorted(sections))}")
            sections = {wanted: sections[wanted]}

        dry = opts["dry_run"]

        if dry:
            # Belt and braces, and the belt is the point. Every write in _sync is
            # guarded by `if not dry`, but that guard is a promise the next edit can
            # quietly break — this command shipped for months with an unguarded
            # Section.objects.get_or_create, so `--dry-run` created section rows
            # while printing "nothing was written". Running the pass inside a
            # transaction that always rolls back makes the claim true by
            # construction instead of by review: a write added later is undone
            # whether or not whoever added it remembered the flag.
            try:
                with transaction.atomic():
                    created_subs, renumbered = self._sync(sections, dry=True)
                    raise _Rollback
            except _Rollback:
                pass
        else:
            created_subs, renumbered = self._sync(sections, dry=False)

        verb = "would create" if dry else "created"
        self.stdout.write(self.style.SUCCESS(
            f"{verb} {created_subs} subtopic(s), reordered {renumbered}."
        ))
        if dry:
            self.stdout.write("Dry run — nothing was written.")

    def _sync(self, sections, dry):
        """Apply the taxonomy, or report what applying it would do.

        Returns (subtopics created, subtopics whose fields were corrected). Every
        write is guarded by `dry`; see handle() for the transaction that backs the
        guard up.
        """
        created_subs = renumbered = 0

        for code, sec in sections.items():
            section = Section.objects.filter(code=code).first()
            if section is None:
                self.stdout.write(f"  + section {code}")
                if not dry:
                    section = Section.objects.create(
                        code=code,
                        name=sec["name"],
                        order=SECTION_ORDER.get(code, 99),
                    )

            # name -> the fields taxonomy.json owns. `topic` and `topic_order`
            # are blank for sections whose taxonomy has no topic layer yet.
            canonical = {
                s["name"]: {
                    "order": s["order"],
                    "topic": s.get("topic", ""),
                    "topic_order": s.get("topic_order", 0),
                }
                for s in sec["subtopics"]
            }

            for name, want in canonical.items():
                # `section is None` only on a dry run of a section that does not
                # exist yet — in which case nothing under it exists either, so
                # every subtopic is reported as a creation rather than queried for.
                sub = (Subtopic.objects.filter(section=section, name=name).first()
                       if section is not None else None)
                if sub is None:
                    if not dry:
                        Subtopic.objects.create(section=section, name=name, **want)
                    created_subs += 1
                    topic = f" [{want['topic']}]" if want["topic"] else ""
                    self.stdout.write(f"  + {code} · {name}{topic}")
                    continue
                stale = [f for f, v in want.items() if getattr(sub, f) != v]
                if stale:
                    if not dry:
                        for f in stale:
                            setattr(sub, f, want[f])
                        sub.save(update_fields=stale)
                    renumbered += 1
                    self.stdout.write(f"  ~ {code} · {name} ({', '.join(stale)})")

            # Anything in the database but not in the taxonomy. Reported only —
            # see the module docstring for why this command will not delete it.
            extra = (Subtopic.objects.filter(section=section)
                     .exclude(name__in=canonical.keys())
                     if section is not None else [])
            for sub in extra:
                n = Question.objects.filter(subtopic=sub).count()
                self.stdout.write(self.style.WARNING(
                    f"  ! {code} · {sub.name} — not in taxonomy.json, holds "
                    f"{n} question(s). Left in place; retire it deliberately."
                ))

        return created_subs, renumbered
