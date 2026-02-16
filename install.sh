#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
#  ARENA eSports Tournament System – One-Command Installer
#  Getestet auf: Ubuntu 22.04 / 24.04 LTS
#  Nutzung:  sudo bash install.sh
# ═══════════════════════════════════════════════════════════════════
set -euo pipefail

# ── Farben ──
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'; BOLD='\033[1m'

banner() {
  echo ""
  echo -e "${YELLOW}╔═══════════════════════════════════════════════════╗${NC}"
  echo -e "${YELLOW}║${NC}   ${BOLD}ARENA${NC} eSports Tournament System – Installer     ${YELLOW}║${NC}"
  echo -e "${YELLOW}╚═══════════════════════════════════════════════════╝${NC}"
  echo ""
}

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }
step() { echo -e "\n${CYAN}── $1 ──${NC}"; }

# ── Root-Check ──
if [ "$EUID" -ne 0 ]; then
  err "Bitte als root ausführen:  sudo bash install.sh"
fi

banner

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

normalize_domain() {
  local value="$1"
  value="${value#http://}"
  value="${value#https://}"
  value="${value%%/*}"
  value="${value%%[[:space:]]*}"
  echo "$value"
}

normalize_email() {
  local value="$1"
  value="$(printf '%s' "$value" | sed -e "s/^[[:space:]\"']*//" -e "s/[[:space:]\"']*$//")"
  value="$(printf '%s' "$value" | tr '[:upper:]' '[:lower:]')"
  echo "$value"
}

dotenv_quote() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  printf '"%s"' "$value"
}

# ── Konfiguration einlesen ──
INSTALL_DIR_DEFAULT="$SCRIPT_DIR"
INSTALL_DIR="$INSTALL_DIR_DEFAULT"
DOMAIN=""
ADMIN_EMAIL="admin@arena.gg"
ADMIN_PASSWORD="admin123"
MONGO_DB_NAME="arena_esports"
JWT_SECRET=$(openssl rand -hex 32)
BACKEND_PORT=8001
FRONTEND_PORT=3000

step "Konfiguration"
read -rp "Domain oder IP-Adresse (z.B. arena.example.com oder 192.168.1.100): " DOMAIN
DOMAIN="$(normalize_domain "$DOMAIN")"
if [ -z "$DOMAIN" ]; then err "Domain/IP ist erforderlich"; fi
read -rp "Installationsverzeichnis [$INSTALL_DIR_DEFAULT]: " input && INSTALL_DIR="${input:-$INSTALL_DIR_DEFAULT}"

read -rp "Admin E-Mail [$ADMIN_EMAIL]: " input && ADMIN_EMAIL="${input:-$ADMIN_EMAIL}"
ADMIN_EMAIL="$(normalize_email "$ADMIN_EMAIL")"
if [[ -z "$ADMIN_EMAIL" || ! "$ADMIN_EMAIL" =~ ^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$ ]]; then
  err "Ungültige Admin-E-Mail"
fi
read -rsp "Admin Passwort [$ADMIN_PASSWORD]: " input && ADMIN_PASSWORD="${input:-$ADMIN_PASSWORD}"
echo ""
if [ -z "$ADMIN_PASSWORD" ]; then
  warn "Leeres Admin-Passwort erkannt, setze Fallback auf admin123"
  ADMIN_PASSWORD="admin123"
fi
read -rp "MongoDB Datenbankname [$MONGO_DB_NAME]: " input && MONGO_DB_NAME="${input:-$MONGO_DB_NAME}"
read -rp "Stripe Secret Key (optional, Enter zum Überspringen): " STRIPE_KEY

echo ""
log "Domain:         $DOMAIN"
log "Installationspfad: $INSTALL_DIR"
log "Admin E-Mail:   $ADMIN_EMAIL"
log "Datenbank:      $MONGO_DB_NAME"
echo ""
read -rp "Alles korrekt? Installation starten? [J/n] " confirm
if [[ "${confirm,,}" == "n" ]]; then exit 0; fi

# ═══════════════════════════════════════════════════
# 1. System-Pakete
# ═══════════════════════════════════════════════════
step "1/8 – System-Pakete installieren"

apt-get update -qq
apt-get install -y -qq curl gnupg software-properties-common git build-essential nginx > /dev/null 2>&1
log "Basis-Pakete installiert"

# ── Python 3.11+ ──
PYTHON_BIN="python3"

PY_VERSION=$($PYTHON_BIN -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")

if ! dpkg -s python${PY_VERSION}-venv >/dev/null 2>&1; then
  apt-get install -y -qq python${PY_VERSION}-venv python${PY_VERSION}-dev > /dev/null 2>&1
  log "python${PY_VERSION}-venv installiert"
fi

log "Python $($PYTHON_BIN --version 2>&1 | awk '{print $2}') gefunden"

# ── Node.js 20.x ──
if ! command -v node &>/dev/null; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash - > /dev/null 2>&1
  apt-get install -y -qq nodejs > /dev/null 2>&1
  log "Node.js $(node --version) installiert"
else
  log "Node.js $(node --version) gefunden"
fi

# ── Yarn ──
if ! command -v yarn &>/dev/null; then
  npm install -g yarn > /dev/null 2>&1
  log "Yarn installiert"
else
  log "Yarn $(yarn --version) gefunden"
fi

# ── MongoDB 8.0 ──
if ! command -v mongod &>/dev/null; then
  rm -f /etc/apt/sources.list.d/mongodb-org-*.list

  curl -fsSL https://pgp.mongodb.com/server-8.0.asc | gpg --dearmor -o /usr/share/keyrings/mongodb-server-8.0.gpg 2>/dev/null

  UBUNTU_CODENAME=$(lsb_release -cs)
  [ "$UBUNTU_CODENAME" = "noble" ] && UBUNTU_CODENAME="jammy"

  echo "deb [ signed-by=/usr/share/keyrings/mongodb-server-8.0.gpg ] https://repo.mongodb.org/apt/ubuntu ${UBUNTU_CODENAME}/mongodb-org/8.0 multiverse" > /etc/apt/sources.list.d/mongodb-org-8.0.list

  apt-get update -qq
  apt-get install -y -qq mongodb-org > /dev/null 2>&1
  systemctl enable mongod --now > /dev/null 2>&1
  log "MongoDB 8.0 installiert und gestartet"
else
  systemctl is-active mongod > /dev/null 2>&1 || systemctl start mongod
  log "MongoDB bereits installiert"
fi

# ═══════════════════════════════════════════════════
# 2. Anwendungs-Verzeichnis
# ═══════════════════════════════════════════════════
step "2/8 – Anwendung einrichten"

# Kopiere Dateien wenn wir in ein anderes Ziel installieren
if [ "$SCRIPT_DIR" != "$INSTALL_DIR" ]; then
  mkdir -p "$INSTALL_DIR"
  cp -r "$SCRIPT_DIR/backend" "$INSTALL_DIR/"
  cp -r "$SCRIPT_DIR/frontend" "$INSTALL_DIR/"
  log "Dateien nach $INSTALL_DIR kopiert"
else
  log "Bereits im Installationsverzeichnis"
fi

# ═══════════════════════════════════════════════════
# 3. Backend – Python Environment
# ═══════════════════════════════════════════════════
step "3/8 – Backend einrichten"

cd "$INSTALL_DIR/backend"
$PYTHON_BIN -m venv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.prod.txt -q 2>/dev/null || pip install -r requirements.txt -q 2>/dev/null
deactivate
log "Python-Abhängigkeiten installiert"

# Backend .env
{
  printf 'MONGO_URL=%s\n' "mongodb://localhost:27017"
  printf 'DB_NAME=%s\n' "$(dotenv_quote "$MONGO_DB_NAME")"
  printf 'JWT_SECRET=%s\n' "$(dotenv_quote "$JWT_SECRET")"
  printf 'CORS_ORIGINS=%s\n' "$(dotenv_quote "http://${DOMAIN},https://${DOMAIN},http://localhost:${FRONTEND_PORT}")"
  printf 'STRIPE_API_KEY=%s\n' "$(dotenv_quote "$STRIPE_KEY")"
  printf 'ADMIN_EMAIL=%s\n' "$(dotenv_quote "$ADMIN_EMAIL")"
  printf 'ADMIN_PASSWORD=%s\n' "$(dotenv_quote "$ADMIN_PASSWORD")"
} > "$INSTALL_DIR/backend/.env"
log "Backend .env erstellt"

# ═══════════════════════════════════════════════════
# 4. Frontend – Build
# ═══════════════════════════════════════════════════
step "4/8 – Frontend bauen"

cd "$INSTALL_DIR/frontend"
cat > .env << EOF
REACT_APP_BACKEND_URL=
EOF

yarn install --frozen-lockfile --silent 2>/dev/null || yarn install --silent
yarn build
log "Frontend gebaut (Production Build)"

# ═══════════════════════════════════════════════════
# 5. Systemd Services
# ═══════════════════════════════════════════════════
step "5/8 – Systemd Services erstellen"

# Backend Service
cat > /etc/systemd/system/arena-backend.service << EOF
[Unit]
Description=ARENA eSports Backend (FastAPI)
After=network.target mongod.service
Wants=mongod.service

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}/backend
Environment=PATH=${INSTALL_DIR}/backend/venv/bin:/usr/local/bin:/usr/bin
ExecStart=${INSTALL_DIR}/backend/venv/bin/uvicorn server:app --host 0.0.0.0 --port ${BACKEND_PORT}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable arena-backend --now
log "Backend-Service gestartet auf Port ${BACKEND_PORT}"

# ═══════════════════════════════════════════════════
# 6. Nginx Konfiguration
# ═══════════════════════════════════════════════════
step "6/8 – Nginx konfigurieren"

cat > /etc/nginx/sites-available/arena << 'NGINX_EOF'
server {
    listen 80;
    server_name DOMAIN_PLACEHOLDER;

    # Frontend (Static Build)
    root INSTALL_DIR_PLACEHOLDER/frontend/build;
    index index.html;

    # Gzip Kompression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;
    gzip_min_length 1000;

    # Backend API Proxy
    location /api/ {
        proxy_pass http://127.0.0.1:BACKEND_PORT_PLACEHOLDER;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
        client_max_body_size 10m;
    }

    # SPA Fallback – alle Routen an index.html
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Statische Assets cachen
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
NGINX_EOF

# Platzhalter ersetzen
sed -i "s|DOMAIN_PLACEHOLDER|${DOMAIN}|g" /etc/nginx/sites-available/arena
sed -i "s|INSTALL_DIR_PLACEHOLDER|${INSTALL_DIR}|g" /etc/nginx/sites-available/arena
sed -i "s|BACKEND_PORT_PLACEHOLDER|${BACKEND_PORT}|g" /etc/nginx/sites-available/arena

# Aktivieren
ln -sf /etc/nginx/sites-available/arena /etc/nginx/sites-enabled/arena
rm -f /etc/nginx/sites-enabled/default

nginx -t > /dev/null 2>&1 || err "Nginx-Konfiguration fehlerhaft"
systemctl enable nginx --now
systemctl reload nginx
log "Nginx konfiguriert und gestartet"

# ═══════════════════════════════════════════════════
# 7. Firewall (optional)
# ═══════════════════════════════════════════════════
step "7/8 – Firewall konfigurieren"

if command -v ufw &>/dev/null; then
  ufw allow 80/tcp > /dev/null 2>&1 || true
  ufw allow 443/tcp > /dev/null 2>&1 || true
  ufw allow 22/tcp > /dev/null 2>&1 || true
  log "Ports 80, 443, 22 geöffnet"
else
  warn "UFW nicht gefunden – Firewall manuell konfigurieren"
fi

# ═══════════════════════════════════════════════════
# 8. Abschluss
# ═══════════════════════════════════════════════════
step "8/8 – Abschluss"

# Warte auf Backend-Start
sleep 3
if curl -sf http://127.0.0.1:${BACKEND_PORT}/api/stats > /dev/null 2>&1; then
  log "Backend läuft und antwortet"
else
  warn "Backend startet noch... Prüfe mit: systemctl status arena-backend"
fi

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ARENA eSports Tournament System erfolgreich installiert!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${BOLD}URL:${NC}           http://${DOMAIN}"
echo -e "  ${BOLD}Admin Login:${NC}   ${ADMIN_EMAIL} / ${ADMIN_PASSWORD}"
echo -e "  ${BOLD}Backend API:${NC}   http://${DOMAIN}/api/stats"
echo ""
echo -e "  ${CYAN}Befehle:${NC}"
echo -e "    Status:    ${BOLD}systemctl status arena-backend${NC}"
echo -e "    Logs:      ${BOLD}journalctl -u arena-backend -f${NC}"
echo -e "    Neustart:  ${BOLD}systemctl restart arena-backend${NC}"
echo -e "    Nginx:     ${BOLD}systemctl reload nginx${NC}"
echo ""
echo -e "  ${YELLOW}Optional – SSL mit Let's Encrypt:${NC}"
echo -e "    sudo apt install certbot python3-certbot-nginx"
echo -e "    sudo certbot --nginx -d ${DOMAIN}"
echo ""
