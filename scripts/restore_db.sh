#!/usr/bin/env bash
# Restore a pg_dump custom-format backup into a NAMED TARGET database
# (Task 5.12 §15; docs/12 §11).
#
#   scripts/restore_db.sh <dump-file> <target-db>
#
# Designed for the rehearsed restore procedure: restore into a
# THROWAWAY database first, verify the data there, and only then decide
# what to do with the live database. Restoring over the live database is
# NOT automated by this script — see docs/12 §11 for the manual,
# deliberate procedure (stop API+worker first, etc.).
#
# The target database is created if it does not exist (so a rehearsal
# target like ketabdaneh_restore_test needs no preparation). Existing
# objects in the target are NOT dropped — pg_restore into a non-empty
# database errors instead of silently clobbering.
#
# Safety properties: never drops a database, never touches volumes,
# never runs against the live database unless the operator literally
# types its name as the target (and confirms twice).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env.prod}"
COMPOSE=(docker compose --env-file "$ENV_FILE" -f "$ROOT_DIR/docker-compose.prod.yml")

fail() { echo "restore: $*" >&2; exit 1; }

usage() {
  echo "usage: $0 <dump-file> <target-db>" >&2
  echo "  <dump-file>  pg_dump custom-format archive (scripts/backup_db.sh output)" >&2
  echo "  <target-db>  database to restore INTO (created if missing; use a" >&2
  echo "               throwaway name for the rehearsal — docs/12 §11)" >&2
}

[[ $# -eq 2 ]] || { usage; fail "exactly two arguments required"; }
DUMP_FILE="$1"
TARGET_DB="$2"

[[ -f "$ENV_FILE" ]] || fail ".env.prod not found at $ENV_FILE"
[[ -f "$DUMP_FILE" ]] || fail "dump file not found: $DUMP_FILE"
MAGIC="$(head -c 5 "$DUMP_FILE")"
[[ "$MAGIC" == "PGDMP" ]] || fail "$DUMP_FILE is not a pg_dump custom-format archive (magic: '$MAGIC')"

env_value() {
  grep -E "^${1}=" "$ENV_FILE" | tail -n 1 | cut -d= -f2- | tr -d '\r'
}
POSTGRES_USER="$(env_value POSTGRES_USER)"
LIVE_DB="$(env_value POSTGRES_DB)"
[[ -n "$POSTGRES_USER" && -n "$LIVE_DB" ]] \
  || fail "POSTGRES_USER / POSTGRES_DB missing in $ENV_FILE"

echo "Restoring: $DUMP_FILE"
echo "  into target database: $TARGET_DB"
if [[ "$TARGET_DB" == "$LIVE_DB" ]]; then
  echo "  !!  THIS IS THE LIVE DATABASE ($LIVE_DB)." >&2
  echo "  !!  The supported path is: rehearse on a throwaway DB first," >&2
  echo "  !!  then follow the manual live-restore procedure in docs/12 §11." >&2
  printf "  type the database name to proceed anyway: "
  read -r CONFIRM
  [[ "$CONFIRM" == "$TARGET_DB" ]] || fail "aborted (nothing was changed)"
else
  printf "Type the target database name to confirm: "
  read -r CONFIRM
  [[ "$CONFIRM" == "$TARGET_DB" ]] || fail "aborted (nothing was changed)"
fi

# Create the target database if needed (no-op when it exists).
if ! "${COMPOSE[@]}" exec -T postgres psql -U "$POSTGRES_USER" -d postgres -tAc \
     "SELECT 1 FROM pg_database WHERE datname = '$TARGET_DB'" | grep -q 1; then
  echo "  creating target database $TARGET_DB"
  "${COMPOSE[@]}" exec -T postgres createdb -U "$POSTGRES_USER" "$TARGET_DB"
fi

# stdin redirect happens on the host; pg_restore runs in the container.
"${COMPOSE[@]}" exec -T postgres pg_restore -U "$POSTGRES_USER" -d "$TARGET_DB" \
  --no-owner --role="$POSTGRES_USER" < "$DUMP_FILE"

TABLE_COUNT="$("${COMPOSE[@]}" exec -T postgres psql -U "$POSTGRES_USER" -d "$TARGET_DB" -tAc \
  "SELECT count(*) FROM pg_tables WHERE schemaname = 'public'")"
echo "restore OK: $TABLE_COUNT tables in public schema of $TARGET_DB"
echo "verify (docs/12 §11):"
echo "  ${COMPOSE[*]} exec postgres psql -U $POSTGRES_USER -d $TARGET_DB -c '\\dt'"
echo "rehearsal cleanup (drops ONLY the throwaway target):"
echo "  ${COMPOSE[*]} exec postgres dropdb -U $POSTGRES_USER $TARGET_DB"
