# Update-Anleitung

Der normale Server-Ablauf ist:

```bash
cd /root/THE-LION_SQUAD-eSPORT-Webseite
./update.sh u
```

Das Script zieht den neuesten Code, baut Frontend/Backend neu, startet die Container und prueft Backend, Frontend und wichtige SPA-Routen.

## Danach pruefen

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
