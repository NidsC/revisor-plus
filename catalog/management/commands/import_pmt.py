"""
Import PMT-derived questions from a JSON file into the question bank.

These are placeholder demo questions (flagged is_placeholder / source="PMT").
Idempotent: re-running for a section replaces that section's PMT questions.

Run:  python manage.py import_pmt path/to/decision_making.json
"""
import json

from django.core.management.base import BaseCommand

from catalog.models import AnswerOption, Question, Section, Subtopic

SECTION_ORDER = {"VR": 1, "DM": 2, "QR": 3, "SJT": 4}


class Command(BaseCommand):
    help = "Import PMT placeholder questions from a JSON file."

    def add_arguments(self, parser):
        parser.add_argument("json_path")

    def handle(self, *args, **opts):
        with open(opts["json_path"]) as f:
            data = json.load(f)

        sec = data["section"]
        source = sec.get("source", "PMT")
        # Whole-pack default: PMT/legacy files omit this and stay placeholder (True);
        # team-authored packs declare "is_placeholder": false to mark them as owned IP.
        pack_placeholder = sec.get("is_placeholder", True)
        section, _ = Section.objects.get_or_create(
            code=sec["code"],
            defaults={"name": sec["name"], "order": SECTION_ORDER.get(sec["code"], 99)},
        )

        # Idempotent per-source: clear only THIS source's questions in the section,
        # so importing a mock never wipes the module packs (both are placeholder PMT).
        n_del = Question.objects.filter(source=source, subtopic__section=section).delete()[0]

        created = 0
        for q in data["questions"]:
            sub, _ = Subtopic.objects.get_or_create(section=section, name=q["subtopic"])
            question = Question.objects.create(
                subtopic=sub,
                kind=q.get("kind", "mcq"),
                passage=q.get("passage", ""),
                stem=q["stem"],
                explanation=q.get("explanation", ""),
                image=q.get("image", ""),
                difficulty=q.get("difficulty", 2),
                is_placeholder=q.get("is_placeholder", pack_placeholder),
                source=source,
            )
            for i, opt in enumerate(q["options"]):
                AnswerOption.objects.create(
                    question=question, text=opt["text"],
                    is_correct=opt.get("correct", False), order=i,
                )
            created += 1

        self.stdout.write(self.style.SUCCESS(
            f"{section.code}: removed {n_del} old PMT questions, imported {created}."
        ))
