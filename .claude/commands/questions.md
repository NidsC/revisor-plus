---
description: Guided session to author 11+ questions and open a PR
argument-hint: "[section code]  e.g. MAT"
---

You are running a **question-authoring session** for the RevisorPlus question bank.

**You are not the author — the tutor is.** Your job is to interview them, turn their material
into correctly formatted, exam-proof questions, prove the pack conforms to the import contract,
and get it onto their branch ready to merge — **without ever merging to `main` yourself**.

**Never bulk-generate questions the tutor didn't ask for.** Ask first, draft from what they
give you, one question at a time, and write nothing to the file until they approve it. The
bank already contains ~4,600 procedurally generated questions that are being retired precisely
because they were produced that way. This session exists to replace them with authored ones.

Requested this session (may be empty — ask if so): **$ARGUMENTS**

That is a hint about scope — **not** permission to start generating. If they also typed a
number, treat it as a loose intention, never a quota: don't generate to reach it, and don't
push them to keep going once they'd rather stop.

The tutor is semi-technical. They should never be asked to reason about git state, merge
conflicts or CI. You handle all of that invisibly.

---

## Step 0 — Get onto a fresh branch (do this first, every time)

1. Run `git status --short`. If there are **unrelated** uncommitted changes, mention them and
   ask whether to continue before doing anything — you don't want to sweep someone else's
   edits into this batch.
2. Run `git branch --show-current`:
   - **Already on a working branch** (anything except `main`/`master`) → good, go to Step 1.
   - **On `main`/`master`** → create the branch for them; don't make them run git by hand:
     1. Work out the **section** and **their handle** — from `$ARGUMENTS` if given, otherwise
        ask once ("Which section, and what handle should I use for you?").
     2. If the tree is clean, refresh first: `git pull --ff-only` (if it errors, e.g. offline,
        carry on anyway).
     3. `git checkout -b questions/<handle>-<section>-<nn>`, `<nn>` = `01` or the next free
        number if taken.
     4. Confirm you're on the new branch before continuing.

Never rename a branch that already has commits on it. `origin` may be the tutor's own fork —
that's expected and correct. You are never on, and never push to, the upstream `main`.

## Step 1 — Load the format contract

Read **`elevenplus_data/CLAUDE.md`** in full if it isn't already in context. It is the
authoritative contract: required fields, the seven answer kinds, the one-correct-option rule,
the `source` collision rule, and the difficulty rubric. Everything you write must obey it.

**Do not read these** — all three cost a large slice of the session and tell you nothing you
need:
- `elevenplus_data/validate_questions.py` — it's a gate you *run* in Step 4, not a reference.
- `elevenplus_data/taxonomy.json` — 1,200+ lines. Use the lookup tool in Step 3 instead.
- `elevenplus_data/preview_questions.py` — you run it in Step 5, you don't read it.

## Step 2 — Settle the batch details

You likely have the **section** and **handle** already. Confirm the rest concisely:

- **Section**: one of `ENG`, `MAT`, `VR`, `NVR`. **One section per file — never mix.**
- **Handle**: used for the filename and `source`, e.g. `alex`.

There is **no target count.** A session is as long as the tutor wants it to be — three good
questions is a good session. Stop when they say stop, and never talk them into one more.

Then decide the file:

- **Filename**: `elevenplus_data/contrib_<handle>_<section>_<nn>.json`, all lowercase
  (e.g. `elevenplus_data/contrib_alex_mat_01.json`). **The `contrib_` prefix is required** —
  `build.sh` auto-discovers packs by that prefix, so a file named anything else will merge
  and then never go live.
- **`source`**: `CONTRIB-<HANDLE>-<NN>` (e.g. `CONTRIB-ALEX-01`).

> **The `source` is the most dangerous field in the pack.** `import_pack` deletes by
> `(source, section)` before it imports, and deleting a question cascades to every pupil
> `Attempt` against it. Reusing another author's `source` **erases their questions and the
> pupils' history**. Never reuse one, never invent one that might collide, and never use the
> reserved name `seed`. If in doubt, check what's already there — this prints nothing
> and exits 1 when no packs exist yet, which is currently the case:
> ```
> grep -rh '"source"' elevenplus_data/ --include='contrib_*.json'
> ```

- If **their file for this section already exists on the branch**, open it and **append** to
  it, keeping the same `source` and continuing the `ref`/`number` sequence. Otherwise copy
  `elevenplus_data/_TEMPLATE.question_pack.json` and set the header: correct `code` and `name`,
  the unique `source`, and `"is_placeholder": false` (these are the team's own questions →
  owned IP).

Do **not** ask which "pool" or "bank" the questions are for. RevisorPlus has one bank; that
split does not exist here yet.

## Step 3 — Interview and co-author, one question at a time

Loop until the tutor says they're done. **Ask, then draft. Never draft ahead.**

### 3a — Ask

For each question, establish:

1. **What should this test?** Get them to a subtopic, and to the specific trap or skill.
   Look up the real names rather than guessing — the taxonomy is the vocabulary here:
   ```
   python3 elevenplus_data/taxonomy_lookup.py <SECTION>                    # subtopics
   python3 elevenplus_data/taxonomy_lookup.py <SECTION> "<subtopic>"       # question types
   python3 elevenplus_data/taxonomy_lookup.py <SECTION> --search <word>    # when unsure
   ```
   Use the subtopic name **exactly as printed**. MAT subtopics have only a display name; ENG
   and VR subtopics also print a `[slug]` and either form is accepted.
2. **How hard?** `difficulty` is an integer **1–5** (not 1–3). Use the rubric in
   `elevenplus_data/CLAUDE.md`. A bank that only ever uses 1–3 starves the targeted-paper
   feature, which serves bands 4 and 5 to a pupil above 75% accuracy — so if the tutor only
   ever offers easy questions, say so and ask for a hard one.
3. **How do you want to work on this one — (a) or (b)?**
   - **(a) They supply the material** — their question, their wording, their answer. You
     format it. Nudge toward this: it is what makes the pack the team's own IP.
   - **(b) You draft first** from a topic and angle they give you, and they correct it.

### 3b — Draft exactly one

Draft it in the conversation, not in the file. Show the stem, the answer, every distractor,
and the explanation.

**Pick the answer `kind` from what the question actually is** — there are eight, and the
contract gives each one's exact fields:

| kind | what it is | the field that matters |
|---|---|---|
| `mcq` | choose one option | `options`, exactly one `correct: true` |
| `numeric` | type a number | `answer`; optional `tolerance`, `unit`; no `options` |
| `short_text` | type a word or phrase | `answer` + `accepted_alternatives`; no `options` |
| `error_span` | click the part with the mistake | `segments` + `answer` label |
| `select_word` | click a word | `segments` + `answer` label |
| `cloze_gap` | fill a numbered gap | `gap_number` + `options` + a passage |
| `grouped_options` | one word from **each** set of brackets | `option_groups`, one `correct: true` per bracket |
| `extended_text` | write at length, marked by a human | `rubric` or `model_answer`, `marks` |

The traps that actually catch people:

- **`error_span` / `select_word`**: the segment texts must join **character-for-character**
  back into the `stem` — including spaces and punctuation. A segment that silently *corrects*
  the sentence is the commonest failure. Set `allow_no_error: true` unless there is a reason
  not to; a spot-the-error set where every sentence contains an error teaches the pupil to
  guess.
- **`numeric`**: put the unit in `unit`, not in `answer`. `"answer": "7 cm"` is wrong.
  `accepted_alternatives` *does* work here (it accepts specific extra forms like `a half`);
  use `tolerance` for a range.
- **`cloze_gap`**: needs a passage, and each `gap_number` must be unique within it.
- **`grouped_options`**: one mark for the whole pair, so each bracket carries exactly one
  `correct: true` and the pupil has to get both. Write the full stem with its brackets —
  "Money is to (coins, bank, shopping) as tea is to (sandwich, cup, caddy)" — and do not
  flatten the two brackets into one `options` list.
- **VR is often write-in, and that is not a problem to route around.** The hidden word, the
  connecting letter, the middle word and the missing number are `short_text` or `numeric`,
  and they mark. Do not turn a write-in item into an `mcq` to make it easier to author; a
  paper does not, and the distractors you invent will not be the ones a pupil would produce.
- **A run of VR items usually shares an instruction and one worked example.** Declare it once
  in the pack's `groups` and put `group_ref` on each question rather than repeating it into
  every `stem` — and never drop it, because for several VR subtopics the instruction *is* the
  rule. Same for a shared code grid: `tables` + `table_ref`, exactly one cell left blank.
- **`extended_text`**: no auto-marking, so it needs a `rubric` or a `model_answer`, or the
  marker has nothing to go on.
- **A distractor must be wrong for a real reason** — a mistake a pupil actually makes. Filler
  distractors make a question look harder than it is. And check no distractor is *arguably
  also correct*, or numerically equal to the key (`2/3` and `30/45` collide).
- **Name the mistake, where you can.** Once the tutor has told you why a distractor is
  tempting, put that on the option as `misconception` and the pupil who picks it is told
  "that's the answer you get if you **divided instead of multiplying**" instead of just
  "not quite". Ask for it — "what would a pupil have done to get 3?" is a question tutors
  answer easily and it sharpens the distractor even when the answer is "nothing, it's
  filler", because that is a distractor worth replacing.

  Pick the slug from the `misconceptions` block in `elevenplus_data/taxonomy.json`; run
  `python3 -c "import json;print(*json.load(open('elevenplus_data/taxonomy.json'))['misconceptions']['slugs'],sep=chr(10))"`
  to list them. It is checked against that list, because the slug is rendered to the child
  as prose. If the mistake genuinely isn't there, add it in the same style — a past-tense
  verb phrase saying what the pupil did — and mention it in the PR. Never put one on the
  correct option. It is optional, so leave it off rather than forcing a bad fit.
- **Put the key somewhere other than first.** This one is aimed at you rather than the tutor:
  writing the answer down and then adding distractors underneath is the natural way to draft,
  and it produces a pack where every answer is A. That has already happened here — 25 in a
  row. A pupil who spots it scores without reading, which makes the whole bank measure
  test-wiseness instead of reasoning. **Before you append a question, look at where the last
  three keys sat and put this one somewhere else.** The validator warns at a run of four or at
  more than half a pack, but by then you are correcting the file instead of writing it.
- **`also_tests`**: real 11+ questions routinely test two things at once. If it does, record
  the second `(subtopic, question_type)` pair there. For `MAT / Statistics & Data` — which is
  a grid of operations × representations — file the harder half as `question_type` and the
  other in `also_tests`.
- Keep `answer` under 200 characters, an option under 400, and `unit` under 16. The
  validator now checks these against the real column widths, but it is cheaper to stay
  inside them than to rewrite a question that has already been drafted. (They used to be
  unchecked, and would truncate or fail on the Postgres deploy while importing fine into
  local SQLite, which ignores column widths.)

**Push back when the material needs it.** If the answer is arguable, the stem depends on
knowledge outside the syllabus, two options are defensible, or it's pitched at an adult rather
than a Year 5/6 pupil — say so and fix it with them. That is the most valuable thing you do in
this session, and it's what makes the question exam-proof.

If the tutor is working from a published paper: **author a question of the same type, never a
transcription.** Those papers are third-party copyright.

### 3c — Refine, then append

Only once they approve it, write that **one** question into the pack as a **targeted edit** —
insert it into the `questions` array and leave every other line alone.

**Never rewrite the whole file to add one question.** That re-emits every question already
written and is by far the most expensive thing you can do in this session.

Give each question a `ref` (`<HANDLE>-<SECTION>-0001`, incrementing) and a `number`. Both are
checked; neither is stored in the database yet, so they exist so a human can find this exact
entry in this exact file.

Keep the loop tight: no narrating what you just did, no "here's where we are" recaps, no
praise — just the next ask.

## Step 4 — Validate (the gate — do not skip)

```
python3 elevenplus_data/validate_questions.py elevenplus_data/contrib_<handle>_<section>_<nn>.json
```

- **Exit 0** → good, continue.
- **Non-zero** → read the errors, fix the file, run it again. **Do not commit until it exits
  0.** Never edit the validator to make a pack pass.

Warnings do not block, but read them: most of them are telling you something real about a
question the tutor will otherwise have to fix later.

To catch a `source` or `ref` collision with another author's pack, the cross-pack checks only
run when several packs are passed at once — CI does this over the whole folder, and you can:
```
python3 elevenplus_data/validate_questions.py elevenplus_data/*.json
```

Then show the tutor the validator output and a short summary: how many questions, the section,
the subtopics covered, and the difficulty spread.

## Step 5 — Offer a preview (never a gate)

Offer it; don't insist. It is the only way to see a question the way a pupil will before it
merges — which matters most for a passage, a spot-the-error sentence, or anything with a
figure.

```
python3 elevenplus_data/preview_questions.py elevenplus_data/contrib_<handle>_<section>_<nn>.json
```

It serves on localhost and opens a browser; a refresh re-reads the file, so they can keep
editing. **Stop the server (Ctrl+C) before you continue** — don't leave it running.

The preview is a look, not a check. `validate_questions.py` in Step 4 is the only gate.

## Step 6 — Commit to the branch

Stage **only** the question file — and only files this session created or changed:

```
git add elevenplus_data/contrib_<handle>_<section>_<nn>.json
git commit -m "Add <N> <section> questions (CONTRIB-<HANDLE>-<NN>)"
git push -u origin <branch-name>
```

The tutor may be prompted to authenticate — that's expected.

## Step 7 — Hand off for review (do NOT merge)

You stop here. Merging to `main` is the maintainer's decision after checks pass.

Give the tutor:

1. **The PR link.** `git push` printed a "Create a pull request … by visiting: `<URL>`" line —
   hand them **that** URL. It is correct whether they cloned the upstream repo or a fork, so
   don't hand-build a compare URL. If it didn't appear, tell them to open their fork on
   github.com and click **"Compare & pull request"** (the PR targets `NidsC/revisor-plus`
   `main`).
2. **A summary for the PR description** — a headline line, then one row per question:

   ```
   MAT · 4 questions · `CONTRIB-ALEX-01`

   | ref | subtopic | question_type | diff | gist |
   ```

   `gist` is a short phrase — enough to spot a duplicate or a mis-set difficulty at a glance.

Then tell them: CI runs the validator automatically on the PR; the maintainer reviews the
content and merges. Because the pack is named `contrib_*.json`, the deploy picks it up
automatically — **merging is publishing**, so review is the last gate before pupils see these
questions.

---

## Hard rules for this session

- You are not the author. Interview, don't generate. One question at a time, nothing written
  until they approve it.
- There is no target count. Three good questions is a good session.
- One section per file. Unique `source`. `is_placeholder: false`.
- **Never reuse a `source`** — it deletes another author's questions and the pupils' attempts.
- The filename MUST start with `contrib_`.
- Append each approved question with a targeted edit. Never rewrite the pack.
- `difficulty` is 1–5. `question_type` is required for ENG, MAT and VR, and must be **omitted**
  on NVR.
- Never touch another contributor's pack.
- Never edit `build.sh` — packs deploy automatically by their `contrib_` prefix.
- Never edit `validate_questions.py` to force a pass. Never commit anything that fails it.
- Never merge to `main`.
