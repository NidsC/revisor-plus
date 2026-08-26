"""
Import a question pack (JSON) into the question bank.

Idempotent per-source: re-running a pack replaces only that pack's questions in
that section, so importing one pack never touches another's.

Run:  python manage.py import_pack path/to/contrib_alex_01.json
"""
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from catalog.models import (
    NO_ERROR_LABEL, NO_ERROR_TEXT, OPTION_LABELS,
    AnswerOption, Question, Section, Subtopic,
)

# Anchored to BASE_DIR, not the working directory. This was a relative path, and
# a relative path made `subtopic_aliases` return {} whenever the importer ran
# from anywhere but the repo root — which is exactly the silent failure its own
# docstring exists to prevent, because an unresolved slug does not error, it
# quietly creates a second Subtopic named `literal_retrieval` beside the real
# one and files the questions there.
TAXONOMY = Path(settings.BASE_DIR) / "elevenplus_data" / "taxonomy.json"
SECTION_ORDER = {"ENG": 1, "MAT": 2, "VR": 3, "NVR": 4}


def _build_options(question, q, kind):
    """Store the choices a question offers, whatever shape they arrive in.

    Ordinary choices come as `options`. Spot-the-error and click-the-word give
    `segments` instead — consecutive pieces of the sentence — and those become
    options too, in reading order, because picking one is the same act and marks
    the same way. Keeping them as options is what lets the marking engine stay a
    single path; only the rendering differs.
    """
    if kind in Question.SELECTION_KINDS:
        answer = str(q.get("answer", ""))
        for i, seg in enumerate(q.get("segments") or []):
            AnswerOption.objects.create(
                question=question, text=seg["text"], label=seg["label"],
                is_correct=(seg["label"] == answer), order=i,
            )
        if q.get("allow_no_error"):
            # Rendered apart from the sentence: it is an answer about the
            # sentence, not a piece of it.
            AnswerOption.objects.create(
                question=question, text=NO_ERROR_TEXT, label=NO_ERROR_LABEL,
                is_correct=(answer == NO_ERROR_LABEL),
                order=len(q.get("segments") or []),
            )
        return

    for i, opt in enumerate(q.get("options") or []):
        AnswerOption.objects.create(
            question=question, text=opt["text"],
            is_correct=opt.get("correct", False), order=i,
            label=OPTION_LABELS[i] if i < len(OPTION_LABELS) else "",
            # A non-verbal answer is a picture. `text` is still required and
            # still carries the panel in words — the contract's rule is that
            # anything needed to answer must be in the text — but this is what
            # the pupil actually compares against the question.
            figure=opt.get("figure"),
        )


def section_name(code):
    """The canonical display name for a section code, from the taxonomy.

    Used only as a fallback when a pack header omits `name`; falls back again to
    the code itself so a taxonomy that has lost a section still imports.
    """
    if not TAXONOMY.exists():
        return code
    sec = json.loads(TAXONOMY.read_text()).get("sections", {}).get(code) or {}
    return sec.get("name") or code


def subtopic_aliases(code):
    """snake_case subtopic slug -> canonical name, for one section.

    The English and VR schemas identify a subtopic by slug (`literal_retrieval`)
    while the bank stores and displays a name ("Literal Retrieval"). The
    validator accepts either, so the importer has to resolve either — otherwise
    a pack written to the schema would silently create a second subtopic named
    after the slug and file its questions somewhere the taxonomy never mentions.
    """
    if not TAXONOMY.exists():
        # Fail loudly. Returning {} here means every slug-written subtopic lands
        # in an orphan of its own, which no check downstream can see.
        raise CommandError(f"taxonomy not found at {TAXONOMY} — cannot resolve subtopic slugs")
    data = json.loads(TAXONOMY.read_text())
    sec = data.get("sections", {}).get(code)
    if not sec:
        return {}
    return {s["slug"]: s["name"] for s in sec["subtopics"] if s.get("slug")}


class Command(BaseCommand):
    help = "Import a question pack from a JSON file."

    def add_arguments(self, parser):
        parser.add_argument("json_path")

    def _build_containers(self, data, section, source, aliases, pack_placeholder):
        """One container row per passage the pack declares. Returns {ref: Question}.

        A container is a Question that nobody answers — it only holds the text
        its questions share. The model already had this shape for multi-part
        paper questions (`parent`, `parts`, `is_container`, `context_passage`),
        and the practice deck already excludes anything with parts, so a
        container cannot be served to a pupil. All that was missing was the
        importer building one.

        Its stem stays empty on purpose: `display_stem` prefixes a parent's stem
        onto every child, so putting the passage title there would render every
        question as "Down the Rabbit-Hole What did Alice complain...".
        """
        passages = data.get("passages") or []
        if not passages:
            return {}

        # A passage's questions usually span several subtopics — a comprehension
        # passage runs through retrieval, inference and vocabulary — so the
        # container is filed under the first one that uses it. Nothing reads a
        # container's subtopic to decide what a pupil practises; the field is
        # simply required.
        first_sub = {}
        for q in data["questions"]:
            ref = q.get("passage_ref")
            if ref and ref not in first_sub:
                first_sub[ref] = aliases.get(q["subtopic"], q["subtopic"])

        containers = {}
        for i, p in enumerate(passages):
            ref = p["passage_ref"]
            if ref not in first_sub:
                # Declared but unused. The validator warns; there is nothing to
                # attach, so creating a childless container would put an
                # answerable empty question into the bank.
                continue
            sub, _ = Subtopic.objects.get_or_create(
                section=section, name=first_sub[ref])
            containers[ref] = Question.objects.create(
                subtopic=sub, source=source, is_placeholder=pack_placeholder,
                stem="", passage=p["text"],
                passage_title=p.get("title", "")[:200],
                passage_source=p.get("source_note", "")[:300],
                order=i, active=True,
            )
        return containers

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
        # `name` is optional in practice: the validator only warns when a pack omits
        # it, promising "import will still work". It did not — `sec["name"]` raised
        # KeyError here, and because build.sh runs under `set -o errexit` a merged
        # pack missing one line of its header failed the whole deploy, not just its
        # own import. Fall back to the canonical name from the taxonomy so the
        # validator's warning is true.
        section, _ = Section.objects.get_or_create(
            code=sec["code"],
            defaults={
                "name": sec.get("name") or section_name(sec["code"]),
                "order": SECTION_ORDER.get(sec["code"], 99),
            },
        )

        # Idempotent per-source: clear only THIS source's questions in the section.
        n_del = Question.objects.filter(source=source, subtopic__section=section).delete()[0]

        created = 0
        aliases = subtopic_aliases(sec["code"])
        containers = self._build_containers(data, section, source, aliases,
                                            pack_placeholder)
        for q in data["questions"]:
            name = aliases.get(q["subtopic"], q["subtopic"])
            sub, _ = Subtopic.objects.get_or_create(section=section, name=name)
            kind = q.get("kind", "mcq")
            parent = containers.get(q.get("passage_ref"))
            question = Question.objects.create(
                subtopic=sub,
                # Questions that share a passage hang off one container row that
                # owns the text, rather than each carrying their own copy. The
                # container is what makes a cloze section one passage with ten
                # gaps instead of ten questions each reprinting the passage.
                parent=parent,
                order=q.get("gap_number") or 0,
                # The third taxonomy level. Until this was added the validator
                # required question_type on every Maths question and the
                # importer silently dropped it, so the whole level was lost the
                # moment a pack was imported.
                question_type=q.get("question_type", ""),
                # Secondary subtopics a question also needs. 38% of real 11+
                # questions have them; see Question.also_tests. Names are
                # canonicalised the same way as the primary subtopic, so a
                # weakness report counts a slug-written pack and a name-written
                # one as the same subtopic rather than two.
                also_tests=[
                    {**p, "subtopic": aliases.get(p.get("subtopic"), p.get("subtopic"))}
                    if isinstance(p, dict) else p
                    for p in q.get("also_tests", [])
                ],
                kind=kind,
                # Empty when the question hangs off a container: the text lives
                # once, on the parent, and `context_passage` reads it from there.
                passage="" if parent else q.get("passage", ""),
                line_ref=q.get("line_ref", ""),
                stem=q["stem"],
                explanation=q.get("explanation", ""),
                image=q.get("image", ""),
                # A diagram declared as data and drawn at render time by
                # catalog/figures, rather than a committed file. Until this
                # line, `figure` existed on the model, in the paper importer and
                # in the generators, and was the one route an authored pack
                # could not reach — which is why the contract said a pack had
                # "no way to declare a chart or diagram and have it drawn", and
                # why non-verbal reasoning could only ever be generated.
                figure=q.get("figure"),
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
                # Which gap of its passage a cloze question fills.
                gap_number=q.get("gap_number"),
                # A question no engine can score carries what a marker needs
                # instead of an answer. These were dropped on import before —
                # the pack could describe a rubric and the importer would throw
                # it away, leaving a human-marked question with nothing to mark
                # against.
                marks=q.get("marks", 1) or 1,
                marking=(Question.Marking.RUBRIC if kind == Question.Kind.EXTENDED_TEXT
                         else Question.Marking.AUTO),
                model_answer=q.get("model_answer", ""),
                rubric=q.get("rubric") if isinstance(q.get("rubric"), dict) else None,
            )
            _build_options(question, q, kind)
            created += 1

        self.stdout.write(self.style.SUCCESS(
            f"{section.code}: removed {n_del} old {source} questions, imported {created}."
        ))
