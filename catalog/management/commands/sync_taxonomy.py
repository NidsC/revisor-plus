"""
Write elevenplus_data/taxonomy.json into the database.

Creates any missing Section and Subtopic rows and fixes their display order, so
the taxonomy in the JSON file is the taxonomy the app shows. Safe to re-run.

**This command never deletes anything.** Deleting a Subtopic cascades into
Attempt (practice/models.py), which would destroy pupils' answer history for
that area and every accuracy figure derived from it. So a subtopic that exists
in the database but not in taxonomy.json is *reported*, not removed. Retiring
one is a deliberate, separate act.

Run:  python manage.py sync_taxonomy
      python manage.py sync_taxonomy --section MAT
      python manage.py sync_taxonomy --dry-run
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from catalog.models import Question, Section, Subtopic

TAXONOMY = Path("elevenplus_data/taxonomy.json")
SECTION_ORDER = {"ENG": 1, "MAT": 2, "VR": 3, "NVR": 4}


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
        created_subs = renumbered = 0

        for code, sec in sections.items():
            section, made = Section.objects.get_or_create(
                code=code,
                defaults={"name": sec["name"], "order": SECTION_ORDER.get(code, 99)},
            )
            if made:
                self.stdout.write(f"  + section {code}")

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
                sub = Subtopic.objects.filter(section=section, name=name).first()
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
            extra = Subtopic.objects.filter(section=section).exclude(
                name__in=canonical.keys())
            for sub in extra:
                n = Question.objects.filter(subtopic=sub).count()
                self.stdout.write(self.style.WARNING(
                    f"  ! {code} · {sub.name} — not in taxonomy.json, holds "
                    f"{n} question(s). Left in place; retire it deliberately."
                ))

        verb = "would create" if dry else "created"
        self.stdout.write(self.style.SUCCESS(
            f"{verb} {created_subs} subtopic(s), reordered {renumbered}."
        ))
        if dry:
            self.stdout.write("Dry run — nothing was written.")
