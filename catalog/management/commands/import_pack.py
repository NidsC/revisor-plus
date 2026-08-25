"""
Import a question pack (JSON) into the question bank.

Idempotent per-source: re-running a pack replaces only that pack's questions in
that section, so importing one pack never touches another's.

Run:  python manage.py import_pack path/to/contrib_alex_01.json
"""
import json

from django.core.management.base import BaseCommand, CommandError

from catalog.models import AnswerOption, Question, Section, Subtopic

SECTION_ORDER = {"ENG": 1, "MAT": 2, "VR": 3, "NVR": 4}


class Command(BaseCommand):
    help = "Import a question pack from a JSON file."

    def add_arguments(self, parser):
        parser.add_argument("json_path")

    def handle(self, *args, **opts):
        with open(opts["json_path"]) as f:
            data = json.load(f)

        sec = data["section"]
        # No default: an unset source would scope the delete below to source="",
        # which is what admin-added questions carry — importing would wipe them.
        source = sec.get("source")
        if not source:
            raise CommandError(
                f"{opts['json_path']}: section.source is required and must be unique to "
                "this pack (e.g. \"CONTRIB-ALEX-01\"). See elevenplus_data/CLAUDE.md."
            )
        # Whole-pack default: packs are team-authored IP unless they say otherwise.
        pack_placeholder = sec.get("is_placeholder", False)
        section, _ = Section.objects.get_or_create(
            code=sec["code"],
            defaults={"name": sec["name"], "order": SECTION_ORDER.get(sec["code"], 99)},
        )

        # Idempotent per-source: clear only THIS source's questions in the section.
        n_del = Question.objects.filter(source=source, subtopic__section=section).delete()[0]

        created = 0
        for q in data["questions"]:
            sub, _ = Subtopic.objects.get_or_create(section=section, name=q["subtopic"])
            kind = q.get("kind", "mcq")
            question = Question.objects.create(
                subtopic=sub,
                # The third taxonomy level. Until this was added the validator
                # required question_type on every Maths question and the
                # importer silently dropped it, so the whole level was lost the
                # moment a pack was imported.
                question_type=q.get("question_type", ""),
                # Secondary subtopics a question also needs. 38% of real 11+
                # questions have them; see Question.also_tests.
                also_tests=q.get("also_tests", []),
                kind=kind,
                passage=q.get("passage", ""),
                stem=q["stem"],
                explanation=q.get("explanation", ""),
                image=q.get("image", ""),
                difficulty=q.get("difficulty", 2),
                is_placeholder=q.get("is_placeholder", pack_placeholder),
                source=source,
                # Free-response fields. Ignored for MCQ, and the marking engine
                # (catalog/marking.py) reads them per kind: NUMERIC compares
                # answer_text within tolerance, SHORT_TEXT matches answer_text
                # or one of accepted_alternatives.
                answer_text=str(q.get("answer", "")),
                tolerance=q.get("tolerance", 0) or 0,
                accepted_alternatives=q.get("accepted_alternatives", []),
                unit=q.get("unit", ""),
            )
            # Options are the answer for MCQ and absent for everything else.
            for i, opt in enumerate(q.get("options") or []):
                AnswerOption.objects.create(
                    question=question, text=opt["text"],
                    is_correct=opt.get("correct", False), order=i,
                )
            created += 1

        self.stdout.write(self.style.SUCCESS(
            f"{section.code}: removed {n_del} old {source} questions, imported {created}."
        ))
