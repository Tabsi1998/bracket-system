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

env_value() {
  local key="$1" default="${2:-}" value
  value="$(grep -E "^${key}=" .env 2>/dev/null | tail -n 1 | cut -d= -f2- || true)"
  value="${value%$'\r'}"
  value="${value%\"}"
  value="${value#\"}"
  value="${value%\'}"
  value="${value#\'}"
  printf "%s" "${value:-$default}"
}

detect_uploads_volume() {
  if [ -n "${UPLOADS_VOLUME:-}" ]; then
    printf "%s" "$UPLOADS_VOLUME"
    return
  fi

  local volume
  volume="$(docker volume ls --format '{{.Name}}' | grep -E '(^|_)uploads_data$' | grep -Ei '(lion|tls)' | head -n 1 || true)"
  if [ -n "$volume" ]; then
    printf "%s" "$volume"
    return
  fi

  printf "%s" "the-lion_squad-esport-webseite_uploads_data"
}

require_cmd docker
require_cmd gzip
require_cmd tar
require_cmd openssl

DB_NAME="${DB_NAME:-$(env_value DB_NAME tls_arena)}"
BACKUP_DIR="${BACKUP_DIR:-/opt/tls-arena/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
BACKUP_ENCRYPTION_PASSWORD_FILE="${BACKUP_ENCRYPTION_PASSWORD_FILE:-/etc/tls-arena/backup-password}"
BACKUP_REMOTE="${BACKUP_REMOTE:-}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
UPLOADS_VOLUME="$(detect_uploads_volume)"

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
docker volume inspect "$UPLOADS_VOLUME" >/dev/null || fail "Uploads volume not found: ${UPLOADS_VOLUME}. Set UPLOADS_VOLUME=... if your Compose project name differs."
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
fi

info "Applying retention (${RETENTION_DAYS} days)"
find "$BACKUP_DIR" -type f -name "tls_${DB_NAME}_*.archive.gz.enc" -mtime +"$RETENTION_DAYS" -delete
find "$BACKUP_DIR" -type f -name "tls_uploads_*.tar.gz.enc" -mtime +"$RETENTION_DAYS" -delete
find "$BACKUP_DIR" -type f -name "tls_backup_*.manifest.txt" -mtime +"$RETENTION_DAYS" -delete

ok "Backup complete."
