#!/usr/bin/env bash
# Non-destructive database restore drill into a temporary Mongo database.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
[ "$#" -eq 1 ] || { echo "Usage: scripts/restore-drill.sh <mongo.archive.gz.enc>"; exit 1; }

source scripts/backup-target.sh
resolve_backup_target || { echo "Cannot safely resolve this Compose project's restore-drill target." >&2; exit 1; }
SOURCE_DB="$DB_NAME"
DRILL_DB="tls_restore_drill_$(date +%Y%m%d_%H%M%S)"
PASSWORD_FILE="${BACKUP_ENCRYPTION_PASSWORD_FILE:-/etc/tls-arena/backup-password}"
[ -r "$PASSWORD_FILE" ] || { echo "Password file not readable: ${PASSWORD_FILE}"; exit 1; }

# A drill that leaves no trace cannot be distinguished from one that never ran.
DRILL_LOG="${RESTORE_DRILL_LOG:-${BACKUP_DIR:-/opt/tls-arena/backups}/restore-drills.log}"
ARCHIVE_NAME="$(basename "$1")"
DRILL_STATUS="failed"
DRILL_DETAILS=""

record_drill() {
  local line
  line="$(date -u +%Y-%m-%dT%H:%M:%SZ) status=${DRILL_STATUS} archive=${ARCHIVE_NAME} db=${SOURCE_DB} ${DRILL_DETAILS}"
  if mkdir -p "$(dirname "$DRILL_LOG")" 2>/dev/null && printf '%s\n' "$line" >>"$DRILL_LOG" 2>/dev/null; then
    echo "Drill recorded in ${DRILL_LOG}"
  else
    echo "Warning: restore drill could not be recorded in ${DRILL_LOG}" >&2
  fi
}

cleanup() {
  docker compose exec -T -e TLS_DRILL_DB="$DRILL_DB" mongodb sh -ec \
    'mongosh --quiet --username "$MONGO_INITDB_ROOT_USERNAME" --password "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin --eval "db.getSiblingDB(\"$TLS_DRILL_DB\").dropDatabase()"' \
    >/dev/null 2>&1 || true
  record_drill
}
trap cleanup EXIT

openssl enc -d -aes-256-cbc -pbkdf2 -iter 250000 -pass "file:${PASSWORD_FILE}" -in "$(realpath "$1")" \
  | docker compose exec -T -e TLS_SOURCE_DB="$SOURCE_DB" -e TLS_DRILL_DB="$DRILL_DB" mongodb sh -ec \
    'mongorestore --username "$MONGO_INITDB_ROOT_USERNAME" --password "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin --archive --gzip --nsFrom="$TLS_SOURCE_DB.*" --nsTo="$TLS_DRILL_DB.*"'

DRILL_SUMMARY="$(docker compose exec -T -e TLS_DRILL_DB="$DRILL_DB" mongodb sh -ec \
  'mongosh --quiet --username "$MONGO_INITDB_ROOT_USERNAME" --password "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin --eval "const d=db.getSiblingDB(\"$TLS_DRILL_DB\"); const names=d.getCollectionNames(); if (!names.length) quit(2); printjson({database:d.getName(), collections:names.length, users:d.users.countDocuments({})})"')"
printf '%s\n' "$DRILL_SUMMARY"
DRILL_DETAILS="summary=$(printf '%s' "$DRILL_SUMMARY" | tr -d '\n\r' | tr -s ' ')"
DRILL_STATUS="ok"
echo "Restore drill succeeded; temporary database will now be removed."
