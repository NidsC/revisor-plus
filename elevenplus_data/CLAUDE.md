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
| `question_type` | **most** | —          | Exact slug from the taxonomy. Required for ENG, MAT and VR; on NVR it must be omitted. |
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
| `passage`       | no       | `""`       | Stimulus text only this question uses. To share one, see `passage_ref`. |
| `passage_ref`   | no       | —          | Points at one of the pack's `passages`. Not with `passage`.           |
| `line_ref`      | no       | `""`       | Passage line this question is about — `"12"` or `"20-21"`. See below. |
| `explanation`   | no       | `""`       | Shown after answering. Strongly encouraged.                           |
| `image`         | no       | `""`       | Filename only if the question needs a figure. See below.              |
| `figure`        | no       | —          | A diagram described as data and drawn for you. See "Figures". Not with `image`. |
| `number`        | no       | —          | Human ordinal ("1", "2"…). Ignored by the importer but keep it.       |
| `ref`           | no       | —          | Your unique tracking code per question. Keep it — used for dedup.     |

### Question kinds

Most 11+ questions are multiple choice, but not all — and which they are depends on the
board. An audit of seven real papers found **GL and ISEB were 150 out of 150 multiple
choice, while CEM and Bond papers ran 58 out of 100 free numeric entry.** Roughly a third
of a GL English paper is neither: whole spelling and punctuation sections are spot-the-error,
and every paper ends with a cloze passage.

Verbal reasoning adds one more shape that `mcq` cannot hold: **grouped brackets**. "Money is
to (coins, bank, shopping) as tea is to (sandwich, cup, caddy)" — one word from each bracket,
one mark for the pair. GL prints these for analogies, similars and opposites, which is a
large part of the paper.

Bending those into `mcq` marks correctly and shows a child something they never meet in the
exam. So a pack may declare any of **eight** kinds:

| `kind` | The pupil… | Needs | Marked by |
|--------|------------|-------|-----------|
| `mcq` (default) | picks an option | `options` | the option flagged `correct` |
| `numeric` | types a number | `answer` (+ optional `tolerance`) | `answer` ± `tolerance` |
| `short_text` | types a word or short phrase | `answer` (+ optional `accepted_alternatives`) | case-insensitive match against `answer`, or any alternative appearing in what they wrote |
| `error_span` | picks the part of a sentence containing a mistake | `segments`, `answer` (a label), usually `allow_no_error` | the segment whose label is `answer` |
| `select_word` | clicks a word in a sentence | `segments`, `answer` (a label) | the segment whose label is `answer` |
| `cloze_gap` | picks a word for a numbered gap | `options`, `gap_number`, `passage` | the option flagged `correct` |
| `grouped_options` | picks one word from **each** set of brackets | `option_groups` | every bracket right, for one mark |
| `extended_text` | writes at length | `marks`, and a `rubric` and/or `model_answer` | a human — it is stored, not scored |

**A worked example of the first seven lives in `_EXAMPLE.answer_kinds.json`**, and of
`grouped_options` in `_EXAMPLE.vr_shapes.json` — the eighth is a VR shape, and demonstrating
it in an English pack would model something no GL English paper does. Both are importable
(`python manage.py import_pack elevenplus_data/_EXAMPLE.answer_kinds.json`) and `test_kinds.py`
checks them, so they stay true.

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

#### One word from each bracket: `grouped_options`

The GL verbal reasoning staple. The pupil picks one word from **each** set of brackets, and
the answer is the pair. Instead of `options` you give `option_groups`: one entry per bracket,
numbered from 1 left to right as the stem prints them, each with **exactly one** `correct`.

```json
{
  "kind": "grouped_options",
  "stem": "Money is to (coins, bank, shopping) as tea is to (sandwich, cup, caddy).",
  "option_groups": [
    { "group": 1, "options": [
        { "text": "coins" }, { "text": "bank" }, { "text": "shopping", "correct": true } ] },
    { "group": 2, "options": [
        { "text": "sandwich" }, { "text": "cup", "correct": true }, { "text": "caddy" } ] }
  ]
}
```

- **One mark for the pair, all or nothing.** That is what a paper gives: half a pair is not
  half an analogy, and awarding partial credit would reward guessing — two brackets of three
  come out half-right by chance one time in two. When a pupil misses, the feedback names the
  bracket that was wrong.
- **Write the whole stem, brackets and all.** The words are read as part of the sentence.
  They are not lettered, because a paper does not letter them.
- **Do not flatten two brackets into one `options` list.** Nine combined pairs is not what
  the child is shown, and `mcq` cannot say which words belong to which bracket.
- At least two brackets, at least two words in each, numbered `1..N` with no gaps.
- The [answer-key rule](#each-option) applies **per bracket**: each one is its own positional
  choice, and the natural way to draft is to write the two right words first and build each
  bracket around them, which puts both keys first.

#### Extended writing

`extended_text` is stored and routed to a human marker — the marking engine will not guess
at a four-mark character study. Give it `marks`, and a `rubric` and/or `model_answer` so
whoever marks it has something to mark against. It must not carry `options`, and `answer`
is ignored.

### Sharing a passage

A comprehension section is one text with a run of questions about it, and a cloze section is
one text with numbered gaps — not ten questions each reprinting the same passage. Declare the
text once at the top of the pack and point at it:

```json
{
  "section": { "...": "..." },
  "passages": [
    {
      "passage_ref": "P1",
      "title": "Down the Rabbit-Hole",
      "text": "Alice was beginning to get very tired...\n\nSo she was considering...",
      "source_note": "Public domain: the opening of 'Alice's Adventures in Wonderland' (1865)."
    }
  ],
  "questions": [
    { "passage_ref": "P1", "stem": "What did Alice complain her sister's book lacked?", "...": "..." },
    { "passage_ref": "P1", "kind": "cloze_gap", "gap_number": 1, "...": "..." }
  ]
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `passage_ref` | yes | Unique in the pack. Questions point at it by this. |
| `title` | yes | Shown above the passage. |
| `text` | yes | Paragraph breaks as `\n\n`. |
| `source_note` | yes | Where the text came from. |

**`source_note` is not paperwork.** It is what separates a public-domain extract from
someone else's copyright, and a bank that cannot tell them apart cannot safely be published.
Write `"Original work written for this pack"` if you wrote it.

On import the passage becomes a **container**: one row holding the text, with its questions
hanging off it. The text is stored once rather than copied into each question, and the
container is never served to a pupil as a question in its own right. A question may use
`passage_ref` **or** an inline `passage`, never both.

Gap numbers must be unique within a passage — two questions numbered gap 3 of the same text
would render on top of each other.

A worked example is in `_EXAMPLE.shared_passage.json`.

### Sharing an instruction and a worked example

A paper prints an instruction and one worked example **once**, above a run of five or six
items. Much of verbal reasoning does not survive losing it: `mal ( ) ens` is not a hard
question without the instruction, it is not a question. Declare each block once and point at
it with `group_ref`:

```json
{
  "groups": [
    {
      "group_ref": "G-ANALOGY",
      "instruction": "Choose one word from each set of brackets so that the second pair of words is connected in the same way as the first pair.",
      "example": "Bee is to (honey, hive, sting) as spider is to (fly, web, silk). A bee makes and lives in a hive, and a spider makes and lives in a web, so the answer is hive, web."
    }
  ],
  "questions": [
    { "group_ref": "G-ANALOGY", "kind": "grouped_options", "...": "..." }
  ]
}
```

Both fields are required. The example is not decoration — it is where the pupil learns what
the notation means, and a block without one is an author who has not noticed.

**This is not the same mechanism as `passages`.** A shared passage becomes one container row
that its questions hang off; a group is **copied onto every question that points at it**.
Two reasons, and they are worth knowing before you propose changing it:

1. A question routinely needs a passage *and* an instruction, or a table *and* an
   instruction. `Question.parent` is a single ForeignKey and cannot hold both.
2. A practice deck is dealt across subtopics, so a question is served **alone, out of its
   block**. It has to carry its own instruction or arrive unanswerable.

So the instruction appears above every question in the block, which is also what a pupil
needs when they meet one on its own. Copying two short strings costs nothing; copying a
400-word passage would, which is why passages work the other way.

### Sharing a data table

GL letter- and number-code sections print a small grid of words and their codes with **one
cell withheld**, and ask several questions against it. That is tabular data, so `passages` is
the wrong home, and `image` would mean committing a picture of a table.

```json
{
  "tables": [
    {
      "table_ref": "T-CODE",
      "headers": ["Word", "Code"],
      "rows": [["CAT", "DBU"], ["PIG", "QJH"], ["HEN", "IFO"], ["DOG", ""]]
    }
  ],
  "questions": [
    { "table_ref": "T-CODE", "kind": "short_text", "answer": "EPH", "...": "..." }
  ]
}
```

- **Exactly one cell must be blank** (`""` or `null`) — it is what the question asks for. Two
  and the pupil cannot tell which one is wanted; none and the answer key has been pasted in
  by mistake. The checker errors on both.
- Every row must have as many cells as there are `headers`.
- It renders as a real table with the blank cell as an empty box. A question may not carry
  both a `table_ref` and an `image`; it shows one figure.
- Copied onto each question, for the same reasons as `groups` above.

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

| Field           | Required | Default | Notes                                                     |
|-----------------|----------|---------|-----------------------------------------------------------|
| `text`          | yes      | —       | The answer text, non-empty.                               |
| `correct`       | no       | `false` | Set `true` on **exactly one** option.                     |
| `misconception` | no       | `""`    | Why this **wrong** answer is tempting. See below.          |
| `figure`        | no       | —       | This answer's picture, for a non-verbal question. See "Figures". |

#### Saying why a distractor is tempting

A good distractor is not a random wrong answer — it is the answer a pupil gets by making
one specific mistake. `misconception` names that mistake, and the pupil is told it when
they pick that option:

> That's the answer you get if you **divided instead of multiplying**.

```json
"options": [
  { "text": "12", "correct": true },
  { "text": "3",  "misconception": "divided-instead-of-multiplying" },
  { "text": "7",  "misconception": "added-two-sides-only" }
]
```

Three things follow from the fact that the slug **is the sentence the child reads**:

- **Pick from the list.** The vocabulary lives in the `misconceptions` block of
  `taxonomy.json` and the validator checks against it. Free text would be unreviewed
  pupil-facing prose, and would make the set impossible to count — "which mistake does
  this pupil keep making?" only has an answer across a shared vocabulary.
- **Never on the correct option.** It would tell a pupil who scored the mark that they
  got it wrong. The validator errors on this.
- **House style is a past-tense verb phrase: what the pupil *did*.**
  `divided-instead-of-multiplying`, not `division-error`. It has to read as the end of
  "that's the answer you get if you …".

If a distractor's mistake genuinely isn't in the list, **add it to `taxonomy.json`** in
that style, and say so in your PR. That is a deliberate edit to the source of truth,
exactly like adding a subtopic — not something to work around by inventing a slug.

It is **optional**. A distractor without one still works; the pupil just gets "not quite"
where a tagged one names the slip. The list came from the generators' error models, so
Maths has most of it and NVR none — authored packs are how the other sections get any.

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

**Move the key around.** The correct answer must not keep landing in the same position. A
pupil who notices that the answer is usually the first option scores without reading the
question — and an 11+ pupil, drilled on past papers, is exactly the person who notices. That
does not just cost marks in a real exam; it corrupts the weakness report, because the whole
point of the analytics is to tell reasoning apart from guessing, and a bank that rewards
guessing cannot.

This is the easiest defect to introduce without noticing, because no single question is
wrong. Writing the answer first and the distractors after it is the natural way to think, and
it produces a pack where every key is A. The generated bank does not have the problem —
`shuffled_options` in `catalog/generators/__init__.py` randomises — but nothing shuffles a
pack you write.

The validator warns when four questions in a row share a key position, or when more than half
a pack of eight or more lands in one. Do not write to the threshold: vary it as you go, the
way a real paper does. `error_span` and `select_word` are exempt and not counted — their
options are the pieces of the sentence, lettered left to right, so the key cannot move.

Varying it by eye works for a short pack; it does not reliably work at batch scale (a run of
25 is exactly how this problem was found). Before validating a batch, run:

```
python3 elevenplus_data/rebalance_keys.py elevenplus_data/contrib_<yours>.json
```

It reorders each question's options — content and correctness untouched — until the same
check above has nothing to warn about, skipping (and telling you about) any question whose
own explanation names a literal option letter, since reordering that one would make it
self-contradictory.

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

### MAT — Maths (17 subtopics, 83 question types)

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
| 8 | Algebra | `Algebra & Sequences` | 70 | `solving-equations`, `function-machines`, `number-sequences`, `nth-term`, `forming-expressions`, `substitution`, `inequalities` |
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

VR is rebuilt too, so `question_type` is required. Fifty-four of the sixty-one types are
`proposed` — treat those as a starting hypothesis and say so if a real paper disagrees. The
seven under `Word Analogies`, `Paired Synonyms` and `Paired Antonyms` are `authored`, on the
strength of a collaborator's report of GL papers rather than a paper audited here. Their
`evidence` fields say so; that is weaker than the seven-paper Maths audit and worth
re-checking against a real paper.

VR subtopics are already at the granularity of a classic GL question type, so the type
layer records the **rule family** — what the pupil actually has to work out. How the item is
answered is *not* a question type; that is presentation, and it belongs to the answer format.

**How VR items are answered.** The three formats and what each one is:

| The paper says | Use | Example |
|---|---|---|
| write it in | `short_text`, or `numeric` for a number | the hidden word, the connecting letter, the middle word; the missing number in a sum or sequence |
| pick one from each bracket | `grouped_options` | analogies, similars, opposites |
| pick one answer | `mcq` | letter sequences, "must be true" |

Write-in is not second best and does not need bending into `mcq`: much of VR genuinely is
write-in, and `short_text` marks it. Two things to know when you use it:

- A one-letter answer works — `"answer": "t"` marks `t` and `T` right and everything else
  wrong. But matching is exact against `answer`, so a pupil who writes `t.` is marked wrong.
  Put the forms you will accept in `accepted_alternatives`, which is matched loosely.
- Capitalisation does not matter; the marking engine casefolds.

**Shading is not a kind.** GL is sat by shading a letter on a separate answer grid. That is
how a paper is *recorded*, not what the pupil works out, and it has no meaning in a web app —
so there is no `shade` kind and no second `entry_mode` axis. This was considered and rejected
deliberately (2026-08-26); do not re-add it without a reason that is about the pupil rather
than the paper.

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
validating. There are no question types, so an NVR question must **not** carry
`question_type` at all: there is no list to pick a slug from, and the validator rejects any
value rather than accept one it cannot check. It becomes required, like the other three
sections, when the NVR taxonomy is rebuilt.

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

Worth knowing before you plan a batch:

- **Multi-part questions** (a single stem with parts a/b/c that each score separately).
  The database supports them and imported papers use them, but a contributor pack has no
  way to declare one — it gets a flat question per entry. Sharing a *passage* between
  questions is supported: see "Sharing a passage" above.
- **Charts drawn from data.** `figure` draws a *closed* set of kinds — `l_shape`,
  `angles_on_line`, `venn`, `table`, `number_box`, `nvr_grid`, `nvr_panel`, `nvr_net` — and
  the validator rejects anything outside it, so a question cannot reach a pupil with a blank
  panel. Bar charts, pie charts, line graphs and pictograms are **not** in that set, which
  matters most for `Statistics & Data`: those still need a committed `image` file. Say so
  before authoring a batch that depends on one.

It is not permanent. If a topic genuinely needs one, say so rather than bending a
question into a shape that shouldn't be.

> **Figures used to be on this list.** "`image` takes a committed file; there is no way to
> declare a chart or diagram and have it drawn" was true until the `figure` field existed,
> and it is why non-verbal reasoning could only ever be generated, never authored. See
> "Figures" below.

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

## Figures

A `figure` is a diagram you **describe**, and the app draws. Nothing in a pack contains
markup: you write what the picture is made of, and `catalog/figures` turns that into SVG at
render time.

```json
"figure": { "kind": "nvr_panel", "data": { "cell": { "shape": "hexagon", "fill": "half" } } }
```

This is the route non-verbal reasoning runs on, and until it existed NVR could not be
authored at all. It also means an author can only ask for pictures this build can actually
draw — every name below is a closed list, and `validate_questions.py` rejects anything
outside it rather than letting the app quietly draw a blank panel.

**See the whole vocabulary rendered:**

```bash
python3 elevenplus_data/preview_figures.py       # writes figures-preview.html
```

A question may carry `figure` **or** `image`, never both.

### The three kinds

| `kind` | For | `data` |
|--------|-----|--------|
| `nvr_grid` | a stem: a row or grid of panels | `cells` (required), `cols`, `blank`, `separator_after`, `alt` |
| `nvr_panel` | one panel — this is what an **answer** is | `cell` (required), `alt` |
| `nvr_net` | a cube net | `squares` (required), `alt` |

`nvr_grid` covers nearly every non-verbal stem there is: a series is a row, a matrix sets
`cols`, an analogy sets `separator_after`. `blank` is the index of the cell the pupil
supplies, and that cell must be `null`.

Only `nvr_panel` and `nvr_net` may go on an option.

### Answers that are pictures

Put the picture on the **option**, not inside the stem figure:

```json
"options": [
  { "text": "hexagon, turned 90°", "correct": true,
    "figure": { "kind": "nvr_panel", "data": { "cell": { "shape": "hexagon", "rot": 90 } } } },
  { "text": "hexagon, turned 270°",
    "figure": { "kind": "nvr_panel", "data": { "cell": { "shape": "hexagon", "rot": 270 } } } }
]
```

Three rules, each of which the checker enforces:

- **All or none.** An option with no figure beside options that have one renders as an
  empty tile.
- **No two options may draw the same picture.** The checker draws them and compares, because
  the specs are not the test — `"rot": 180` and `"rot": -180` are different specs and the
  same panel. Two answers a pupil cannot tell apart is one answer with two letters on it.
- **`text` is still required**, and describes the panel in words. It is what the review
  screens print and what a pupil gets if the drawing fails.

  Be honest about its limit here. For a Maths diagram the text really can carry everything
  needed. A non-verbal question asks a pupil to *see* a relationship between shapes, and no
  sentence makes that available to someone who cannot see them. Write the best description
  you can; do not claim the section is answerable without sight.

### What a cell may contain

A cell is one glyph, or `{"items": [...]}` for several:

```json
{ "items": [ { "shape": "square", "size": "large" },
             { "shape": "circle", "size": "small", "fill": "solid", "at": "top_right" } ] }
```

| Field | Values |
|-------|--------|
| `shape` | `arrow`, `circle`, `cross`, `diamond`, `ellipse`, `flag`, `hexagon`, `l_shape`, `octagon`, `pentagon`, `rectangle`, `right_trapezium`, `right_triangle`, `semicircle`, `square`, `star`, `star6`, `trapezium`, `triangle` |
| `size` | `tiny`, `small`, `medium` (default), `large` |
| `fill` | `none` (default), `solid`, `half`, `quarter`, `hatch`, `cross_hatch`, `dots` |
| `stroke` | `solid` (default), `dashed`, `bold` |
| `at` | `center` (default), `top`, `bottom`, `left`, `right`, `top_left`, `top_right`, `bottom_left`, `bottom_right` |
| `rot` | whole degrees, a **multiple of 15** |
| `flip` | `horizontal`, `vertical` — applied *before* `rot` |
| `repeat` | 1–5 copies in a row, for a counting rule |
| `marker` | `true` puts a dot near one corner |

Four things worth knowing, because each is a question that silently doesn't work otherwise:

- **`rot` must be a multiple of 15.** A pupil cannot tell 20° from 25° on a 46-pixel glyph,
  so a finer angle only makes a distractor that differs from the key invisibly.
- **`marker` is what makes a rotation readable.** A square looks identical every 90° and a
  circle at every angle. Without a marker, "which option shows it after a quarter turn" has
  no answer.
- **A reflection needs an asymmetric shape.** Reflecting a mirror-symmetric shape gives the
  same picture as some rotation of it, so on a `square` or `hexagon` a "reflected"
  distractor *is* one of the rotation answers. The outlines with no mirror symmetry are
  `right_triangle`, `l_shape`, `right_trapezium` and `flag` — or make a symmetric shape
  chiral with a `half` or `quarter` fill.
- **Use `tiny` for anything counted.** A row of `small` glyphs does not fit a panel past two,
  so it gets compressed — and marks that shrink as the count rises read as a size rule as
  well as a counting one. The checker warns when a row will compress.

### Size

Every panel is the same size in every figure of every kind, and every figure on a page is
drawn at one shared scale. You do not set a size and cannot: a figure that sized itself is
how two questions in one paper ended up drawing the same square at different sizes.

A stem figure wider than **292px** — more than three panels and a blank — scrolls sideways
on a phone rather than shrinking. The checker warns you when yours will.

A full worked pack, exercising every kind and every answer arrangement, is in
`_EXAMPLE.nvr_figures.json`.

### Templates: naming an arrangement instead of hand-building it

A `figure` can be a named template instead of a hand-built `cells`/`cell`/`squares`:

```json
"figure": { "template_id": "nvr.rotating_series", "data": { "shape": "pentagon", "step": 90 } }
```

`data` here is **slot data**, not the vocabulary above — a template turns a small number of
values into the `cells`/`cell`/`squares` a `kind` needs, so you supply what changes about
*this* question rather than the whole shape of it. The importer resolves a template exactly
once, when your pack is imported; the database only ever stores the resolved `kind`/`data`,
so nothing downstream — rendering, the pupil-facing page, the preview tool — needs to know a
template was involved. A figure carries either `{"kind", "data"}` or `{"template_id", "data"}`,
never a mix of the two, and `kind` is never written alongside `template_id` — the template
already knows what `kind` it produces.

List every template and what it needs:

```bash
python3 -c "from catalog.figures.templates import TEMPLATES as T; [print(t.id, '—', t.subtopic, '—', t.summary, '| required:', sorted(t.required), '| optional:', sorted(t.optional)) for t in T.values()]"
```

| `template_id` | Subtopic | For |
|---|---|---|
| `nvr.rotating_series` | Series & Sequences | A row of one shape turning by a fixed step each panel, last one blank. |
| `nvr.size_progression` | Series & Sequences | A row of one shape stepping through named sizes, last one blank. |
| `nvr.count_progression` | Series & Sequences | A row counting up by a fixed step each panel, last one blank. |
| `nvr.rotate_reflect` | Rotation & Reflection | A single shape, shown before a rotation or reflection is applied. |
| `nvr.which_net_folds` | 3D Shapes & Nets | A guaranteed-valid 1-4-1 cube net (a strip of four, one above, one below). |
| `nvr.matching_net` | 3D Shapes & Nets | A given net, rotated or reflected — for "which net is the same net turned?" |
| `nvr.simple_analogy` | Analogies | A is to B as C is to ? — the classic four-cell analogy with one separator. |
| `nvr.corner_code` | Codes | A grid of shapes, each carrying a small mark at a named corner as its code. |
| `nvr.shape_to_symbol_grid` | Codes | A matrix crossing a row rule with a column rule, one cell blank. |
| `nvr.odd_one_out` | Odd One Out | One option: a shared base cell with one named field overridden. |
| `nvr.odd_one_out_grid` | Odd One Out | One option: a shared multi-glyph cell with one item's field overridden. |

The first six mirror the three existing NVR generators (`catalog/generators/nonverbal.py`) —
`nvr.rotating_series`/`nvr.rotate_reflect`/`nvr.which_net_folds` build a cell or net the same
way the generator does, so a rotated cell means the same thing whether a rule built it or you
did. The last five are new: **Analogies, Codes and Odd One Out have no generator and, before
this, no questions** — every arrangement they need was already drawable with the existing
`nvr_grid`/`nvr_panel` kinds, so what was missing was a name for it, not a new kind. See
`_EXAMPLE.nvr_figures.json` for one worked question per subtopic using its template.

Two things worth knowing:

- **`nvr.odd_one_out`/`nvr.odd_one_out_grid` build one OPTION at a time, not the stem** —
  Odd One Out has no stem figure, so each option repeats the same `common` cell and overrides
  the one field the rule turns on. Every other template builds the stem; a question's options
  are still plain `nvr_panel`/`nvr_net` figures, templated or not, exactly as in "Answers that
  are pictures" above.
- **A template is optional, not a requirement.** A one-off figure with no reusable shape is
  still written by hand, `{"kind": ..., "data": {...}}`, exactly as before. Reach for a
  template when the arrangement is one of the ones above; don't force a question into a
  template that doesn't fit it.

`validate_questions.py` checks a `template_id` the same way it checks everything else: an
unknown id, a missing required field, or a field the template doesn't take are each a named
ERROR, and a template producing the wrong `kind` for where it's used (a stem-shaped template
on an option, say) is caught the same way a hand-written `kind` mismatch would be.

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
- [ ] `misconception` on the distractors where you know the mistake, from the taxonomy list, never on the key.
- [ ] Difficulty spread across the batch, not all 2s.
- [ ] `number` and `ref` filled in; refs unique across every pack, not just yours.
- [ ] Any `image` file actually committed under `static/questions/`.
- [ ] Any `figure` uses only names from the vocabulary (or a known `template_id`), and no
      two options draw the same picture. Looked at it —
      `python3 elevenplus_data/preview_questions.py <pack>`.
- [ ] Ran `python3 elevenplus_data/rebalance_keys.py <pack>` before validating.
- [ ] `python3 elevenplus_data/validate_questions.py elevenplus_data/*.json` exits 0.
