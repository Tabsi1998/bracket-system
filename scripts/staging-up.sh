#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
ENV_FILE="${STAGING_ENV_FILE:-.env.staging}"
[ -f "$ENV_FILE" ] || { echo "${ENV_FILE} fehlt. Kopiere .env.staging.example und setze eigene Secrets." >&2; exit 1; }

COMPOSE=(docker compose --env-file "$ENV_FILE" -p tls-staging -f docker-compose.yml -f docker-compose.staging.yml)
"${COMPOSE[@]}" config -q
"${COMPOSE[@]}" up -d --build

backend_port="$(grep -E '^BACKEND_PORT=' "$ENV_FILE" | tail -n1 | cut -d= -f2- || true)"
frontend_port="$(grep -E '^FRONTEND_PORT=' "$ENV_FILE" | tail -n1 | cut -d= -f2- || true)"
backend_port="${backend_port:-18001}"
frontend_port="${frontend_port:-13000}"

for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:${backend_port}/api/health/ready" >/dev/null 2>&1 \
    && curl -fsS "http://127.0.0.1:${frontend_port}/health" >/dev/null 2>&1; then
    echo "Staging ist bereit: Frontend http://127.0.0.1:${frontend_port}, API http://127.0.0.1:${backend_port}"
    exit 0
  fi
  sleep 2
done

"${COMPOSE[@]}" ps
"${COMPOSE[@]}" logs --no-color --tail=150
echo "Staging wurde nicht rechtzeitig bereit." >&2
exit 1
