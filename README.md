# ARENA – eSports Tournament System

Vollständiges eSports-Turniersystem mit dynamischen Brackets, Team-Management, Ergebnis-Bestätigung, Admin-Panel und mehr.

![Status](https://img.shields.io/badge/Status-Production_Ready-green) ![License](https://img.shields.io/badge/Lizenz-Privat-blue) ![Stack](https://img.shields.io/badge/Stack-FastAPI_+_React_+_MongoDB-yellow)

---

## Features

| Feature | Beschreibung |
|---------|-------------|
| **Turnierverwaltung** | Single/Double Elimination, Round Robin, Gruppenphase, Gruppenphase+Playoffs, Swiss, Ladder, King of the Hill, Battle Royale, Liga |
| **Teilnehmer-Modus** | Turniere als Team-Modus oder Einzelspieler-Modus (Solo) |
| **14+ Spiele** | CoD, FIFA, Rocket League, CS2, Valorant, LoL, Fortnite u.v.m. – erweiterbar |
| **Rollen-System** | Admin (erstellt Turniere/Spiele) und Spieler (nimmt teil) |
| **Team-Management** | Hauptteam + Sub-Teams, Beitrittscode, Leader-System, Team-Profile mit Banner/Logo/Socials |
| **Ergebnis-System** | Team-Scores mit Auto-Bestätigung oder optionaler Admin-Freigabe; Battle Royale mit Platzierungs-Workflow + Admin-Resolve |
| **Zahlungen** | Stripe und PayPal (umschaltbar via Admin-Settings) |
| **Kommentare** | Kommentare auf Turnier- und Match-Ebene |
| **Benachrichtigungen** | In-App Benachrichtigungsglocke mit Unread-Counter |
| **Admin-Panel** | Dashboard, Benutzer-/Team-/Turnier-/Spiel-Verwaltung, Rollenwechsel, Last-Login, Zahlungs- & SMTP-Einstellungen |
| **Profil-Seiten** | Spieler-Statistiken, Wins/Losses, Team-Zugehörigkeiten |
| **Widget** | Einbettbares iFrame für externe Webseiten |
| **Regelwerk** | Markdown-Rendering für Turnierregeln |

---

## Schnellstart

### Ein-Befehl-Installation (Ubuntu 22.04/24.04)

```bash
sudo bash install.sh
```

Das Skript installiert automatisch:
- Python 3.11+, Node.js 20, Yarn
- MongoDB 7.0
- Nginx als Reverse Proxy
- Systemd Service für den Backend-Server
- Production Build des Frontends
- optional Demo-Daten (Testnutzer, Teams, Turniere in verschiedenen Stati)
- optional Admin-Reset per CLI

Nach der Installation ist die Anwendung unter `http://deine-domain` erreichbar.

### Manuelle Installation

<details>
<summary>Schritt-für-Schritt-Anleitung</summary>

#### Voraussetzungen

- Ubuntu 22.04+ / Debian 12+
- Python 3.11+
- Node.js 18+
- MongoDB 7.0+
- Nginx

#### 1. Repository klonen

```bash
git clone <repo-url> /opt/arena
cd /opt/arena
```

#### 2. Backend einrichten

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.prod.txt
```

Backend `.env` erstellen:

```env
MONGO_URL=mongodb://localhost:27017
DB_NAME=arena_esports
JWT_SECRET=dein-geheimer-schluessel-hier
CORS_ORIGINS=http://localhost:3000,https://deine-domain.de
STRIPE_API_KEY=sk_test_...
PAYPAL_CLIENT_ID=...
PAYPAL_SECRET=...
PAYPAL_MODE=sandbox
```

Backend starten:

```bash
uvicorn server:app --host 0.0.0.0 --port 8001
```

#### 3. Frontend einrichten

```bash
cd frontend
```

Frontend `.env` erstellen:

```env
REACT_APP_BACKEND_URL=https://deine-domain.de
```

Für Production:

```bash
yarn install
yarn build
# Build-Ordner über Nginx ausliefern
```

Für Entwicklung:

```bash
yarn install
yarn start
```

#### 4. Nginx konfigurieren

```nginx
server {
    listen 80;
    server_name deine-domain.de;

    root /opt/arena/frontend/build;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

#### 5. SSL mit Let's Encrypt (empfohlen)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d deine-domain.de
```

</details>

---

## Architektur

```
arena/
├── backend/
│   ├── server.py              # FastAPI – alle API-Endpunkte
│   ├── seed_demo_data.py      # Demo-Daten erzeugen (optional)
│   ├── requirements.prod.txt  # Python-Abhängigkeiten (Production)
│   └── .env                   # Konfiguration (wird beim Install erstellt)
├── frontend/
│   ├── src/
│   │   ├── context/AuthContext.js     # JWT Auth State
│   │   ├── components/
│   │   │   ├── Navbar.js              # Navigation (rollenbasiert)
│   │   │   ├── BracketView.js         # Bracket mit Bezier-SVG
│   │   │   ├── CommentSection.js      # Kommentar-Komponente
│   │   │   └── NotificationBell.js    # Benachrichtigungen
│   │   └── pages/
│   │       ├── HomePage.js
│   │       ├── LoginPage.js / RegisterPage.js
│   │       ├── TournamentsPage.js / TournamentDetailPage.js
│   │       ├── CreateTournamentPage.js   # Nur Admin
│   │       ├── GamesPage.js
│   │       ├── TeamsPage.js
│   │       ├── AdminPage.js              # Nur Admin
│   │       ├── ProfilePage.js
│   │       └── WidgetPage.js             # Einbettbar
│   └── .env
├── install.sh                 # Ein-Befehl-Installer
├── update.sh                  # Produktions-Update inkl. Admin-Reset/Demo-Seed
└── README.md
```

**Tech-Stack:**

| Komponente | Technologie |
|-----------|-------------|
| Backend | FastAPI (Python) |
| Datenbank | MongoDB 7.0 |
| Frontend | React 19, Tailwind CSS, Shadcn/UI, Framer Motion |
| Auth | JWT (python-jose + bcrypt) |
| Zahlungen | Stripe + PayPal |
| Reverse Proxy | Nginx |

---

## Rollen & Berechtigungen

| Aktion | Admin | Spieler | Gast |
|--------|:-----:|:-------:|:----:|
| Turniere ansehen | ✅ | ✅ | ✅ |
| Für Turnier registrieren | ✅ | ✅ | ✅ |
| Turnier erstellen/bearbeiten | ✅ | ❌ | ❌ |
| Bracket generieren | ✅ | ❌ | ❌ |
| Spiele hinzufügen/löschen | ✅ | ❌ | ❌ |
| Ergebnis eintragen | ✅ | ✅* | ❌ |
| Streitfall lösen / Disqualifizierung | ✅ | ❌ | ❌ |
| Team erstellen / beitreten | ✅ | ✅ | ❌ |
| Kommentieren | ✅ | ✅ | ❌ |
| Admin-Panel | ✅ | ❌ | ❌ |

*\* Nur Team-Owner oder Leader können Ergebnisse für ihr Team eintragen.*

---

## Ergebnis-System

Das Ergebnis-System funktioniert in drei Stufen:

1. **Team A** trägt das Ergebnis ein (z.B. 3:1)
2. **Team B** trägt das Ergebnis ein (z.B. 3:1)
3. **Automatische Bestätigung** wenn beide Ergebnisse übereinstimmen

Bei Unstimmigkeiten:
- Match wird als **"Streitfall"** markiert
- Admins werden **automatisch benachrichtigt**
- Admin prüft die Einreichungen und setzt das **endgültige Ergebnis**
- Optional: Admin kann ein Team **disqualifizieren**

---

## Team-System

- **Team erstellen**: Jedes Team erhält einen automatischen 6-stelligen Beitrittscode
- **Beitreten**: Spieler treten mit Team-ID + Beitrittscode bei
- **Leader**: Owner kann Mitglieder zu "Leadern" befördern (können Ergebnisse eintragen)
- **Hauptteam + Sub-Teams**: Sub-Teams für einzelne Ligen/Spiele (z.B. "Alpha CoD", "Alpha FIFA")
- **Profil-Vererbung**: Sub-Teams übernehmen standardmäßig Banner, Logo, Tag und Social-Links vom Hauptteam
- **Turnierregistrierung**:
  - Team-Modus: Registrierung über Sub-Teams
  - Solo-Modus: Registrierung über den Benutzer (ohne Team)
- **Öffentliche Teamliste**: Gast- und Spieleransicht mit Team-Finder, Sub-Team-Übersicht und Social-Links (Discord/Website/X/Instagram/Twitch/YouTube)
- **Verwaltung**: Owner sieht Team-ID und Code, kann Code erneuern und Profil zentral pflegen

---

## API-Endpunkte

<details>
<summary>Vollständige API-Referenz</summary>

### Authentifizierung

| Methode | Endpunkt | Beschreibung |
|---------|----------|-------------|
| POST | `/api/auth/register` | Benutzer registrieren |
| POST | `/api/auth/login` | Einloggen → JWT Token |
| GET | `/api/auth/me` | Aktuellen Benutzer abrufen |

### Turniere (Admin)

| Methode | Endpunkt | Beschreibung |
|---------|----------|-------------|
| GET | `/api/tournaments` | Alle Turniere auflisten |
| POST | `/api/tournaments` | Turnier erstellen (Admin) |
| GET | `/api/tournaments/:id` | Turnier-Details |
| PUT | `/api/tournaments/:id` | Turnier bearbeiten (Admin) |
| DELETE | `/api/tournaments/:id` | Turnier löschen (Admin) |
| POST | `/api/tournaments/:id/generate-bracket` | Bracket generieren (Admin) |

### Registrierung & Check-in

| Methode | Endpunkt | Beschreibung |
|---------|----------|-------------|
| POST | `/api/tournaments/:id/register` | Für Turnier registrieren |
| GET | `/api/tournaments/:id/registrations` | Teilnehmer auflisten |
| POST | `/api/tournaments/:id/checkin/:regId` | Check-in |

### Ergebnisse

| Methode | Endpunkt | Beschreibung |
|---------|----------|-------------|
| POST | `/api/tournaments/:id/matches/:matchId/submit-score` | Ergebnis einreichen (Team) |
| GET | `/api/tournaments/:id/matches/:matchId/submissions` | Eingereichte Ergebnisse |
| PUT | `/api/tournaments/:id/matches/:matchId/resolve` | Streit lösen (Admin) |
| PUT | `/api/tournaments/:id/matches/:matchId/score` | Ergebnis direkt setzen (Admin) |
| POST | `/api/tournaments/:id/matches/:matchId/submit-battle-royale` | BR-Platzierungen einreichen |
| GET | `/api/tournaments/:id/matches/:matchId/battle-royale-submissions` | BR-Einreichungen ansehen |
| PUT | `/api/tournaments/:id/matches/:matchId/battle-royale-resolve` | BR-Ergebnis freigeben (Admin) |

### Teams

| Methode | Endpunkt | Beschreibung |
|---------|----------|-------------|
| GET | `/api/teams` | Eigene Teams auflisten |
| GET | `/api/teams/public` | Öffentliche Teamliste (inkl. Sub-Teams) |
| GET | `/api/teams/registerable-sub-teams` | Eigene registrierbare Sub-Teams |
| POST | `/api/teams` | Team erstellen |
| POST | `/api/teams/join` | Team beitreten (ID + Code) |
| DELETE | `/api/teams/:id` | Team löschen (Owner) |
| POST | `/api/teams/:id/members` | Mitglied hinzufügen (E-Mail) |
| DELETE | `/api/teams/:id/members/:userId` | Mitglied entfernen |
| PUT | `/api/teams/:id/leaders/:userId` | Zum Leader befördern |
| DELETE | `/api/teams/:id/leaders/:userId` | Leader-Rechte entziehen |
| GET | `/api/teams/:id/sub-teams` | Sub-Teams auflisten |
| PUT | `/api/teams/:id/regenerate-code` | Beitrittscode erneuern |

### Spiele (Admin)

| Methode | Endpunkt | Beschreibung |
|---------|----------|-------------|
| GET | `/api/games` | Alle Spiele auflisten |
| POST | `/api/games` | Spiel hinzufügen (Admin) |
| PUT | `/api/games/:id` | Spiel bearbeiten (Admin) |
| DELETE | `/api/games/:id` | Spiel löschen (Admin) |

### Kommentare

| Methode | Endpunkt | Beschreibung |
|---------|----------|-------------|
| GET | `/api/tournaments/:id/comments` | Turnier-Kommentare |
| POST | `/api/tournaments/:id/comments` | Kommentar schreiben |
| GET | `/api/matches/:id/comments` | Match-Kommentare |
| POST | `/api/matches/:id/comments` | Match-Kommentar schreiben |

### Benachrichtigungen

| Methode | Endpunkt | Beschreibung |
|---------|----------|-------------|
| GET | `/api/notifications` | Benachrichtigungen auflisten |
| GET | `/api/notifications/unread-count` | Ungelesene Anzahl |
| PUT | `/api/notifications/:id/read` | Als gelesen markieren |
| PUT | `/api/notifications/read-all` | Alle gelesen markieren |

### Payments

| Methode | Endpunkt | Beschreibung |
|---------|----------|-------------|
| POST | `/api/payments/create-checkout` | Payment-Checkout erzeugen (Stripe oder PayPal) |
| GET | `/api/payments/status/:sessionId` | Payment-Status prüfen und Registrierung auf paid setzen |

### Admin

| Methode | Endpunkt | Beschreibung |
|---------|----------|-------------|
| GET | `/api/admin/dashboard` | Dashboard-Statistiken |
| GET | `/api/admin/users` | Benutzer-Verwaltung |
| PUT | `/api/admin/users/:id/role` | Benutzerrolle (admin/user) ändern |
| DELETE | `/api/admin/users/:id` | Benutzer inkl. zugehöriger Daten löschen |
| GET | `/api/admin/teams` | Team-Verwaltung (alle Teams) |
| DELETE | `/api/admin/teams/:id` | Beliebiges Team löschen |
| GET | `/api/admin/settings` | Einstellungen abrufen |
| PUT | `/api/admin/settings` | Einstellung speichern |

### Widget & Profil

| Methode | Endpunkt | Beschreibung |
|---------|----------|-------------|
| GET | `/api/widget/tournament/:id` | Widget-Daten |
| GET | `/api/users/:id/profile` | Benutzerprofil |
| GET | `/api/stats` | Öffentliche Statistiken |

</details>

---

## Konfiguration

### Backend `.env`

| Variable | Beschreibung | Pflicht |
|----------|-------------|:-------:|
| `MONGO_URL` | MongoDB Verbindungs-URL | ✅ |
| `DB_NAME` | Datenbankname | ✅ |
| `JWT_SECRET` | Geheimer Schlüssel für Token-Signierung | ✅ |
| `CORS_ORIGINS` | Erlaubte Origins (kommagetrennt) | ✅ |
| `STRIPE_API_KEY` | Stripe Secret Key für Zahlungen | Optional |
| `PAYPAL_CLIENT_ID` | PayPal Client ID | Optional |
| `PAYPAL_SECRET` | PayPal Secret | Optional |
| `PAYPAL_MODE` | `sandbox` oder `live` | Optional |
| `ADMIN_EMAIL` | Seed/Admin-Reset Default E-Mail | Optional |
| `ADMIN_USERNAME` | Seed/Admin-Reset Default Username | Optional |

### Frontend `.env`

| Variable | Beschreibung | Pflicht |
|----------|-------------|:-------:|
| `REACT_APP_BACKEND_URL` | URL zum Backend (z.B. `https://arena.example.com`) | ✅ |

### Admin-Panel Einstellungen

Folgende Einstellungen können im Admin-Panel konfiguriert werden:

- **Payment Provider** – `stripe`, `paypal` oder leer/auto
- **Stripe** – Public Key, Secret Key, Webhook Secret
- **PayPal** – Client ID, Secret, Mode (`sandbox`/`live`)
- **SMTP** – Host, Port, Benutzer, Passwort (für E-Mail-Benachrichtigungen)

---

## Updates (Production)

Standard-Update:

```bash
./update.sh
```

Nützliche Optionen:

```bash
# Update trotz lokaler Änderungen
./update.sh --force

# Admin-Konto direkt zurücksetzen/erstellen
./update.sh --admin-reset --admin-email admin@arena.gg --admin-password 'NeuesPasswort'

# Demo-Daten importieren
./update.sh --seed-demo

# Demo-Daten vorher zurücksetzen und neu importieren
./update.sh --seed-demo-reset
```

---

## Widget einbetten

Kopiere den folgenden Code in deine Webseite:

```html
<iframe
  src="https://deine-domain.de/widget/TURNIER_ID"
  width="100%"
  height="400"
  frameborder="0"
  style="border-radius: 12px; overflow: hidden;">
</iframe>
```

Den Embed-Code findest du auch auf der Turnier-Detailseite unter dem Tab **"Info & Regeln"**.

---

## Verwaltung

```bash
# Service-Status prüfen
sudo systemctl status arena-backend

# Logs anzeigen
sudo journalctl -u arena-backend -f

# Backend neustarten
sudo systemctl restart arena-backend

# Nginx neustarten
sudo systemctl reload nginx

# MongoDB Shell
mongosh arena_esports
```

---

## Entwicklung

```bash
# Backend (mit Hot-Reload)
cd backend
source venv/bin/activate
uvicorn server:app --host 0.0.0.0 --port 8001 --reload

# Frontend (Dev-Server)
cd frontend
yarn start
```

---

## Lizenz

Privat – Alle Rechte vorbehalten.
