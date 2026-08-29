#!/usr/bin/env bash
#
# RevisorPlus database backup / restore helper.
#
#   ./backup.sh                  back up the database in DATABASE_URL (or local SQLite)
#   ./backup.sh restore FILE     load a dump into DATABASE_URL (or local SQLite)
#
# Produces two files, because they have very different sensitivity:
#
#   backups/full-<timestamp>.json   EVERYTHING, incl. user emails + password
#                                   hashes. Gitignored. Never commit this.
#   elevenplus_data/catalog_backup.json    Questions only — your question-bank IP.
#                                   No personal data. Safe to commit.
#
# To back up the live Render database from your own machine, grab the EXTERNAL
# Database URL from the Render dashboard (the Internal one only works inside
# Render's network) and run:
#
#   export DATABASE_URL="postgresql://..."
#   ./backup.sh
#
# The dumps are database-agnostic Django fixtures, so they restore into
# Postgres, MySQL or SQLite on any host — you are not tied to Render.

set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python}"
command -v "$PY" >/dev/null 2>&1 || {
  echo "error: '$PY' not found. Activate your virtualenv first, e.g."
  echo "  source /Users/nidsc/alpha/medrev-venv/bin/activate"
  exit 1
}

# Describe the target without ever printing the password.
if [ -n "${DATABASE_URL:-}" ]; then
  TARGET=$(printf '%s' "$DATABASE_URL" | sed -E 's#://[^@/]*@#://***:***@#')
else
  TARGET="local SQLite (db.sqlite3)"
fi

# These four are excluded from every dump: contenttypes and auth.permission are
# rebuilt by migrate and collide on primary key when reloaded; sessions and
# admin logs are transient noise.
EXCLUDES=(--exclude contenttypes --exclude auth.permission
          --exclude sessions.session --exclude admin.logentry)

restore() {
  local file="$1"
  [ -f "$file" ] || { echo "error: no such file: $file"; exit 1; }
  echo "About to load '$file'"
  echo "                 into: $TARGET"
  echo "This overwrites rows with matching primary keys."
  read -r -p "Continue? [y/N] " reply
  case "$reply" in
    [yY]*) ;;
    *) echo "Aborted."; exit 1 ;;
  esac
  "$PY" main.py migrate --no-input
  "$PY" main.py loaddata "$file"
  echo "Restore complete."
}

if [ "${1:-}" = "restore" ]; then
  [ $# -ge 2 ] || { echo "usage: ./backup.sh restore <file.json>"; exit 1; }
  restore "$2"
  exit 0
fi

mkdir -p backups
STAMP=$(date +%Y%m%d-%H%M%S)
FULL="backups/full-${STAMP}.json"
CATALOG="elevenplus_data/catalog_backup.json"

echo "Backing up: $TARGET"

"$PY" main.py dumpdata --natural-foreign --natural-primary \
  "${EXCLUDES[@]}" --indent 2 > "$FULL"

"$PY" main.py dumpdata catalog --natural-foreign --natural-primary \
  --indent 2 > "$CATALOG"

# Fail loudly rather than leave a reassuring but empty backup behind.
for f in "$FULL" "$CATALOG"; do
  if [ ! -s "$f" ] || ! "$PY" -c "import json,sys; sys.exit(0 if json.load(open('$f')) else 1)"; then
    echo "error: $f is empty or invalid — backup FAILED"; exit 1
  fi
done

# Guard against a future edit letting personal data into the committable file.
if grep -q "pbkdf2\|@" "$CATALOG" 2>/dev/null && \
   "$PY" -c "import json,sys; d=json.load(open('$CATALOG')); sys.exit(0 if any('user' in o['model'] or 'auth' in o['model'] for o in d) else 1)"; then
  echo "error: $CATALOG contains user data — refusing to leave it in place"; rm -f "$CATALOG"; exit 1
fi

echo
"$PY" - "$FULL" "$CATALOG" <<'EOF'
import json, os, sys
from collections import Counter
for path in sys.argv[1:]:
    data = json.load(open(path))
    kb = os.path.getsize(path) / 1024
    top = ", ".join(f"{m.split('.')[-1]} {n}" for m, n in Counter(o["model"] for o in data).most_common(4))
    print(f"  {path}\n    {len(data)} objects, {kb:.0f} KB  ({top})")
EOF

echo
echo "  $FULL"
echo "    -> PRIVATE: contains password hashes. Gitignored. Do not commit."
echo "  $CATALOG"
echo "    -> Safe to commit: question bank only, no personal data."
echo
echo "Restore elsewhere with:  DATABASE_URL=... ./backup.sh restore $FULL"
