---
description: Guided session to author UCAT questions and open a PR
argument-hint: "[section code] [count]  e.g. QR 15"
---

You are running a **question-authoring session** for the Med-revisor question bank. Your job
is to help the contributor produce a batch of high-quality UCAT questions, prove they conform
to the import contract, and get them committed to their branch and ready to merge — **without
ever merging to `main` yourself**.

Requested this session (may be empty — ask if so): **$ARGUMENTS**
(first token = section code `VR`/`DM`/`QR`/`SJT`, second = how many questions, target 10–20.)

Work through these steps in order. Do not skip the branch step or the validation gate.

---

## Step 0 — Get onto a fresh branch (do this first, every time)

1. Run `git status --short`. If there are **unrelated** uncommitted changes, mention them and
   ask whether to continue before doing anything — you don't want to sweep someone else's edits
   into this batch.
2. Run `git branch --show-current`:
   - **Already on a working branch** (anything except `main`/`master`) → good, go to Step 1.
   - **On `main`/`master`** → create the branch for them; don't make them run git by hand:
     1. Work out the **section** and **their handle** — from `$ARGUMENTS` if given, otherwise
        ask once (e.g. "Which section, and what handle should I use for you?").
     2. If the tree is clean, refresh first: `git pull --ff-only` (if it errors, e.g. offline,
        carry on anyway).
     3. Create and switch to the branch:
        ```
        git checkout -b questions/<handle>-<section>-<nn>
        ```
        Use `<nn>` = `01`, or the next free number if that branch name is taken.
     4. Confirm you're now on the new branch before continuing.

(In the fork-based setup, `origin` is the contributor's own fork — that's expected and correct.
You are never on, and never push to, the upstream `main`.)

## Step 1 — Load the format rules

Read `pmt_data/CLAUDE.md` in full if it isn't already in context. It is the authoritative
contract: canonical subtopics, required fields, the one-correct-option rule, the `source`
collision rule, and the difficulty rubric. Everything you generate must obey it.

## Step 2 — Settle the batch details

You likely already have the **section** and **handle** from Step 0. Confirm the rest (use
`$ARGUMENTS` where given, otherwise ask concisely):
- **Section**: one of VR, DM, QR, SJT. One section per file — never mix. (Already chosen above.)
- **Count**: aim for 10–20 this session.
- **Their handle**: used for the `source` and filename, e.g. `alex`. (Already chosen above.)

Then decide the file:
- Contributor file naming: `pmt_data/contrib_<handle>_<section>_<nn>.json`
  (e.g. `pmt_data/contrib_alex_qr_01.json`). **The `contrib_` prefix is required** — the
  deploy auto-discovers packs by that prefix, so a file named anything else will merge but
  never go live.
- `source`: `CONTRIB-<HANDLE>-<NN>` (e.g. `CONTRIB-ALEX-01`) — unique to this batch, never a
  reserved name (`PMT`, `PMT-M1`, `PMT-M2`, `seed`) and never another contributor's.
- If **their file for this section already exists on the branch**, open it and **append** new
  questions to it (keep the same `source`). If not, copy `pmt_data/_TEMPLATE.question_pack.json`
  as the starting point and set the header: correct `code`/`name`, the unique `source`, and
  `"is_placeholder": false` (these are the team's own questions → owned IP).

## Step 3 — Author the questions

Generate the questions in small batches (about 5 at a time), and after each batch **self-review
every question** against this checklist before moving on:

- [ ] `subtopic` is an exact canonical name for this section (character-for-character).
- [ ] Exactly **one** option has `"correct": true`, and it is genuinely, defensibly correct.
- [ ] Distractors are plausible and wrong for a real reason — not filler.
- [ ] `difficulty` is set honestly: 1 easy · 2 standard · 3 hard.
- [ ] `stem` is self-contained; if it needs a passage/figure, `passage` (or `image`) is present.
- [ ] `kind` matches (`tf` only for True/False/Can't-tell style; otherwise `mcq`).
- [ ] `number` and `ref` are filled in; every `ref` is unique within the file.
- [ ] Not a near-duplicate of another question in the file.
- [ ] Written in real UCAT style for this section — not a generic trivia question.

Keep `ref` codes consistent, e.g. `<HANDLE>-<SECTION>-0001`, incrementing.

## Step 4 — Validate (the gate — do not skip)

Run:
```
python3 pmt_data/validate_questions.py pmt_data/contrib_<handle>_<section>_<nn>.json
```
- **Exit 0** → good, continue.
- **Non-zero** → read the errors, fix the file, and run it again. **Do not commit until it
  exits 0.** Never edit the validator to make a pack pass.

Show the contributor the validator output and a short summary: how many questions, the section,
the subtopics covered, and the difficulty spread.

## Step 5 — Commit to the branch

Once validation passes and the contributor is happy, stage and commit **only** the question
file (and only files this session created/changed):
```
git add pmt_data/contrib_<handle>_<section>_<nn>.json
git commit -m "Add <N> <section> questions (CONTRIB-<HANDLE>-<NN>)"
```
Then push the branch:
```
git push -u origin <branch-name>
```
(The contributor may be prompted to authenticate / approve — that's expected.)

## Step 6 — Hand off for review (do NOT merge)

You stop here. Merging to `main` is the maintainer's decision after checks pass.

Give the contributor:
1. The **PR link**. When you pushed in Step 5, `git push` printed a
   "Create a pull request … by visiting: <URL>" line — hand them **that** URL. It is correct
   whether they cloned the upstream repo or their own fork, so don't hand-build a compare URL.
   If it didn't appear, tell them to open their fork on github.com and click
   **"Compare & pull request"** (the PR targets `NidsC/med-revisor` `main`).
2. A one-line **summary for the PR description**: section, number of questions, subtopics
   covered, difficulty spread, and the `source` used.

Then remind them: CI runs the validator automatically on the PR, and the maintainer reviews the
content and merges. Because the pack is named `contrib_*.json`, the deploy picks it up
automatically — no build script changes needed. On the next Render deploy the questions go live.

---

**Hard rules for this session**
- One section per file. Unique `source`. `is_placeholder: false`.
- The filename MUST start with `contrib_` — that prefix is how the deploy auto-discovers it.
- Never touch the existing built-in packs (`decision_making.json`, the `mock*` files, etc.).
- Never edit `build.sh` — contributor packs deploy automatically by their `contrib_` prefix.
- Never merge to `main`. Never edit the validator to force a pass.
- Do not commit anything that fails `validate_questions.py`.
