# Question Authoring Guide — Med-revisor question packs

**Read this before writing or editing any `*.json` question file in this folder.**
It is the contract between your questions and the importer that loads them onto the live
site (`catalog/management/commands/import_pmt.py`). Follow it and your pack merges cleanly.
Break it and the pack either fails to import, silently corrupts a subtopic, or **deletes
someone else's questions**.

If you use Claude Code, this file loads automatically. If you don't, read it anyway.

---

## The one rule that matters most: `source`

Every pack declares a `source` in its section header. On import, the loader **deletes every
existing question with the same `(section code, source)` and replaces them with your file.**
That is how re-importing an updated pack stays clean — but it also means:

> **If two people use the same `source` for the same section, whoever imports second wipes
> the first person's questions.**

So: **pick a `source` unique to your batch** and never reuse someone else's. Suggested pattern:

    "source": "CONTRIB-<yourname>-<batch>"      e.g. "CONTRIB-ALEX-01"

These names are **reserved** by the built-in demo content — never use them:
`PMT`, `PMT-M1`, `PMT-M2`, `seed`.

---

## File shape

One file = **one section** = **one source**. Copy `_TEMPLATE.question_pack.json` and edit it.

```json
{
  "section": { "code": "VR", "name": "Verbal Reasoning", "source": "CONTRIB-ALEX-01" },
  "questions": [ { ...question... }, { ...question... } ]
}
```

### Section header

| Field            | Required | Notes                                                              |
|------------------|----------|--------------------------------------------------------------------|
| `code`           | yes      | One of `VR`, `DM`, `QR`, `SJT`. Nothing else.                       |
| `name`           | yes      | Must match the code (see table below).                             |
| `source`         | yes      | Unique to your batch. See the rule above.                          |
| `is_placeholder` | yes\*    | `false` for team-authored packs. See "Ownership" below.            |

\* Technically optional — the importer defaults it to `true` — but a contributor pack **must**
set `false`, so the checker treats a missing value as a warning and the template ships `false`.

| code | name                    |
|------|-------------------------|
| VR   | Verbal Reasoning        |
| DM   | Decision Making         |
| QR   | Quantitative Reasoning  |
| SJT  | Situational Judgement   |

> Abstract Reasoning is **not** part of the UCAT anymore — there is no AR section. Don't add one.

### Ownership: `is_placeholder`

This flag records whether a question is disposable filler or content the project owns.

- `"is_placeholder": true` — placeholder demo content (the original PMT-derived packs). Meant
  to be swapped out; **not** treated as owned intellectual property.
- `"is_placeholder": false` — **your team's original, authored questions → owned IP.**

Every contributor pack you write is original work, so set **`false`** in the section header.
It applies to every question in the file. (You can override a single question by putting
`is_placeholder` on that question, but you rarely need to.) After import, the owned questions
are exactly those where `is_placeholder = false`.

### Each question

| Field         | Required | Default    | Notes                                                                 |
|---------------|----------|------------|-----------------------------------------------------------------------|
| `subtopic`    | **yes**  | —          | Must be an exact canonical name from the list below.                  |
| `stem`        | **yes**  | —          | The question the student answers.                                     |
| `options`     | **yes**  | —          | List of ≥2 options; **exactly one** has `"correct": true`.            |
| `difficulty`  | **yes**  | —          | Integer `1`, `2` or `3`. Required on every question — see rubric below.|
| `kind`        | no       | `"mcq"`    | `"mcq"` or `"tf"` (True/False/Can't-tell style). Nothing else.        |
| `passage`     | no       | `""`       | Shared reading/stimulus text. Repeating it across questions is fine.  |
| `explanation` | no       | `""`       | Shown after answering. Strongly encouraged.                           |
| `image`       | no       | `""`       | Filename only if the question needs a figure (mostly QR). See below.  |
| `number`      | no       | —          | Human ordinal ("1", "2"…). Ignored by the importer but keep it.       |
| `ref`         | no       | —          | Your unique tracking code per question. Keep it — used for dedup.     |

**Difficulty rubric** — set it honestly and consistently:

| Value | Meaning                                                                    |
|-------|----------------------------------------------------------------------------|
| `1`   | Easy — most prepared students get it; one clear step.                       |
| `2`   | Standard — typical exam-level difficulty. Use this when unsure.             |
| `3`   | Hard — multi-step, subtle distractors, or heavy time pressure.              |

`number` and `ref` are **not** loaded into the database, but they make review, dedup and
"which question is broken?" possible. Always include them.

### Each option

| Field     | Required | Default | Notes                                        |
|-----------|----------|---------|----------------------------------------------|
| `text`    | yes      | —       | The answer text, non-empty.                  |
| `correct` | no       | `false` | Set `true` on **exactly one** option.        |

---

## Canonical subtopics — copy these strings exactly

A subtopic name that isn't on this list does **not** error on import — it silently creates a
new, unintended subtopic and hides your question in it. Case, punctuation and spacing must
match character-for-character.

**VR**
- `Inference (True/False/Can't Tell)`
- `Reading Comprehension`

**DM**
- `Interpreting Information`
- `Logical Puzzles`
- `Probabilistic Reasoning`
- `Recognising Assumptions`
- `Syllogisms`
- `Venn Diagrams`

**QR**
- `Averages & Statistics`
- `Data Interpretation`
- `Geometry & Measurement`
- `Money & Finance`
- `Percentages`
- `Rates: Speed, Distance & Time`
- `Ratios, Proportion & Units`

**SJT**
- `Confidentiality`
- `Coping with Pressure`
- `Patient Safety`
- `Professionalism`
- `Teamwork`

---

## Images

Only some questions (mainly QR) need a figure. If yours does:
1. Set `"image": "your_figure.png"` — **filename only**, no path.
2. Put the file where the maintainer tells you (question images live under the app's
   `static/` tree). If you can't add the file, tell the maintainer in your PR — a broken
   image path will show a missing image on the live site.

Leave `image` as `""` or omit it for everything else.

---

## Before you open a pull request — validate

Run the checker. It needs nothing but Python 3:

```bash
python3 validate_questions.py your_pack.json
```

- **Exit 0** — clean, safe to merge. (Warnings are worth a glance but don't block.)
- **Exit 1** — errors. Fix them; do not merge.
- **Exit 2** — the file isn't valid JSON / can't be read.

The checker enforces everything above: valid section code, a non-reserved unique source,
required fields present (including `difficulty` 1–3), subtopics on the canonical list, exactly
one correct option per question, valid `is_placeholder`, unique refs, and it warns on typo'd
field names, duplicate stems, and packs left as placeholder.

**Maintainer:** validate the files the PR *adds or changes*, not the whole folder — the
original built-in packs (`decision_making.json`, the `mock*` files, etc.) predate this
contract: they use legacy subtopic names and no `source`, and are remapped at build time by
`reclassify_taxonomy`. They will fail this checker by design. Validate just the new packs:

```bash
git diff --name-only main...HEAD | grep '^pmt_data/.*\.json$' | xargs -r python3 pmt_data/validate_questions.py
```

If it exits non-zero, don't merge.

---

## Quick checklist

- [ ] Copied `_TEMPLATE.question_pack.json`; one section per file.
- [ ] Unique `source` (not `PMT*`/`seed`, not another contributor's).
- [ ] `"is_placeholder": false` in the section header (it's your IP).
- [ ] Every question has `subtopic` (canonical), `stem`, `options`, and `difficulty` (1–3).
- [ ] Exactly one `"correct": true` per question.
- [ ] `number` and `ref` filled in; refs unique.
- [ ] `python3 validate_questions.py <file>` exits 0.
