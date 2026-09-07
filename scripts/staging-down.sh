#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
ENV_FILE="${STAGING_ENV_FILE:-.env.staging}"
[ -f "$ENV_FILE" ] || { echo "${ENV_FILE} fehlt." >&2; exit 1; }

# Volumes werden absichtlich nicht entfernt.
docker compose --env-file "$ENV_FILE" -p tls-staging -f docker-compose.yml -f docker-compose.staging.yml down --remove-orphans
echo "Staging ist gestoppt; Datenvolumes wurden beibehalten."
