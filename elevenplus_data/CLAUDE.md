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
| `subtopic`      | **yes**  | —          | Canonical name, or the snake_case `slug`, from the taxonomy below.    |
| `question_type` | **most** | —          | Exact slug from the taxonomy. Required for ENG, MAT and VR; NVR only is exempt. |
| `stem`          | **yes**  | —          | The question the student answers.                                     |
| `kind`          | no       | `"mcq"`    | One of seven — see "Question kinds" below.                            |
| `options`       | **mcq**  | —          | `mcq` and `cloze_gap`. List of ≥2; **exactly one** `"correct": true`.  |
| `answer`        | **typed**| —          | `numeric`/`short_text` only. What the pupil types.                    |
| `tolerance`     | no       | `0`        | `numeric` only. Absolute; accepts answer ± tolerance.                 |
| `accepted_alternatives` | no | `[]`     | `short_text` only. Other spellings or wordings you accept.            |
| `segments`      | **selection** | —   | `error_span`/`select_word`. Pieces of the stem, lettered left to right. |
| `allow_no_error`| no       | `false`    | `error_span`. Adds the **N — No mistake** answer.                     |
| `gap_number`    | **cloze**| —          | `cloze_gap`. Which numbered gap of the passage this is.               |
| `marks`         | no       | `1`        | Marks available. Mostly for `extended_text`.                          |
| `model_answer`  | no       | `""`       | `extended_text`. What a marker compares against.                      |
| `rubric`        | no       | —          | `extended_text`. Object, e.g. `{"max": 4, "bands": [...]}`.           |
| `unit`          | no       | `""`       | Shown beside the answer box, not typed by the pupil (e.g. `£`, `cm`). |
| `also_tests`    | no       | `[]`       | Other subtopics the question needs — see "Questions that test two things". |
| `difficulty`    | **yes**  | —          | Integer `1`–`5`. Required on every question — see rubric below.       |
| `passage`       | no       | `""`       | Shared reading/stimulus text. Repeating it across questions is fine.  |
| `line_ref`      | no       | `""`       | Passage line this question is about — `"12"` or `"20-21"`. See below. |
| `explanation`   | no       | `""`       | Shown after answering. Strongly encouraged.                           |
| `image`         | no       | `""`       | Filename only if the question needs a figure. See below.              |
| `number`        | no       | —          | Human ordinal ("1", "2"…). Ignored by the importer but keep it.       |
| `ref`           | no       | —          | Your unique tracking code per question. Keep it — used for dedup.     |

### Question kinds

Most 11+ questions are multiple choice, but not all — and which they are depends on the
board. An audit of seven real papers found **GL and ISEB were 150 out of 150 multiple
choice, while CEM and Bond papers ran 58 out of 100 free numeric entry.** Roughly a third
of a GL English paper is neither: whole spelling and punctuation sections are spot-the-error,
and every paper ends with a cloze passage.

Bending those into `mcq` marks correctly and shows a child something they never meet in the
exam. So a pack may declare any of **seven** kinds:

| `kind` | The pupil… | Needs | Marked by |
|--------|------------|-------|-----------|
| `mcq` (default) | picks an option | `options` | the option flagged `correct` |
| `numeric` | types a number | `answer` (+ optional `tolerance`) | `answer` ± `tolerance` |
| `short_text` | types a word or short phrase | `answer` (+ optional `accepted_alternatives`) | case-insensitive match against `answer`, or any alternative appearing in what they wrote |
| `error_span` | picks the part of a sentence containing a mistake | `segments`, `answer` (a label), usually `allow_no_error` | the segment whose label is `answer` |
| `select_word` | clicks a word in a sentence | `segments`, `answer` (a label) | the segment whose label is `answer` |
| `cloze_gap` | picks a word for a numbered gap | `options`, `gap_number`, `passage` | the option flagged `correct` |
| `extended_text` | writes at length | `marks`, and a `rubric` and/or `model_answer` | a human — it is stored, not scored |

**A worked example of all seven lives in `_EXAMPLE.answer_kinds.json`.** It is importable
(`python manage.py import_pack elevenplus_data/_EXAMPLE.answer_kinds.json`) and `test_kinds.py`
checks it, so it stays true.

Rules the checker enforces:

- A typed question **must not** carry `options`, and an MCQ **must** carry them.
- A typed question **must** have a non-empty `answer`. Without one it imports perfectly
  and can never be marked correct — which no other check would catch.
- Put units in `unit`, never in `answer`. `"answer": "7 cm"` is an error; `"answer": 7`
  with `"unit": "cm"` is right. The unit is shown beside the box rather than typed, so a
  pupil is not marked wrong for writing "7cm" instead of "7 cm".

#### Picking part of a sentence: `error_span` and `select_word`

These two are one shape. The pupil is not choosing between answers printed underneath the
question — they are choosing a piece of the sentence in front of them. So instead of
`options` you give `segments`: consecutive pieces of the stem, lettered left to right.

```json
"kind": "error_span",
"stem": "She was definately going to win the race.",
"segments": [
  { "label": "A", "text": "She was " },
  { "label": "B", "text": "definately " },
  { "label": "C", "text": "going to win " },
  { "label": "D", "text": "the race." }
],
"answer": "B",
"allow_no_error": true
```

**The segments must join back to the stem exactly, spaces included.** That is the check
that matters, and it catches the mistake this format invites: silently *correcting* the
sentence while splitting it up, so the pupil is shown a spelling error that isn't there.
Note the trailing spaces above — they belong to a segment like any other character.

`"allow_no_error": true` adds the **N — No mistake** answer that real spelling and
punctuation sections offer. Without it a pupil who thinks the sentence is already correct
has nowhere to say so, so the checker warns if a spot-the-error question omits it.

`select_word` works identically, one word per segment; it just has no `N`.

#### Cloze gaps

A cloze section is one passage with numbered gaps, not ten questions each repeating the
passage. Give every gap the same `passage` text and its own `gap_number`, and the choices
for that gap as ordinary `options`.

#### Extended writing

`extended_text` is stored and routed to a human marker — the marking engine will not guess
at a four-mark character study. Give it `marks`, and a `rubric` and/or `model_answer` so
whoever marks it has something to mark against. It must not carry `options`, and `answer`
is ignored.

### Citing a line of the passage

Comprehension questions constantly point at a line — *"another way of saying 'lulled'
(line 1)"*. Put the reference in `line_ref` rather than burying it in the stem, and the
pupil sees it as a marker beside the question:

```json
"passage": "...",
"line_ref": "7",
"stem": "Why does the writer describe the storms as coming in 'like herds of grey horses'?"
```

`line_ref` is a line number (`"7"`) or a range (`"20-21"`). It only makes sense alongside a
`passage`, and the validator warns if there isn't one.

**Count lines at 100 characters.** A printed paper's line breaks are fixed by its
typesetting; a web page's are not, so the passage is wrapped server-side at a fixed width
before it is shown, and every 5th line is numbered. That width is **100 characters**, and it
is part of this contract — paragraph breaks (`\n\n`) start a new line and are not numbered
themselves. If you write a `line_ref`, count against that width, or check it by importing
the pack and looking at the question.

### Questions that test two things

The audit found **38% of real 11+ questions genuinely need more than one subtopic** — the
type you file names the last or hardest step, not the whole question. Record the rest in
`also_tests`:

```json
"subtopic": "Measurement",
"question_type": "money-and-change",
"also_tests": [
  { "subtopic": "Four Operations", "question_type": "addition-subtraction" }
]
```

`subtopic` and `question_type` stay primary — they are where the question is filed and
what practice decks are built from. `also_tests` is secondary and uses the same canonical
names, checked the same way. It matters because without it a subtopic can be load-bearing
across a whole paper and still register zero attempts, which quietly corrupts a pupil's
weakness diagnosis.

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

### MAT — Maths (17 subtopics, 82 question types)

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
| 15 | Statistics & Probability | `Statistics & Data` | 100 | `read-value`, `compare-values`, `proportion-of-total`, `mean`, `median`, `mode-and-range`, `table-reading`, `bar-charts`, `pictograms`, `pie-charts`, `line-graphs`, `venn-carroll` |
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

### Statistics questions are a grid, not a list

`Statistics & Data` is the one subtopic whose types split across two axes, because a real
question is an **operation** performed on a **representation** — "find the mean *from* a
bar chart".

- **Operations** — `read-value`, `compare-values`, `proportion-of-total`, `mean`,
  `median`, `mode-and-range`
- **Representations** — `table-reading`, `bar-charts`, `pictograms`, `pie-charts`,
  `line-graphs`, `venn-carroll`

File whichever axis carries the difficulty as `question_type` and put the other in
`also_tests`. A question with no representation — "find the median of 4, 7, 8" — simply
has no second half, which is why the checker only *warns* when a representation appears
without an operation.

### ENG — English (34 subtopics, 81 question types)

English has been rebuilt against the confirmed GL English schema, so an ENG question needs
**both** a `subtopic` and a `question_type`, exactly as Maths does.

A subtopic may be written either way round: the Title Case `subtopic` name, or the
snake_case `slug` the schema uses. Both resolve to the same subtopic on import, so a pack
authored straight from the schema validates without translation.

18 of the 81 types are evidenced by questions already written — those carry an
`evidence` field in `taxonomy.json` citing the question. The rest are marked
`"provenance": "proposed"`: structurally expected, but not yet confirmed against a real
paper. Confirming them is the job of an English paper audit of the kind Maths had.

| # | Topic | `subtopic` | `slug` | `question_type` slugs |
|---|-------|------------|--------|------------------------|
| 1 | Comprehension | `Literal Retrieval` | `literal_retrieval` | `fact-recall`, `locate-detail`, `cause-in-text` |
| 2 |  | `Inference` | `inference` | `infer-motive`, `infer-character`, `infer-situation`, `select-evidence` |
| 3 |  | `Vocabulary in Context` | `vocab_in_context` | `word-meaning-in-context`, `phrase-meaning`, `shade-of-meaning` |
| 4 |  | `Author's Purpose` | `authors_purpose` | `why-detail-included`, `why-structured-this-way`, `viewpoint-and-tone` |
| 5 |  | `Figurative Language` | `figurative_language` | `identify-device`, `find-example-of-device`, `effect-of-device` |
| 6 |  | `Text Structure` | `text_structure` | `sequence-events`, `overall-shape`, `paragraph-function` |
| 7 |  | `Poetry` | `poetry` | `poetic-form`, `sound-devices`, `imagery-in-poem` |
| 8 |  | `Comparing Texts` | `comparing_texts` | `similarity-between-texts`, `difference-between-texts`, `tone-contrast` |
| 9 | Grammar | `Word Classes` | `word_classes` | `identify-word-class`, `word-class-in-context` |
| 10 |  | `Verb Tenses` | `verb_tenses` | `identify-tense`, `choose-correct-tense` |
| 11 |  | `Subject-Verb Agreement` | `subject_verb_agreement` | `choose-agreeing-verb`, `spot-agreement-error` |
| 12 |  | `Active & Passive Voice` | `active_passive` | `identify-voice`, `convert-voice` |
| 13 |  | `Reported Speech` | `reported_speech` | `direct-to-reported`, `reported-to-direct` |
| 14 |  | `Sentence Types` | `sentence_types` | `identify-sentence-type`, `choose-sentence-type` |
| 15 |  | `Clauses & Phrases` | `clauses_phrases` | `main-vs-subordinate`, `identify-clause-type`, `identify-phrase` |
| 16 |  | `Modals & Subjunctive` | `modals_subjunctive` | `choose-modal`, `subjunctive-form` |
| 17 | Punctuation | `Apostrophes` | `apostrophes` | `possession`, `contraction`, `spot-apostrophe-error` |
| 18 |  | `Commas` | `commas` | `list-commas`, `clause-commas`, `spot-comma-error` |
| 19 |  | `Speech Marks` | `speech_marks` | `punctuate-speech`, `spot-speech-error` |
| 20 |  | `Colons & Semicolons` | `colons_semicolons` | `choose-colon-semicolon`, `spot-colon-error` |
| 21 |  | `Capital Letters` | `capital_letters` | `proper-nouns`, `spot-capital-error` |
| 22 |  | `Sentence Endings` | `sentence_endings` | `choose-end-mark`, `spot-end-error` |
| 23 |  | `Brackets, Dashes & Hyphens` | `brackets_dashes_hyphens` | `parenthesis-pairs`, `hyphen-use` |
| 24 | Spelling | `Misspelling Spotting` | `misspelling_spotting` | `spot-misspelling`, `choose-correct-spelling` |
| 25 |  | `Homophones` | `homophones` | `choose-homophone`, `spot-homophone-error` |
| 26 |  | `Prefixes & Suffixes` | `prefixes_suffixes` | `add-prefix`, `add-suffix`, `suffix-spelling-change` |
| 27 |  | `Plurals` | `plurals` | `regular-plural`, `irregular-plural` |
| 28 |  | `Silent Letters` | `silent_letters` | `identify-silent-letter`, `spell-with-silent-letter` |
| 29 | Vocabulary | `Synonyms` | `synonyms` | `closest-meaning`, `synonym-in-context` |
| 30 |  | `Antonyms` | `antonyms` | `opposite-meaning`, `antonym-in-context` |
| 31 |  | `Idioms` | `idioms` | `idiom-meaning`, `complete-idiom` |
| 32 |  | `Definitions` | `definitions` | `word-to-definition`, `definition-to-word` |
| 33 |  | `Homonyms` | `homonyms` | `same-word-two-meanings` |
| 34 | Cloze | `Word Choice` | `word_choice` | `grammar-driven-gap`, `meaning-driven-gap`, `collocation-gap` |

### VR — Verbal Reasoning (24 subtopics, 61 question types)

VR is rebuilt too, so `question_type` is required. Every type here is `proposed` — no VR
paper has been audited yet and no VR pack has been authored, so treat the type layer as a
starting hypothesis and say so if a real paper disagrees.

VR subtopics are already at the granularity of a classic GL question type, so the type
layer records the **rule family** — what the pupil actually has to work out. How the item is
answered (written in, shaded, or chosen from bracketed groups) is *not* a question type;
that is presentation, and it belongs to the answer format.

| # | Topic | `subtopic` | `slug` | `question_type` slugs |
|---|-------|------------|--------|------------------------|
| 1 | Word Meanings | `Paired Synonyms` | `synonyms_paired` | `one-from-each-group`, `closest-pair` |
| 2 |  | `Paired Antonyms` | `antonyms_paired` | `one-from-each-group`, `opposite-pair` |
| 3 |  | `Odd One Out` | `odd_one_out` | `by-category`, `by-word-property`, `by-letter-pattern` |
| 4 |  | `Double Meanings` | `double_meaning` | `two-senses-one-word`, `word-completes-both` |
| 5 |  | `Word Analogies` | `analogies_word` | `synonym-relation`, `antonym-relation`, `category-relation`, `function-relation`, `part-whole-relation` |
| 6 | Word Building | `Hidden Words` | `hidden_words` | `across-two-words`, `within-one-word` |
| 7 |  | `Compound Words` | `compound_words` | `one-from-each-group`, `join-two-words` |
| 8 |  | `Letter Moves` | `letter_moves` | `move-one-letter`, `swap-two-letters` |
| 9 |  | `Three-Letter Insertion` | `three_letter_insertion` | `insert-to-complete` |
| 10 |  | `Middle Word` | `middle_word` | `derive-from-both-sides` |
| 11 |  | `Word Patterns` | `word_pattern` | `apply-pattern`, `find-pattern` |
| 12 |  | `Anagrams` | `anagrams` | `plain-anagram`, `anagram-with-clue` |
| 13 | Letters & Codes | `Connecting Letters` | `connecting_letter` | `single-connector`, `two-connectors` |
| 14 |  | `Letter Sequences` | `letter_sequences` | `constant-shift`, `alternating-shift`, `mirror-alphabet`, `paired-letters` |
| 15 |  | `Letter Analogies` | `letter_analogies` | `single-letter-shift`, `pair-shift`, `position-swap` |
| 16 |  | `Letter Codes` | `letter_codes` | `word-to-code`, `code-to-word`, `find-the-rule` |
| 17 |  | `Number Codes` | `number_codes` | `number-to-code`, `code-to-number`, `symbol-substitution` |
| 18 | Number Work | `Number Sequences` | `number_sequences` | `constant-difference`, `changing-difference`, `multiplicative`, `alternating`, `two-step-rule` |
| 19 |  | `Missing Number Sums` | `missing_number_sum` | `missing-operand`, `missing-operator`, `balance-both-sides` |
| 20 |  | `Triplet Rules` | `triplet_rules` | `find-the-rule`, `apply-the-rule` |
| 21 |  | `Letter Algebra` | `letter_algebra` | `substitute-and-evaluate`, `solve-for-letter` |
| 22 | Logic | `Scenario Deduction` | `scenario_deduction` | `seating-order`, `attribute-grid`, `ranking` |
| 23 |  | `Must Be True` | `must_be_true` | `valid-conclusion`, `spot-invalid-conclusion` |
| 24 |  | `Directions` | `directions` | `compass-bearing`, `turns-and-facing`, `relative-position` |

### NVR — Non-Verbal Reasoning

Not rebuilt yet — these are the pre-rebuild subtopics, carried over so existing packs keep
validating. There are no question types, so `question_type` is optional (and ignored) in an
NVR pack.

- `3D Shapes & Nets`
- `Analogies`
- `Codes`
- `Odd One Out`
- `Rotation & Reflection`
- `Series & Sequences`

### Subtopics that left the taxonomy

The Maths, English and VR rebuilds each replaced the section's earlier subtopics. Nothing is
deleted — dropping a `Subtopic` cascades into every `Attempt` against it and would destroy
pupils' history — so the old rows stay in the database, holding the content that was filed
there before the rebuild. They are simply no longer valid in a new pack:

- **ENG:** `Grammar & Punctuation`, `Reading Comprehension`, `Spelling`, `Vocabulary`
- **VR:** `Analogies`, `Codes & Sequences`, `Hidden & Compound Words`, `Letters & Alphabet`,
  `Logic Problems`, `Word Meanings` — `Odd One Out` survives the rebuild under the same name.

---

## What a pack cannot do yet

Worth knowing before you plan a batch, because real 11+ papers are full of all three:

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
- [ ] MCQ: exactly one `"correct": true`. Typed: an `answer`, and no `options`.
- [ ] Units in `unit`, never inside `answer`.
- [ ] `also_tests` filled in wherever the question really needs a second subtopic.
- [ ] No distractor equal in value to the correct answer.
- [ ] Difficulty spread across the batch, not all 2s.
- [ ] `number` and `ref` filled in; refs unique across every pack, not just yours.
- [ ] Any `image` file actually committed under `static/questions/`.
- [ ] `python3 elevenplus_data/validate_questions.py elevenplus_data/*.json` exits 0.
