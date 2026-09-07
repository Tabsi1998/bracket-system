# Konfiguration durch den Betreiber

Die Plattform enthält keine Zugangsdaten eines früheren Dienstleisters. Geheimnisse
werden entweder in der Server-`.env` oder verschlüsselt über den Adminbereich gespeichert.

## 1. Erster Start

```bash
cp .env.example .env
./install.sh
```

Danach als Superadmin anmelden, MFA im Profil einrichten und `/setup` öffnen. Den dortigen
Gesundheitswert auf 100 % bringen.

## 2. Google-Anmeldung mit deinem eigenen Konto

1. In der Google Cloud Console ein eigenes Projekt auswählen oder erstellen.
2. Den OAuth-Zustimmungsbildschirm mit Vereinsname, Supportadresse, Domain sowie Links zu
   `/privacy` und `/terms` pflegen.
3. Unter „APIs & Services → Credentials“ eine OAuth-Client-ID vom Typ „Web application“
   erstellen.
4. Als autorisierte JavaScript-Quellen exakt `https://lionsquad.at` und – falls genutzt –
   `https://www.lionsquad.at` bzw. deine Staging-Domain eintragen. Keine Wildcards.
5. Im Superadminbereich `Einstellungen → Anmeldung` nur die öffentliche Client-ID im Format
   `…apps.googleusercontent.com` eintragen, testen und danach Login/Registrierung/Verknüpfung
   gezielt aktivieren.

Ein Google-Client-Secret wird für Google Identity Services nicht benötigt und gehört weder
ins Frontend noch in den Adminbereich. Bestehende Konten werden nicht allein anhand einer
gleichen E-Mail automatisch verknüpft; die Verknüpfung erfolgt angemeldet im eigenen Profil.

## 3. E-Mail

Unter `Einstellungen → E-Mail/SMTP` entweder SMTP oder Resend mit deinem eigenen Zugang
konfigurieren. Danach Diagnose und Testmail ausführen. Maskierte Werte sind bereits gespeichert;
leer absenden überschreibt sie nicht. Die Schaltfläche zum Löschen entfernt den gespeicherten
Schlüssel tatsächlich.

## 4. Discord, Twitch und Server

- Discord: eigenen Webhook anlegen, im Adminbereich speichern und Testnachricht senden.
- Twitch: eigene Client-ID und eigenes Client-Secret verwenden; anschließend Verbindung testen.
- Gameserver: Zugangskennwörter nur im geschützten Adminbereich pflegen.

Diese Geheimnisse liegen verschlüsselt in MongoDB. `SETTINGS_ENCRYPTION_KEY` muss deshalb stabil
bleiben und separat gesichert werden.

## 5. Rechtliches und Einwilligungsversionen

Unter `Einstellungen → Rechtliches` echte Vereinsdaten, Datenschutzkontakt und ergänzende
Nutzungsbedingungen pflegen. Danach `/imprint`, `/privacy` und `/terms` im ausgeloggten Browser
kontrollieren. Die vorformulierten Texte ersetzen keine juristische Prüfung.

Bei einer wesentlichen Änderung Versionen in `.env` erhöhen, zum Beispiel:

```env
PRIVACY_POLICY_VERSION=2026-09-15
TERMS_VERSION=2026-09-15
```

Anschließend `docker compose up -d --force-recreate backend`. Web und App verlangen dann bei der
nächsten Anmeldung erneut eine ausdrückliche Zustimmung und protokollieren sie im Consent-Ledger.

## 6. Rollen

- `moderator`: Meldungen und operative Moderation
- `tournament_admin`: Turnierbetrieb
- `club_admin`: Mitglieder, Rechtliches, Integrationen und Vereinskonfiguration
- `superadmin`: Rollen, Einladungen und Anmeldeanbieter

Adminrollen müssen MFA verwenden. Rollen nach dem Minimalprinzip vergeben und vierteljährlich
prüfen.
