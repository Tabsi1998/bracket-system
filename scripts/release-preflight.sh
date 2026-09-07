#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ -n "$(git status --porcelain)" ]; then
  echo "Abbruch: Lokale Änderungen oder nicht versionierte Dateien vorhanden." >&2
  exit 1
fi

python3 scripts/check-secrets.py
bash -n install.sh update.sh scripts/*.sh
python3 -m compileall -q backend
(cd backend && python3 -m pytest -q -m "not live")
(cd frontend && corepack yarn install --frozen-lockfile && corepack yarn test && corepack yarn build && corepack yarn check:contrast && corepack yarn audit:high)

if [ "${FULL_PREFLIGHT:-false}" = "true" ]; then
  (cd mobile && npm ci && npm run typecheck && npm run test:security && npm run release:preflight)
fi

if command -v docker >/dev/null 2>&1 && [ -f .env ]; then
  docker compose config -q
fi

echo "Release-Preflight erfolgreich für $(git rev-parse --short HEAD)."
