#!/usr/bin/env bash
# Source after changing into the repository root; caller must use set -euo pipefail.
resolve_backup_target() {
  local resolved_target
  command -v python3 >/dev/null 2>&1 || { echo "Backup target validation requires python3." >&2; return 1; }
  resolved_target="$(docker compose config --format json \
    | python3 scripts/compose-backup-target.py --db "${DB_NAME:-}" --volume "${UPLOADS_VOLUME:-}")" || return 1
  DB_NAME="${resolved_target%%$'\n'*}"
  UPLOADS_VOLUME="${resolved_target#*$'\n'}"
  export DB_NAME UPLOADS_VOLUME
}
