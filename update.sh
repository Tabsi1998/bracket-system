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

  if [ -n "$configured" ]; then
    echo "$configured"
    return 0
  fi

  if $SUDO systemctl cat nginx >/dev/null 2>&1 || $SUDO systemctl cat nginx.service >/dev/null 2>&1; then
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
    -h|--help)
      usage
      exit 0
      ;;
    *)
      err "Unbekannte Option: $1"
      ;;
  esac
done

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
if [ -n "$NGINX_BIN" ] && [ -n "$NGINX_SERVICE_UNIT" ]; then
  $SUDO "$NGINX_BIN" -t >/dev/null
  $SUDO systemctl reload "$NGINX_SERVICE_UNIT"
  log "Nginx-Konfiguration geprüft und neu geladen ($NGINX_SERVICE_UNIT)"
else
  if [ -z "$NGINX_BIN" ]; then
    warn "Nginx-Binary nicht gefunden, Reload übersprungen"
  else
    warn "Nginx-Service nicht gefunden, Reload übersprungen"
  fi
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
