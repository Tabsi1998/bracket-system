# Staging, Release und Rollback

## Staging einmalig einrichten

```bash
cp .env.staging.example .env.staging
nano .env.staging
python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
openssl rand -hex 32
bash scripts/staging-up.sh
```

Die ausgegebenen Zufallswerte als `SETTINGS_ENCRYPTION_KEY`, `JWT_SECRET` und ein separates
Mongo-Passwort eintragen. Staging nutzt eigene Container, Ports, Datenbank und Volumes. Niemals
Produktiv-Secrets oder einen Produktiv-Datenbankdump ohne vorherige Anonymisierung verwenden.

Standardmäßig: Web `127.0.0.1:13000`, API `127.0.0.1:18001`. Der Staging-Reverse-Proxy erhält eine
eigene HTTPS-Domain. Stoppen ohne Datenverlust:

```bash
bash scripts/staging-down.sh
```

## Abnahme

```bash
bash scripts/release-preflight.sh
PUBLIC_AUDIT_BASE_URL=https://staging.example.at corepack yarn --cwd frontend audit:public
```

Zusätzlich manuell testen: Registrierung plus E-Mail-Verifikation, Login/MFA, Google mit eigenem
Client, Passwortreset, erneute Zustimmung, Upload, Turnieranmeldung, Moderationsmeldung,
Admin-Rollen, Testmail und verschlüsseltes Backup samt Restore-Drill.

## Release erstellen

Nur einen grün geprüften Commit markieren:

```bash
git tag -a v2.3.0 -m "TLS platform v2.3.0"
git push origin v2.3.0
```

## Produktiv deployen

```bash
cd /opt/the-lion-squad
bash scripts/deploy-release.sh v2.3.0
```

Das Skript verlangt einen sauberen Worktree, speichert den vorherigen Commit, legt ein
verschlüsseltes Backup an, baut die Container und prüft Backend, Frontend und SPA-Routen.

## Rollback

Wenn nur der Code zurück muss:

```bash
target=$(cat .deploy/previous-release)
ROLLBACK_CONFIRM="$target" bash scripts/rollback-release.sh "$target"
```

Wenn eine Migration Daten inkompatibel verändert hat, zuerst den Dienst stoppen und anschließend
den ausdrücklich bestätigten Restore aus `BACKUP_RESTORE.md` verwenden. Ein DB-Restore ist keine
Standardreaktion auf einen reinen Frontendfehler.

## Go-live

- DNS/Proxy auf den richtigen Loopback-Port, TLS und HTTP→HTTPS prüfen.
- `/api/health/live`, `/api/health/ready` und `/health` extern überwachen.
- Admin-Setup 100 %, MFA für alle Admins, keine unnötigen Rollen.
- Google, SMTP/Resend, Discord und Twitch ausschließlich mit eigenen Zugängen testen.
- Impressum, Datenschutz, Nutzungsbedingungen und Consent-Versionen kontrollieren.
- Backup, Offsite-Kopie und Restore-Drill erfolgreich.
- Browser-Smoke auf Desktop und Mobil; danach Logs und Mailqueue mindestens 30 Minuten beobachten.
