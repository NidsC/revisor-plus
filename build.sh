#!/usr/bin/env bash
# Render build script for RevisorPlus.
set -o errexit

pip install -r requirements.txt

# Which database is this deploy actually talking to? Printed first, before any
# work, because getting this wrong is silent. config/settings.py reads
# DATABASE_URL and nothing else; if it is unset — or an environment group
# supplies the connection string under some other key — Django falls back to
# SQLite on the instance disk without raising anything. The deploy goes green,
# the site serves the full question bank, and every account and attempt is
# discarded on the next deploy or 15-minute idle spin-down. Free instances have
# no shell, so this log line is the only place that fact is observable.
# Reads settings only; it opens no connection and cannot fail the build on a
# database that is merely unreachable.
python main.py shell -c "from django.db import connection as c; print('DATABASE:', c.vendor, '|', c.settings_dict['ENGINE'], '| name=', c.settings_dict['NAME'], '| host=', c.settings_dict.get('HOST') or 'local-file')"

python main.py collectstatic --no-input
python main.py migrate
# The taxonomy, from elevenplus_data/taxonomy.json into the database. THIS MUST RUN
# BEFORE anything that files questions — seed_demo, generate_bank, import_pack,
# import_paper — and the reason is not tidiness.
#
# All four of those importers reach a subtopic by get_or_create on its NAME. If the
# subtopic does not exist yet they create it, with order 0 and no topic. So whichever
# of them runs first silently defines the taxonomy, and two spellings of the same
# area become two subtopics: a pack using the canonical "Algebra & Sequences" lands
# beside a generator-made "Algebra", holding half the content each. Nothing errors.
# Practice decks, the topic grouping and the weakness profile then treat the two as
# unrelated areas, and a pupil weak in algebra can be shown strong in one of them.
#
# Running sync_taxonomy first means every name in taxonomy.json already exists, with
# its real order and topic, so those get_or_creates find a row instead of inventing
# one. Move this line below any of them and the split comes straight back — silently,
# which is what makes it worth a paragraph.
#
# It never deletes: a subtopic in the database but not in the JSON is reported and
# left alone, because deleting one cascades into pupils' Attempts.
python main.py sync_taxonomy
python main.py seed_demo
# Procedural bank. Idempotent for a given seed: questions are matched on gen_key
# and update_or_create'd, so re-running keeps the same row ids and never cascades
# a delete into pupils' Attempts. Keep the seed fixed across deploys.
#
# --per-module, not per generator. Maths has 14 generators and English 8, and
# their parameter spaces differ by orders of magnitude, so a per-generator target
# produced 8,397 Maths questions against 163 English ones. Filling each module to
# the same target keeps the four papers comparable.
# 1150 is roughly the balanced ceiling: Non-Verbal Reasoning has only three
# generators and tops out near 1,146, so a higher target only unbalances it again.
#
# --inactive: the ~4,600 generated questions have not been audited against real
# papers the way the authored packs have, and are held back from practice, mocks
# and the landing count until that audit happens. This flag is applied on every
# deploy, not a one-off DB edit — without it, this same command running on the
# next deploy would silently flip every row back to active=True, because it
# always writes an explicit "active" value. Nothing is deleted and no pupil
# Attempt is touched; remove this flag once the bank has been audited.
python main.py generate_bank --per-module 1150 --seed 11 --inactive
# Question packs, auto-discovered by the "contrib_" prefix so a new pack deploys on
# merge without editing this script.
# nullglob => if there are no packs yet, the loop simply runs zero times.
#
# A failing pack is REPORTED AND SKIPPED, not fatal. That is a change from the
# original shape, and the reasoning is worth keeping because the two are easy to
# swap back by accident:
#
#   * It is now safe. `import_pack.handle` is @transaction.atomic, so a failed
#     import leaves the bank exactly as it was — it cannot delete a pack's old
#     questions and then fail before rewriting them, and it cannot cascade into
#     pupils' Attempts. test_import_safety.py is the check that keeps that true.
#     Before that decorator existed, aborting was the lesser of two bad outcomes:
#     the build stopped, but the bank was already half-written.
#   * The protection moved EARLIER rather than away. CI's `pipeline` job now runs
#     import_pack over every contrib_*.json on the PR, so a pack that cannot
#     import fails a required check and never merges. Deploy time was always the
#     wrong place to catch this — no operator is watching, and the alternative to
#     shipping was shipping nothing at all.
#   * Aborting costs availability for an unrelated reason. One malformed pack
#     took down every other change in the same deploy, including fixes.
#
# What skipping gives up is VISIBILITY: the deploy goes green while the bank is
# missing content someone believes shipped. Render's free instances have no
# shell, so this log is the only place that is observable — hence the summary at
# the end of this script, which names every skipped file as the last thing in the
# build output. If you are reading a deploy log, that block is where to look.
skipped_imports=()
shopt -s nullglob
for pack in elevenplus_data/contrib_*.json; do
  echo "Importing question pack: $pack"
  python main.py import_pack "$pack" || {
    echo "  SKIPPED $pack — see the error above. The bank is unchanged for this"
    echo "          pack (the import is atomic); nothing was half-written."
    skipped_imports+=("$pack")
  }
done
# Exam papers use a different format and importer — timed, marked out of a total,
# free-entry answers, multi-part questions. Discovered by the "*-paper-*" name.
# A paper that declares a passage but ships no passage text makes import_paper
# exit non-zero, which under `set -o errexit` would fail the whole build, so
# failures here are reported and skipped. The two starter papers are not
# blockers. (This loop is where that pattern started; the pack loop above now
# matches it, for the reasons set out there.)
# --skip-if-present matters: re-importing replaces a paper's questions, and
# deleting a question cascades to every Attempt against it. Without the flag,
# every deploy would silently wipe pupils' history for these papers. Re-import
# deliberately (and knowingly) when a paper's content actually changes.
for paper in elevenplus_data/*-paper-*.json; do
  echo "Importing paper: $paper"
  python main.py import_paper "$paper" --skip-if-present || {
    echo "  SKIPPED $paper — see the error above (a missing passage is the usual cause)"
    skipped_imports+=("$paper")
  }
done
shopt -u nullglob

# The last thing in the build log, deliberately. Skipping a bad pack protects the
# deploy, but a skip nobody reads is content missing from production with a green
# tick beside it. This is the one place that fact is observable on an instance
# with no shell — so it is loud, it is last, and it names the files.
#
# It does NOT fail the build: the whole point of skipping is that the rest of the
# deploy should land. If you want a skip to block a release, the place to catch it
# is CI, which imports every contrib_*.json on the PR.
if [ ${#skipped_imports[@]} -gt 0 ]; then
  echo ""
  echo "=================================================================="
  echo "  DEPLOY COMPLETED WITH ${#skipped_imports[@]} FILE(S) NOT IMPORTED"
  echo "=================================================================="
  for f in "${skipped_imports[@]}"; do
    echo "  - $f"
  done
  echo ""
  echo "  The site is live and the question bank is intact, but it does NOT"
  echo "  contain the questions in the file(s) above. Each import is atomic,"
  echo "  so nothing was partially written. Fix the file and redeploy."
  echo "=================================================================="
else
  echo "All question packs and papers imported (or already present)."
fi
