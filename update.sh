#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
#  ARENA eSports Tournament System – Update Script
#  Nutzung: ./update.sh [--force] [--branch <name>]
# ═══════════════════════════════════════════════════════════════════
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'; BOLD='\033[1m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }
step() { echo -e "\n${CYAN}── $1 ──${NC}"; }

resolve_backend_service() {
  local configured="${BACKEND_SERVICE_NAME:-}"
  local name=""
  local unit_files=""

  if [ -n "$configured" ]; then
    echo "$configured"
    return 0
  fi

  # Fast path for default install service name.
  if $SUDO systemctl cat arena-backend >/dev/null 2>&1 || $SUDO systemctl cat arena-backend.service >/dev/null 2>&1; then
    echo "arena-backend"
    return 0
  fi

  unit_files="$($SUDO systemctl list-unit-files --type=service --no-pager --no-legend 2>/dev/null | awk '{print $1}')"
  for name in arena-backend.service arena_backend.service bracket-backend.service bracket-system-backend.service; do
    if printf '%s\n' "$unit_files" | grep -qx "$name"; then
      echo "$name"
      return 0
    fi
  done

  name="$(printf '%s\n' "$unit_files" | grep -E 'arena.*backend|backend.*arena|bracket.*backend|backend.*bracket' | head -n1 || true)"
  if [ -n "$name" ]; then
    echo "$name"
    return 0
  fi

  return 1
}

resolve_nginx_service() {
  local configured="${NGINX_SERVICE_NAME:-}"
  local name=""
  local unit_files=""
  local active_units=""

  if [ -n "$configured" ]; then
    echo "$configured"
    return 0
  fi

  if $SUDO systemctl is-active --quiet nginx || $SUDO systemctl is-active --quiet nginx.service; then
    echo "nginx"
    return 0
  fi

  if $SUDO systemctl cat nginx >/dev/null 2>&1 || $SUDO systemctl cat nginx.service >/dev/null 2>&1; then
    echo "nginx"
    return 0
  fi

  if $SUDO systemctl status nginx >/dev/null 2>&1 || $SUDO systemctl status nginx.service >/dev/null 2>&1; then
    echo "nginx"
    return 0
  fi

  unit_files="$($SUDO systemctl list-unit-files --type=service --no-pager --no-legend 2>/dev/null | awk '{print $1}')"
  for name in nginx.service nginx-mainline.service; do
    if printf '%s\n' "$unit_files" | grep -qx "$name"; then
      echo "$name"
      return 0
    fi
  done

  active_units="$($SUDO systemctl list-units --type=service --all --no-pager --no-legend 2>/dev/null | awk '{print $1}')"
  name="$(printf '%s\n' "$active_units" | grep -E '^nginx(\.service|@.+\.service)?$' | head -n1 || true)"
  if [ -n "$name" ]; then
    echo "$name"
    return 0
  fi

  return 1
}

resolve_nginx_binary() {
  if command -v nginx >/dev/null 2>&1; then
    command -v nginx
    return 0
  fi

  for p in /usr/sbin/nginx /usr/local/sbin/nginx /sbin/nginx; do
    if [ -x "$p" ]; then
      echo "$p"
      return 0
    fi
  done

  return 1
}

collect_untracked_changes() {
  git ls-files --others --exclude-standard | while IFS= read -r path; do
    case "$path" in
      frontend/yarn.lock|frontend/build|frontend/build/*)
        continue
        ;;
      *)
        echo "$path"
        ;;
    esac
  done
}

usage() {
  cat << 'EOF'
Usage: ./update.sh [options]

Options:
  --force           update auch bei lokalen Änderungen an getrackten Dateien
  --branch <name>   expliziter Git-Branch (Standard: aktueller Branch)
  --admin-reset     Admin-Konto zurücksetzen/neu anlegen (CLI)
  --admin-email     E-Mail für Admin-Reset
  --admin-password  Passwort für Admin-Reset
  --admin-username  Benutzername für Admin-Reset (optional)
  --seed-demo       Demo-Daten importieren
  --seed-demo-reset Vorhandene Demo-Daten vor Import löschen
  -h, --help        Hilfe anzeigen
EOF
}

SUDO=""
if [ "${EUID:-$(id -u)}" -ne 0 ]; then
  command -v sudo >/dev/null 2>&1 || err "sudo fehlt. Bitte als root ausführen."
  SUDO="sudo"
fi

FORCE=0
BRANCH=""
ADMIN_RESET=0
ADMIN_EMAIL_OVERRIDE=""
ADMIN_PASSWORD_OVERRIDE=""
ADMIN_USERNAME_OVERRIDE=""
DEMO_SEED=0
DEMO_RESET=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --force)
      FORCE=1
      shift
      ;;
    --branch)
      [ $# -ge 2 ] || err "--branch benötigt einen Wert"
      BRANCH="$2"
      shift 2
      ;;
    --admin-reset)
      ADMIN_RESET=1
      shift
      ;;
    --admin-email)
      [ $# -ge 2 ] || err "--admin-email benötigt einen Wert"
      ADMIN_EMAIL_OVERRIDE="$2"
      shift 2
      ;;
    --admin-password)
      [ $# -ge 2 ] || err "--admin-password benötigt einen Wert"
      ADMIN_PASSWORD_OVERRIDE="$2"
      shift 2
      ;;
    --admin-username)
      [ $# -ge 2 ] || err "--admin-username benötigt einen Wert"
      ADMIN_USERNAME_OVERRIDE="$2"
      shift 2
      ;;
    --seed-demo)
      DEMO_SEED=1
      shift
      ;;
    --seed-demo-reset)
      DEMO_SEED=1
      DEMO_RESET=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      err "Unbekannte Option: $1"
      ;;
  esac
done

normalize_email() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | sed -e "s/^[[:space:]\"']*//" -e "s/[[:space:]\"']*$//"
}

run_admin_reset() {
  local admin_email="$1"
  local admin_password="$2"
  local admin_username="$3"
  local backend_env_file="$SCRIPT_DIR/backend/.env"

  [ -n "$admin_email" ] || err "Admin-Reset: E-Mail fehlt"
  [ -n "$admin_password" ] || err "Admin-Reset: Passwort fehlt"

  admin_email="$(normalize_email "$admin_email")"
  if [[ -z "$admin_email" || ! "$admin_email" =~ ^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$ ]]; then
    err "Admin-Reset: ungültige E-Mail"
  fi
  admin_username="$(printf '%s' "$admin_username" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"

  [ -f "$backend_env_file" ] || err "Admin-Reset: backend/.env nicht gefunden"

  cd "$SCRIPT_DIR/backend"
  if [ ! -d venv ]; then
    python3 -m venv venv
  fi
  # shellcheck disable=SC1091
  source venv/bin/activate

  ADMIN_RESET_EMAIL="$admin_email" \
  ADMIN_RESET_PASSWORD="$admin_password" \
  ADMIN_RESET_USERNAME="$admin_username" \
  python - << 'PY'
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import bcrypt
from dotenv import load_dotenv
from pymongo import MongoClient

root = Path.cwd()
load_dotenv(root / ".env")

mongo_url = os.environ.get("MONGO_URL", "").strip()
db_name = os.environ.get("DB_NAME", "").strip()
if not mongo_url or not db_name:
    raise SystemExit("Admin-Reset: MONGO_URL oder DB_NAME fehlt in backend/.env")

admin_email = os.environ["ADMIN_RESET_EMAIL"].strip().lower()
admin_password = os.environ["ADMIN_RESET_PASSWORD"]
admin_username = os.environ.get("ADMIN_RESET_USERNAME", "").strip() or (admin_email.split("@")[0] if "@" in admin_email else "admin")

client = MongoClient(mongo_url)
db = client[db_name]

email_re = {"$regex": r"^\s*" + re.escape(admin_email) + r"\s*$", "$options": "i"}
username_re = {"$regex": r"^\s*" + re.escape(admin_username) + r"\s*$", "$options": "i"}

now = datetime.now(timezone.utc).isoformat()
password_hash = bcrypt.hashpw(admin_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

existing = db.users.find_one({"email": email_re})
if existing:
    update_doc = {
        "role": "admin",
        "email": admin_email,
        "password_hash": password_hash,
        "updated_at": now,
    }
    if not existing.get("id"):
        update_doc["id"] = str(uuid.uuid4())
    if not existing.get("username"):
        update_doc["username"] = admin_username
    if not existing.get("avatar_url"):
        seed = update_doc.get("username", existing.get("username", admin_username))
        update_doc["avatar_url"] = f"https://api.dicebear.com/7.x/avataaars/svg?seed={seed}"

    db.users.update_one(
        {"_id": existing["_id"]},
        {"$set": update_doc, "$unset": {"password": ""}},
    )
    print(f"Admin-Reset: bestehender User aktualisiert ({admin_email})")
else:
    if db.users.find_one({"username": username_re}):
        admin_username = f"{admin_username}_{uuid.uuid4().hex[:6]}"

    admin_doc = {
        "id": str(uuid.uuid4()),
        "username": admin_username,
        "email": admin_email,
        "password_hash": password_hash,
        "role": "admin",
        "avatar_url": f"https://api.dicebear.com/7.x/avataaars/svg?seed={admin_username}",
        "created_at": now,
    }
    db.users.insert_one(admin_doc)
    print(f"Admin-Reset: neuer Admin erstellt ({admin_email})")
PY

  deactivate
  cd "$SCRIPT_DIR"
  log "Admin-Konto per CLI gesetzt: $admin_email"
}

run_demo_seed() {
  local reset_flag="${1:-0}"
  local backend_env_file="$SCRIPT_DIR/backend/.env"
  local seed_script="$SCRIPT_DIR/backend/seed_demo_data.py"

  [ -f "$backend_env_file" ] || err "Demo-Seed: backend/.env nicht gefunden"
  [ -f "$seed_script" ] || err "Demo-Seed: backend/seed_demo_data.py nicht gefunden"

  cd "$SCRIPT_DIR/backend"
  if [ ! -d venv ]; then
    python3 -m venv venv
  fi
  # shellcheck disable=SC1091
  source venv/bin/activate

  if [ "$reset_flag" -eq 1 ]; then
    python seed_demo_data.py --reset
  else
    python seed_demo_data.py
  fi

  deactivate
  cd "$SCRIPT_DIR"
  log "Demo-Daten importiert"
}

read_env_default() {
  local key="$1"
  local file="$2"
  local value=""
  if [ -f "$file" ]; then
    value="$(grep -E "^${key}=" "$file" | tail -n1 | cut -d'=' -f2- || true)"
    value="$(printf '%s' "$value" | sed -e "s/^[[:space:]\"']*//" -e "s/[[:space:]\"']*$//")"
  fi
  printf '%s' "$value"
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

step "Preflight"
command -v git >/dev/null 2>&1 || err "git nicht gefunden"
command -v python3 >/dev/null 2>&1 || err "python3 nicht gefunden"
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || err "Kein Git-Repository in $SCRIPT_DIR"

CURRENT_BRANCH="${BRANCH:-$(git rev-parse --abbrev-ref HEAD)}"
if [ -z "$CURRENT_BRANCH" ] || [ "$CURRENT_BRANCH" = "HEAD" ]; then
  CURRENT_BRANCH="main"
fi
log "Branch: $CURRENT_BRANCH"

if [ -n "$ADMIN_EMAIL_OVERRIDE" ] || [ -n "$ADMIN_PASSWORD_OVERRIDE" ] || [ -n "$ADMIN_USERNAME_OVERRIDE" ]; then
  ADMIN_RESET=1
fi

TRACKED_CHANGES="$(git status --porcelain --untracked-files=no)"
UNTRACKED_CHANGES="$(collect_untracked_changes || true)"

if [ "$FORCE" -ne 1 ] && [ -n "$TRACKED_CHANGES" ]; then
  warn "Geänderte getrackte Dateien:"
  printf '%s\n' "$TRACKED_CHANGES"
  err "Lokale Änderungen vorhanden. Committe/stashe oder nutze --force."
fi

if [ -n "$UNTRACKED_CHANGES" ]; then
  warn "Ungetrackte Dateien erkannt (werden nicht blockiert):"
  printf '%s\n' "$UNTRACKED_CHANGES"
fi

step "Git aktualisieren"
git fetch origin "$CURRENT_BRANCH"
LOCAL_SHA="$(git rev-parse HEAD)"
REMOTE_SHA="$(git rev-parse "origin/$CURRENT_BRANCH")"
if [ "$LOCAL_SHA" = "$REMOTE_SHA" ]; then
  log "Repository ist bereits aktuell"
else
  git pull --ff-only origin "$CURRENT_BRANCH"
  log "Git-Update abgeschlossen"
fi

step "Backend aktualisieren"
[ -d backend ] || err "backend/ nicht gefunden"
cd backend
if [ ! -d venv ]; then
  python3 -m venv venv
  log "Python venv erstellt"
fi
source venv/bin/activate
python -m pip install --upgrade pip -q
if [ -f requirements.prod.txt ]; then
  pip install -r requirements.prod.txt -q || pip install -r requirements.txt -q
elif [ -f requirements.txt ]; then
  pip install -r requirements.txt -q
else
  deactivate || true
  err "Keine requirements-Datei gefunden"
fi
deactivate
cd "$SCRIPT_DIR"
log "Backend-Abhängigkeiten aktualisiert"

BACKEND_SERVICE_UNIT="$(resolve_backend_service || true)"
if [ -n "$BACKEND_SERVICE_UNIT" ]; then
  $SUDO systemctl restart "$BACKEND_SERVICE_UNIT"
  $SUDO systemctl is-active --quiet "$BACKEND_SERVICE_UNIT" || err "Service $BACKEND_SERVICE_UNIT konnte nicht gestartet werden"
  log "Service $BACKEND_SERVICE_UNIT neu gestartet"
else
  warn "Kein passender Backend-Service gefunden."
  warn "Setze optional BACKEND_SERVICE_NAME, z. B.: BACKEND_SERVICE_NAME=arena-backend ./update.sh"
fi

step "Admin Konto (optional)"
if [ "$ADMIN_RESET" -ne 1 ] && [ -t 0 ]; then
  read -rp "Admin-Konto zurücksetzen/neu anlegen? [j/N] " admin_choice
  case "$admin_choice" in
    j|J|y|Y) ADMIN_RESET=1 ;;
    *) ADMIN_RESET=0 ;;
  esac
fi

if [ "$ADMIN_RESET" -eq 1 ]; then
  BACKEND_ENV_FILE="$SCRIPT_DIR/backend/.env"
  default_admin_email="$(read_env_default "ADMIN_EMAIL" "$BACKEND_ENV_FILE")"
  default_admin_username="$(read_env_default "ADMIN_USERNAME" "$BACKEND_ENV_FILE")"

  [ -n "$default_admin_email" ] || default_admin_email="admin@arena.gg"
  [ -n "$default_admin_username" ] || default_admin_username="${default_admin_email%%@*}"
  [ -n "$default_admin_username" ] || default_admin_username="admin"

  admin_email="$ADMIN_EMAIL_OVERRIDE"
  admin_password="$ADMIN_PASSWORD_OVERRIDE"
  admin_username="$ADMIN_USERNAME_OVERRIDE"

  if [ -t 0 ]; then
    read -rp "Admin E-Mail [$default_admin_email]: " input_email
    if [ -z "$admin_email" ]; then
      admin_email="${input_email:-$default_admin_email}"
    fi

    if [ -z "$admin_password" ]; then
      read -rsp "Admin Passwort (Pflichtfeld): " admin_password
      echo ""
    fi

    read -rp "Admin Benutzername [$default_admin_username]: " input_username
    if [ -z "$admin_username" ]; then
      admin_username="${input_username:-$default_admin_username}"
    fi
  fi

  [ -n "$admin_email" ] || admin_email="$default_admin_email"
  [ -n "$admin_username" ] || admin_username="$default_admin_username"
  [ -n "$admin_password" ] || err "Admin-Reset gewählt, aber kein Passwort angegeben"

  run_admin_reset "$admin_email" "$admin_password" "$admin_username"
else
  log "Admin-Reset übersprungen"
fi

step "Demo-Daten (optional)"
if [ "$DEMO_SEED" -ne 1 ] && [ -t 0 ]; then
  read -rp "Demo-Daten importieren? [j/N] " demo_choice
  case "$demo_choice" in
    j|J|y|Y) DEMO_SEED=1 ;;
    *) DEMO_SEED=0 ;;
  esac
fi

if [ "$DEMO_SEED" -eq 1 ] && [ "$DEMO_RESET" -ne 1 ] && [ -t 0 ]; then
  read -rp "Vorhandene Demo-Daten vorher löschen? [j/N] " demo_reset_choice
  case "$demo_reset_choice" in
    j|J|y|Y) DEMO_RESET=1 ;;
    *) DEMO_RESET=0 ;;
  esac
fi

if [ "$DEMO_SEED" -eq 1 ]; then
  run_demo_seed "$DEMO_RESET"
else
  log "Demo-Seed übersprungen"
fi

step "Frontend aktualisieren"
[ -d frontend ] || err "frontend/ nicht gefunden"
cd frontend
if ! command -v yarn >/dev/null 2>&1; then
  command -v npm >/dev/null 2>&1 || err "weder yarn noch npm gefunden"
  warn "Yarn nicht gefunden, versuche globale Installation"
  $SUDO npm install -g yarn >/dev/null 2>&1 || err "Yarn-Installation fehlgeschlagen"
fi

if [ -f yarn.lock ]; then
  yarn install --frozen-lockfile --silent 2>/dev/null || yarn install --silent
else
  yarn install --silent
fi
yarn build
cd "$SCRIPT_DIR"
log "Frontend Build aktualisiert"

step "Nginx reload"
NGINX_BIN="$(resolve_nginx_binary || true)"
NGINX_SERVICE_UNIT="$(resolve_nginx_service || true)"
if [ -n "$NGINX_SERVICE_UNIT" ]; then
  if [ -n "$NGINX_BIN" ]; then
    $SUDO "$NGINX_BIN" -t >/dev/null
  else
    warn "Nginx-Binary nicht gefunden, überspringe nginx -t"
  fi
  $SUDO systemctl reload "$NGINX_SERVICE_UNIT"
  log "Nginx-Konfiguration geprüft und neu geladen ($NGINX_SERVICE_UNIT)"
else
  warn "Nginx-Service nicht gefunden, Reload übersprungen"
fi

echo ""
log "Update erfolgreich abgeschlossen"
echo -e "${BOLD}Nützliche Checks:${NC}"
if [ -n "${BACKEND_SERVICE_UNIT:-}" ]; then
  echo "  $SUDO systemctl status $BACKEND_SERVICE_UNIT --no-pager -l"
  echo "  $SUDO journalctl -u $BACKEND_SERVICE_UNIT -n 80 --no-pager"
else
  echo "  $SUDO systemctl status <backend-service> --no-pager -l"
  echo "  $SUDO journalctl -u <backend-service> -n 80 --no-pager"
fi
