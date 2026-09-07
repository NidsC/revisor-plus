"""
Regression guard for the "diversity architecture, Stage 1" contract fixes:
LetterCode/LogicOrdering's metadata, Item.kind's MCQ fallback, and
generate_bank.py's new taxonomy/misconception contract checks (see plans.md's
"VR generator coverage" entry, diversity architecture audit, Stage 1).

Run:  python3 catalog/generators/test_generator_contract.py

Needs django.setup() (to import catalog.models / generate_bank.Command) but no
live database connection and no migration — every check below either calls a
generator's build() directly or a plain static method, the same posture
test_verbal_gap_batch.py already uses in this same CI job.
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402
django.setup()  # noqa: E402

from catalog.generators import Item  # noqa: E402
from catalog.generators.verbal import LetterCode, LogicOrdering  # noqa: E402
from catalog.management.commands.generate_bank import (  # noqa: E402
    Command, MISCONCEPTION_SLUGS, TAXONOMY_QUESTION_TYPES,
)
from catalog.models import Question  # noqa: E402

fails = []


def ck(label, cond, extra=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + (f"   [{extra}]" if extra and not cond else ""))
    if not cond:
        fails.append(label)


BUILDS = 2000


def build_many(gen, n):
    """Draw up to n items, tolerating LetterCode's known finite without-
    replacement pool (see the diversity audit's §6/§1) — a RuntimeError once
    a difficulty's pool is exhausted is expected production behaviour
    (generate_bank._fill_module catches the same exception and moves on),
    not a defect this test should fail on."""
    items, exhausted = [], 0
    for i in range(n):
        rng = random.Random(f"contract:{gen.slug}:{i}")
        try:
            item = gen.build(rng, gen.difficulties[i % len(gen.difficulties)])
        except RuntimeError:
            exhausted += 1
            continue
        if item is not None:
            items.append(item)
    return items, exhausted


print("== LetterCode always sets a valid question_type, both directions reachable ==")
gen = LetterCode()
items, exhausted = build_many(gen, BUILDS)
seen = {item.question_type for item in items}
ck(f"{len(items)} builds ({exhausted} pool-exhausted) only ever set "
   f"word-to-code/code-to-word", seen <= {"word-to-code", "code-to-word"}, str(seen))
ck("both directions are actually reached at this sample size",
   seen == {"word-to-code", "code-to-word"}, str(seen))
for qtype in ("word-to-code", "code-to-word"):
    ck(f"{qtype!r} is a real question_type for Letter Codes in taxonomy.json",
       qtype in TAXONOMY_QUESTION_TYPES.get(("VR", "Letter Codes"), set()))
# code-to-word's own uniqueness guarantee: the shown code must never also be
# producible by any of its own distractor options under the same shift, i.e.
# no two options in the same item decode/encode to the same thing.
code_to_word_items = [item for item in items if item.question_type == "code-to-word"]
ck(f"{len(code_to_word_items)} code-to-word items all have 4 distinct options",
   all(len({text for text, _ in item.options}) == len(item.options)
       for item in code_to_word_items))

print("\n== LogicOrdering always sets a valid question_type, both framings reachable ==")
gen = LogicOrdering()
items, exhausted = build_many(gen, BUILDS)
seen = {item.question_type for item in items}
ck(f"{len(items)} builds ({exhausted} pool-exhausted) only ever set "
   f"ranking/seating-order", seen <= {"ranking", "seating-order"}, str(seen))
ck("both framings are actually reached at this sample size",
   seen == {"ranking", "seating-order"}, str(seen))
for qtype in ("ranking", "seating-order"):
    ck(f"{qtype!r} is a real question_type for Scenario Deduction in taxonomy.json",
       qtype in TAXONOMY_QUESTION_TYPES.get(("VR", "Scenario Deduction"), set()))
# Every option in every item must be a distinct name -- a duplicate would
# mean two options read identically to a pupil regardless of which is
# flagged correct.
ck(f"all {len(items)} LogicOrdering items have distinct option texts",
   all(len({text for text, _ in item.options}) == len(item.options)
       for item in items))

print("\n== the params[\"variant\"] convention: no generator still writes the old keys ==")
verbal_src = open(os.path.join(os.path.dirname(__file__), "verbal.py")).read()
ck('zero remaining params={"kind": ...} sites', 'params={"kind":' not in verbal_src)
ck('zero remaining params={"qtype": ...} sites', 'params={"qtype":' not in verbal_src)
ck('zero remaining "qtype": ... anywhere in params', '"qtype":' not in verbal_src)
ck('zero remaining "mode": ... anywhere in params (LetterAlgebra, Stage 2)',
   '"mode":' not in verbal_src)

print("\n== Item.kind defaults to None and generate_bank falls back to MCQ ==")
plain = Item(stem="x", options=[("a", True), ("b", False)], difficulty=1, params={})
ck("Item.kind defaults to None", plain.kind is None)
ck("None-or-MCQ fallback yields MCQ", (plain.kind or Question.Kind.MCQ) == Question.Kind.MCQ)
typed = Item(stem="x", options=[("a", True), ("b", False)], difficulty=1, params={},
             kind=Question.Kind.SHORT_TEXT)
ck("a set kind survives the fallback expression",
   (typed.kind or Question.Kind.MCQ) == Question.Kind.SHORT_TEXT)


class _FakeGen:
    slug = "fake.gen"
    section = "VR"
    subtopic = "Letter Codes"


print("\n== generate_bank._check_taxonomy_contract: catches what it should, silent on the rest ==")
fake = _FakeGen()

valid_qtype = Item(stem="x", options=[("a", True), ("b", False)], difficulty=1,
                    params={}, question_type="word-to-code")
ck("a real question_type produces no warning",
   Command._check_taxonomy_contract(fake, valid_qtype) == [])

invalid_qtype = Item(stem="x", options=[("a", True), ("b", False)], difficulty=1,
                      params={}, question_type="not-a-real-slug")
warnings = Command._check_taxonomy_contract(fake, invalid_qtype)
ck("an invented question_type is caught", len(warnings) == 1 and "not-a-real-slug" in warnings[0])

valid_misc = Item(stem="x", options=[("a", True), ("b", False)], difficulty=1,
                   params={}, question_type="word-to-code",
                   misconceptions={"b": "shifted-the-wrong-way"})
ck("a registered misconception slug produces no warning",
   Command._check_taxonomy_contract(fake, valid_misc) == [])

invalid_misc = Item(stem="x", options=[("a", True), ("b", False)], difficulty=1,
                     params={}, question_type="word-to-code",
                     misconceptions={"b": "totally-invented-slug"})
warnings = Command._check_taxonomy_contract(fake, invalid_misc)
ck("an invented misconception slug is caught",
   len(warnings) == 1 and "totally-invented-slug" in warnings[0])

print("\n== the 8 slugs the diversity audit found unregistered are now registered ==")
for slug in ("no-shift-applied", "used-the-wrong-pair-rule", "shifted-only-one-letter",
             "swapped-the-wrong-letters", "did-not-swap", "only-changed-one-word",
             "mixed-up-which-word-changed", "not-an-antonym-of-the-fixed-word"):
    ck(f"{slug!r} is in taxonomy.json's vocabulary", slug in MISCONCEPTION_SLUGS)

print("\n== Stage 2's 6 new misconception slugs are registered ==")
for slug in ("copied-a-given-number-instead-of-solving", "flipped-the-sign-of-one-term",
             "read-the-code-in-reverse", "skipped-a-step-of-the-equation",
             "swapped-two-symbols-in-the-code", "found-only-one-of-the-two-odd-words-out"):
    ck(f"{slug!r} is in taxonomy.json's vocabulary", slug in MISCONCEPTION_SLUGS)

print("\n== Stage 2: MissingNumberSum/LetterAlgebra/NumberCode actually attach "
      "misconceptions at scale (quality work, not a new format) ==")
from catalog.generators.verbal import MissingNumberSum, LetterAlgebra, NumberCode  # noqa: E402

for gen in (MissingNumberSum(), LetterAlgebra(), NumberCode()):
    items, _exhausted = build_many(gen, BUILDS)
    with_misc = [i for i in items if i.misconceptions]
    ck(f"{gen.slug}: at least some of {len(items)} builds carry a misconception "
       f"label ({len(with_misc)} do)", len(with_misc) > 0)
    bad_slugs = {slug for i in items for slug in i.misconceptions.values()
                if slug not in MISCONCEPTION_SLUGS}
    ck(f"{gen.slug}: every misconception slug used is registered",
       not bad_slugs, str(bad_slugs))
    on_correct = [i for i in items
                 if any(text == opt_text and correct
                        for text in i.misconceptions
                        for opt_text, correct in i.options)]
    ck(f"{gen.slug}: no misconception is ever attached to the correct option",
       not on_correct)

print("\n== Stage 2: OddOneOut's Two Odd Ones Out is reachable and stays "
      "question_type='by-category' (no taxonomy inflation) ==")
from catalog.generators.verbal import OddOneOut  # noqa: E402

items, _exhausted = build_many(OddOneOut(), BUILDS)
variants = {i.params.get("variant") for i in items}
ck("both single-odd and two-odd variants are reached at this sample size",
   variants == {"single-odd", "two-odd"}, str(variants))
ck("every OddOneOut item still uses the existing 'by-category' question_type "
   "(Two Odd Ones Out is a params[\"variant\"], not a new taxonomy type)",
   {i.question_type for i in items} == {"by-category"})

print()
if fails:
    print(f"RESULT: {len(fails)} FAILED")
    sys.exit(1)
print("RESULT: ALL PASSED")
