# Known issues

Problems that are understood and **not fixed**. One heading per issue. Facts only —
what happens, where, and what the options are. Decisions go in the PR that makes them.

This file is tracked. It is not `pending_issues.md`, which is gitignored, carries
session-to-session working notes, and is absent from this checkout.

---

## `import_pack` deletes questions, and the delete cascades into pupils' attempts

**Status:** open. No fix attempted.
**Found:** while building the dashboard bands (branch `dashboard-redesign`, 2026-09-09).

### What happens

`import_pack` is idempotent per source, and it achieves that by deleting first:

- `catalog/management/commands/import_pack.py:301-303` — every `Question` matching
  `(source, subtopic__section)` is deleted, then the pack's questions are written back
  as new rows with new primary keys.
- `practice/models.py:36` — `Attempt.question` is
  `models.ForeignKey("catalog.Question", on_delete=models.CASCADE)`.

So every `Attempt` against a question in that `(section, source)` is deleted with it.
The new rows are not the old rows: they have different ids, and nothing reattaches the
history to them.

`build.sh:90-97` runs `import_pack` over every `elevenplus_data/contrib_*.json` on every
deploy. The path is therefore taken on each deploy, for each pack, whether or not the
pack's content changed.

This is the **successful** path, not a failure path. `import_pack.handle` is
`@transaction.atomic` (`import_pack.py:265`), so a *failed* import leaves the bank
untouched; `test_import_safety.py` covers that case. A successful import destroys the
attempts by design and no test covers it.

### What it destroys

Everything downstream of `Attempt`, because `Attempt` is the analytics spine:

- `analytics/services.py` — `compute_progress` (overall accuracy, per-subtopic and
  per-section accuracy, the weakness list, the trend chart), `compute_subject_summary`
  (completion, `weekly_avg`, and the dashboard `band`), `compute_coverage`.
- `analytics/readiness.py` — `hours_done`, `recent_hours_per_week` and therefore
  `required_hours_per_week`, `readiness_pct`, `section_gaps`, `projected_overall`,
  `coverage`, and the headline status.
- `assignments` progress counts, which read attempts to decide whether homework is done.

For the dashboard bands specifically: a band needs 20 attempts in the last 30 days
(`BAND_MIN_ATTEMPTS`, `BAND_WINDOW_DAYS` in `analytics/services.py`), so a deploy that
re-imports a pack drops the affected subject rows to no band until the pupil rebuilds
20 attempts.

### Measured

On a scratch database, 2026-09-09, re-importing `elevenplus_data/_EXAMPLE.nvr_figures.json`
unchanged, with 5 attempts recorded against its 5 questions:

    attempts before:        5
    question ids before:    [4260, 4261, 4262, 4263, 4264]
    attempts after:         0
    question ids after:     [8871, 8872, 8873, 8874, 8875]

The command's own output for that run was:

    NVR: removed 5 old EXAMPLE-NVR-FIGURES question(s) (30 rows in total,
    including cascaded options and passage containers), imported 5.

The pack has 5 questions and 20 answer options. The remaining 5 of the 30 rows are the
deleted attempts: they are inside the reported total, but the sentence names only
options and passage containers, so the log does not say that pupil history was removed.

### Related, and already handled differently

- `import_paper` takes `--skip-if-present` (`catalog/management/commands/import_paper.py:118,140-145`),
  which build.sh passes, explicitly to avoid this cascade for papers.
- `generate_bank` avoids it a third way: questions carry
  `Question.gen_key` (`catalog/models.py:178`), a `sha1(generator|template|params)`;
  `generate_bank.py:315` `update_or_create`s on it so re-running keeps the same row ids,
  and `generate_bank.py:133-141` deactivates rather than deletes anything stale that has
  attempts against it.
- `main.py sync_taxonomy` never deletes a `Subtopic`, for the same cascade reason
  (`CLAUDE.md`, Ground rules).

`import_pack` is the remaining importer that deletes rows a pupil may have answered.

### Two candidate fixes

**1. Soft-delete.** Do not delete the old questions; deactivate them. Set `active=False`
on rows matching `(source, section)` that have attempts, delete only those with none,
and write the pack's questions as new rows. `generate_bank.py:133-141` is the existing
implementation of exactly this split.

- The `Attempt` rows survive with their `question_id` intact.
- The bank grows: superseded rows stay in the table. They are excluded from practice by
  `active=True` in `answerable()` (`practice/views.py:44-46`) and from every bank count.
- A question edited in a pack becomes two rows, one deactivated. History points at the
  old wording, which is what the pupil actually answered.
- `Question.source` alone no longer identifies the live set for a section; callers that
  filter on source and expect only current questions would need `active=True` too.

**2. Match on a stable key instead of delete-and-reload.** Give pack questions the
identity `generate_bank` questions already have, and `update_or_create` on it rather than
deleting first.

- There is no such column today. `Question` has `gen_key`, documented and used for
  generated questions only; the pack format's per-question `ref`
  (`elevenplus_data/CLAUDE.md:115`) is optional, is not stored on `Question`, and is not
  read by the importer. Either the key is derived (a hash of stem plus subtopic plus
  source, as `gen_key` is derived) or `ref` becomes required and gets a column.
- Row ids are preserved across imports, so attempts stay attached and no rows accumulate.
- Questions dropped from a pack still need a rule: deleting them re-opens the cascade for
  those rows, so this fix does not remove the need for the retire-if-attempted branch.
- If the key is derived from the stem, editing a typo in a question changes its key and
  the row is treated as a different question — the attempts against the old one are then
  in the same position as they are today.
- Requires a migration and a change to the authoring contract in
  `elevenplus_data/CLAUDE.md`, whose `source` rule (lines 13-26) currently describes the
  delete as the defined behaviour.
