# Datenschutz und Datenlebenszyklus

## Technische Umsetzung

- Neue Profile sind standardmäßig privat.
- Registrierungen benötigen Datenschutz- und Nutzungszustimmung sowie E-Mail-Verifikation.
- Jede Zustimmung wird mit Benutzer, Version, Zeitpunkt, Clienttyp und technischen Auditdaten
  nachvollziehbar protokolliert.
- Nutzer können ihren erweiterten Datenexport anfordern, Sessions verwalten, Newsletter widerrufen,
  andere Nutzer blockieren und Inhalte melden.
- „Löschen“ anonymisiert personenbezogene Daten; historische Turnierergebnisse bleiben ohne
  identifizierende Profildaten erhalten.
- Integrationsgeheimnisse werden mit `SETTINGS_ENCRYPTION_KEY` verschlüsselt; Passwörter werden
  ausschließlich gehasht gespeichert.
- Öffentliche Benutzerobjekte enthalten weder Passwort-/MFA-Daten noch stabile Google-Konto-IDs.

## Betreiberpflichten

Der Verein muss reale Zwecke, Rechtsgrundlagen, Auftragsverarbeiter, Löschfristen und Kontakte
festlegen. Vor Livebetrieb sind `/privacy`, `/terms` und `/imprint` fachlich beziehungsweise
juristisch zu prüfen. Besonders zu dokumentieren sind Hosting, Mailanbieter, Google-Anmeldung,
Analytics, Discord/Twitch-Einbindungen, Backups und mögliche Drittlandübermittlungen.

## Empfohlene Fristen

Diese Werte sind eine technische Ausgangsbasis und müssen rechtlich bestätigt werden:

- Sicherheits-/Auditlogs: 90 bis 180 Tage
- Clientfehlerlogs: höchstens 30 Tage
- Zustell-/Mailqueue-Fehler: 90 Tage
- abgelehnte Kontakt- und Mitgliedsanträge: 6 bis 12 Monate
- Backups: 14 bis 30 Tage, danach automatisiert löschen
- Consent- und notwendige Vereinsnachweise: entsprechend Nachweis-/Aufbewahrungspflicht

## Regelmäßige Kontrolle

Monatlich fehlgeschlagene Mail-, Backup- und Moderationsvorgänge prüfen. Vierteljährlich Rollen,
Admin-MFA, aktive Sessions, Dienstleister, öffentliche Profile und Löschfristen auditieren. Bei
einem Vorfall Zugangsdaten rotieren, Beweise geschützt sichern, Umfang bewerten und die
gesetzlichen Melde- und Informationsfristen mit dem Datenschutzverantwortlichen prüfen.
