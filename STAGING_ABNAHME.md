# Staging-Abnahme: dein Praxistest

Status: **noch nicht ausgeführt**. Es gibt derzeit keinen bestätigten Staging-Stack.
Reihenfolge und Zuständigkeiten: [RESTPLAN.md](RESTPLAN.md).

## Technische Vorbereitung durch mich

- [ ] Serverkapazität, Installationspfad, vorhandener Konsolen-/Privatzugang und Staging-Domain bestätigt.
- [ ] Separates Checkout/Compose-Projekt; eigene DB, Uploads, Netzwerk und Secrets geprüft.
- [ ] Staging-Ressourcen begrenzt; laufende Produktion vor/nach Start gesund.
- [ ] HTTPS, Host-/CORS-Konfiguration, hostgebundene Cookies und API/Web-Health geprüft.
- [ ] Testnutzer für normales Konto, Mitglied und abgestufte Adminrollen angelegt.
- [ ] Testmailadresse und ausschließlich eigene Integrationen eingerichtet; keine echten Empfänger.
- [ ] Keine Produktivdaten kopiert; Beispieldaten/Turniere als TEST gekennzeichnet.
- [ ] Sicherheits- und CI-Prüfungen für den exakten Testcommit grün.
- [ ] Verschlüsseltes Staging-Backup und Restore-Drill mit explizitem Staging-Ziel erfolgreich.

## Testkopf

Vor dem Test ausfüllen, ohne Passwörter, Tokens oder private Nutzerdaten:

- Staging-URL: noch offen
- Getesteter Commit: noch offen
- Datum / Tester: noch offen
- Desktop-Browser / Version: noch offen
- Smartphone / Browser / Version: noch offen

## Deine Pflichtfälle

Verwende nur vorbereitete Testkonten. Ich stelle die Testdaten und begleite die
Einrichtung; du prüfst die tatsächliche Bedienung auf Desktop und Smartphone.

| ID | Was du ausprobierst | Erwartung | Ergebnis |
| --- | --- | --- | --- |
| T01 | Neues Testkonto registrieren, E-Mail bestätigen, anmelden/abmelden | Mail kommt im Testpostfach an; Aktivierung und Sitzungsende funktionieren | offen |
| T02 | Passwort vergessen, neues Passwort setzen; alten Resetlink erneut öffnen | Reset klappt genau einmal; alter Link wird abgewiesen | offen |
| T03 | MFA im Test-Adminprofil aktivieren, erneut anmelden, einen Recovery-Code verwenden | Admin verlangt MFA; verwendeter Recovery-Code ist nicht erneut nutzbar | offen |
| T04 | Eigenen Google-Client im Admin eintragen; Anmeldung und bewusste Kontoverknüpfung testen | Kein fremder Client; kein stilles Zusammenlegen von Konten | offen |
| T05 | Rollen wechseln: Nutzer, Mitglied, Turnier-Admin; nicht erlaubte Adminseite direkt aufrufen | Nur freigegebene Inhalte/Aktionen verfügbar; Server weist unberechtigte Aktionen ab | offen |
| T06 | Profil bearbeiten; privates Profil mit anderem Testkonto ansehen; Zustimmung erneuern | Sichtbarkeit und gespeicherte Einstellungen stimmen; erforderliche Zustimmung wird abgefragt | offen |
| T07 | News im Editor mit Fett/Kursiv/Link/Bild erstellen, speichern, neu öffnen | Formatierung und Upload bleiben erhalten; Desktop und Mobil bedienbar | offen |
| T08 | Team erstellen/einladen; Fortschritt bzw. vorbereitetes Level-up ansehen | Mitgliedschaft, Levelanzeige und Erfolge plausibel; kein dauerhaftes Overlay | offen |
| T09 | Testturnier anmelden, einchecken, Match melden/bestätigen, Tabelle/Bracket ansehen | Teilnehmer, Ergebnis und Platzierung stimmen; keine echten Turniere verändern | offen |
| T10 | Zweites Preview-Turnier planen/anwenden; Wiederholung und veralteten Plan prüfen | Gleicher Apply ohne Duplikate; veralteter Plan abgewiesen; reale Strukturen geschützt | offen |
| T11 | Testnachricht/Inhalt melden, Testnutzer blockieren, Moderationsfall bearbeiten | Meldung für Berechtigte sichtbar; Blockieren und Bearbeitung funktionieren | offen |
| T12 | Event-Anmeldung und Fast-Lap-Testzeit anlegen; persönliche Übersicht kontrollieren | Anzeige, Status und berechtigte Aktionen passen zusammen | offen |
| T13 | Datenexport und Kontolöschung mit entbehrlichem Testkonto durchführen | Nur eigene Daten exportiert; Konto anonymisiert, Turnierhistorie weiterhin nutzbar | offen |
| T14 | Mobil navigieren, Menü/Formulare/Uploads und Fehlermeldungen bedienen | Kein seitliches Überlaufen, unerreichbare Schaltflächen oder Sackgassen | offen |
| T15 | Testmail senden; bei Nutzung Discord/Twitch mit Testzielen prüfen | Nur eigene Konfiguration und vorgesehene Testempfänger werden verwendet | offen |

Nicht genutzte optionale Integrationen können mit Begründung als „nicht genutzt,
deaktiviert“ vermerkt werden. Sicherheits-, Rollen-, Daten- und Kernablauftests
werden nicht einfach übersprungen. App-Gerätetests erhalten einen eigenen Bericht,
wenn eine App-Version mit diesem Release veröffentlicht werden soll.

## Fehler melden

Für jeden Fehler: Test-ID, Seite, Testrolle, genaue Schritte, erwartetes/tatsächliches
Ergebnis und Screenshot ohne Secrets. Ich dokumentiere Ursache, Korrekturcommit
und Nachtest. „Offen“ ist nicht „bestanden“.

## Freigabe vor Produktion

- [ ] Pflichtfälle bestanden; optionale Ausnahmen nachvollziehbar dokumentiert.
- [ ] Keine offenen Sicherheits-, Datenverlust-, Berechtigungs- oder Kernablauffehler.
- [ ] Produktivkonfiguration und Rechtstexte vom Betreiber freigegeben.
- [ ] Produktivbackup, externe Kopie und Wiederherstellbarkeit nachgewiesen.
- [ ] Releasecommit/-tag, vorherige Version, Wartungsfenster und Rollback festgelegt.
- [ ] Betreiberfreigabe mit Datum dokumentiert.

Freigabe: **ausstehend**. Ein Release erfolgt erst danach nach [RELEASE.md](RELEASE.md).
