#!/usr/bin/env bash
# PostgreSQL backup for the Ketabdaneh production stack (Task 5.12
# §14; docs/12 §10).
#
#   pg_dump (custom format, -Fc) streamed OUT of the container to a
#   host-side file — the dump never lives inside an ephemeral container.
#
# Output: $KETABDANEH_BACKUP_DIR/ketabdaneh-<UTC timestamp>.dump
#   default directory: /opt/ketabdaneh/backups
#
# This script NEVER deletes or rotates old backups (retention is a
# deliberate operator decision — docs/12 §10) and never sends anything
# to third-party storage. It writes only the one new dump file.
#
# Restores are rehearsed against a throwaway database first — see
# scripts/restore_db.sh and docs/12 §11.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env.prod}"

BACKUP_DIR="${KETABDANEH_BACKUP_DIR:-/opt/ketabdaneh/backups}"

fail() { echo "backup: $*" >&2; exit 1; }

[[ -f "$ENV_FILE" ]] || fail ".env.prod not found at $ENV_FILE"
env_value() {
  grep -E "^${1}=" "$ENV_FILE" | tail -n 1 | cut -d= -f2- | tr -d '\r'
}
POSTGRES_USER="$(env_value POSTGRES_USER)"
POSTGRES_DB="$(env_value POSTGRES_DB)"
[[ -n "$POSTGRES_USER" && -n "$POSTGRES_DB" ]] \
  || fail "POSTGRES_USER / POSTGRES_DB missing in $ENV_FILE"

mkdir -p "$BACKUP_DIR"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
DUMP_FILE="$BACKUP_DIR/ketabdaneh-$STAMP.dump"

# exec -T: no TTY, stdout is the byte stream — the redirection happens
# on the HOST, which is the whole point (nothing inside the container
# holds the backup).
docker compose --env-file "$ENV_FILE" -f "$ROOT_DIR/docker-compose.prod.yml" \
  exec -T postgres pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB" \
  > "$DUMP_FILE"

# Structural verification: a custom-format pg_dump starts with "PGDMP".
[[ -s "$DUMP_FILE" ]] || fail "dump is empty: $DUMP_FILE"
MAGIC="$(head -c 5 "$DUMP_FILE")"
[[ "$MAGIC" == "PGDMP" ]] || fail "$DUMP_FILE is not a pg_dump custom-format archive (magic: '$MAGIC')"

SIZE="$(du -h "$DUMP_FILE" | cut -f1)"
echo "backup OK: $DUMP_FILE ($SIZE)"
echo "restore rehearsal: scripts/restore_db.sh $DUMP_FILE <throwaway-db>   (docs/12 §11)"
