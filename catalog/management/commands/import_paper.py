"""
Import a whole exam paper into the question bank.

Distinct from `import_pack`, which loads flat MCQ contributor packs. Papers are a
different shape: timed, marked out of a total, free-entry answers rather than
multiple choice, questions split into parts a/b/c, and some items that only a
human can mark.

Run:  python manage.py import_paper elevenplus_data/revisor-maths-paper-01_2.json

Multi-part questions become a parent row carrying the shared stem and figure plus
one child row per answerable part, so a 26-question Maths paper lands as 26
parents and 47 answerable children. Only children go into practice decks.
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.figures import SUPPORTED as SUPPORTED_FIGURES
from catalog.models import Question, Section, Subtopic

# The papers use a dotted taxonomy of their own; the bank uses Section + canonical
# Subtopic. This is the whole mapping, and it doubles as the section lookup — the
# paper files carry no section code, so the topics are what identify the paper.
# An unmapped topic is a hard error, not a silent new subtopic: silently inventing
# "number.rounding" as a subtopic name is how a question disappears from the UI.
TOPIC_MAP = {
    # --- English ---
    "comprehension.retrieval": ("ENG", "Reading Comprehension"),
    "comprehension.inference": ("ENG", "Reading Comprehension"),
    "comprehension.language": ("ENG", "Reading Comprehension"),
    "comprehension.character": ("ENG", "Reading Comprehension"),
    "comprehension.language_structure": ("ENG", "Reading Comprehension"),
    "comprehension.vocabulary": ("ENG", "Vocabulary"),
    "grammar.punctuation": ("ENG", "Grammar & Punctuation"),
    "spelling.general": ("ENG", "Spelling"),
    # --- Maths ---
    "number.rounding": ("MAT", "Number & Place Value"),
    "number.place_value": ("MAT", "Number & Place Value"),
    "number.factors_multiples": ("MAT", "Number & Place Value"),
    "number.negatives": ("MAT", "Number & Place Value"),
    "number.four_operations": ("MAT", "Four Operations"),
    "fractions.of_amount": ("MAT", "Fractions, Decimals & Percentages"),
    "fractions.arithmetic": ("MAT", "Fractions, Decimals & Percentages"),
    "fdp.ordering": ("MAT", "Fractions, Decimals & Percentages"),
    "percentages.of_amount": ("MAT", "Fractions, Decimals & Percentages"),
    "algebra.linear_equations": ("MAT", "Algebra"),
    "algebra.simultaneous_word": ("MAT", "Algebra"),
    "sequences.linear": ("MAT", "Algebra"),
    "geometry.angles_line": ("MAT", "Geometry & Shape"),
    "geometry.perimeter_area": ("MAT", "Geometry & Shape"),
    "measures.time": ("MAT", "Measurement"),
    "measures.metric": ("MAT", "Measurement"),
    "ratio.scaling": ("MAT", "Ratio & Proportion"),
    "stats.tables": ("MAT", "Statistics & Data Handling"),
    "stats.venn": ("MAT", "Statistics & Data Handling"),
    "stats.mean_median_range": ("MAT", "Statistics & Data Handling"),
    "probability.basic": ("MAT", "Statistics & Data Handling"),
}

SECTION_ORDER = {"ENG": 1, "MAT": 2, "VR": 3, "NVR": 4}
SECTION_NAME = {"ENG": "English", "MAT": "Maths",
                "VR": "Verbal Reasoning", "NVR": "Non-Verbal Reasoning"}

ANSWER_KINDS = {
    "numeric": Question.Kind.NUMERIC,
    "short_text": Question.Kind.SHORT_TEXT,
    "extended_text": Question.Kind.EXTENDED_TEXT,
    "mcq": Question.Kind.MCQ,
}


class Command(BaseCommand):
    help = "Import an exam paper (JSON) into the question bank."

    def add_arguments(self, parser):
        parser.add_argument("json_path")
        parser.add_argument(
            "--allow-missing-passage", action="store_true",
            help="Import comprehension questions whose passage text is absent. They "
                 "are created INACTIVE, because a passage question with no passage "
                 "cannot be answered.",
        )
        parser.add_argument("--dry-run", action="store_true",
                            help="Report what would happen and roll back.")
        parser.add_argument(
            "--skip-if-present", action="store_true",
            help="Do nothing if this paper is already imported. Re-importing "
                 "replaces its questions, and deleting a question CASCADES to every "
                 "Attempt against it — so an unconditional re-import on each deploy "
                 "would erase pupils' history for this paper. build.sh uses this.",
        )

    def handle(self, *args, **opts):
        path = Path(opts["json_path"])
        try:
            data = json.loads(path.read_text())
        except FileNotFoundError:
            raise CommandError(f"{path}: not found")
        except json.JSONDecodeError as exc:
            raise CommandError(f"{path}: not valid JSON — {exc}")

        paper_id = data.get("paper_id") or path.stem
        source = f"PAPER-{paper_id}".upper()[:50]
        questions = data.get("questions") or []
        if not questions:
            raise CommandError(f"{path}: no 'questions' list")

        if opts["skip_if_present"]:
            existing = Question.objects.filter(source=source).count()
            if existing:
                self.stdout.write(
                    f"{paper_id}: already imported ({existing} rows) — skipping to "
                    f"preserve pupil attempts. Re-run without --skip-if-present to "
                    f"replace it (that will delete those attempts)."
                )
                return

        # --- section, derived from the topics rather than guessed from a filename
        codes = set()
        unmapped = set()
        for q in questions:
            topic = q.get("topic")
            if topic in TOPIC_MAP:
                codes.add(TOPIC_MAP[topic][0])
            else:
                unmapped.add(topic)
        if unmapped:
            raise CommandError(
                f"{path}: {len(unmapped)} topic(s) not in TOPIC_MAP: "
                f"{sorted(unmapped)}. Add them to catalog/management/commands/"
                "import_paper.py rather than letting them create stray subtopics."
            )
        if len(codes) != 1:
            raise CommandError(f"{path}: topics span sections {sorted(codes)}; "
                               "one paper must be one section.")
        code = codes.pop()

        # --- the passage a comprehension paper is built on
        passage = (data.get("passage_text") or "").strip()
        declares_passage = bool(data.get("passage_id") or data.get("passage_title"))
        passage_missing = declares_passage and not passage
        if passage_missing and not opts["allow_missing_passage"]:
            raise CommandError(
                f"{path}: declares a passage ({data.get('passage_title')!r}, "
                f"{data.get('passage_words')} words) but contains no 'passage_text'. "
                f"Every question in this paper is asked about that text, so none of "
                f"them can be answered without it.\n"
                f"  Fix: add a \"passage_text\" key with the passage body.\n"
                f"  Or:  re-run with --allow-missing-passage to import them inactive."
            )

        section, _ = Section.objects.get_or_create(
            code=code,
            defaults={"name": SECTION_NAME.get(code, code),
                      "order": SECTION_ORDER.get(code, 99)},
        )

        stats = {"parents": 0, "parts": 0, "rubric": 0, "inactive": 0, "figures": 0}
        warnings = []

        with transaction.atomic():
            removed = Question.objects.filter(
                source=source, subtopic__section=section
            ).delete()[0]

            for index, raw in enumerate(questions):
                self._import_question(
                    raw, index, section, source, passage, passage_missing, stats, warnings
                )

            if opts["dry_run"]:
                transaction.set_rollback(True)

        for warning in warnings:
            self.stdout.write(self.style.WARNING(f"  ! {warning}"))

        verb = "would import" if opts["dry_run"] else "imported"
        self.stdout.write(self.style.SUCCESS(
            f"{code} {paper_id}: removed {removed}, {verb} {stats['parents']} questions "
            f"-> {stats['parts']} answerable parts "
            f"({stats['figures']} with figures, {stats['rubric']} needing a human marker, "
            f"{stats['inactive']} inactive). source={source}"
        ))
        if stats["inactive"]:
            self.stdout.write(self.style.WARNING(
                f"  {stats['inactive']} question(s) are INACTIVE and will not appear in "
                "practice. Supply the missing passage text and re-run to activate them."
            ))
        if opts["dry_run"]:
            self.stdout.write(self.style.WARNING("  --dry-run: rolled back."))

    # ------------------------------------------------------------------ helpers

    def _figure(self, raw, warnings, qid):
        """Paper figure spec -> {"kind", "data"} the renderer understands."""
        if isinstance(raw.get("table"), dict):
            return {"kind": "table", "data": raw["table"]}
        if raw.get("numbers_shown"):
            return {"kind": "number_box", "data": {"numbers": raw["numbers_shown"]}}
        name = raw.get("svg")
        if name:
            if name == "number_box":
                return {"kind": "number_box",
                        "data": {"numbers": raw.get("numbers_shown") or []}}
            if name in SUPPORTED_FIGURES:
                return {"kind": name, "data": raw.get("dimensions") or {}}
            warnings.append(
                f"{qid}: figure {name!r} is not one this build can draw "
                f"(known: {sorted(SUPPORTED_FIGURES)}). Imported without a diagram — "
                f"check the question still makes sense."
            )
        return None

    def _import_question(self, raw, index, section, source, passage,
                         passage_missing, stats, warnings):
        code, subtopic_name = TOPIC_MAP[raw["topic"]]
        subtopic, _ = Subtopic.objects.get_or_create(section=section, name=subtopic_name)
        qid = raw.get("id") or f"q{index}"

        # English puts the question text in `prompt`, Maths in `stem`.
        stem = (raw.get("stem") or raw.get("prompt") or "").strip()
        difficulty = raw.get("difficulty")
        difficulty = min(5, max(1, int(difficulty))) if isinstance(difficulty, int) else 2
        figure = self._figure(raw, warnings, qid)
        parts = raw.get("parts") or []
        # A paper question is only answerable itself when it has no parts.
        active = not passage_missing

        parent = Question.objects.create(
            subtopic=subtopic, source=source, is_placeholder=False,
            stem=stem, passage=passage, difficulty=difficulty, figure=figure,
            marks=raw.get("marks") or 1, order=raw.get("number") or index,
            active=active,
            kind=ANSWER_KINDS.get(raw.get("answer_type"), Question.Kind.MCQ),
            marking=self._marking(raw, parts),
            model_answer=raw.get("model_answer") or "",
            rubric=raw.get("rubric") if isinstance(raw.get("rubric"), dict) else None,
        )
        stats["parents"] += 1
        if figure:
            stats["figures"] += 1

        if not parts:
            self._finish_leaf(parent, raw, stats)
            if not active:
                stats["inactive"] += 1
            return

        for order, part in enumerate(parts):
            child = Question.objects.create(
                subtopic=subtopic, parent=parent, source=source, is_placeholder=False,
                stem=self._part_stem(part),
                passage=passage,
                difficulty=difficulty,
                marks=part.get("marks") or 1,
                label=(part.get("label") or "")[:4],
                order=order,
                active=active,
                kind=ANSWER_KINDS.get(part.get("answer_type"),
                                      ANSWER_KINDS.get(raw.get("answer_type"),
                                                       Question.Kind.SHORT_TEXT)),
                marking=self._marking(part, []),
                unit=(part.get("unit") or "")[:16],
                working_note=part.get("working_note") or "",
                model_answer=part.get("model_answer") or "",
                rubric=part.get("rubric") if isinstance(part.get("rubric"), dict) else None,
            )
            self._finish_leaf(child, part, stats)
            stats["parts"] += 1
            if not active:
                stats["inactive"] += 1

    @staticmethod
    def _marking(raw, parts):
        """Which marker can handle this: exact/numeric, keywords, or a person."""
        if raw.get("marking") == "rubric" or isinstance(raw.get("rubric"), dict):
            return Question.Marking.RUBRIC
        if raw.get("answer_type") == "extended_text":
            return Question.Marking.RUBRIC
        if raw.get("accepted_keywords") or raw.get("reject_keywords"):
            return Question.Marking.KEYWORD
        return Question.Marking.AUTO

    @staticmethod
    def _part_stem(part):
        """Vocabulary parts carry a target word and its context rather than a
        prompt, so build a stem a pupil can actually read."""
        if part.get("prompt"):
            return part["prompt"].strip()
        word = part.get("target_word")
        if word:
            context = part.get("context")
            return f"“{word}” — as used in: “{context}”" if context else f"“{word}”"
        return ""

    @staticmethod
    def _finish_leaf(question, raw, stats):
        """Attach the answer key to an answerable row."""
        updates = []
        answer = raw.get("answer")
        if answer is not None:
            question.answer_text = str(answer)[:200]
            updates.append("answer_text")
        tolerance = raw.get("tolerance")
        if tolerance is not None:
            question.tolerance = float(tolerance)
            updates.append("tolerance")
        # Keyword lists and word-form alternatives share one field: both are
        # "things that count as right", and the marking engine reads them per kind.
        accepted = list(raw.get("accepted_alternatives") or []) + \
            list(raw.get("accepted_keywords") or [])
        if accepted:
            question.accepted_alternatives = accepted
            updates.append("accepted_alternatives")
        if raw.get("reject_keywords"):
            question.reject_keywords = list(raw["reject_keywords"])
            updates.append("reject_keywords")
        if question.marking == Question.Marking.RUBRIC:
            stats["rubric"] += 1
        if updates:
            question.save(update_fields=updates)
