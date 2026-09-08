# Update-Anleitung

Der normale Server-Ablauf ist:

```bash
cd /root/THE-LION_SQUAD-eSPORT-Webseite
./update.sh u
```

Das Script zieht den neuesten Code, baut Frontend/Backend neu, startet die Container und prueft Backend, Frontend und wichtige SPA-Routen.

## Danach pruefen

### Bestehendes Konto: „E-Mail-Adresse noch nicht bestätigt“

Vor der verpflichtenden E-Mail-Bestätigung wurden auch Passwort-Konten mit
`email_verified=false` angelegt und konnten sich anmelden. Seit der Härtung
werden diese Konten beim **Passwort-Login vor der MFA-Abfrage** gesperrt, bis
die Adresse bestätigt ist. Ein erneuter Login verschickt keine Mail.
Das Konto muss nicht neu angelegt und das Passwort nicht geändert werden.

1. `https://lionsquad.at/verify-email` öffnen, bisherige E-Mail eintragen und
   den Bestätigungslink einmal anfordern. Einige Minuten warten und Spam prüfen.
2. Link öffnen; danach mit bisherigem Passwort und MFA-/Wiederherstellungscode
   anmelden. MFA stammt aus der Authenticator-App, nicht aus einer Login-E-Mail.
3. Kommt keine Mail: Der Betreiber führt im Server-Checkout folgenden
   **rein lesenden** Bericht aus (Adresse durch die betroffene Adresse ersetzen):

   ```bash
   docker compose exec -T backend python - person@example.test < backend/login_diagnostics.py
   ```

   Der Bericht lässt E-Mail-Adresse, Benutzer-ID, Passwörter, Tokens, Mailtexte
   und rohe Providerfehler weg. Er verändert keine Daten und versendet nichts.
   Nach Aktualisierung des Checkouts ist dafür kein Backend-Neubau nötig.

   - `recent_auth_mail` leer: kein neuer Bestätigungsversand erfasst.
   - `pending`/`sending`: Warteschlange; `scheduler_disabled=true` verhindert
     den automatischen Versand. Status allein beweist keinen laufenden Worker.
   - `skipped`: Versand deaktiviert.
   - `failed` oder `attempts > 0` mit Fehlerkategorie: SMTP/Resend-Konfiguration
     unter **Admin → E-Mail** prüfen. Bei `configuration_readable=false` auch
     den unverändert erforderlichen `SETTINGS_ENCRYPTION_KEY` lokal prüfen;
     Schlüssel niemals hier veröffentlichen oder durch einen neuen ersetzen.
   - `sent`: Mailserver hat angenommen, keine Garantie für Postfachzustellung.
     Spam, Mailserver-Zustellung und Absender-Domain prüfen.

Wenn kein Admin mehr ins Menü kommt, zunächst diesen Bericht auswerten.
Keine pauschale Datenbankänderung aller Konten auf `email_verified=true`, keine
MFA-Deaktivierung und kein Löschen/Neuanlegen des bestehenden Kontos.
Der öffentliche Resend-Endpunkt bestätigt aus Datenschutzgründen weder die
Existenz eines Kontos noch eine erfolgreiche Zustellung.

Referenz: [OWASP – sichere Wiederherstellungsantworten](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html).

```bash
docker compose ps
docker compose logs --tail=100 backend
curl -fsS http://localhost:8001/api/health/live
curl -fsS http://localhost:8001/api/health/ready
```

Oeffentlich pruefen:

- `https://lionsquad.at`
- `https://lionsquad.at/community`
- `https://lionsquad.at/events`
- `https://lionsquad.at/members`

Im Admin:

- `Einstellungen -> Status`
- `Einstellungen -> Discord`
- `Einstellungen -> Twitch`
- ein kleiner Upload-Test

## Daten behalten

MongoDB und Uploads liegen in Docker-Volumes bzw. persistenten Upload-Pfaden.

Nicht ausfuehren, ausser du willst Daten bewusst loeschen:

```bash
docker compose down -v
```

## Wenn public routes alte Assets liefern

`update.sh` prueft unter anderem `/community` und `/seasons/current`. Wenn dort alte Vite-Dateien aus `/assets/` auftauchen:

1. Reverse-Proxy-Cache leeren.
2. HTML-Caching fuer SPA-Routen deaktivieren.
3. `./update.sh u` nochmal laufen lassen.

Mehr Details: [OPERATIONS.md](OPERATIONS.md).

## Rollback

Releases bevorzugt per Tag mit `scripts/deploy-release.sh` ausrollen. Der bestätigte Rollback
steht in [RELEASE.md](RELEASE.md); dadurch bleiben vorheriger Commit, Backup und Prüfablauf
nachvollziehbar.
