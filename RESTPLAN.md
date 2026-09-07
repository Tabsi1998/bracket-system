# Verbindlicher Restplan

Stand: 7. September 2026. Ausgangspunkt: `main` nach PR #151 (`bab4dc5`).

Dieser Plan bestimmt die Reihenfolge. Ältere Roadmaps bleiben als Historie erhalten;
ihre Checkboxen sind weder ein aktueller Release-Nachweis noch automatisch neue Aufträge.
**Quellcode umgesetzt, automatisch getestet und auf dem echten Server abgenommen sind
drei unterschiedliche Zustände.** Ein fertiger Quellstand ist noch kein Go-live.

## Reihenfolge und Abschlusskriterien

| Paket | Stand | Was ich umsetze | Wann abgeschlossen |
| --- | --- | --- | --- |
| R0 – Restplan | konsolidiert | Dieser Plan, eindeutige Verweise, historische Pläne kennzeichnen | Ein gemeinsamer Arbeitsstand ohne konkurrierende To-do-Listen |
| R1 – Sicherheitsupdates | umgesetzt und lokal geprüft; Integration über PR #152 | Tiptap-Familie 3.30.4, CSS-Parser 6.1.4, Editor-Sicherheitsregression; Build, Tests und Audit | PR und Main grün; die beiden GitHub-Meldungen geschlossen |
| R2 – Staging | vorbereitet, noch nicht eingerichtet | Ressourcen und Proxy prüfen; getrennten Testbetrieb auf vorhandenem Server einrichten | Eigene HTTPS-Subdomain, DB, Volumes, Secrets und Testnutzer; Produktion unverändert gesund |
| R3 – Praxistest | offen | Testdaten/Abläufe vorbereiten, Fehler nachstellen und korrigieren | Du bestätigst die Pflichtfälle aus STAGING_ABNAHME.md; kritische Fehler behoben |
| R4 – Release/Betrieb | offen | Backup/Restore nachweisen, Release festhalten, kontrolliert deployen, Rollback und Monitoring prüfen | Abnahme dokumentiert, Backup extern gesichert, Produktiv-Smoke grün |
| R5 – Competition Engine | ausdrücklich nachgelagert | Getrenntes Umbaupaket nach COMPETITION_ENGINE.md | Parität, Dry Runs, reversible Migration und nachgewiesene Ablösung alter Schreibwege |

R2 startet erst nach R1. R3 verwendet ausschließlich Staging-Testdaten. R4 benötigt
deine fachliche Freigabe und ein vereinbartes Wartungsfenster. R5 verändert bis dahin
keine Bestandswettbewerbe und ist keine Voraussetzung für den Test der heutigen Plattform.

### Nachweise dieses Pakets

- Vollständige lokale Nicht-Live-Backend-Suite: 368 bestanden, 19 übersprungen,
  277 Live-Tests abgewählt; darunter 17 neue Backup-Zieltests.
- Frontend: 16 Unit-Tests, Frozen-Lockfile-Installation, Build und Kontrastprüfung bestanden.
- Vollständiger Yarn-Audit am 7. September 2026: 0 bekannte Schwachstellen in allen Stufen.
- Secret-Scan und Syntaxprüfung aller Shell-Skripte bestanden.
- Verbindliche Linux-/Docker-/Browser-/Mobile- und CodeQL-Nachweise:
  [PR #152 mit Checks](https://github.com/Tabsi1998/THE-LION_SQUAD-eSPORT-Webseite/pull/152).
  Ein laufender/fehlgeschlagener Check ist keine Freigabe; nach dem Merge auch Main prüfen.
- Diese Nachweise ersetzen weder den echten Backup-/Restore-Drill noch deinen Praxistest.

## Bereits im Quellstand erledigt

- Plattform-Review P0–P12: eigene Integrationskonfiguration, Auth/MFA/Rollen,
  Datenschutzfunktionen, Container-/CI-Härtung, Betriebs- und Releasewerkzeuge;
  Details in [IMPROVEMENT_REPORT.md](IMPROVEMENT_REPORT.md).
- PR #151: abgesichertes Struktur-Plan/Apply für leere bzw. Preview-Strukturen,
  Team-Fortschritt und Level-up-Anzeige. Keine Migration laufender Turniere.
- Alte Arbeitsbranches bereinigt; nicht einfach ersetzbare Historie ist unter
  `archive/2026-09-07/*` gesichert. Routine-Updatebranches sind keine Altlasten.

Das ist kein Nachweis, dass diese Version bereits auf dem Produktivserver läuft,
alle Integrationen eingerichtet sind oder die Benutzerabnahme erfolgt ist.

## R1 – konkret begrenzte Sicherheitsarbeit

- Tiptap: alle direkt verwendeten Pakete gemeinsam auf 3.30.4; optionale Menüpakete
  ebenfalls auf diese Version begrenzen, damit keine inkompatiblen Peers einziehen.
- `postcss-selector-parser`: transitiven 6.x-Eintrag auf 6.1.4 aktualisieren.
- Regression: JSON-Prototype-Attribute dürfen nicht zu geerbten DOM-Attributen werden;
  normales Editieren und Serialisieren muss weiterhin funktionieren.
- Frozen-Lockfile-Installation, Unit-Tests, Produktionsbuild, Kontrastprüfung,
  Dependency-Audit, Desktop-/Mobile-Browser-Smoke sowie CI/CodeQL prüfen.
- Erst nach erfolgreicher Integration die durch diesen Stand ersetzten
  Sicherheits-PRs #144/#148 schließen, sofern GitHub das nicht selbst erledigt.

Die zum Planstand offenen Routine-PRs #141 (Actions), #143 (Mobile), #149 (Python)
und #150 (Frontend-Gruppe) bleiben einzeln zu prüfen. Sie sind nicht automatisch
Sicherheitsblocker. Vor jedem Release erneut auf neue Meldungen prüfen; keine
pauschale Freigabe ungeprüfter Gruppenupdates. Die Expo-SDK-Migration (#117) bleibt
ein eigenes Kompatibilitätspaket, nicht Teil dieses Patch-Updates.

## R2 – nur ein Server vorhanden

Der Betreiber hat bestätigt: Es gibt nur den Produktivserver. Daher zuerst
read-only prüfen: vorhandener Zugangsweg, tatsächlicher Installationspfad, freie RAM-/CPU-/Disk-
Kapazität, Docker/Compose, belegte Ports, Proxy/DNS/TLS und bestehende Backupziele.
Keine Serverzugänge oder Secrets in Git oder Testberichte schreiben. **Öffentliches SSH
ist nicht erforderlich und soll dafür nicht freigeschaltet werden.** Eine vorhandene
Hosting-/Serverkonsole oder ein privater Zugang reicht. Wenn ich keinen direkten Zugriff
habe, bereite ich die geprüften Befehle vor und der Betreiber führt sie dort aus.
Staging dient der Update-Abnahme und schaltet keine zusätzliche Website-Funktion frei.

Bei ausreichender Reserve kann derselbe Host einen zweiten Stack betreiben:

- separates Checkout, zum Beispiel `/opt/the-lion-squad-staging`;
- Compose-Projekt `tls-staging`, eigene Container, Netzwerk, DB und Volumes;
- Loopback-Ports 13000/18001 und eigene, noch festzulegende HTTPS-Subdomain;
- `.env.staging` mit eigenen Secrets; hostgebundene Cookies, keine Domain-Cookies;
- nur synthetische Testdaten, Testpostfächer und eigene Test-Integrationen;
- Scheduler/Benachrichtigungen erst gezielt freischalten; keine Nachrichten an Mitglieder;
- RAM-/CPU-Limits auch für Staging-MongoDB vor Start festlegen; Image-Builds können
  zusätzlich Ressourcen verbrauchen. Gemeinsamer Host bleibt eine gemeinsame Ausfallzone.

Vor einem parallelen Start muss die aufgelöste Compose-Konfiguration nachweislich
getrennt sein. Die Backup-/Restore-Zielauswahl ist in diesem Paket auf das konkrete
Compose-Projekt begrenzt und mit Regressionstests abgesichert; der echte Restore-Drill
steht noch aus. Bei zu wenig Reserve wird nicht auf der laufenden
Produktion getestet: Dann braucht es einen separaten Host oder eine lokale Docker-Umgebung.

Technischer Ablauf: [RELEASE.md](RELEASE.md). Nachweise und Testercheckliste:
[STAGING_ABNAHME.md](STAGING_ABNAHME.md).

## R3/R4 – was du tun musst

Du musst nicht programmieren. Von dir brauche ich:

1. Vorhandenen Zugangsweg (zum Beispiel Hosting-Konsole), Installationspfad und gewünschte
   Staging-Subdomain nennen. Kein öffentliches SSH einrichten, keine Passwörter im Chat.
   Ohne direkten Agent-Zugriff nur die von mir vorbereiteten Befehle in deiner Konsole ausführen.
2. Eigene Betreiberkonten für Google/Mail und bei Nutzung Discord/Twitch. Geheime
   Werte nur direkt in die geschützte Konfiguration eingeben. Ich begleite die Einrichtung
   nach [CONFIGURATION.md](CONFIGURATION.md).
3. Echte Vereins-/Kontaktdaten und fachliche Prüfung/Freigabe der Rechtstexte.
4. Die beschriebenen Klicktests durchführen und Fehler mit Schritten/Screenshot melden.
5. Nach erfolgreichem Test Go-live und Wartungsfenster freigeben.

Ich übernehme Code, technische Konfiguration im freigegebenen Ziel, Tests,
Fehlerkorrekturen, Dokumentation sowie den vorbereiteten Deploymentablauf.
Externe Kontoanlage, rechtliche Freigabe und dein Nutzungstest lassen sich nicht
durch einen automatisierten Build ersetzen.

## R5 – späteres, klar abgegrenztes Turnierpaket

Die Reihenfolge bleibt: fehlende Consumer-/Write-Parität → versionierter Schreibkern
mit Dispute/Forfeit/Korrektur → Standardformate einzeln → neue Turniere per Flag →
Bestands-Dry-Run mit IDs/Counts/Hash/Diff und Backup-/Restore-Nachweis → Test/Draft,
Archive und aktive Turniere zuletzt → alte Writes read-only, Nullnutzung messen,
erst danach entfernen. Fachliche Details und Abnahmematrix stehen ausschließlich
in [COMPETITION_ENGINE.md](COMPETITION_ENGINE.md).

Mobile-Gerätetests, SDK-Umstieg und weitere UX-/Feature-Wünsche bleiben sichtbar im
Backlog, werden aber nicht still in dieses Stabilisierungspaket hineingemischt.
