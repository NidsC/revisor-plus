"""
Checks that a failed pack import cannot destroy the questions it was replacing.

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

from catalog.models import Question

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
print("RESULT: " + ("ALL PASSED" if not fails else f"{len(fails)} FAILED"))
for f in fails:
    print("  - " + f)
