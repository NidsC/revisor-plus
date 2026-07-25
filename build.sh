#!/usr/bin/env bash
# Render build script for RevisorPlus.
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate
python manage.py seed_demo
# Question packs, auto-discovered by the "contrib_" prefix so a new pack deploys on
# merge without editing this script. Validated in CI before merge.
# nullglob => if there are no packs yet, the loop simply runs zero times.
shopt -s nullglob
for pack in elevenplus_data/contrib_*.json; do
  echo "Importing question pack: $pack"
  python manage.py import_pack "$pack"
done
shopt -u nullglob
