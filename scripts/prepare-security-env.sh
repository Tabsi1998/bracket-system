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
settings_key_created=false
if placeholder "$settings_key"; then
  settings_key="$(python3 -c 'import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())')"
  settings_key_created=true
fi

mongo_user="$(get_env MONGO_USERNAME)"
mongo_user="${mongo_user:-tls_admin}"
mongo_password="$(get_env MONGO_PASSWORD)"
if placeholder "$mongo_password"; then
  mongo_password="$(openssl rand -hex 32 2>/dev/null || python3 -c 'import secrets;print(secrets.token_hex(32))')"
fi

if docker inspect -f '{{.State.Running}}' tls-mongodb 2>/dev/null | grep -q true; then
  if docker exec -e TLS_MONGO_USER="$mongo_user" -e TLS_MONGO_PASSWORD="$mongo_password" tls-mongodb \
      mongosh --quiet --eval 'try { const admin = db.getSiblingDB("admin"); if (!admin.auth(process.env.TLS_MONGO_USER, process.env.TLS_MONGO_PASSWORD)) quit(13); const result = admin.runCommand({usersInfo: process.env.TLS_MONGO_USER}); quit(result.ok === 1 && result.users.length === 1 ? 0 : 13); } catch (_) { quit(13); }' >/dev/null 2>&1; then
    echo "MongoDB-Anmeldung mit vorhandenen Zugangsdaten erfolgreich."
  else
    mongo_probe=0
    docker exec -e TLS_MONGO_USER="$mongo_user" tls-mongodb mongosh --quiet --eval 'try { const result = db.getSiblingDB("admin").runCommand({usersInfo: 1}); if (result.ok !== 1) quit(13); quit(result.users.length === 0 ? 0 : 14); } catch (_) { quit(13); }' >/dev/null 2>&1 || mongo_probe=$?
    if [ "$mongo_probe" -ne 0 ]; then
      echo "MongoDB ist bereits eingerichtet, aber die Anmeldung mit MONGO_USERNAME/MONGO_PASSWORD aus .env ist fehlgeschlagen. Vorhandene Zugangsdaten prüfen; keine Benutzer neu anlegen oder Volumes löschen." >&2
      exit 1
    fi
    if ! docker exec -e TLS_MONGO_USER="$mongo_user" -e TLS_MONGO_PASSWORD="$mongo_password" tls-mongodb \
        mongosh --quiet --eval 'try { db.getSiblingDB("admin").createUser({user: process.env.TLS_MONGO_USER, pwd: process.env.TLS_MONGO_PASSWORD, roles: [{role: "root", db: "admin"}]}); } catch (_) { quit(13); }' >/dev/null 2>&1; then
      echo "MongoDB-Ersteinrichtung fehlgeschlagen. Update vor dem Container-Neustart abgebrochen." >&2
      exit 1
    fi
    echo "MongoDB-Authentifizierung für das bisher ungeschützte Volume vorbereitet."
  fi
fi

set_env SETTINGS_ENCRYPTION_KEY "$settings_key"
set_env MONGO_USERNAME "$mongo_user"
set_env MONGO_PASSWORD "$mongo_password"
mongo_uri="$(printf '%s\n%s' "$mongo_user" "$mongo_password" | python3 -c 'import sys; from urllib.parse import quote; user,password=sys.stdin.read().split("\n",1); print("mongodb://"+quote(user,safe="")+":"+quote(password,safe="")+"@mongodb:27017/?authSource=admin")')"
set_env MONGO_URL "$mongo_uri"
chmod 600 .env
if [ "$settings_key_created" = true ]; then
  echo "SETTINGS_ENCRYPTION_KEY wurde erzeugt. Sichere .env verschlüsselt außerhalb des Servers."
fi
