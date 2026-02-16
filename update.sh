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

usage() {
  cat << 'EOF'
Usage: ./update.sh [options]

Options:
  --force           update auch bei lokalen Änderungen
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

if [ "$FORCE" -ne 1 ] && [ -n "$(git status --porcelain)" ]; then
  err "Lokale Änderungen vorhanden. Committe/stashe zuerst oder nutze --force."
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

if systemctl list-unit-files 2>/dev/null | grep -q '^arena-backend\.service'; then
  $SUDO systemctl restart arena-backend
  $SUDO systemctl is-active --quiet arena-backend || err "arena-backend konnte nicht gestartet werden"
  log "Service arena-backend neu gestartet"
else
  warn "Service arena-backend nicht gefunden, Restart übersprungen"
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
if command -v nginx >/dev/null 2>&1 && systemctl list-unit-files 2>/dev/null | grep -q '^nginx\.service'; then
  $SUDO nginx -t >/dev/null
  $SUDO systemctl reload nginx
  log "Nginx-Konfiguration geprüft und neu geladen"
else
  warn "Nginx nicht gefunden, Reload übersprungen"
fi

echo ""
log "Update erfolgreich abgeschlossen"
echo -e "${BOLD}Nützliche Checks:${NC}"
echo "  $SUDO systemctl status arena-backend --no-pager -l"
echo "  $SUDO journalctl -u arena-backend -n 80 --no-pager"

