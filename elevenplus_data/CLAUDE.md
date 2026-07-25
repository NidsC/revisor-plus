# Question Authoring Guide — 11+ question packs

**Read this before writing or editing any `*.json` question file in this folder.**
It is the contract between your questions and the importer that loads them onto the live
site (`catalog/management/commands/import_pack.py`). Follow it and your pack merges cleanly.
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

`seed` is **reserved** by the built-in demo content — never use it. A pack with no `source`
at all is refused outright by the importer.

Name your file to match: `contrib_<yourname>_<batch>.json`. The build script auto-imports
everything matching `contrib_*.json`, so a merged pack deploys without any code change.

---

## File shape

One file = **one section** = **one source**. Copy `_TEMPLATE.question_pack.json` and edit it.

```json
{
  "section": { "code": "ENG", "name": "English", "source": "CONTRIB-ALEX-01", "is_placeholder": false },
  "questions": [ { ...question... }, { ...question... } ]
}
```

### Section header

| Field            | Required | Notes                                                              |
|------------------|----------|--------------------------------------------------------------------|
| `code`           | yes      | One of `ENG`, `MAT`, `VR`, `NVR`. Nothing else.                     |
| `name`           | yes      | Must match the code (see table below).                             |
| `source`         | yes      | Unique to your batch. See the rule above.                          |
| `is_placeholder` | no       | Defaults to `false` (owned IP). See "Ownership" below.             |

| code | name                 |
|------|----------------------|
| ENG  | English              |
| MAT  | Maths                |
| VR   | Verbal Reasoning     |
| NVR  | Non-Verbal Reasoning |

These are the four 11+ papers. Don't invent a fifth section — if a topic doesn't fit, it
belongs in a subtopic of one of these.

### Ownership: `is_placeholder`

This flag records whether a question is disposable filler or content the project owns.

- `"is_placeholder": false` — **your original, authored questions → owned IP.** This is the
  default and what every contributor pack should be.
- `"is_placeholder": true` — disposable scaffold/demo content, meant to be swapped out and
  **not** treated as owned intellectual property. Only the `seed_demo` sample questions use this.

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
| `kind`        | no       | `"mcq"`    | Only `"mcq"`. Every 11+ question is multiple choice.                  |
| `passage`     | no       | `""`       | Shared reading/stimulus text. Repeating it across questions is fine.  |
| `explanation` | no       | `""`       | Shown after answering. Strongly encouraged.                           |
| `image`       | no       | `""`       | Filename only if the question needs a figure (mostly NVR). See below. |
| `number`      | no       | —          | Human ordinal ("1", "2"…). Ignored by the importer but keep it.       |
| `ref`         | no       | —          | Your unique tracking code per question. Keep it — used for dedup.     |

**Difficulty rubric** — set it honestly and consistently. Pitch it at a Year 5/6 pupil
sitting the exam, not at an adult:

| Value | Meaning                                                                    |
|-------|----------------------------------------------------------------------------|
| `1`   | Easy — most prepared pupils get it; one clear step.                         |
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

**ENG — English**
- `Grammar & Punctuation`
- `Reading Comprehension`
- `Spelling`
- `Vocabulary`

**MAT — Maths**
- `Algebra`
- `Four Operations`
- `Fractions, Decimals & Percentages`
- `Geometry & Shape`
- `Measurement`
- `Number & Place Value`
- `Ratio & Proportion`
- `Statistics & Data Handling`

**VR — Verbal Reasoning**
- `Analogies`
- `Codes & Sequences`
- `Hidden & Compound Words`
- `Letters & Alphabet`
- `Logic Problems`
- `Odd One Out`
- `Word Meanings`

**NVR — Non-Verbal Reasoning**
- `3D Shapes & Nets`
- `Analogies`
- `Codes`
- `Odd One Out`
- `Rotation & Reflection`
- `Series & Sequences`

---

## Images

Most NVR questions and some MAT ones (charts, shapes, diagrams) need a figure. If yours does:
1. Set `"image": "your_figure.png"` — **filename only**, no path.
2. Put the file in `static/questions/`. If you can't add the file, say so in your PR — a
   broken image path shows a missing image on the live site.

Leave `image` as `""` or omit it for everything else. Note that a question whose answer
depends on a figure is unusable without it, so don't merge NVR items with no image.

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
field names and duplicate stems.

CI runs it automatically on every PR touching this folder, so a failing pack can't merge.
To check just the packs a branch adds or changes:

```bash
git diff --name-only main...HEAD | grep '^elevenplus_data/.*\.json$' | xargs -r python3 elevenplus_data/validate_questions.py
```

---

## Quick checklist

- [ ] Copied `_TEMPLATE.question_pack.json`; one section per file, named `contrib_*.json`.
- [ ] Unique `source` (not `seed`, not another contributor's).
- [ ] `"is_placeholder": false` in the section header (it's your IP).
- [ ] Every question has `subtopic` (canonical), `stem`, `options`, and `difficulty` (1–3).
- [ ] Exactly one `"correct": true` per question.
- [ ] `number` and `ref` filled in; refs unique.
- [ ] Any `image` file actually committed under `static/questions/`.
- [ ] `python3 validate_questions.py <file>` exits 0.
