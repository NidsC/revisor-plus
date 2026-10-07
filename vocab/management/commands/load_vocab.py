"""
Load vocab/data/*.json into the database. Safe to re-run; build.sh runs it on
every deploy.

**This command never deletes a word.** Pupils' progress and past rounds point at
words with PROTECT, so a delete would either fail or, if someone changed that,
take a pupil's history with it. A word that is no longer in any pack file is
set inactive instead: it stops appearing in new rounds, and comes back intact
if it is ever restored to a file.

The files are checked with vocab/validate_words.py first, and nothing is written
unless every file passes. The load itself is one transaction, so a failure part
way leaves the words exactly as they were.

Run:  python main.py load_vocab
      python main.py load_vocab --dry-run
"""
import glob
import json
import os

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from vocab.models import Word, WordPack
from vocab.validate_words import DATA_DIR, validate


class DryRun(Exception):
    """Raised inside the transaction to roll a dry run back."""


def load_packs(packs):
    """Write `packs`, a list of (slug, parsed pack), and return counts.

    Assumes the packs have passed validate_words. Call inside a transaction.
    """
    counts = {"created": 0, "updated": 0, "unchanged": 0, "retired": 0, "restored": 0}
    in_files = set()
    members = {}   # pack slug -> set of headwords
    for slug, pack in packs:
        WordPack.objects.update_or_create(slug=slug, defaults={"title": pack["title"]})
        members[slug] = set()
        for e in pack["words"]:
            members[slug].add(e["word"])
            if e["word"] in in_files:
                continue   # a shared word, already written from an earlier pack
            in_files.add(e["word"])
            fields = {
                "pos": e["pos"], "year": e["year"], "definition": e["definition"],
                "synonyms": e["synonyms"], "group": e["group"], "example": e["example"],
                "gap_frame": e["gap"]["frame"], "gap_distractors": e["gap"]["distractors"],
            }
            word = Word.objects.filter(headword=e["word"]).first()
            if word is None:
                Word.objects.create(headword=e["word"], active=True, **fields)
                counts["created"] += 1
                continue
            changed = any(getattr(word, k) != v for k, v in fields.items())
            if not word.active:
                counts["restored"] += 1
            elif changed:
                counts["updated"] += 1
            else:
                counts["unchanged"] += 1
            if changed or not word.active:
                for k, v in fields.items():
                    setattr(word, k, v)
                word.active = True
                word.save()

    by_headword = dict(Word.objects.filter(headword__in=in_files).values_list("headword", "pk"))
    for slug, headwords in members.items():
        WordPack.objects.get(slug=slug).words.set([by_headword[h] for h in headwords])

    gone = Word.objects.filter(active=True).exclude(headword__in=in_files)
    counts["retired"] = gone.count()
    for word in gone:
        word.packs.clear()
    gone.update(active=False)
    return counts


class Command(BaseCommand):
    help = "Load the vocab word packs from vocab/data/. Never deletes a word."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Check and report, then roll everything back.")

    def handle(self, *args, dry_run=False, **options):
        paths = sorted(glob.glob(os.path.join(DATA_DIR, "*.json")))
        if not paths:
            raise CommandError(f"no word packs found in {DATA_DIR}")
        errors, _warnings, unreadable = validate(paths)
        if errors or unreadable:
            for msg in unreadable + errors:
                self.stderr.write(f"  {msg}")
            raise CommandError(f"{len(errors) + len(unreadable)} problem(s) in the word "
                               f"packs; nothing was loaded. Run vocab/validate_words.py.")

        packs = []
        for path in paths:
            with open(path, encoding="utf-8") as f:
                packs.append((os.path.splitext(os.path.basename(path))[0], json.load(f)))

        try:
            with transaction.atomic():
                counts = load_packs(packs)
                if dry_run:
                    raise DryRun
        except DryRun:
            pass

        sizes = ", ".join(f"{slug} {len(p['words'])}" for slug, p in packs)
        self.stdout.write(
            ("DRY RUN, nothing written. " if dry_run else "")
            + f"Packs: {sizes}. Words: {counts['created']} created, {counts['updated']} "
            f"updated, {counts['unchanged']} unchanged, {counts['restored']} restored, "
            f"{counts['retired']} retired (set inactive, not deleted)."
        )
