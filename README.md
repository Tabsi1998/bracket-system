# ARENA – eSports Tournament System

Vollständiges eSports-Turniersystem mit FastAPI + React + MongoDB für Team- und Solo-Turniere.

Dokumentationsstand: 2026-02-16 (entspricht dem aktuellen Code in `main`).

![Status](https://img.shields.io/badge/Status-Production_Ready-green) ![License](https://img.shields.io/badge/Lizenz-Privat-blue) ![Stack](https://img.shields.io/badge/Stack-FastAPI_+_React_+_MongoDB-yellow)

---

## Überblick

ARENA deckt den kompletten Flow ab:

- Benutzer-Registrierung/Login mit JWT
- Team-Management mit Hauptteam + Sub-Teams
- Turniere mit mehreren Bracket-Formaten
- Liga-/Round-Robin-Spieltage mit Zeitfenstern
- Match-Hub pro Match (Termin, Setup, Kommentare, Ergebnis)
- Spielmodus-Templates für Match-Settings (Kategorie-Defaults + Overrides)
- Score-Submission mit Auto-Confirm/Dispute/Admin-Resolve
- Battle-Royale-Heats mit Placement-Workflow
- Check-in, Payments (Stripe + PayPal) inkl. Retry-Flow
- Kommentare, Benachrichtigungen, Match-Terminabstimmung
- Admin-Panel (User/Team/Turnier/Spiel/Settings + PayPal-Validation)
- Profilseiten und Widget-Einbettung

---

## Kernfunktionen

| Bereich | Status |
|---|---|
| Auth (Register/Login/Me) | ✅ |
| Team-System (Main/Sub, Join-Code, Leader) | ✅ |
| Öffentliche Teamliste mit Team Finder | ✅ |
| Turniere (Create/Update/Delete/Register/Check-in + Matchday/Punkte-Config) | ✅ |
| Brackets (11 Formate) | ✅ |
| Tabellen/Standings API (konfigurierbares Punktesystem) | ✅ |
| Matchday-API (Spieltage + Statusaggregation) | ✅ |
| Match-Scheduling (Vorschläge/Accept + Bracket `scheduled_for` Sync) | ✅ |
| Match-Setup-Workflow (Team A/B Confirm + Admin Resolve) | ✅ |
| Score-Workflow inkl. Dispute/Admin-Resolve | ✅ |
| Battle Royale Workflow inkl. Admin-Resolve | ✅ |
| Zahlungen (Stripe + PayPal, Provider-Hardening, Retry) | ✅ |
| PayPal Admin-Validierung + Provider-Status | ✅ |
| Stripe Webhook | ✅ |
| SMTP-Test + Check-in-Reminder | ✅ |
| Admin-Panel (Users/Teams/Games/Tournaments/Settings) | ✅ |
| Profil bearbeiten (User selbst) | ✅ |
| Widget-API + Frontend-Widgetseite (`view=bracket|standings|matchdays`) | ✅ |

---

## Unterstützte Formate

Interner `bracket_type` in der API:

- `single_elimination`
- `double_elimination`
- `round_robin`
- `group_stage`
- `group_playoffs`
- `swiss_system`
- `ladder_system`
- `king_of_the_hill`
- `battle_royale`
- `league`

Teilnehmermodus:

- `team`
- `solo`

Hinweise:

- `battle_royale` erzwingt `require_admin_score_approval=true`.
- `solo` erzwingt `team_size=1`.
- `group_playoffs` generiert die Playoffs automatisch nach Abschluss der Gruppen.
- `swiss_system`, `ladder_system` und `king_of_the_hill` erweitern das Bracket dynamisch.

---

## Rollen & Rechte

| Aktion | Gast | User | Admin |
|---|:---:|:---:|:---:|
| Turniere ansehen | ✅ | ✅ | ✅ |
| Spiele ansehen | ✅ | ✅ | ✅ |
| Registrieren für Turnier | ❌ | ✅ | ✅ |
| Team erstellen/joinen | ❌ | ✅ | ✅ |
| Turniere erstellen/bearbeiten/löschen | ❌ | ❌ | ✅ |
| Bracket generieren | ❌ | ❌ | ✅ |
| Score einreichen (eigenes Team/Solo) | ❌ | ✅ | ✅ |
| Streitfall lösen / Score direkt setzen | ❌ | ❌ | ✅ |
| BR-Heat final freigeben | ❌ | ❌ | ✅ |
| Admin-Panel | ❌ | ❌ | ✅ |

---

## Architektur

```text
bracket-system/
├── backend/
│   ├── server.py
│   ├── seed_demo_data.py
│   ├── requirements.prod.txt
│   ├── requirements.txt
│   └── tests/
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   └── context/
│   ├── package.json
│   └── README.md
├── install.sh
├── update.sh
├── backend_test.py
└── README.md
```

Stack:

- Backend: FastAPI, Motor/PyMongo, Pydantic v2, python-jose, bcrypt, Stripe SDK
- Frontend: React 19, React Router, Tailwind, Shadcn UI, Framer Motion
- DB: MongoDB
- Runtime: Uvicorn
- Reverse Proxy: Nginx

---

## Installation

### Option A: Ein-Befehl-Installer (empfohlen für Ubuntu Server)

```bash
sudo bash install.sh
```

`install.sh` macht automatisch:

- Systempakete installieren
- Node.js 20 + Yarn installieren
- MongoDB 8.0 installieren/aktivieren
- Backend-Venv + Dependencies installieren
- `backend/.env` erzeugen
- Frontend bauen
- `arena-backend` systemd-Service anlegen/starten
- Nginx konfigurieren und reloaden
- optional Demo-Daten importieren

### Option B: Manuell

1. Backend:

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.prod.txt
uvicorn server:app --host 0.0.0.0 --port 8001
```

2. Frontend:

```bash
cd frontend
yarn install
yarn build
```

3. Nginx so konfigurieren, dass:

- `/api/*` auf `http://127.0.0.1:8001` proxyt
- alle anderen Routen auf `frontend/build/index.html` fallen

---

## Konfiguration

### Backend `.env`

| Variable | Pflicht | Beschreibung |
|---|:---:|---|
| `MONGO_URL` | ✅ | MongoDB URI |
| `DB_NAME` | ✅ | Datenbankname |
| `JWT_SECRET` | ✅ | JWT Secret |
| `CORS_ORIGINS` | ✅ | Kommaseparierte Origins |
| `STRIPE_API_KEY` | Optional | Stripe Secret Key |
| `STRIPE_WEBHOOK_SECRET` | Optional | Stripe Webhook Secret |
| `PAYPAL_CLIENT_ID` | Optional | PayPal Client ID |
| `PAYPAL_SECRET` | Optional | PayPal Secret |
| `PAYPAL_MODE` | Optional | `sandbox` oder `live` |
| `ADMIN_EMAIL` | Optional | Seed/Admin-Ensure E-Mail (Default `admin@arena.gg`) |
| `ADMIN_PASSWORD` | Optional | Seed/Admin-Ensure Passwort (Default `admin123`) |
| `ADMIN_USERNAME` | Optional | Seed/Admin-Ensure Username |
| `ADMIN_FORCE_PASSWORD_RESET` | Optional | `true` setzt Admin-Passwort beim Startup neu |
| `DEMO_USER_PASSWORD` | Optional | Passwort für Demo-User in `seed_demo_data.py` |

### Frontend `.env`

| Variable | Pflicht | Beschreibung |
|---|:---:|---|
| `REACT_APP_BACKEND_URL` | Optional | Backend-Base-URL. Leer = same-origin (`/api`) |

---

## Admin Settings (`/api/admin/settings`)

Diese Keys werden im Admin-Bereich gepflegt:

- `payment_provider` (`stripe`, `paypal`, leer/`auto`)
- `stripe_public_key`
- `stripe_secret_key`
- `stripe_webhook_secret`
- `paypal_client_id`
- `paypal_secret`
- `paypal_mode` (`sandbox`/`live`)
- `paypal_last_validation_status` (automatisch)
- `paypal_last_validation_detail` (automatisch)
- `paypal_last_validation_checked_at` (automatisch)
- `smtp_host`
- `smtp_port`
- `smtp_user`
- `smtp_password`
- `smtp_from_name`
- `smtp_from_email`
- `smtp_reply_to`
- `smtp_use_starttls`
- `smtp_use_ssl`

Payment-Provider-Auswahl in der API:

1. explizit über Request (`provider`)
2. sonst `admin_settings.payment_provider`
3. sonst Auto-Fallback: PayPal wenn Client-ID+Secret vorhanden, sonst Stripe

---

## Team-System (Main/Sub)

- Main-Teams sind organisatorische Stammteams.
- Sub-Teams sind Turnier-aktive Teams.
- Team-Registrierung (`participant_mode=team`) funktioniert nur mit Sub-Team.
- Profilfelder (Bio, Logo, Banner, Socials, Tag) werden für Sub-Teams vom Main-Team geerbt, wenn das Sub-Team den Wert nicht gesetzt hat.
- Änderungen an Main-Team-Logo/Banner/Tag werden als Fallback in leere Sub-Team-Felder propagiert.
- Öffentliche Teamliste (`GET /api/teams/public`) zeigt Main-Teams inkl. Sub-Teams ohne sensible Felder.

Rechte im Team:

- Owner: Vollzugriff + Join-Code regenerieren + Leader verwalten
- Leader: Teamprofil bearbeiten, Mitglieder verwalten
- Member: Teilnahme/Registrierung je nach Endpoint

---

## Liga, Matchdays, Match-Hub

Turniere unterstützen zusätzliche Liga-/Matchday-Konfiguration:

- `matchday_interval_days` (Default `7`)
- `matchday_window_days` (Default `7`)
- `points_win`, `points_draw`, `points_loss`
- `tiebreakers` (Default: `points,score_diff,score_for,team_name`)

Für `round_robin`, `league`, `group_stage` und `group_playoffs` enthält jede Runde:

- `matchday`
- `window_start`
- `window_end`

Der Match-Hub (`/tournaments/:id/matches/:matchId`) bündelt:

- Terminabstimmung inkl. Accept-Flow
- Match-Setup JSON pro Teamseite
- Konflikterkennung (`disputed`) + Admin-Resolve
- Match-Kommentare
- Ergebnis-Submission

---

## Ergebnis- und Match-Workflow

### Standard-Score (`submit-score`)

- Team A und Team B reichen separat ein.
- Bei identischen Scores:
  - direkt bestätigt, oder
  - bei `require_admin_score_approval=true`: Status `pending_admin_approval` bis Admin bestätigt.
- Bei abweichenden Scores: `disputed` + Admin-Benachrichtigung.
- Admin kann final mit `/resolve` entscheiden oder `/score` direkt setzen.

### Battle Royale

- Heats mit Teilnehmerliste, Placements und Points-Map.
- Teams/Spieler reichen Placements ein (`submit-battle-royale`).
- Optional Admin-Freigabe (`battle-royale-resolve`).
- Bei komplettem Round-Abschluss werden nächste Heats automatisch erzeugt.

### Match Scheduling

- Zeitvorschläge pro Match (`/matches/{id}/schedule`).
- Annahme eines Vorschlags setzt alle anderen auf `rejected`.
- Akzeptierter Termin wird zusätzlich persistent in `match.scheduled_for` im Bracket gespeichert.

### Match Setup (neu)

- Endpoints: `GET/POST /api/matches/{match_id}/setup`, `PUT /api/matches/{match_id}/setup/resolve`.
- Team A und Team B reichen Setup-JSON ein.
- Identische Inputs => `confirmed`.
- Unterschiedliche Inputs => `disputed`.
- Admin kann final auflösen (`resolved_by_admin`).

---

## Zahlungsprozess

### Checkout

- Endpoint: `POST /api/payments/create-checkout`
- Erzeugt Stripe Checkout Session oder PayPal Order.
- Rückgabe enthält Redirect-URL.
- Bei PayPal wird vor Checkout aktiv validiert (Credentials + Mode).
- Bei ungültiger PayPal-Konfiguration wird Checkout blockiert (z. B. `invalid_client`).
- Pending-Registrierungen können Checkout erneut starten (Retry ohne Neuregistrierung).

### Status

- Endpoint: `GET /api/payments/status/{session_id}`
- Auth erforderlich.
- Setzt bei Erfolg `registrations.payment_status = paid`.

### Check-in-Hardening

- Bei `entry_fee > 0` ist Check-in nur mit `payment_status = paid` erlaubt.

### Stripe Webhook

- Endpoint: `POST /api/webhook/stripe`
- Verarbeitet `checkout.session.completed` und setzt Zahlung auf `paid`.

Hinweis:

- PayPal wird im aktuellen Stand über Status-Polling/Order-Capture verarbeitet.

---

## Vollständige API-Referenz

### Auth

| Methode | Endpoint | Auth | Beschreibung |
|---|---|---|---|
| POST | `/api/auth/register` | ❌ | Benutzer registrieren |
| POST | `/api/auth/login` | ❌ | Login |
| GET | `/api/auth/me` | ✅ | Aktueller Benutzer |

### Teams

| Methode | Endpoint | Auth | Beschreibung |
|---|---|---|---|
| GET | `/api/teams` | ✅ | Eigene Main-Teams |
| GET | `/api/teams/registerable-sub-teams` | ✅ | Eigene registrierbare Sub-Teams |
| GET | `/api/teams/public` | ❌ | Öffentliche Teamliste |
| POST | `/api/teams` | ✅ | Team/Sub-Team erstellen |
| GET | `/api/teams/{team_id}` | Optional | Team abrufen |
| PUT | `/api/teams/{team_id}` | ✅ | Team bearbeiten |
| DELETE | `/api/teams/{team_id}` | ✅ | Team als Owner löschen |
| POST | `/api/teams/join` | ✅ | Team via Join-Code beitreten |
| PUT | `/api/teams/{team_id}/regenerate-code` | ✅ | Join-Code regenerieren (Owner) |
| POST | `/api/teams/{team_id}/members` | ✅ | Mitglied per E-Mail hinzufügen |
| DELETE | `/api/teams/{team_id}/members/{member_id}` | ✅ | Mitglied entfernen |
| PUT | `/api/teams/{team_id}/leaders/{user_id}` | ✅ | Mitglied zum Leader machen (Owner) |
| DELETE | `/api/teams/{team_id}/leaders/{user_id}` | ✅ | Leader zurückstufen (Owner) |
| GET | `/api/teams/{team_id}/sub-teams` | ✅ | Sub-Teams eines Main-Teams |

### Games

| Methode | Endpoint | Auth | Beschreibung |
|---|---|---|---|
| GET | `/api/games` | ❌ | Spieleliste (inkl. `modes[].settings_template`) |
| POST | `/api/games` | Admin | Spiel erstellen (Templates werden normalisiert) |
| GET | `/api/games/{game_id}` | ❌ | Spieldetails |
| PUT | `/api/games/{game_id}` | Admin | Spiel bearbeiten (Mode-Template-Overrides möglich) |
| DELETE | `/api/games/{game_id}` | Admin | Spiel löschen |

### Tournaments

| Methode | Endpoint | Auth | Beschreibung |
|---|---|---|---|
| GET | `/api/tournaments` | ❌ | Turnierliste (`status`, `game_id` optional) |
| POST | `/api/tournaments` | Admin | Turnier erstellen |
| GET | `/api/tournaments/{tournament_id}` | ❌ | Turnierdetails |
| PUT | `/api/tournaments/{tournament_id}` | Admin | Turnier bearbeiten |
| DELETE | `/api/tournaments/{tournament_id}` | Admin | Turnier löschen |
| GET | `/api/tournaments/{tournament_id}/registrations` | Optional | Teilnehmerliste |
| GET | `/api/tournaments/{tournament_id}/my-registrations` | ✅ | Eigene Registrierungen inkl. `can_retry_payment` |
| POST | `/api/tournaments/{tournament_id}/register` | ✅ | Registrierung |
| GET | `/api/tournaments/{tournament_id}/standings` | ❌ | Tabelle/Standings |
| GET | `/api/tournaments/{tournament_id}/matchdays` | ❌ | Spieltage + Fenster + Matchstatus |
| POST | `/api/tournaments/{tournament_id}/checkin/{registration_id}` | ✅ | Check-in |
| POST | `/api/tournaments/{tournament_id}/generate-bracket` | Admin | Bracket generieren |

### Match Hub / Setup

| Methode | Endpoint | Auth | Beschreibung |
|---|---|---|---|
| GET | `/api/matches/{match_id}` | ✅ | Match-Detail (Kontext, Setup, Schedule, Viewer-Rechte) |
| GET | `/api/matches/{match_id}/setup` | ✅ | Setup-Daten + Mode-Template |
| POST | `/api/matches/{match_id}/setup` | ✅ | Setup einreichen (Teamseite) |
| PUT | `/api/matches/{match_id}/setup/resolve` | Admin | Setup-Konflikt finalisieren |

### Match Scoring / BR

| Methode | Endpoint | Auth | Beschreibung |
|---|---|---|---|
| POST | `/api/tournaments/{tournament_id}/matches/{match_id}/submit-score` | ✅ | Score einreichen |
| GET | `/api/tournaments/{tournament_id}/matches/{match_id}/submissions` | ✅ | Score-Submissions abrufen |
| PUT | `/api/tournaments/{tournament_id}/matches/{match_id}/resolve` | Admin | Dispute auflösen |
| PUT | `/api/tournaments/{tournament_id}/matches/{match_id}/score` | Admin | Score direkt setzen |
| POST | `/api/tournaments/{tournament_id}/matches/{match_id}/submit-battle-royale` | ✅ | BR-Placements einreichen |
| GET | `/api/tournaments/{tournament_id}/matches/{match_id}/battle-royale-submissions` | ✅ | BR-Submissions |
| PUT | `/api/tournaments/{tournament_id}/matches/{match_id}/battle-royale-resolve` | Admin | BR final freigeben |

### Payments

| Methode | Endpoint | Auth | Beschreibung |
|---|---|---|---|
| POST | `/api/payments/create-checkout` | ✅ | Stripe/PayPal Checkout erzeugen (PayPal-Validierung aktiv) |
| GET | `/api/payments/status/{session_id}` | ✅ | Zahlungsstatus prüfen |
| POST | `/api/webhook/stripe` | ❌ | Stripe Webhook |

### Profile / Users

| Methode | Endpoint | Auth | Beschreibung |
|---|---|---|---|
| PUT | `/api/users/me/account` | ✅ | Eigenes Konto bearbeiten |
| PUT | `/api/users/me/password` | ✅ | Eigenes Passwort ändern |
| GET | `/api/users/{user_id}/profile` | ❌ | Profil + Teams + Turniere + Stats |

### Comments

| Methode | Endpoint | Auth | Beschreibung |
|---|---|---|---|
| GET | `/api/tournaments/{tournament_id}/comments` | ❌ | Turnier-Kommentare |
| POST | `/api/tournaments/{tournament_id}/comments` | ✅ | Turnier-Kommentar |
| GET | `/api/matches/{match_id}/comments` | ❌ | Match-Kommentare |
| POST | `/api/matches/{match_id}/comments` | ✅ | Match-Kommentar |

### Notifications

| Methode | Endpoint | Auth | Beschreibung |
|---|---|---|---|
| GET | `/api/notifications` | ✅ | Eigene Notifications |
| GET | `/api/notifications/unread-count` | ✅ | Unread-Count |
| PUT | `/api/notifications/{notification_id}/read` | ✅ | Notification als gelesen |
| PUT | `/api/notifications/read-all` | ✅ | Alle als gelesen |

### Match Scheduling

| Methode | Endpoint | Auth | Beschreibung |
|---|---|---|---|
| GET | `/api/matches/{match_id}/schedule` | ✅ | Zeitvorschläge abrufen |
| POST | `/api/matches/{match_id}/schedule` | ✅ | Zeitvorschlag einreichen |
| PUT | `/api/matches/{match_id}/schedule/{proposal_id}/accept` | ✅ | Vorschlag akzeptieren |

### Widget / Public Stats

| Methode | Endpoint | Auth | Beschreibung |
|---|---|---|---|
| GET | `/api/widget/tournament/{tournament_id}` | ❌ | Widget-Daten (`view=bracket|standings|matchdays`, optional `matchday`) |
| GET | `/api/stats` | ❌ | Öffentliche Zahlen |

### Admin

| Methode | Endpoint | Auth | Beschreibung |
|---|---|---|---|
| GET | `/api/admin/dashboard` | Admin | Dashboard |
| GET | `/api/admin/users` | Admin | Userliste inkl. Team-/Turnierzuordnung |
| PUT | `/api/admin/users/{user_id}/role` | Admin | Rolle ändern |
| DELETE | `/api/admin/users/{user_id}` | Admin | User löschen inkl. Cleanup |
| GET | `/api/admin/teams` | Admin | Teamliste |
| DELETE | `/api/admin/teams/{team_id}` | Admin | Team inkl. Hierarchie löschen |
| GET | `/api/admin/settings` | Admin | Settings lesen |
| PUT | `/api/admin/settings` | Admin | Setting schreiben |
| GET | `/api/admin/payments/providers/status` | Admin | Provider-Status inkl. PayPal-Validation-Metadaten |
| POST | `/api/admin/payments/paypal/validate` | Admin | PayPal Credentials aktiv validieren |
| POST | `/api/admin/email/test` | Admin | SMTP-Testmail |
| POST | `/api/admin/reminders/checkin/{tournament_id}` | Admin | Check-in-Reminder versenden |

---

## Operations

### Update im Betrieb

```bash
./update.sh
```

Wichtige Optionen:

```bash
./update.sh --force
./update.sh --branch main
./update.sh --admin-reset --admin-email admin@arena.gg --admin-password 'NeuesPasswort'
./update.sh --seed-demo
./update.sh --seed-demo-reset
```

### Services / Logs

```bash
sudo systemctl status arena-backend --no-pager -l
sudo journalctl -u arena-backend -f
sudo systemctl restart arena-backend
sudo systemctl reload nginx
```

---

## Demo-Daten

Seed-Script:

```bash
cd backend
source venv/bin/activate
python seed_demo_data.py
python seed_demo_data.py --reset
```

Default-Demo-Login:

- `demo.admin@arena.gg`
- Passwort: `demo123` (oder Wert aus `DEMO_USER_PASSWORD`)

Weitere Demo-User verwenden dasselbe Passwort.

---

## Tests

### API-Tests (pytest)

```bash
cd backend
source venv/bin/activate
pytest tests -v
```

### Erweiterter API-Schnelltest

```bash
python backend_test.py
```

Optional via Env:

- `BACKEND_URL` / `REACT_APP_BACKEND_URL`
- `ADMIN_EMAIL`
- `ADMIN_PASSWORD`

---

## Troubleshooting (wichtig)

### Admin-Login schlägt fehl

1. Prüfe Backend-Env:

```bash
cat backend/.env | grep -E 'ADMIN_EMAIL|ADMIN_PASSWORD|ADMIN_FORCE_PASSWORD_RESET'
```

2. Admin-Konto explizit zurücksetzen:

```bash
./update.sh --admin-reset --admin-email admin@arena.gg --admin-password 'NeuesPasswort'
```

3. Alternativ erzwungen beim Startup:

```env
ADMIN_FORCE_PASSWORD_RESET=true
```

4. Logs prüfen:

```bash
journalctl -u arena-backend -n 120 --no-pager
```

### PayPal `invalid_client` / Checkout schlägt fehl

1. Credentials und Modus prüfen:

```bash
curl -H "Authorization: Bearer <ADMIN_JWT>" \
  -H "Content-Type: application/json" \
  -X POST https://DEINE-DOMAIN/api/admin/payments/paypal/validate
```

2. Achte auf die korrekte Kombination:

- Sandbox Client/Secret nur mit `paypal_mode=sandbox`
- Live Client/Secret nur mit `paypal_mode=live`

3. Provider-Status prüfen:

```bash
curl -H "Authorization: Bearer <ADMIN_JWT>" https://DEINE-DOMAIN/api/admin/payments/providers/status
```

4. Bei abgebrochener/fehlgeschlagener Zahlung im Turnier die Aktion `Jetzt bezahlen` verwenden (Retry auf bestehende Registrierung).

### Nginx wurde nicht neu geladen

- `update.sh` erkennt gängige Nginx-Service-Namen automatisch.
- Falls dein Service abweicht:

```bash
NGINX_SERVICE_NAME=nginx ./update.sh
```

---

## Lizenz

Privat – Alle Rechte vorbehalten.
