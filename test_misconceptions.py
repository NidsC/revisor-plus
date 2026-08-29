"""Checks that a misconception written in a PACK reaches the pupil.

Run:  python main.py shell < test_misconceptions.py

`AnswerOption.misconception` records why a wrong answer was tempting. The read
path has been live for months — catalog/marking.py puts it into Result.detail,
practice/views.py hands it to the template, and mock_result.html renders "That's
the answer you get if you <b>...</b>" — but only `generate_bank` could ever write
it. A pack had nowhere to put one, so the feature covered generated questions and
not authored ones, and the plan is for authored content to become the bank.

That is four components that have to agree: the validator must admit the field,
the importer must carry it, the model must store it, and the marking engine must
read it back. They have disagreed silently before, which is why test_kinds.py
exists for the seven answer kinds; this is the same check for this one field.

It also pins the two rules that are about what the pupil reads rather than about
storage: the slug must come from the controlled vocabulary in taxonomy.json,
because it is rendered to the child as prose, and it must not sit on the correct
option, because there it would tell a pupil who scored the mark that they erred.
"""
import json
import subprocess
import sys
import tempfile
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.core.management import call_command

from catalog.marking import mark
from catalog.models import AnswerOption, Question

fails = []


def ck(label, cond, extra=""):
    print(f"  [{'OK  ' if cond else 'FAIL'}] {label}" + (f" — {extra}" if extra else ""))
    if not cond:
        fails.append(label)


SOURCE = "TEST-MISCONCEPTION"
DATA = Path(settings.BASE_DIR) / "elevenplus_data"
TAX = json.loads((DATA / "taxonomy.json").read_text(encoding="utf-8"))
VOCAB = TAX.get("misconceptions", {}).get("slugs", [])

print("== the vocabulary exists and has the shape the contract promises ==")
ck("taxonomy.json carries a misconceptions vocabulary", bool(VOCAB), f"{len(VOCAB)} slugs")
ck("every slug is a lowercase hyphenated phrase",
   all(s == s.lower() and "-" in s and " " not in s for s in VOCAB))
ck("every slug fits the column",
   all(len(s) <= TAX["misconceptions"]["max_length"] for s in VOCAB))

SLUG = "divided-instead-of-multiplying"
ck(f"{SLUG!r} is in the vocabulary", SLUG in VOCAB)


def _pack(misconception=SLUG, on_correct=False):
    eng = TAX["sections"]["ENG"]
    sub = next(s for s in eng["subtopics"] if s.get("question_types"))
    qt = sub["question_types"][0]
    qt = qt["slug"] if isinstance(qt, dict) else qt
    right = {"text": "table", "correct": True}
    wrong = {"text": "quickly", "correct": False}
    (right if on_correct else wrong)["misconception"] = misconception
    return {
        "section": {"code": "ENG", "name": "English", "source": SOURCE},
        "questions": [{
            "ref": "MC-0001", "subtopic": sub["name"], "question_type": qt,
            "stem": "Misconception probe: which word is a noun?",
            "difficulty": 3,
            "options": [right, wrong,
                        {"text": "green", "correct": False},
                        {"text": "ran", "correct": False}],
            "explanation": "A noun names a thing.",
        }],
    }


def _write(pack):
    fh = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                     encoding="utf-8")
    json.dump(pack, fh, ensure_ascii=False)
    fh.close()
    return fh.name


def _validate(pack):
    """Run the real validator as a contributor would, and return its output."""
    path = _write(pack)
    proc = subprocess.run(
        [sys.executable, str(DATA / "validate_questions.py"), path],
        capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


print("\n== the validator admits a listed slug and refuses an invented one ==")
code, out = _validate(_pack())
ck("a pack naming a vocabulary slug validates", code == 0,
   out.strip().splitlines()[-1] if out.strip() else "")

code, out = _validate(_pack(misconception="made-a-silly-error"))
ck("an invented slug is refused", code == 1)
ck("and the message says why the wording is not the author's to invent",
   "printed to the pupil" in out)

code, out = _validate(_pack(on_correct=True))
ck("a misconception on the CORRECT option is refused", code == 1)
ck("and the message shows the sentence a pupil would have read",
   "that's the answer you get if you divided instead of multiplying" in out)

print("\n== it survives the import and reaches the marking engine ==")
call_command("import_pack", _write(_pack()), stdout=StringIO())
q = Question.objects.filter(source=SOURCE).first()
ck("the question imported", q is not None)

if q is not None:
    tagged = AnswerOption.objects.filter(question=q, misconception=SLUG).first()
    ck("the importer stored the misconception on the distractor", tagged is not None)
    ck("and stored nothing on the correct answer",
       not AnswerOption.objects.filter(question=q, is_correct=True)
       .exclude(misconception="").exists())

    if tagged is not None:
        ck("the model renders it as prose for the pupil",
           tagged.misconception_text == "divided instead of multiplying",
           tagged.misconception_text)
        result = mark(q, option=tagged)
        ck("marking it wrong reports the misconception",
           not result.correct and "divided instead of multiplying" in result.detail,
           str(result.detail))

    right = AnswerOption.objects.filter(question=q, is_correct=True).first()
    if right is not None:
        result = mark(q, option=right)
        ck("marking it right reports no misconception",
           result.correct and not result.detail, str(result.detail))

Question.objects.filter(source=SOURCE).delete()

print()
print("RESULT: " + ("ALL PASSED" if not fails else f"{len(fails)} FAILED"))
for f in fails:
    print("  - " + f)
