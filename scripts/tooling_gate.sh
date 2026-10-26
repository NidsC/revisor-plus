#!/usr/bin/env bash
# Proves the shared pack tooling (elevenplus_data/_packtools.py) still reproduces every
# pack generator's output byte for byte.
#
# Each elevenplus_data/generate_*.py is run into a temp dir. Its output must equal the
# committed pack at the generator's default path (cmp), or else match the sha256 held in
# elevenplus_data/_fixtures/tooling_gate/generator_sha256.txt. A generator that exits
# non-zero saying it "needs wordfreq" is SKIPPED, not failed: antonym_pairs and
# synonym_pairs band their pairs with wordfreq, which CI does not install. So CI covers
# 16 generators and skips 2; a machine with wordfreq covers all 18.
#
# Summary line: "tooling_gate: N identical, S skipped, M different". Exit 1 only if M > 0.
#
#   PYTHON=/path/to/python bash scripts/tooling_gate.sh      (default: python3)
set -u

PY="${PYTHON:-python3}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA="$ROOT/elevenplus_data"
FIXTURE="$DATA/_fixtures/tooling_gate/generator_sha256.txt"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

if command -v sha256sum >/dev/null 2>&1; then
  sha() { sha256sum "$1" | cut -d' ' -f1; }
else
  sha() { shasum -a 256 "$1" | cut -d' ' -f1; }
fi

identical=0
skipped=0
different=0

for gen in "$DATA"/generate_*.py; do
  file="$(basename "$gen")"
  [ "$file" = "generate_candidates.py" ] && continue   # takes --out; not a pack generator
  name="${file#generate_}"
  name="${name%.py}"
  out="$TMP/$name.json"

  "$PY" "$gen" "$out" >"$TMP/$name.log" 2>&1
  rc=$?
  if [ "$rc" -ne 0 ]; then
    if grep -q "needs wordfreq" "$TMP/$name.log"; then
      echo "SKIPPED (needs wordfreq)  $name"
      skipped=$((skipped + 1))
    else
      echo "DIFFERENT  $name  (generator exited $rc)"
      different=$((different + 1))
    fi
    continue
  fi

  default="$(grep -A2 'argv' "$gen" | grep -o 'contrib_[A-Za-z0-9_]*\.json' | head -1)"
  if [ -n "$default" ] && cmp -s "$out" "$DATA/$default"; then
    echo "IDENTICAL (committed pack)  $name"
    identical=$((identical + 1))
    continue
  fi

  want="$(grep "  $name\.json\$" "$FIXTURE" | grep -v '^#' | cut -d' ' -f1)"
  if [ -n "$want" ] && [ "$(sha "$out")" = "$want" ]; then
    echo "IDENTICAL (fixture)  $name"
    identical=$((identical + 1))
  else
    echo "DIFFERENT  $name"
    different=$((different + 1))
  fi
done

echo "tooling_gate: $identical identical, $skipped skipped, $different different"
[ "$different" -eq 0 ]
