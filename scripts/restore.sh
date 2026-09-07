#!/usr/bin/env bash
# Explicit, validated disaster-recovery restore for MongoDB and uploads.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

fail() { printf "\033[1;31m==> %s\033[0m\n" "$*"; exit 1; }
info() { printf "\033[1;36m==> %s\033[0m\n" "$*"; }
ok() { printf "\033[1;32m==> %s\033[0m\n" "$*"; }

[ "$#" -eq 2 ] || fail "Usage: RESTORE_CONFIRM=<db-name> scripts/restore.sh <mongo.archive.gz.enc> <uploads.tar.gz.enc>"
MONGO_ARCHIVE="$(realpath "$1")"
UPLOADS_ARCHIVE="$(realpath "$2")"
DB_NAME="${DB_NAME:-tls_arena}"
UPLOADS_VOLUME="${UPLOADS_VOLUME:-the-lion_squad-esport-webseite_uploads_data}"
PASSWORD_FILE="${BACKUP_ENCRYPTION_PASSWORD_FILE:-/etc/tls-arena/backup-password}"

[ "${RESTORE_CONFIRM:-}" = "$DB_NAME" ] || fail "Set RESTORE_CONFIRM=${DB_NAME} to acknowledge destructive restore."
[ -f "$MONGO_ARCHIVE" ] && [ -f "$UPLOADS_ARCHIVE" ] || fail "Both backup files must exist."
[ -r "$PASSWORD_FILE" ] || fail "Password file not readable: ${PASSWORD_FILE}"

BACKUP_ENCRYPTION_PASSWORD_FILE="$PASSWORD_FILE" bash scripts/restore-check.sh "$MONGO_ARCHIVE" "$UPLOADS_ARCHIVE"
if [ "${SKIP_PRE_RESTORE_BACKUP:-false}" != "true" ]; then
  info "Creating mandatory pre-restore safety backup"
  BACKUP_ENCRYPTION_PASSWORD_FILE="$PASSWORD_FILE" bash scripts/backup.sh
fi

info "Restoring MongoDB database '${DB_NAME}' with --drop"
openssl enc -d -aes-256-cbc -pbkdf2 -iter 250000 -pass "file:${PASSWORD_FILE}" -in "$MONGO_ARCHIVE" \
  | docker compose exec -T mongodb sh -ec 'mongorestore --username "$MONGO_INITDB_ROOT_USERNAME" --password "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin --db "$1" --archive --gzip --drop' sh "$DB_NAME"

docker volume inspect "$UPLOADS_VOLUME" >/dev/null || fail "Uploads volume not found: ${UPLOADS_VOLUME}"
info "Replacing files in uploads volume '${UPLOADS_VOLUME}'"
docker run --rm -v "${UPLOADS_VOLUME}:/uploads" alpine sh -ec 'find /uploads -mindepth 1 -delete'
openssl enc -d -aes-256-cbc -pbkdf2 -iter 250000 -pass "file:${PASSWORD_FILE}" -in "$UPLOADS_ARCHIVE" \
  | docker run --rm -i -v "${UPLOADS_VOLUME}:/uploads" alpine tar -xzf - -C /uploads

docker compose restart backend frontend
ok "Restore completed. Verify /api/health/ready, admin login, uploads, and one historical tournament."
