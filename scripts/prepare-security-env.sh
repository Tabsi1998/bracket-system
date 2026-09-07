#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
[ -f .env ] || { echo ".env fehlt" >&2; exit 1; }

get_env() { grep -E "^$1=" .env 2>/dev/null | tail -n1 | cut -d= -f2- || true; }
set_env() {
  local key="$1" value="$2"
  if grep -q "^${key}=" .env; then
    awk -v k="$key" -v v="$value" 'BEGIN{FS=OFS="="} $1==k{$0=k"="v} {print}' .env > .env.tmp && mv .env.tmp .env
  else
    printf '%s=%s\n' "$key" "$value" >> .env
  fi
}
placeholder() { case "${1:-}" in ""|change-me-*|*generate-with*|*replace-me*) return 0 ;; *) return 1 ;; esac; }

settings_key="$(get_env SETTINGS_ENCRYPTION_KEY)"
if placeholder "$settings_key"; then
  settings_key="$(python3 -c 'import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())')"
  set_env SETTINGS_ENCRYPTION_KEY "$settings_key"
  echo "SETTINGS_ENCRYPTION_KEY wurde erzeugt. Sichere .env verschlüsselt außerhalb des Servers."
fi

mongo_user="$(get_env MONGO_USERNAME)"
mongo_user="${mongo_user:-tls_admin}"
set_env MONGO_USERNAME "$mongo_user"
mongo_password="$(get_env MONGO_PASSWORD)"
if placeholder "$mongo_password"; then
  mongo_password="$(openssl rand -hex 32 2>/dev/null || python3 -c 'import secrets;print(secrets.token_hex(32))')"
  set_env MONGO_PASSWORD "$mongo_password"
fi
set_env MONGO_URL "mongodb://${mongo_user}:${mongo_password}@mongodb:27017/?authSource=admin"

# Existing volumes predate Mongo authentication. Create the first admin while
# the old unauthenticated container is still running, before Compose recreates it.
if docker inspect -f '{{.State.Running}}' tls-mongodb 2>/dev/null | grep -q true; then
  if docker exec -e TLS_MONGO_USER="$mongo_user" tls-mongodb mongosh --quiet --eval 'quit(db.getSiblingDB("admin").getUser(process.env.TLS_MONGO_USER) ? 0 : 3)' >/dev/null 2>&1; then
    echo "MongoDB-Administrator ist bereits vorhanden."
  else
    docker exec -e TLS_MONGO_USER="$mongo_user" -e TLS_MONGO_PASSWORD="$mongo_password" tls-mongodb \
      mongosh --quiet --eval 'db.getSiblingDB("admin").createUser({user: process.env.TLS_MONGO_USER, pwd: process.env.TLS_MONGO_PASSWORD, roles: [{role: "root", db: "admin"}]})'
    echo "MongoDB-Authentifizierung für das vorhandene Volume vorbereitet."
  fi
fi

chmod 600 .env
