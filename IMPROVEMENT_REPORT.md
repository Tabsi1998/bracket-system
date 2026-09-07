# Vollständiger Plattform-Review – Umsetzungsstand

Stand: 7. September 2026

## Ergebnis

Der Quellstand wurde von P0 bis P12 überarbeitet. Aktiver Code enthält keine Bindung an einen
früheren Generator- oder Hostinganbieter. Google Identity, Mail, Discord, Twitch und Gameserver
verwenden ausschließlich Betreiberkonfiguration; geheime Werte werden serverseitig verschlüsselt.

## Umgesetzte Bereiche

- P0/P1: Bestand geprüft, Fremdartefakte und obsolete interne Berichte entfernt, Secret-Scanner
  als CI-Gate ergänzt.
- P2: Offizielles Google Identity Services mit serverseitiger Tokenprüfung, eigener Client-ID im
  Superadminbereich, expliziter Kontoverknüpfung und deaktiviertem Secure Default.
- P3: E-Mail-Verifikation, atomare Session-/Rate-Limit-Flows, Einladungen statt Admin-Passwörtern,
  versionierte Datenschutz-/Nutzungszustimmung in Web und App.
- P4: TOTP-MFA plus Recovery-Codes für Admins, feinere Rollen, Auditierung, verschlüsselte
  Integrationseinstellungen und keine Auth-Geheimnisse in API-Antworten.
- P5: Erweiterter DSGVO-Export, Anonymisierung statt kaputter Historie, private Profile als
  Standard, Blockieren, Melden und Moderationsworkflow sowie eigene Nutzungsbedingungen.
- P6: Nicht-Root-/Read-only-Container, restriktive CSP, Proxy-/Host-Prüfung, Liveness/Readiness,
  Mongo-Authentifizierung und verschlüsselte Backups/Restore-Drills.
- P7: Backend-, Frontend-, Mobile-, Dependency-, Coverage-, Container- und Secret-Gates in CI.
- P8/P9: geordnete Datenmigrationen, CRA/CRACO vollständig durch Vite/Vitest ersetzt,
  Route-Splitting, kleiner Einstiegschunk, PWA-Cache ohne API-Daten und Kontrastprüfung.
- P10–P12: getrenntes Staging, reproduzierbare Release-/Rollback-Skripte, systemd-Timer,
  Monitoring-/Incident-Ablauf sowie Betreiber-, Datenschutz- und Backuphandbuch.

## Automatisch verifiziert

- Backend: vollständige lokale Testsammlung und Python-Compile
- Frontend: Vitest, Vite-Produktionsbuild, Kontrast- und High/Critical-Dependency-Audit
- Mobile: TypeScript-, Sicherheits-, Release- und Dependency-Prüfung
- Quelltext: Secret-/Provider-Scan

Docker- und Bash-Prüfungen sind zusätzlich in Linux-CI hinterlegt, da auf dem aktuellen
Windows-Arbeitsplatz keine Docker-/Bash-Laufzeit vorhanden ist.

## Noch vom Betreiber auszuführen

Keine Softwareänderung kann externe Konten, echte Vereinsdaten oder einen Serverzugriff erfinden.
Der Betreiber muss deshalb die Schritte aus `CONFIGURATION.md`, `RELEASE.md` und
`BACKUP_RESTORE.md` durchführen, die Staging-Abnahme testen und die Rechtstexte fachlich prüfen.
Danach ist der manuelle Testbericht die Grundlage für gezielte Restkorrekturen.
