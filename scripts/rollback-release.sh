#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
default_ref="$(cat .deploy/previous-release 2>/dev/null || true)"
target_ref="${1:-$default_ref}"
[ -n "$target_ref" ] || { echo "Kein Rollback-Ziel vorhanden. Commit explizit angeben." >&2; exit 1; }
[ "${ROLLBACK_CONFIRM:-}" = "$target_ref" ] || { echo "Setze ROLLBACK_CONFIRM=${target_ref} und starte erneut." >&2; exit 1; }
[ -z "$(git status --porcelain)" ] || { echo "Lokale Änderungen oder nicht versionierte Dateien vorhanden." >&2; exit 1; }

current_commit="$(git rev-parse HEAD)"
target_commit="$(git rev-parse --verify "${target_ref}^{commit}")"
git switch --detach "$target_commit"
SKIP_GIT_UPDATE=true PRE_UPDATE_BACKUP=false bash update.sh
mkdir -p .deploy
printf '%s\n' "$current_commit" > .deploy/previous-release
printf '%s\n' "$target_commit" > .deploy/current-release
echo "Rollback abgeschlossen: $(git rev-parse --short HEAD)."
