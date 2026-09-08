#!/usr/bin/env bash
# Read-only inventory: no sudo, installs, builds, service changes, env reads or secret output.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
command -v python3 >/dev/null 2>&1 || { echo "Python 3 fehlt; bitte den vorhandenen Serverzugang und die Betriebssystemversion nennen." >&2; exit 1; }
exec python3 "$ROOT/scripts/staging-preflight.py"
