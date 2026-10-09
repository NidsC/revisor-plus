#!/bin/bash
# Mirrors .github/workflows/validate-questions.yml (the `validate` job then the
# `pipeline` job) locally, step for step and in the same order, so the CI result
# can be reproduced without pushing. Keep this in sync by hand whenever the
# workflow's steps change — nothing enforces that the two agree.
#
# Usage:
#   PYTHON=/path/to/venv/bin/python \
#   DATABASE_URL=sqlite:////tmp/ci_mirror.sqlite3 \
#   bash scripts/ci_mirror.sh [repo-path]
#
# repo-path defaults to this script's parent directory. DATABASE_URL must
# point at a scratch database — there is no default, so a mistake cannot
# silently hit a real one. PYTHON defaults to `python` on PATH.
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WT="${1:-$(dirname "$SCRIPT_DIR")}"
PY="${PYTHON:-python}"
TMP="${TMPDIR:-/tmp}"
: "${DATABASE_URL:?set DATABASE_URL to a scratch database}"
export DATABASE_URL

cd "$WT" || exit 1
pass=0; fail=0

step() {  # step <name> <command...>
  local name="$1"; shift
  if "$@" > "$TMP/ci_mirror_step.log" 2>&1; then
    pass=$((pass+1)); echo "OK   $name"
  else
    fail=$((fail+1)); echo "FAIL $name"; tail -15 "$TMP/ci_mirror_step.log"
  fi
}

gated() {  # gated <name> <script>  -> main.py shell < script, grep RESULT: ALL PASSED
  local name="$1" script="$2"
  $PY main.py shell < "$script" > "$TMP/ci_mirror_$name.log" 2>&1
  if grep -q "RESULT: ALL PASSED" "$TMP/ci_mirror_$name.log"; then
    pass=$((pass+1)); echo "OK   $name"
  else
    fail=$((fail+1)); echo "FAIL $name"
    grep -n "^FAIL\|RESULT\|Traceback\|Error" "$TMP/ci_mirror_$name.log" | head -20
  fi
}

ran_direct() {  # ran_direct <name> <script>  -> run <script> directly (no django), grep RESULT: ALL PASSED
  local name="$1" script="$2"
  $PY "$script" > "$TMP/ci_mirror_$name.log" 2>&1
  if grep -q "RESULT: ALL PASSED" "$TMP/ci_mirror_$name.log"; then
    pass=$((pass+1)); echo "OK   $name"
  else
    fail=$((fail+1)); echo "FAIL $name"
    grep -n "^FAIL\|RESULT\|Traceback\|Error" "$TMP/ci_mirror_$name.log" | head -20
  fi
}

echo "== validate job"
shopt -s nullglob
packs=(elevenplus_data/_TEMPLATE.question_pack.json elevenplus_data/_EXAMPLE.*.json elevenplus_data/contrib_*.json)
step "validate packs" $PY elevenplus_data/validate_questions.py "${packs[@]}"
step "ast preview_questions" $PY -c "import ast; ast.parse(open('elevenplus_data/preview_questions.py').read())"
step "taxonomy_lookup --sections" $PY elevenplus_data/taxonomy_lookup.py --sections
step "taxonomy_lookup MAT" $PY elevenplus_data/taxonomy_lookup.py MAT
step "preview_figures" $PY elevenplus_data/preview_figures.py "$TMP/ci_mirror_figures.html"
ran_direct test_figures test_figures.py
step "test_compound_words" $PY test_compound_words.py
step "test_word_analogies" $PY test_word_analogies.py
step "test_odd_one_out" $PY test_odd_one_out.py
step "diversity_audit (advisory)" $PY diversity_audit.py
step "test_validator" $PY test_validator.py
step "test_preview_questions" $PY test_preview_questions.py
step "check_contract_docs" $PY elevenplus_data/check_contract_docs.py
step "check_nvr_board_coverage" $PY elevenplus_data/check_nvr_board_coverage.py
step "check_evidence_refs" $PY elevenplus_data/check_evidence_refs.py
step "test_vocab_data" $PY test_vocab_data.py
step "test_wizard_art" $PY test_wizard_art.py
step "test_audit_packs" $PY test_audit_packs.py
step "test_generate_candidates" $PY test_generate_candidates.py
step "test_middle_word" $PY test_middle_word.py

echo "== pipeline job"
step "pip install -r requirements.txt" $PY -m pip install -q -r requirements.txt
step "check" $PY main.py check
step "makemigrations --check" $PY main.py makemigrations --check --dry-run
step "test_verbal_gap_batch" $PY catalog/generators/test_verbal_gap_batch.py
step "test_generator_contract" $PY catalog/generators/test_generator_contract.py
step "migrate" $PY main.py migrate
step "sync_taxonomy" $PY main.py sync_taxonomy
step "seed_demo" $PY main.py seed_demo
for p in elevenplus_data/_EXAMPLE.answer_kinds.json elevenplus_data/_EXAMPLE.shared_passage.json elevenplus_data/_EXAMPLE.vr_shapes.json elevenplus_data/_EXAMPLE.nvr_figures.json; do
  step "import $p" $PY main.py import_pack "$p"
done
for p in elevenplus_data/contrib_*.json; do step "import $p" $PY main.py import_pack "$p"; done
gated test_kinds test_kinds.py
gated test_taxonomy test_taxonomy.py
gated test_import_safety test_import_safety.py
gated test_misconceptions test_misconceptions.py
gated test_hardening test_hardening.py
gated test_billing test_billing.py
gated test_google test_google.py
gated test_adaptive test_adaptive.py
gated test_readiness test_readiness.py
gated test_subject_dashboard test_subject_dashboard.py
step "load_vocab" $PY main.py load_vocab
gated test_vocab test_vocab.py
gated test_vocab_api test_vocab_api.py
gated test_vocab_models test_vocab_models.py
step "generate_bank" $PY main.py generate_bank --per-module 60 --seed 11
gated test_nvr_page test_nvr_page.py

echo "== SUMMARY: $pass ok, $fail failed"
[ "$fail" -eq 0 ]
