#!/usr/bin/env bash
# Validates backup files before a real restore.
set -euo pipefail

ok()   { printf "\033[1;32m==> %s\033[0m\n" "$*"; }
fail() { printf "\033[1;31m==> %s\033[0m\n" "$*"; exit 1; }

usage() {
  cat <<'EOF'
Usage:
  scripts/restore-check.sh <mongo-archive.gz.enc> <uploads.tar.gz.enc>

This validates archive integrity only. It does not restore or modify data.
EOF
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage
  exit 0
fi
[ "$#" -eq 2 ] || { usage; exit 1; }

MONGO_ARCHIVE="$1"
UPLOADS_ARCHIVE="$2"
BACKUP_ENCRYPTION_PASSWORD_FILE="${BACKUP_ENCRYPTION_PASSWORD_FILE:-/etc/tls-arena/backup-password}"

[ -f "$MONGO_ARCHIVE" ] || fail "Mongo archive not found: ${MONGO_ARCHIVE}"
[ -f "$UPLOADS_ARCHIVE" ] || fail "Uploads archive not found: ${UPLOADS_ARCHIVE}"
[ -r "$BACKUP_ENCRYPTION_PASSWORD_FILE" ] || fail "Password file not readable: ${BACKUP_ENCRYPTION_PASSWORD_FILE}"

openssl enc -d -aes-256-cbc -pbkdf2 -iter 250000 -pass "file:${BACKUP_ENCRYPTION_PASSWORD_FILE}" -in "$MONGO_ARCHIVE" | gzip -t
openssl enc -d -aes-256-cbc -pbkdf2 -iter 250000 -pass "file:${BACKUP_ENCRYPTION_PASSWORD_FILE}" -in "$UPLOADS_ARCHIVE" | tar -tzf - >/dev/null

ok "Backup files are readable and structurally valid."
