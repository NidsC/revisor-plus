"""
Checks that a failed pack import cannot destroy the questions it was replacing,
and that a re-import — changed or unchanged — never deletes a Question an
Attempt points at.

Run:  python main.py shell < test_import_safety.py

`import_pack` is idempotent per-source, and it achieves that by DELETING every
question already filed under the pack's `source` and then writing the pack's
questions back. The delete comes first and the writes happen one at a time in a
loop, so without a transaction any failure part-way through that loop leaves the
old questions gone and only some of the new ones written.

Three things make that worse than an ordinary bug:

  * build.sh imports every `contrib_*.json` on every deploy, so the half-written
    state is reached in production with no operator watching.
  * Deleting a Question cascades into every Attempt against it. What is lost is
    pupils' history, not just question rows.
  * Nothing reports it. The import fails loudly, but the *bank* is left quietly
    short, and the next deploy re-runs the same import and "fixes" it, so the
    evidence disappears.

Measured on 2026-08-26 against `contrib_pr_eng_01.json` (20 questions plus one
passage container). With `@transaction.atomic` on `handle` the count survives a
failed import at 21; with the decorator removed it drops to 20. This file is the
check that keeps it at 21.

It builds its own pack in a temp file rather than shipping a broken one in
`elevenplus_data/`, because a deliberately malformed pack sitting in that folder
is something CI validates, `build.sh` globs, and an author copies by mistake.
"""
import copy
import json
import tempfile
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.core.management import call_command

import re

from django.db import connection
from django.test.utils import CaptureQueriesContext

from catalog.management.commands.generate_bank import SOURCE as GEN_SOURCE
from catalog.management.commands.import_pack import _rows_pack_would_write
from catalog.models import ImportFingerprint, Question

fails = []


def ck(label, cond, extra=""):
    print(f"  [{'OK  ' if cond else 'FAIL'}] {label}" + (f" — {extra}" if extra else ""))
    if not cond:
        fails.append(label)


SOURCE = "TEST-IMPORT-SAFETY"
DATA = Path(settings.BASE_DIR) / "elevenplus_data"


def _pack():
    """A minimal two-question ENG pack, built from the taxonomy so it stays valid.

    Read from taxonomy.json rather than hard-coded: subtopic and question_type
    names are matched character for character on import, and a rebuilt section
    requires a question_type on every question. Hard-coding either would make
    this test fail the next time the taxonomy is edited, for a reason that has
    nothing to do with what it checks.
    """
    tax = json.loads((DATA / "taxonomy.json").read_text(encoding="utf-8"))
    eng = tax["sections"]["ENG"]
    sub = next(s for s in eng["subtopics"] if s.get("question_types"))
    qt = sub["question_types"][0]
    qt = qt["slug"] if isinstance(qt, dict) else qt
    first = {
        "ref": "IS-0001",
        "subtopic": sub["name"],
        "question_type": qt,
        "stem": "Import-safety probe: which of these words is a noun?",
        "difficulty": 3,
        "options": [
            {"text": "table", "correct": True},
            {"text": "quickly", "correct": False},
            {"text": "green", "correct": False},
            {"text": "ran", "correct": False},
        ],
        "explanation": "A noun names a thing.",
    }
    second = copy.deepcopy(first)
    second["ref"] = "IS-0002"
    second["stem"] = "Import-safety probe: which of these words is a verb?"
    return {
        "section": {"code": "ENG", "name": "English", "source": SOURCE},
        "questions": [first, second],
    }


def _write(pack):
    fh = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                     encoding="utf-8")
    json.dump(pack, fh, ensure_ascii=False)
    fh.close()
    return fh.name


def _count():
    return Question.objects.filter(source=SOURCE).count()


print("== a failed import leaves the bank exactly as it was ==")

call_command("import_pack", _write(_pack()), stdout=StringIO())
before = _count()
ck("the good pack imports", before == 2, f"{before} questions")

# Same `source`, so this import targets exactly the rows just written. The
# second question is missing `subtopic`, which raises KeyError inside the write
# loop — AFTER the delete has run and the first question has been created. That
# ordering is the whole point: an error before the delete would prove nothing.
broken = _pack()
del broken["questions"][1]["subtopic"]

raised = None
try:
    call_command("import_pack", _write(broken), stdout=StringIO())
except Exception as exc:                                        # noqa: BLE001
    raised = exc

ck("the broken pack fails rather than importing silently", raised is not None,
   type(raised).__name__ if raised else "no exception")

after = _count()
ck("the questions it was replacing are still there", after == before,
   f"{before} before, {after} after — a drop means the delete committed "
   f"without the writes")

# Leave no probe rows behind for the next thing that counts questions.
Question.objects.filter(source=SOURCE).delete()

print()
print("== re-importing a pack never destroys attempts ==")

from django.contrib.auth import get_user_model                    # noqa: E402
from practice.models import Attempt, TestSession                  # noqa: E402

call_command("import_pack", _write(_pack()), stdout=StringIO())
ids_before = sorted(Question.objects.filter(source=SOURCE).values_list("id", flat=True))
ck("the pack imports two questions", len(ids_before) == 2, f"{ids_before}")

# Identified by stem, not `ref` — the whole point of this section is to prove
# the importer keys on `ref` once it does; looking it up the same way would
# make the check circular.
q1 = Question.objects.get(source=SOURCE, stem=_pack()["questions"][0]["stem"])
probe = get_user_model().objects.create_user(
    username="import-safety-probe", email="import-safety-probe@example.test")
session = TestSession.objects.create(student=probe, mode="practice")
attempt = Attempt.objects.create(
    session=session, student=probe, question=q1, subtopic=q1.subtopic,
    selected_option=q1.correct_option(), is_correct=True,
    marks_earned=1, marks_available=1,
)
opt_id = attempt.selected_option_id

# (c) re-import the UNCHANGED pack.
call_command("import_pack", _write(_pack()), stdout=StringIO())
ids_after = sorted(Question.objects.filter(source=SOURCE).values_list("id", flat=True))
ck("an unchanged re-import keeps the same question ids",
   ids_after == ids_before, f"{ids_before} -> {ids_after}")
# Re-fetched rather than .refresh_from_db(), which raises DoesNotExist and
# would abort the whole run if the importer is still deleting the row — the
# very thing this section exists to catch.
attempt_now = Attempt.objects.filter(pk=attempt.pk).first()
ck("the attempt survives an unchanged re-import", attempt_now is not None)
ck("the attempt still points at the same option and question",
   attempt_now is not None
   and attempt_now.selected_option_id == opt_id and attempt_now.question_id == q1.id,
   f"{attempt_now.selected_option_id if attempt_now else None} (want {opt_id}), "
   f"question_id={attempt_now.question_id if attempt_now else None} (want {q1.id})")

# (d) edit q1's stem and drop IS-0002 — IS-0002 has no attempts, so it may go.
edited = _pack()
edited["questions"][0]["stem"] += " (edited)"
del edited["questions"][1]
call_command("import_pack", _write(edited), stdout=StringIO())
q1_now = Question.objects.filter(pk=q1.id).first()
ck("q1 keeps its id with the edited stem",
   q1_now is not None and q1_now.stem.endswith("(edited)"),
   f"id={q1_now.id if q1_now else None}, stem={q1_now.stem if q1_now else None!r}")
ck("IS-0002 (no attempts, dropped from the pack) is gone",
   not Question.objects.filter(source=SOURCE, ref="IS-0002").exists())
ck("the attempt still exists after the edit-and-drop re-import",
   Attempt.objects.filter(pk=attempt.pk, question_id=q1.id).exists())

# (e) re-import a pack that drops q1 (IS-0001) entirely, keeping only IS-0002.
# q1 was attempted, so it must be retired (active=False), not deleted.
only_second = _pack()
del only_second["questions"][0]
call_command("import_pack", _write(only_second), stdout=StringIO())
q1_now = Question.objects.filter(pk=q1.id).first()
ck("q1 (attempted, dropped from the pack) is retired rather than deleted",
   q1_now is not None and not q1_now.active,
   f"q1_now={q1_now}, active={q1_now.active if q1_now else None}")
ck("the attempt still points at the retired q1",
   Attempt.objects.filter(pk=attempt.pk, question_id=q1.id).exists())
ck("IS-0002 exists again",
   Question.objects.filter(source=SOURCE, ref="IS-0002").exists())

# Leave no probe rows behind. Deleting the user cascades into the session and
# the attempt.
probe.delete()
Question.objects.filter(source=SOURCE).delete()


def _writes(ctx):
    return [q["sql"] for q in ctx.captured_queries
            if re.match(r'^(INSERT INTO|UPDATE|DELETE FROM) "catalog_', q["sql"])]


print()
print("== --skip-unchanged skips an unchanged pack and nothing else ==")

SKIP_SOURCE = "TEST-SKIP-UNCHANGED"
SKIP_KEY = f"pack:{SKIP_SOURCE}"
skip_pack = json.loads((DATA / "_EXAMPLE.shared_passage.json").read_text(encoding="utf-8"))
skip_pack["section"]["source"] = SKIP_SOURCE
skip_path = _write(skip_pack)
expected_rows = _rows_pack_would_write(skip_pack)

out = StringIO()
call_command("import_pack", skip_path, skip_unchanged=True, stdout=out)
n_rows = Question.objects.filter(source=SKIP_SOURCE).count()
ck("first run writes exactly the rows the pack would write",
   n_rows == expected_rows, f"{n_rows} rows, expected {expected_rows}")
ck("first run records a fingerprint",
   ImportFingerprint.objects.filter(key=SKIP_KEY).exists())
ck("first run is not skipped", "skipped" not in out.getvalue())
digest_1 = ImportFingerprint.objects.get(key=SKIP_KEY).digest

out2 = StringIO()
with CaptureQueriesContext(connection) as ctx:
    call_command("import_pack", skip_path, skip_unchanged=True, stdout=out2)
bad = _writes(ctx)
ck("second run on the same file is skipped", "skipped" in out2.getvalue(),
   out2.getvalue().strip())
ck("the skipped run issues no INSERT/UPDATE/DELETE on any catalog_ table",
   bad == [], bad[0][:120] if bad else "")
ck("the skipped run leaves the row count unchanged",
   Question.objects.filter(source=SKIP_SOURCE).count() == n_rows)

edited = copy.deepcopy(skip_pack)
edited["questions"][0]["stem"] = "Skip-unchanged probe: edited stem"
edited_path = _write(edited)
out3 = StringIO()
call_command("import_pack", edited_path, skip_unchanged=True, stdout=out3)
ck("an edited pack is not skipped", "skipped" not in out3.getvalue())
ck("the fingerprint digest changed",
   ImportFingerprint.objects.get(key=SKIP_KEY).digest != digest_1)
ck("the edit reached the question",
   Question.objects.get(source=SKIP_SOURCE, ref=edited["questions"][0]["ref"]).stem
   == "Skip-unchanged probe: edited stem")

Question.objects.filter(source=SKIP_SOURCE).delete()
out4 = StringIO()
call_command("import_pack", edited_path, skip_unchanged=True, stdout=out4)
ck("with the rows deleted a matching fingerprint does not skip",
   "skipped" not in out4.getvalue())
ck("the rows are back",
   Question.objects.filter(source=SKIP_SOURCE).count() == expected_rows,
   f"{Question.objects.filter(source=SKIP_SOURCE).count()} rows, expected {expected_rows}")

out5 = StringIO()
with CaptureQueriesContext(connection) as ctx:
    call_command("import_pack", edited_path, stdout=out5)
ck("without the flag an unchanged pack still re-imports",
   "skipped" not in out5.getvalue() and _writes(ctx) != [])

Question.objects.filter(source=SKIP_SOURCE).delete()
ImportFingerprint.objects.filter(key=SKIP_KEY).delete()

print()
print("== --skip-unchanged skips an unchanged generated bank ==")

if Question.objects.filter(source=GEN_SOURCE).exists():
    print("  (skipped — a generated bank is present)")
else:
    out = StringIO()
    call_command("generate_bank", per_module=20, seed=11, skip_unchanged=True, stdout=out)
    n1 = Question.objects.filter(source=GEN_SOURCE).count()
    ck("first run generates a bank", n1 > 0, f"{n1} rows")
    ck("first run records the bank fingerprint",
       ImportFingerprint.objects.filter(key="bank:generated").exists())
    ck("first run is not skipped", "skipped" not in out.getvalue())

    out = StringIO()
    with CaptureQueriesContext(connection) as ctx:
        call_command("generate_bank", per_module=20, seed=11, skip_unchanged=True, stdout=out)
    bad = _writes(ctx)
    ck("second run with the same parameters is skipped", "skipped" in out.getvalue(),
       out.getvalue().strip())
    ck("the skipped bank run issues no INSERT/UPDATE/DELETE on any catalog_ table",
       bad == [], bad[0][:120] if bad else "")
    ck("the skipped bank run leaves the row count unchanged",
       Question.objects.filter(source=GEN_SOURCE).count() == n1)

    out = StringIO()
    call_command("generate_bank", per_module=20, seed=12, skip_unchanged=True, stdout=out)
    ck("a different seed is not skipped", "skipped" not in out.getvalue())

    Question.objects.filter(source=GEN_SOURCE).delete()
    ImportFingerprint.objects.filter(key="bank:generated").delete()

print()
print("RESULT: " + ("ALL PASSED" if not fails else f"{len(fails)} FAILED"))
for f in fails:
    print("  - " + f)
