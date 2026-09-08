#!/usr/bin/env bash
# Reports whether a successful restore drill happened recently enough.
# Reads only the drill log written by scripts/restore-drill.sh; it never touches
# backups, containers or data, so it is safe to run from a monitoring job.
set -euo pipefail

DRILL_LOG="${RESTORE_DRILL_LOG:-${BACKUP_DIR:-/opt/tls-arena/backups}/restore-drills.log}"
MAX_AGE_DAYS="${RESTORE_DRILL_MAX_AGE_DAYS:-35}"

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  cat <<'EOF'
Usage: scripts/restore-drill-status.sh

Environment:
  RESTORE_DRILL_LOG           Path to the drill log (default: $BACKUP_DIR/restore-drills.log)
  RESTORE_DRILL_MAX_AGE_DAYS  Maximum accepted age of the last successful drill (default: 35)

Exit codes: 0 recent success · 1 too old, failed or never run · 2 log unreadable
EOF
  exit 0
fi

if [ ! -r "$DRILL_LOG" ]; then
  echo "No restore drill log at ${DRILL_LOG}. A restore has never been proven on this host." >&2
  exit 2
fi

LAST_OK="$(grep 'status=ok' "$DRILL_LOG" | tail -n 1 || true)"
if [ -z "$LAST_OK" ]; then
  echo "Restore drill log exists but contains no successful drill." >&2
  LAST_ANY="$(tail -n 1 "$DRILL_LOG" || true)"
  [ -n "$LAST_ANY" ] && echo "Last entry: ${LAST_ANY}" >&2
  exit 1
fi

DRILL_TIME="${LAST_OK%% *}"
if ! DRILL_EPOCH="$(date -u -d "$DRILL_TIME" +%s 2>/dev/null)"; then
  echo "Cannot read the timestamp of the last successful drill: ${DRILL_TIME}" >&2
  exit 2
fi

AGE_DAYS=$(( ( $(date -u +%s) - DRILL_EPOCH ) / 86400 ))
if [ "$AGE_DAYS" -gt "$MAX_AGE_DAYS" ]; then
  echo "Last successful restore drill was ${AGE_DAYS} days ago (limit ${MAX_AGE_DAYS}): ${LAST_OK}" >&2
  exit 1
fi

echo "Last successful restore drill ${AGE_DAYS} day(s) ago: ${LAST_OK}"
