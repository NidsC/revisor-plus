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

    "source": "CONTRIB-<yourinitials>-<batch>"      e.g. "CONTRIB-NC-01"

`seed` is **reserved** by the built-in demo content — never use it. A pack with no `source`
at all is refused outright by the importer.

Name your file to match: `contrib_<initials>_<section>_<nn>.json`. The build script
auto-imports everything matching `contrib_*.json`, so a merged pack deploys without any code
change.

`validate_questions.py` now checks this **across packs**, not just within one — see
"Validate" below. That check only works when it is given several packs at once, which is why
CI runs it over the whole folder.

---

## File shape

One file = **one section** = **one source**. Copy `_TEMPLATE.question_pack.json` and edit it.

```json
{
  "section": { "code": "MAT", "name": "Maths", "source": "CONTRIB-NC-01", "is_placeholder": false },
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

**If you are working from a past paper, you are writing a question *of the same type*, not a
copy of theirs.** A transcribed question is someone else's copyright and quietly makes the
`is_placeholder: false` claim above untrue. Source papers live in `source_papers/`, which is
gitignored so they never ship.

### Each question

| Field           | Required | Default    | Notes                                                                 |
|-----------------|----------|------------|-----------------------------------------------------------------------|
| `subtopic`      | **yes**  | —          | Exact canonical name from the taxonomy below.                         |
| `question_type` | **MAT**  | —          | Exact slug from the taxonomy. Required for Maths; ignored elsewhere.  |
| `stem`          | **yes**  | —          | The question the student answers.                                     |
| `options`       | **yes**  | —          | List of ≥2 options; **exactly one** has `"correct": true`.            |
| `difficulty`    | **yes**  | —          | Integer `1`–`5`. Required on every question — see rubric below.       |
| `kind`          | no       | `"mcq"`    | Only `"mcq"`. See "What a pack cannot do yet".                        |
| `passage`       | no       | `""`       | Shared reading/stimulus text. Repeating it across questions is fine.  |
| `explanation`   | no       | `""`       | Shown after answering. Strongly encouraged.                           |
| `image`         | no       | `""`       | Filename only if the question needs a figure. See below.              |
| `number`        | no       | —          | Human ordinal ("1", "2"…). Ignored by the importer but keep it.       |
| `ref`           | no       | —          | Your unique tracking code per question. Keep it — used for dedup.     |

**Difficulty rubric** — set it honestly and consistently. Pitch it at a Year 5/6 pupil
sitting the exam, not at an adult. The scale is **1–5**: the model, the generators and both
author papers all use 1–5, and the targeted-paper feature draws its hard questions from the
top of it. A bank that only ever uses 1–3 leaves that feature nothing to reach for.

| Value | Meaning                                                                              |
|-------|--------------------------------------------------------------------------------------|
| `1`   | Recall or one clear step. Almost every prepared pupil gets it.                        |
| `2`   | Standard single-topic question, one or two steps, no trap.                            |
| `3`   | Typical exam level — two steps, or one step plus a common misconception to avoid.     |
| `4`   | Hard — multi-step, subtle distractors, or real time pressure.                         |
| `5`   | Stretch — combines topics, or scholarship/top-set level. Use sparingly.               |

Aim for a spread across a batch rather than a single band. A reasonable default per
question type is roughly **2 × difficulty 1–2, 7 × difficulty 3, 4 × difficulty 4, 1 × difficulty 5**.

`number` and `ref` are **not** loaded into the database, but they make review, dedup and
"which question is broken?" possible. Always include them.

### Each option

| Field     | Required | Default | Notes                                        |
|-----------|----------|---------|----------------------------------------------|
| `text`    | yes      | —       | The answer text, non-empty.                  |
| `correct` | no       | `false` | Set `true` on **exactly one** option.        |

**No distractor may be the correct answer written a different way.** `2/3` and `30/45` are
the same number; a question offering both has two right answers, and the pupil who picks the
"wrong" one is right. This is the single easiest defect to introduce in a fractions,
ratio or probability question — the published syllabus we work from has three of them.

Either change the distractor, or make the stem ask for a specific form:

- ✗ `Calculate 3/5 × 10/9` → options `2/3` (key) and `30/45`
- ✓ `Calculate 3/5 × 10/9, giving your answer in its simplest form` → same options, now fair
- ✓ `Calculate 3/5 × 10/9` → options `2/3` (key) and `5/6`

`validate_questions.py` catches this as an ERROR when one of the pair is the key, and as a
warning when two distractors collide. It compares numbers only when the text around them
matches, so `£20` and `20%`, or `20 cm` and `20 cm²`, are never confused.

---

## The taxonomy

`taxonomy.json` in this folder is the **single source of truth**. The validator loads it,
`manage.py sync_taxonomy` writes it to the database, and the tables below are generated from
it. Change the taxonomy there, not here.

**Version 2** applies a seven-paper audit — 250 real questions across CEM, GL, ISEB and a
Bond/OUP paper. Ten question types were added or split as a result, each recording the papers
that produced it in an `evidence` field in `taxonomy.json`. Targets were re-weighted from the
same frequency data. If a type you expect is missing, check there first: it may have been
looked for and not found.

Names and slugs are matched **character for character**. A typo does not error on import —
it silently creates a new, unintended subtopic and hides your question in it.

### MAT — Maths (17 subtopics, 79 question types)

Maths is the one section whose taxonomy has been rebuilt against the 11+ syllabus, so a MAT
question needs **both** a `subtopic` and a `question_type`. The slug must belong to that
subtopic — the same slug may appear under two different subtopics, so they are only ever
valid as a pair.

**Target** is this topic's share of the 1000 Maths questions. It is a planning number, not
a rule the validator enforces; the split within a topic is yours to judge.

| # | Topic | `subtopic` | Target | `question_type` slugs |
|---|-------|------------|--------|------------------------|
| 1 | Number | `Number & Place Value` | 70 | `place-value`, `rounding`, `negative-numbers`, `roman-numerals` |
| 2 |  | `Factors, Multiples & Primes` | 45 | `listing-factors`, `prime-numbers`, `multiples`, `hcf-lcm` |
| 3 |  | `Powers, Squares & Cubes` | 25 | `square-numbers`, `cube-numbers`, `square-roots` |
| 4 |  | `Four Operations` | 85 | `long-multiplication`, `long-division`, `order-of-operations`, `addition-subtraction` |
| 5 | Fractions, Decimals & Percentages | `Fractions, Decimals & Percentages` | 125 | `equivalent-fractions`, `adding-subtracting-fractions`, `multiplying-fractions`, `dividing-fractions`, `mixed-improper-fractions`, `fraction-of-amount`, `quantity-as-fraction`, `percentage-change`, `percentage-of-amount`, `converting-forms`, `ordering-comparing` |
| 6 | Ratio & Proportion | `Ratio & Proportion` | 60 | `simplifying-ratios`, `sharing-in-ratio`, `direct-proportion`, `best-buy` |
| 7 |  | `Speed, Distance & Time` | 25 | `calculating-speed`, `calculating-distance`, `calculating-time`, `average-speed` |
| 8 | Algebra | `Algebra & Sequences` | 70 | `solving-equations`, `function-machines`, `number-sequences`, `nth-term`, `forming-expressions`, `substitution` |
| 9 | Measurement | `Measurement` | 65 | `unit-conversion`, `reading-scales`, `time-calculations`, `money-and-change` |
| 10 |  | `Perimeter, Area & Volume` | 70 | `perimeter`, `area-rectangle`, `area-triangle`, `volume-cuboid`, `compound-shapes` |
| 11 | Geometry | `2D Shapes & Angles` | 70 | `angles-in-triangle`, `angle-types`, `angles-on-line`, `polygon-properties`, `angles-in-quadrilateral`, `angles-around-point`, `parts-of-circle` |
| 12 |  | `3D Shapes` | 20 | `faces-edges-vertices`, `nets` |
| 13 |  | `Symmetry & Transformation` | 30 | `lines-of-symmetry`, `rotational-symmetry`, `translation`, `reflection`, `rotation` |
| 14 |  | `Coordinates` | 25 | `plotting-points`, `midpoint` |
| 15 | Statistics & Probability | `Statistics & Data` | 100 | `mean`, `median`, `mode-and-range`, `pie-charts`, `bar-charts`, `pictograms`, `line-graphs`, `table-reading`, `venn-carroll` |
| 16 |  | `Probability` | 20 | `probability-scale`, `single-event-probability` |
| 17 | Problem Solving | `Word Problems & Multi-Step Reasoning` | 95 | `additive-word-problem`, `multiplicative-word-problem`, `number-puzzles` |

### The topic layer

Eight topics group the 17 subtopics. **They are structural only.** The seven-paper audit
found that no real 11+ paper groups its questions by topic — papers are deliberately
topic-shuffled — so this layer exists for navigation and for rolling up a pupil's weakness
report, not as a claim about how exams are built. **You never put a topic in a question
pack**; a pack carries `subtopic` and `question_type`, and the topic follows from the
subtopic.

| # | Topic | Target | Subtopics |
|---|-------|--------|-----------|
| 1 | **Number** | 225 | Number & Place Value, Factors, Multiples & Primes, Powers, Squares & Cubes, Four Operations |
| 2 | **Fractions, Decimals & Percentages** | 125 | Fractions, Decimals & Percentages |
| 3 | **Ratio & Proportion** | 85 | Ratio & Proportion, Speed, Distance & Time |
| 4 | **Algebra** | 70 | Algebra & Sequences |
| 5 | **Measurement** | 135 | Measurement, Perimeter, Area & Volume |
| 6 | **Geometry** | 145 | 2D Shapes & Angles, 3D Shapes, Symmetry & Transformation, Coordinates |
| 7 | **Statistics & Probability** | 120 | Statistics & Data, Probability |
| 8 | **Problem Solving** | 95 | Word Problems & Multi-Step Reasoning |

### The other three sections

Their taxonomies have **not** been rebuilt yet — these are the pre-rebuild subtopics, carried
over so existing packs keep validating. There are no question types for them, so
`question_type` is optional (and ignored) in an ENG, VR or NVR pack.

**ENG — English**
- `Grammar & Punctuation`
- `Reading Comprehension`
- `Spelling`
- `Vocabulary`

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

## What a pack cannot do yet

Worth knowing before you plan a batch, because real 11+ papers are full of all three:

- **Short-answer and numeric-entry questions.** `import_pack.py` reads `options`
  unconditionally and never reads `answer_text`, `tolerance` or `marking`, so a numeric
  question imported through this route would arrive unmarkable. The validator therefore
  accepts `"kind": "mcq"` only. The database model supports the other kinds and the *paper*
  importer already uses them — it is this contributor route that doesn't.
- **Multi-part questions** (a shared stem with parts a/b/c). Same reason: the pack importer
  creates one flat question per entry.
- **Figures generated from data.** `image` takes a committed file; there is no way to declare
  a chart or diagram and have it drawn.

None of these are permanent. If a topic genuinely needs one, say so rather than bending a
question into multiple choice that shouldn't be.

---

## Images

Some MAT questions (charts, shapes, diagrams) need a figure. If yours does:

1. Set `"image": "your_figure.png"` — **filename only**, no path.
2. Put the file in `static/questions/`. If you can't add the file, say so in your PR — a
   broken image path shows a missing image on the live site.

Leave `image` as `""` or omit it for everything else. A question whose answer depends on a
figure is unusable without it, so don't merge one with no image.

**Anything needed to answer the question must also be in the text.** A pupil using a screen
reader, or looking at a figure that failed to load, should still be able to answer.

---

## Before you open a pull request — validate

Run the checker. It needs nothing but Python 3:

```bash
python3 elevenplus_data/validate_questions.py elevenplus_data/contrib_<yours>.json
```

- **Exit 0** — clean, safe to merge. (Warnings are worth a glance but don't block.)
- **Exit 1** — errors. Fix them; do not merge.
- **Exit 2** — the file isn't valid JSON / can't be read.

It enforces everything above: valid section code, a non-reserved `source`, required fields
(including `difficulty` 1–5), canonical subtopics **and question types**, exactly one correct
option, no option that duplicates the key's value, valid `is_placeholder`, unique refs, and it
warns on typo'd field names and duplicate stems.

**Pass it every pack at once, not just yours.** Duplicate sources, duplicate refs and
duplicate stems *between* packs are invisible when files are checked one at a time — and a
duplicate source is the one that deletes another author's work:

```bash
python3 elevenplus_data/validate_questions.py elevenplus_data/*.json
```

CI runs exactly that on every PR touching this folder, so a colliding pack can't merge.

---

## Quick checklist

- [ ] Copied `_TEMPLATE.question_pack.json`; one section per file, named `contrib_*.json`.
- [ ] Unique `source` (not `seed`, not another contributor's, not `CONTRIB-EXAMPLE-01`).
- [ ] `"is_placeholder": false` in the section header (it's your IP).
- [ ] Every question has `subtopic` (canonical), `stem`, `options`, `difficulty` (1–5) —
      **and `question_type` if this is a MAT pack**.
- [ ] Exactly one `"correct": true` per question.
- [ ] No distractor equal in value to the correct answer.
- [ ] Difficulty spread across the batch, not all 2s.
- [ ] `number` and `ref` filled in; refs unique across every pack, not just yours.
- [ ] Any `image` file actually committed under `static/questions/`.
- [ ] `python3 elevenplus_data/validate_questions.py elevenplus_data/*.json` exits 0.
