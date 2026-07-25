#!/usr/bin/env bash
# Render build script for Med-revisor.
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate
python manage.py seed_demo
# Load PMT question packs (placeholder demo content)
python manage.py import_pmt pmt_data/decision_making.json
python manage.py import_pmt pmt_data/situational_judgement.json
python manage.py import_pmt pmt_data/quantitative_reasoning.json
python manage.py import_pmt pmt_data/verbal_reasoning.json
# Mock 1 (tagged PMT-M1)
python manage.py import_pmt pmt_data/mock1_vr.json
python manage.py import_pmt pmt_data/mock1_dm.json
python manage.py import_pmt pmt_data/mock1_qr.json
python manage.py import_pmt pmt_data/mock1_sjt.json
# Mock 2 (tagged PMT-M2)
python manage.py import_pmt pmt_data/mock2_vr.json
python manage.py import_pmt pmt_data/mock2_dm.json
python manage.py import_pmt pmt_data/mock2_qr.json
python manage.py import_pmt pmt_data/mock2_sjt.json
# Contributor packs (team-authored IP), auto-discovered by the "contrib_" prefix so a
# new pack deploys on merge without editing this script. Validated in CI before merge.
# nullglob => if there are no contributor packs yet, the loop simply runs zero times.
shopt -s nullglob
for pack in pmt_data/contrib_*.json; do
  echo "Importing contributor pack: $pack"
  python manage.py import_pmt "$pack"
done
shopt -u nullglob
# Reclassify subtopics to the official UCAT taxonomy (runs after all imports)
python manage.py reclassify_taxonomy
