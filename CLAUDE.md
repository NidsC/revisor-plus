# RevisorPlus

A Django app for 11+ practice: a bank of questions across four papers (English, Maths,
Verbal Reasoning, Non-Verbal Reasoning), the practice and mock-paper flows pupils work
through, and the analytics that turn their attempts into a weakness report.

---

## Working notes — read these at the start of a session

Two files and three folders carry state between sessions. **All five are gitignored**, so
they exist only in this checkout and will not arrive with a fresh clone. Read whichever is
relevant before starting work, and write to them as instructed inside each one.

| File or folder | Holds |
|------|-------|
| `pending_issues.md` | Known problems that are **not fixed**: bugs found in passing, deferred decisions, constraints that will bite later. Check here before reporting a problem — it may already be recorded, and half the value is not rediscovering the same thing every few weeks. |
| `plans.md` | Plans that were designed, written up as an artifact, and **not finished**. Each entry links the artifact and says what is built versus what is still only written down. Check here before planning new work — you may be picking up a thread rather than starting one. |
| `.claude/audits/` | The `/audit` and `/full-audit` skills' reports and state: dated audit logs, the consolidated report, `learning-log.md`. Written by the audit skills and read by the next audit. Gitignored; a fresh clone starts with none. |
| `.claude/plans/` | The `/plan-it` skill's state: plan logs and `learning-log.md`. Written by the planning skill. Gitignored; a fresh clone starts with none. |
| `docs/plans/` | Live plan artifacts written by `/plan-it`. A plan is retired into `plans.md` once it is built. Gitignored; a fresh clone starts with none. |

Both files contain their own instructions for adding, cross-referencing and closing
entries. Follow them rather than inventing a format: they exist so that one problem does
not end up recorded three slightly different ways.

If any of these is missing, this checkout simply has not got it yet. Say so rather than
recreating it from scratch.

**Files in this folder that are not RevisorPlus:** `Outreach_Research_and_Evaluation_Criteria.md`
and the `Carshalton and Sutton*.xlsx` spreadsheet are business documents kept here for
convenience and gitignored. Agents may read them for business context, but no development
task touches them.

---

## Where the rules live

- **`elevenplus_data/CLAUDE.md`** — the question-pack authoring contract: the taxonomy,
  the required fields, the seven answer kinds, the `source` rule that decides whose
  questions get deleted on import. Authoritative for anything touching a `*.json` pack.
  It loads automatically when working in that folder.
- **`.claude/commands/questions.md`** — the guided authoring session (`/questions`).

## Ground rules

- `elevenplus_data/taxonomy.json` is the single source of truth for sections, subtopics
  and question types. It is read by the validator, `sync_taxonomy` (writes it to the
  database), `import_pack` (section names, subtopic aliases), `generate_bank` (question-type
  and misconception vocabulary), `preview_questions.py`, `taxonomy_lookup.py`, the three
  `elevenplus_data/check_*.py` scripts, `diversity_audit.py` and the root `test_*.py`
  scripts that build fixtures from it; `elevenplus_data/CLAUDE.md`'s tables are generated
  from it. Change its shape and every one of those must still load it. Edit the file, not
  the copies.
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
