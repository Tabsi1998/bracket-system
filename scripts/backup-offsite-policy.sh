#!/usr/bin/env bash
# Off-site policy for encrypted backups.
# Sourced by scripts/backup.sh; covered by backend/tests/test_backup_offsite_policy.py.

# Reads the effective APP_ENV without sourcing .env, so no other variable of the
# deployment configuration can leak into the backup run.
resolve_app_env() {
  local env_file="${1:-.env}"
  if [ -n "${APP_ENV:-}" ]; then
    printf '%s' "$APP_ENV"
    return 0
  fi
  if [ -r "$env_file" ]; then
    sed -n 's/^[[:space:]]*APP_ENV[[:space:]]*=[[:space:]]*//p' "$env_file" \
      | tail -n 1 | tr -d "\"'" | tr -d '\r'
    return 0
  fi
  printf '%s' ""
}

# Returns 0 when the backup run may continue, otherwise prints the reason and
# returns 1. A local-only backup is fine while testing, but in production it
# means a single host failure destroys the only copy.
offsite_backup_allowed() {
  local remote="${1:-}"
  local app_env="${2:-}"
  local optional="${3:-false}"

  if [ -n "$remote" ]; then
    return 0
  fi
  if [ "$app_env" = "production" ] && [ "$optional" != "true" ]; then
    printf '%s' "BACKUP_REMOTE is empty in production: the encrypted backup exists on this host only, so losing the host loses the backup. Configure an rclone remote, or set BACKUP_REMOTE_OPTIONAL=true to accept local-only backups on purpose."
    return 1
  fi
  return 0
}
