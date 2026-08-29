"""
Generate the question bank procedurally.

Run:  python main.py generate_bank --count 60 --seed 11

THE CENTRAL SAFETY PROPERTY: this command never deletes a question a pupil has
answered. Deleting a Question cascades to every Attempt against it, which would
take the pupil's history, their accuracy charts and (once it lands) every ability
estimate derived from those rows. import_pack and import_paper both delete-then-
recreate; this one must not, because it is designed to be re-run.

How that is achieved:
  * gen_key = sha1(generator|template|params) identifies a question by what it IS,
    so the same --seed regenerates the same keys and update_or_create keeps the
    same row ids.
  * Per-generator RNG streams: Random(f"{seed}:{slug}:{i}"). With one shared
    stream, adding a generator would shift every later draw, change every
    gen_key, and orphan the whole bank on the next deploy.
  * Retire, never remove: a generated row that is no longer produced is deleted
    only if nothing references it; if it has attempts it is deactivated instead.
"""
import random
from itertools import zip_longest

from django.core.management.base import BaseCommand
from django.db import transaction

from catalog.figures import render_option_figure
from catalog.generators import load_all
from catalog.models import (OPTION_LABELS, AnswerOption, Question, Section,
                            Subtopic)

SOURCE = "GEN"
SECTION_NAME = {"ENG": "English", "MAT": "Maths",
                "VR": "Verbal Reasoning", "NVR": "Non-Verbal Reasoning"}
SECTION_ORDER = {"ENG": 1, "MAT": 2, "VR": 3, "NVR": 4}


class Command(BaseCommand):
    help = "Generate the procedural question bank (idempotent for a given seed)."

    def add_arguments(self, parser):
        parser.add_argument("--per-module", type=int, default=1100,
                            help="Target questions per module (ENG/MAT/VR/NVR). Filled "
                                 "round-robin across that module's generators, so one "
                                 "with a small parameter space does not starve the "
                                 "module and one with a huge space does not swamp it.")
        parser.add_argument("--count", type=int, default=0,
                            help="Legacy: target per GENERATOR instead of per module. "
                                 "Produces wildly unbalanced modules — Maths has 14 "
                                 "generators and English 8 — so prefer --per-module.")
        parser.add_argument("--seed", type=int, default=11,
                            help="Same seed => same questions => same row ids.")
        parser.add_argument("--check", action="store_true",
                            help="Generate and validate, write nothing.")
        parser.add_argument("--skip-if-present", action="store_true",
                            help="Do nothing if a generated bank already exists.")

    def handle(self, *args, **opts):
        generators = load_all()
        if opts["skip_if_present"] and Question.objects.filter(source=SOURCE).exists():
            self.stdout.write(f"Generated bank already present "
                              f"({Question.objects.filter(source=SOURCE).count()} rows) "
                              f"— skipping.")
            return

        seed = opts["seed"]
        built, problems, seen_keys = [], [], set()

        by_section = {}
        for gen in generators:
            by_section.setdefault(gen.section, []).append(gen)

        for code, gens in by_section.items():
            target = (opts["count"] * len(gens)) if opts["count"] else opts["per_module"]
            made = self._fill_module(code, gens, target, seed, built, problems, seen_keys)
            short = " " if made >= target else " (module parameter space is smaller) "
            self.stdout.write(
                f"  {code}: {made}/{target}{short}from {len(gens)} generators"
            )

        for p in problems[:15]:
            self.stdout.write(self.style.WARNING(f"  ! {p}"))
        if len(problems) > 15:
            self.stdout.write(self.style.WARNING(f"  ! …and {len(problems) - 15} more"))

        if opts["check"]:
            self.stdout.write(self.style.SUCCESS(
                f"--check: {len(built)} questions generated cleanly from "
                f"{len(generators)} generators, {len(problems)} rejected. Nothing written."
            ))
            return

        created, updated = self._write(built)

        # Retire anything this run no longer produces.
        stale = Question.objects.filter(source=SOURCE).exclude(gen_key__in=seen_keys)
        retired = stale.filter(attempts__isnull=False).distinct()
        n_retired = retired.count()
        for q in retired:
            if q.active:
                q.active = False
                q.save(update_fields=["active"])
        n_deleted = stale.filter(attempts__isnull=True).delete()[0]

        self.stdout.write(self.style.SUCCESS(
            f"Bank: {created} created, {updated} updated, {n_deleted} removed, "
            f"{n_retired} retired (kept, deactivated — they have attempts). "
            f"Total generated: {Question.objects.filter(source=SOURCE).count()} "
            f"across {len(generators)} generators."
        ))

    # ------------------------------------------------------------------ helpers

    def _fill_module(self, code, gens, target, seed, built, problems, seen_keys):
        """Fill one module to `target`, round-robin across its generators.

        Round-robin rather than an equal per-generator quota, because the
        parameter spaces differ by orders of magnitude — Maths averages can
        produce ~1,500 distinct questions and vr.hidden exactly 8. A fixed quota
        would either starve the module or leave the big generators idle. Here a
        generator that runs dry simply drops out and the others carry on, so the
        module still reaches its target if the questions exist anywhere in it.
        """
        # Quota per SUBTOPIC, then redistribute what the small ones cannot use.
        # Round-robin alone kept going wrong: interleaving generator order left
        # Grammar with 951 against Spelling's 61, and taking one per subtopic per
        # round starved Grammar at 99 while its generators still had 4,400 unused
        # combinations. Explicit quotas are simply easier to be sure about.
        buckets = {}
        for g in gens:
            buckets.setdefault(g.subtopic, []).append(g)

        cursor = {g.slug: 0 for g in gens}
        exhausted = set()
        counts = {sub: 0 for sub in buckets}
        quota = max(1, target // len(buckets))

        def draw(sub_gens):
            """One unseen question from this subtopic, or None if it is spent."""
            live = [g for g in sub_gens if g.slug not in exhausted]
            for gen in sorted(live, key=lambda g: cursor[g.slug]):
                for _ in range(150):
                    i = cursor[gen.slug]
                    cursor[gen.slug] += 1
                    if i > 400_000:
                        break
                    rng = random.Random(f"{seed}:{gen.slug}:{i}")
                    difficulty = gen.difficulties[i % len(gen.difficulties)]
                    try:
                        item = gen.build(rng, difficulty)
                    except Exception as exc:                   # noqa: BLE001
                        problems.append(f"{gen.slug} d{difficulty}: raised {exc!r}")
                        continue
                    if item is None:
                        continue
                    bad = self._validate(gen, item)
                    if bad:
                        problems.append(f"{gen.slug} d{difficulty}: {bad}")
                        continue
                    key = item.key(gen.slug, gen.template_id)
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    built.append((gen, item, key))
                    return True
                exhausted.add(gen.slug)     # this one is spent; try the next
            return False

        # Pass 1 — every subtopic gets an equal share.
        for sub, sub_gens in buckets.items():
            while counts[sub] < quota:
                if not draw(sub_gens):
                    break
                counts[sub] += 1

        # Pass 2 — hand the shortfall to whichever subtopics still have capacity,
        # so a module is not held back to four times its smallest subtopic.
        while sum(counts.values()) < target:
            progressed = False
            for sub, sub_gens in buckets.items():
                if sum(counts.values()) >= target:
                    break
                if draw(sub_gens):
                    counts[sub] += 1
                    progressed = True
            if not progressed:
                break
        return sum(counts.values())

    @staticmethod
    def _validate(gen, item):
        """Reject anything that would import badly. A generator bug should show up
        here, not as a broken question in a pupil's deck."""
        if not item.stem or not item.stem.strip():
            return "empty stem"
        correct = [o for o in item.options if o[1]]
        if len(correct) != 1:
            return f"{len(correct)} correct options (need exactly 1)"
        if len(item.options) < 3:
            return f"only {len(item.options)} options"
        texts = [str(o[0]).strip() for o in item.options]
        if len(set(texts)) != len(texts):
            return "duplicate option text"
        if any(not t for t in texts):
            return "blank option text"
        if item.difficulty not in (1, 2, 3, 4, 5):
            return f"difficulty {item.difficulty} out of range"
        # No two answers may be the same PICTURE. The duplicate-text check above
        # cannot see this on its own: non-verbal options used to hold the bare
        # letters "A".."D", which are always distinct however identical the
        # panels behind them, and a half-turn question shipped for months whose
        # "turned the wrong way" distractor was the correct answer — `base - 180`
        # and `base + 180` being the same angle. Comparing the specs would not
        # catch it either; only comparing what they draw does.
        drawn = {}
        for text, _, figure in item.option_rows():
            if not figure:
                continue
            markup = render_option_figure(figure)
            if not markup:
                return f"option {text!r} has a figure that draws nothing"
            if markup in drawn:
                return (f"options {drawn[markup]!r} and {text!r} draw the same "
                        f"picture, so this question has two identical answers")
            drawn[markup] = text
        return None

    @transaction.atomic
    def _write(self, built):
        """One transaction: ~12k statements in autocommit is ~12k fsyncs."""
        sections, subtopics = {}, {}
        created = updated = 0
        for gen, item, key in built:
            if gen.section not in sections:
                sections[gen.section], _ = Section.objects.get_or_create(
                    code=gen.section,
                    defaults={"name": SECTION_NAME.get(gen.section, gen.section),
                              "order": SECTION_ORDER.get(gen.section, 99)},
                )
            sub_key = (gen.section, gen.subtopic)
            if sub_key not in subtopics:
                subtopics[sub_key], _ = Subtopic.objects.get_or_create(
                    section=sections[gen.section], name=gen.subtopic)

            question, was_created = Question.objects.update_or_create(
                gen_key=key,
                defaults={
                    "subtopic": subtopics[sub_key],
                    "kind": Question.Kind.MCQ,
                    "marking": Question.Marking.AUTO,
                    "question_type": item.question_type,
                    "stem": item.stem,
                    "passage": item.passage,
                    "explanation": item.explanation,
                    "difficulty": item.difficulty,
                    "figure": item.figure,
                    "source": SOURCE,
                    "is_placeholder": False,
                    "active": True,
                    "marks": 1,
                },
            )
            created += was_created
            updated += not was_created

            # Options are rewritten, but only those no Attempt points at. A
            # SET_NULL wipe would silently blank "what you picked" in review.
            existing = {o.text: o for o in question.options.all()}
            wanted = {str(row[0]): row[1] for row in item.option_rows()}
            for text, obj in existing.items():
                if text not in wanted and not obj.attempt_set.exists():
                    obj.delete()
            for order, (text, correct, option_figure) in enumerate(item.option_rows()):
                AnswerOption.objects.update_or_create(
                    question=question, text=str(text),
                    defaults={
                        "is_correct": correct, "order": order,
                        # The letter printed beside this choice. import_pack has
                        # always set it; generated questions had it blank, which
                        # was invisible until non-verbal answers became tiles
                        # that print their own letter.
                        "label": OPTION_LABELS[order] if order < len(OPTION_LABELS) else "",
                        # This option's picture, for a non-verbal question whose
                        # answers are panels. The panel and the row that marks
                        # the answer are now one object; they used to be kept in
                        # step by list position alone.
                        "figure": option_figure,
                        # The error model the generator used to build this
                        # distractor. Carried through so feedback can name the
                        # specific slip rather than just marking it wrong.
                        "misconception": "" if correct else
                                         (item.misconceptions or {}).get(str(text), ""),
                    },
                )
        return created, updated
