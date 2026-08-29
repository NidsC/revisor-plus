# RevisorPlus

A Django app for 11+ practice: a bank of questions across four papers (English, Maths,
Verbal Reasoning, Non-Verbal Reasoning), the practice and mock-paper flows pupils work
through, and the analytics that turn their attempts into a weakness report.

---

## Working notes — read these at the start of a session

Two files at the repo root carry state between sessions. **They are gitignored**, so they
exist only in this checkout and will not arrive with a fresh clone. Read whichever is
relevant before starting work, and write to them as instructed inside each file.

| File | Holds |
|------|-------|
| `pending_issues.md` | Known problems that are **not fixed**: bugs found in passing, deferred decisions, constraints that will bite later. Check here before reporting a problem — it may already be recorded, and half the value is not rediscovering the same thing every few weeks. |
| `plans.md` | Plans that were designed, written up as an artifact, and **not finished**. Each entry links the artifact and says what is built versus what is still only written down. Check here before planning new work — you may be picking up a thread rather than starting one. |

Both files contain their own instructions for adding, cross-referencing and closing
entries. Follow them rather than inventing a format: they exist so that one problem does
not end up recorded three slightly different ways.

If either file is missing, this checkout simply has not got them yet. Say so rather than
recreating them from scratch.

---

## Where the rules live

- **`elevenplus_data/CLAUDE.md`** — the question-pack authoring contract: the taxonomy,
  the required fields, the seven answer kinds, the `source` rule that decides whose
  questions get deleted on import. Authoritative for anything touching a `*.json` pack.
  It loads automatically when working in that folder.
- **`.claude/commands/questions.md`** — the guided authoring session (`/questions`).

## Ground rules

- `elevenplus_data/taxonomy.json` is the single source of truth for sections, subtopics
  and question types. The validator enforces it, `main.py sync_taxonomy` writes it to the
  database, and `elevenplus_data/CLAUDE.md`'s tables are generated from it. Edit the file,
  not the copies.
- `main.py sync_taxonomy` never deletes. Dropping a `Subtopic` cascades into every
  `Attempt` against it and would destroy pupils' history.
- Never edit `validate_questions.py` to make a pack pass. If a pack is genuinely a shape
  the contract should allow, change the contract deliberately and say so.
- `build.sh` auto-imports `contrib_*.json` and `*-paper-*.json` from `elevenplus_data/`.
  Anything else in that folder does not deploy — which is why example and fixture packs are
  named with a leading underscore.
- **A stacked PR must be opened with an explicit `--base`, and merged only once its base
  reads `main`.** `gh pr create` with no `--base` targets the branch the head was cut from,
  which for a stacked PR is its parent — so merging it puts the work on the parent branch,
  not on `main`, and the parent then has to be merged too or the work is stranded. This has
  happened twice: PR #5 needed commit `ef7ebab` to undo it, and PR #11 was found stranded on
  `worktree-vr-shapes-and-answer-key` on 2026-08-26, a week after it merged. Neither failed
  loudly. `git merge-base --is-ancestor <commit> origin/main` is how you check, and it is
  worth checking after merging anything stacked.
