# THE LION SQUAD eSports

[![CI](https://github.com/Tabsi1998/THE-LION_SQUAD-eSPORT-Webseite/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Tabsi1998/THE-LION_SQUAD-eSPORT-Webseite/actions/workflows/ci.yml)
[![CodeQL](https://github.com/Tabsi1998/THE-LION_SQUAD-eSPORT-Webseite/actions/workflows/codeql.yml/badge.svg?branch=main)](https://github.com/Tabsi1998/THE-LION_SQUAD-eSPORT-Webseite/actions/workflows/codeql.yml)

Selbst gehostete Vereins- und eSports-Plattform für THE LION SQUAD: öffentliche
Website, Mitgliederbereich, Teams, Turniere, Fast Lap, Jahreswertung, Nachrichten,
Galerie, Dokumente und Administration.

**[Dokumentation](DOCS.md) · [Installation](INSTALL.md) · [Updates und Fehlerhilfe](UPDATE.md) · [Restplan](RESTPLAN.md)**

## Stand und nächste Schritte

Der [Restplan](RESTPLAN.md) führt offene Arbeit und Abnahmen verbindlich zusammen.
Aktuell haben Update-Zuverlässigkeit, Anmeldung und Dashboard Vorrang. Passkeys
ergänzen Passwort und Google; [Einrichtung und Voraussetzungen](CONFIGURATION.md).
Die native Android-App ist auf Wunsch pausiert. Der größere Turnier-Umbau bleibt
ein eigenes Paket nach [COMPETITION_ENGINE.md](COMPETITION_ENGINE.md).

Die Badges zeigen den aktuellen Prüfstatus von `main`, keine Abnahme des
Produktivservers. Dazu gehören [Praxistest](STAGING_ABNAHME.md),
[Backup-/Restore-Nachweis](BACKUP_RESTORE.md) und [Release-Freigabe](RELEASE.md).

## Betrieb

Erstinstallation mit eigener `.env` nach [INSTALL.md](INSTALL.md).
Eine bestehende Installation aktualisieren:

```bash
cd /root/THE-LION_SQUAD-eSPORT-Webseite
./update.sh u
```

Bei `createUser requires authentication`, ausbleibenden Bestätigungen oder
veralteten Browseransichten zuerst die [Update-Fehlerhilfe](UPDATE.md) verwenden.
MongoDB- und Upload-Volumes enthalten die Bestandsdaten.

Eigene Google-, SMTP-/Resend-, Discord- und Twitch-Zugänge werden über die
[Betreiberkonfiguration](CONFIGURATION.md) eingerichtet. Geheimnisse gehören in
die geschützte `.env` bzw. verschlüsselte Einstellungen im Adminbereich.

## Aufbau

| Verzeichnis | Inhalt |
| --- | --- |
| `backend/` | FastAPI, MongoDB, Auth, Fachlogik und Backend-Tests |
| `frontend/` | React 19, Vite, Tailwind, Nginx und Browser-Tests |
| `mobile/` | Native Expo-App; Weiterentwicklung derzeit pausiert |
| `scripts/` | Update-Prüfungen, Backups, Restore und Staging |
| `.github/workflows/` | CI, Container-Smoke, CodeQL und Android-Builds |

Die Website läuft hinter dem eigenen HTTPS-Reverse-Proxy. API-Pfad: `/api`.
Anmeldung: HttpOnly-Cookies mit CSRF-Schutz, E-Mail-Bestätigung, optionale Passkeys,
eigener Google-Login und MFA für Adminfunktionen.

## Entwicklung und Prüfungen

Backend: Python 3.11; Frontend: Node 24 und Yarn gemäß Lockfile.
Anleitungen: [Frontend](frontend/README.md), [Live-/Staging-Tests](LIVE_TESTS.md),
[Leistungsbudgets](frontend/PERFORMANCE_BUDGETS.md).

```bash
python -m pytest -m "not live"
python scripts/check-doc-links.py
cd frontend
corepack yarn install --frozen-lockfile
corepack yarn test
corepack yarn build
```

Benötigte Python-Pakete stehen in `backend/requirements.txt` und
`backend/requirements-dev.txt`. Schreibende Live-Tests laufen ausschließlich auf
einem dafür vorbereiteten Teststack. Die [CI-Workflows](https://github.com/Tabsi1998/THE-LION_SQUAD-eSPORT-Webseite/actions)
enthalten die verbindlichen automatischen Prüfungen; [Releases](https://github.com/Tabsi1998/THE-LION_SQUAD-eSPORT-Webseite/releases)
dokumentieren veröffentlichte Artefakte.

## Lizenz

Proprietär. Nutzung und Weitergabe nur für THE LION SQUAD bzw. nach Freigabe.
