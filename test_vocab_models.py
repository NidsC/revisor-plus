"""
Checks the vocab app's models, the load_vocab loader, and pack choice.

Run:  python main.py load_vocab
      python main.py shell < test_vocab_models.py

The rules that matter most here are about what can be deleted. Pupils' vocab
history must survive anything that happens to the question bank or the word
files, so this checks the structure (nothing points into catalog; words are held
with PROTECT) as well as the loader's behaviour (a dropped word is retired, never
deleted).

Every case that writes runs inside a transaction that is always rolled back,
so the script leaves the database exactly as it found it, even if it fails.
"""
import json
import os
import sys
from datetime import timedelta

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.db.models import ProtectedError
from django.utils import timezone

from goals.models import Goal, School
from vocab.management.commands.load_vocab import load_packs
from vocab.models import VocabProfile, Word, WordPack, WordProgress
from vocab.services import pack_for, pack_slug_for
from vocab.validate_words import DATA_DIR

fails = []


def ck(label, cond, extra=""):
    print(f"  [{'OK  ' if cond else 'FAIL'}] {label}" + (f" — {extra}" if extra else ""))
    if not cond:
        fails.append(label)


class Rollback(Exception):
    pass


def rolled_back(fn):
    """Run fn() in a transaction, then undo everything it wrote."""
    try:
        with transaction.atomic():
            fn()
            raise Rollback
    except Rollback:
        pass


def read_packs():
    out = []
    for name in sorted(os.listdir(DATA_DIR)):
        if name.endswith(".json"):
            with open(os.path.join(DATA_DIR, name), encoding="utf-8") as f:
                out.append((name[:-5], json.load(f)))
    return out


def without(packs, slug, headword):
    """packs with one word removed from one pack."""
    return [(s, dict(p, words=[e for e in p["words"]
                               if not (s == slug and e["word"] == headword)]))
            for s, p in packs]


PACKS = read_packs()
User = get_user_model()


def pupil(tag):
    return User.objects.create_user(username=f"vocabtest_{tag}", email=f"vocabtest_{tag}@x.test",
                                    password="x", role=User.Role.STUDENT)


print("== structure: what can delete what ==")
vocab_models = apps.get_app_config("vocab").get_models()
targets = {(m.__name__, f.name): f.related_model._meta.app_label
           for m in vocab_models for f in m._meta.get_fields()
           if f.is_relation and f.concrete and f.related_model}
outside = {k: v for k, v in targets.items() if v not in ("vocab", "accounts")}
ck("no vocab foreign key points outside vocab and the user model", not outside, str(outside))


def on_delete(model, field):
    return apps.get_model("vocab", model)._meta.get_field(field).remote_field.on_delete


ck("progress holds its word with PROTECT", on_delete("WordProgress", "word") is models.PROTECT)
ck("round items hold their word with PROTECT", on_delete("RoundItem", "word") is models.PROTECT)
ck("rounds hold their pack with PROTECT", on_delete("Round", "pack") is models.PROTECT)
ck("progress, profile and rounds go with the pupil",
   all(on_delete(m, "pupil") is models.CASCADE
       for m in ("WordProgress", "VocabProfile", "Round")))

print("\n== the loaded packs ==")
gl, general = WordPack.objects.filter(slug="gl").first(), WordPack.objects.filter(slug="general").first()
ck("both packs are loaded (run load_vocab first)", gl is not None and general is not None)
if gl is None or general is None:
    print("\nRESULT: FAILURES:", fails)
    sys.exit(1)
ck("gl has 50 words", gl.words.count() == 50, str(gl.words.count()))
ck("general has 50 words", general.words.count() == 50, str(general.words.count()))
shared = set(gl.words.values_list("headword", flat=True)) & set(
    general.words.values_list("headword", flat=True))
ck("words in both packs are stored once", Word.objects.filter(active=True).count()
   == 100 - len(shared), f"{len(shared)} shared")
ck("reluctant and vivid are shared", {"reluctant", "vivid"} <= shared, str(sorted(shared)))
w = Word.objects.get(headword="meticulous")
ck("fields come through from the file",
   w.pos == "adjective" and w.year == 7 and w.group == "care-and-effort"
   and len(w.gap_distractors) == 3 and "___" in w.gap_frame and "thorough" in w.synonyms)

print("\n== the loader ==")


def reload_is_a_no_op():
    c = load_packs(PACKS)
    ck("reloading the same files changes nothing",
       c["created"] == c["updated"] == c["retired"] == c["restored"] == 0, str(c))


rolled_back(reload_is_a_no_op)


def dropped_word_is_retired():
    c = load_packs(without(PACKS, "gl", "scrutinise"))
    word = Word.objects.filter(headword="scrutinise").first()
    ck("a word dropped from every file is kept", word is not None)
    ck("...but set inactive", word is not None and not word.active)
    ck("...and taken out of its pack", word is not None and not word.packs.exists())
    ck("...and counted as retired", c["retired"] == 1, str(c))
    c = load_packs(PACKS)
    word.refresh_from_db()
    ck("putting it back restores it", word.active and c["restored"] == 1, str(c))
    ck("...into its pack", word.packs.filter(slug="gl").exists())


rolled_back(dropped_word_is_retired)


def shared_word_leaves_one_pack():
    load_packs(without(PACKS, "general", "vivid"))
    word = Word.objects.get(headword="vivid")
    ck("a shared word dropped from one pack stays active",
       word.active, str(list(word.packs.values_list("slug", flat=True))))
    ck("...and stays in the other pack",
       list(word.packs.values_list("slug", flat=True)) == ["gl"])


rolled_back(shared_word_leaves_one_pack)


def edits_are_applied():
    packs = json.loads(json.dumps(PACKS))
    for _, p in packs:
        for e in p["words"]:
            if e["word"] == "abundant":
                e["definition"] = "More than enough."
    c = load_packs(packs)
    ck("an edited entry is updated in place",
       c["updated"] == 1 and Word.objects.get(headword="abundant").definition
       == "More than enough.", str(c))


rolled_back(edits_are_applied)

print("\n== deleting ==")


def protect_and_cascade():
    p = pupil("protect")
    word = Word.objects.get(headword="devour")
    WordProgress.objects.create(pupil=p, word=word, due_on=timezone.localdate())
    VocabProfile.objects.create(pupil=p, xp=10)
    try:
        with transaction.atomic():
            word.delete()
        ck("a word with progress cannot be deleted", False)
    except ProtectedError:
        ck("a word with progress cannot be deleted", True)
    p.delete()
    ck("deleting the pupil deletes their progress",
       not WordProgress.objects.filter(word=word, pupil_id=p.pk).exists())
    ck("...and their profile", not VocabProfile.objects.filter(pupil_id=p.pk).exists())
    ck("...and leaves the word", Word.objects.filter(pk=word.pk).exists())


rolled_back(protect_and_cascade)

print("\n== which pack a pupil gets ==")


def pack_choice():
    exam = timezone.localdate() + timedelta(days=200)
    cases = [("no goal", None, "general")]
    for fmt, expect in (("set", "gl"), ("gl", "gl"), ("bespoke", "general"), ("", "general")):
        cases.append((f"school format {fmt or 'blank'}", fmt, expect))
    cases.append(("goal with a school note but no school", "note", "general"))
    for label, fmt, expect in cases:
        p = pupil(label.replace(" ", "_")[:20])
        if fmt == "note":
            Goal.objects.create(student=p, school=None, school_note="Somewhere", exam_date=exam)
        elif fmt is not None:
            school = School.objects.create(slug=f"vocabtest-{fmt or 'blank'}",
                                           name=f"Test {fmt}", exam_format=fmt)
            Goal.objects.create(student=p, school=school, exam_date=exam)
        ck(f"{label} -> {expect}", pack_slug_for(p) == expect, pack_slug_for(p))
    p = pupil("inactive")
    school = School.objects.create(slug="vocabtest-inactive", name="Old", exam_format="gl")
    Goal.objects.create(student=p, school=school, exam_date=exam, is_active=False)
    ck("an inactive goal does not count -> general", pack_slug_for(p) == "general")
    ck("pack_for returns the WordPack", pack_for(p) == general)
    WordPack.objects.filter(slug="general").delete()
    ck("pack_for is None, not an error, when packs are not loaded", pack_for(p) is None)


rolled_back(pack_choice)

print("\n== nothing left behind ==")
ck("no test pupils remain", not User.objects.filter(username__startswith="vocabtest_").exists())
ck("no test schools remain", not School.objects.filter(slug__startswith="vocabtest-").exists())

if fails:
    print("\nRESULT: FAILURES:", fails)
    sys.exit(1)
print("\nRESULT: ALL PASSED")
