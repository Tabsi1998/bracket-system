#!/usr/bin/env bash
# THE LION SQUAD - production backup helper.
# Creates validated MongoDB and uploads backups without stopping the stack.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ok()    { printf "\033[1;32m==> %s\033[0m\n" "$*"; }
info()  { printf "\033[1;36m==> %s\033[0m\n" "$*"; }
warn()  { printf "\033[1;33m==> %s\033[0m\n" "$*"; }
fail()  { printf "\033[1;31m==> %s\033[0m\n" "$*"; exit 1; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}

require_cmd docker
require_cmd gzip
require_cmd tar
require_cmd openssl

# Resolve both targets from the selected project before creating any backup files.
source scripts/backup-target.sh
source scripts/backup-offsite-policy.sh
resolve_backup_target || fail "Cannot safely resolve this Compose project's backup targets."
BACKUP_DIR="${BACKUP_DIR:-/opt/tls-arena/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
BACKUP_ENCRYPTION_PASSWORD_FILE="${BACKUP_ENCRYPTION_PASSWORD_FILE:-/etc/tls-arena/backup-password}"
BACKUP_REMOTE="${BACKUP_REMOTE:-}"
BACKUP_REMOTE_OPTIONAL="${BACKUP_REMOTE_OPTIONAL:-false}"
RESOLVED_APP_ENV="$(resolve_app_env .env)"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

# Checked before any archive is written so a misconfigured off-site target fails
# fast instead of after a long dump.
if ! OFFSITE_BLOCK_REASON="$(offsite_backup_allowed "$BACKUP_REMOTE" "$RESOLVED_APP_ENV" "$BACKUP_REMOTE_OPTIONAL")"; then
  fail "$OFFSITE_BLOCK_REASON"
fi

MONGO_FILE="tls_${DB_NAME}_${TIMESTAMP}.archive.gz.enc"
UPLOADS_FILE="tls_uploads_${TIMESTAMP}.tar.gz.enc"
MANIFEST_FILE="tls_backup_${TIMESTAMP}.manifest.txt"

mkdir -p "$BACKUP_DIR"
[ -r "$BACKUP_ENCRYPTION_PASSWORD_FILE" ] || fail "Encrypted backups require readable BACKUP_ENCRYPTION_PASSWORD_FILE=${BACKUP_ENCRYPTION_PASSWORD_FILE}"

info "Checking Docker Compose services"
docker compose ps mongodb >/dev/null || fail "MongoDB service is not available via docker compose."
docker compose ps backend >/dev/null || warn "Backend service not listed by docker compose."
docker compose ps frontend >/dev/null || warn "Frontend service not listed by docker compose."

info "Creating encrypted MongoDB backup for database '${DB_NAME}'"
docker compose exec -T mongodb sh -ec 'mongodump --username "$MONGO_INITDB_ROOT_USERNAME" --password "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin --db "$1" --archive --gzip' sh "$DB_NAME" \
  | openssl enc -aes-256-cbc -salt -pbkdf2 -iter 250000 -pass "file:${BACKUP_ENCRYPTION_PASSWORD_FILE}" -out "${BACKUP_DIR}/${MONGO_FILE}"
openssl enc -d -aes-256-cbc -pbkdf2 -iter 250000 -pass "file:${BACKUP_ENCRYPTION_PASSWORD_FILE}" -in "${BACKUP_DIR}/${MONGO_FILE}" | gzip -t
ok "MongoDB backup validated: ${BACKUP_DIR}/${MONGO_FILE}"

info "Creating uploads backup from Docker volume '${UPLOADS_VOLUME}'"
docker volume inspect "$UPLOADS_VOLUME" >/dev/null || fail "Uploads volume not found: ${UPLOADS_VOLUME}. Check the selected Compose project."
docker run --rm \
  -v "${UPLOADS_VOLUME}:/uploads:ro" \
  alpine tar -czf - -C /uploads . \
  | openssl enc -aes-256-cbc -salt -pbkdf2 -iter 250000 -pass "file:${BACKUP_ENCRYPTION_PASSWORD_FILE}" -out "${BACKUP_DIR}/${UPLOADS_FILE}"
openssl enc -d -aes-256-cbc -pbkdf2 -iter 250000 -pass "file:${BACKUP_ENCRYPTION_PASSWORD_FILE}" -in "${BACKUP_DIR}/${UPLOADS_FILE}" | tar -tzf - >/dev/null
ok "Uploads backup validated: ${BACKUP_DIR}/${UPLOADS_FILE}"

{
  echo "created_at=${TIMESTAMP}"
  echo "db_name=${DB_NAME}"
  echo "mongo_file=${MONGO_FILE}"
  echo "uploads_file=${UPLOADS_FILE}"
  echo "uploads_volume=${UPLOADS_VOLUME}"
  echo "retention_days=${RETENTION_DAYS}"
  echo "git_commit=$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "${BACKUP_DIR}/${MONGO_FILE}" "${BACKUP_DIR}/${UPLOADS_FILE}"
  fi
} > "${BACKUP_DIR}/${MANIFEST_FILE}"
ok "Manifest written: ${BACKUP_DIR}/${MANIFEST_FILE}"

if [ -n "$BACKUP_REMOTE" ]; then
  require_cmd rclone
  info "Copying encrypted backup set to off-site remote '${BACKUP_REMOTE}'"
  rclone copyto "${BACKUP_DIR}/${MONGO_FILE}" "${BACKUP_REMOTE%/}/${MONGO_FILE}"
  rclone copyto "${BACKUP_DIR}/${UPLOADS_FILE}" "${BACKUP_REMOTE%/}/${UPLOADS_FILE}"
  rclone copyto "${BACKUP_DIR}/${MANIFEST_FILE}" "${BACKUP_REMOTE%/}/${MANIFEST_FILE}"
  ok "Off-site copy complete."
else
  warn "BACKUP_REMOTE is empty: encrypted backup exists locally only. Configure an rclone remote for off-site resilience."
  warn "Accepted because APP_ENV='${RESOLVED_APP_ENV:-unset}' and BACKUP_REMOTE_OPTIONAL='${BACKUP_REMOTE_OPTIONAL}'."
fi

info "Applying retention (${RETENTION_DAYS} days)"
find "$BACKUP_DIR" -type f -name "tls_${DB_NAME}_*.archive.gz.enc" -mtime +"$RETENTION_DAYS" -delete
find "$BACKUP_DIR" -type f -name "tls_uploads_*.tar.gz.enc" -mtime +"$RETENTION_DAYS" -delete
find "$BACKUP_DIR" -type f -name "tls_backup_*.manifest.txt" -mtime +"$RETENTION_DAYS" -delete

ok "Backup complete."
