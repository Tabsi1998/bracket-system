#!/bin/bash
# E2E: crown transition -> notifications (gained/changed/lost) + idempotency
set -u
API=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d '=' -f2)
J=/tmp/tls_crown_admin.txt
: "${TLS_ADMIN_EMAIL:?Set TLS_ADMIN_EMAIL before running this smoke script}"
: "${TLS_ADMIN_PASSWORD:?Set TLS_ADMIN_PASSWORD before running this smoke script}"

curl -s -c $J -X POST "$API/api/auth/login" -H "Content-Type: application/json" -H "Origin: $API" \
  --data "$(TLS_ADMIN_EMAIL="$TLS_ADMIN_EMAIL" TLS_ADMIN_PASSWORD="$TLS_ADMIN_PASSWORD" python3 -c 'import json,os; print(json.dumps({"email": os.environ["TLS_ADMIN_EMAIL"], "password": os.environ["TLS_ADMIN_PASSWORD"]}))')" \
  -o /dev/null -w "admin login: %{http_code}\n"
CSRF=$(grep csrf_token $J | awk '{print $7}')

echo "== leaderboard top4 =="
curl -s "$API/api/achievements/leaderboard?limit=4" | python3 -c "
import sys,json
rows=json.load(sys.stdin)
for r in rows: print(r['rank'], r['user_id'][:8], r['display_name'], r['points'])
"
