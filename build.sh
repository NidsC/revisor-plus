#!/usr/bin/env bash
# Render build script for RevisorPlus.
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate
python manage.py seed_demo
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
python manage.py generate_bank --per-module 1150 --seed 11
# Question packs, auto-discovered by the "contrib_" prefix so a new pack deploys on
# merge without editing this script. Validated in CI before merge.
# nullglob => if there are no packs yet, the loop simply runs zero times.
shopt -s nullglob
for pack in elevenplus_data/contrib_*.json; do
  echo "Importing question pack: $pack"
  python manage.py import_pack "$pack"
done
# Exam papers use a different format and importer — timed, marked out of a total,
# free-entry answers, multi-part questions. Discovered by the "*-paper-*" name.
# A paper that declares a passage but ships no passage text makes import_paper
# exit non-zero, which under `set -o errexit` fails the whole build. That is
# deliberate for a pack you have chosen to deploy, but the two starter papers are
# not blockers, so failures here are reported and skipped rather than fatal.
# --skip-if-present matters: re-importing replaces a paper's questions, and
# deleting a question cascades to every Attempt against it. Without the flag,
# every deploy would silently wipe pupils' history for these papers. Re-import
# deliberately (and knowingly) when a paper's content actually changes.
for paper in elevenplus_data/*-paper-*.json; do
  echo "Importing paper: $paper"
  python manage.py import_paper "$paper" --skip-if-present || \
    echo "  SKIPPED $paper — see the error above (a missing passage is the usual cause)"
done
shopt -u nullglob
