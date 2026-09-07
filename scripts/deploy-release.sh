#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
[ "$#" -eq 1 ] || { echo "Usage: scripts/deploy-release.sh <git-tag-oder-commit>" >&2; exit 1; }
[ -z "$(git status --porcelain)" ] || { echo "Lokale Änderungen oder nicht versionierte Dateien vorhanden." >&2; exit 1; }

target_ref="$1"
git fetch --prune --tags origin
target_commit="$(git rev-parse --verify "${target_ref}^{commit}")"
previous_commit="$(git rev-parse HEAD)"
mkdir -p .deploy
printf '%s\n' "$previous_commit" > .deploy/previous-release
printf '%s\n' "$target_commit" > .deploy/target-release

git switch --detach "$target_commit"
PRE_UPDATE_BACKUP=true SKIP_GIT_UPDATE=true bash update.sh
printf '%s\n' "$target_commit" > .deploy/current-release
echo "Release aktiv: $(git rev-parse --short HEAD). Vorheriger Commit: ${previous_commit}."
