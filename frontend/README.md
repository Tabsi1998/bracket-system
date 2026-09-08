# Web-Frontend

React 19 wird mit Vite gebaut. Der Entwicklungsserver leitet `/api` standardmäßig
an `http://127.0.0.1:8001` weiter.

```bash
corepack yarn install --frozen-lockfile
corepack yarn start
corepack yarn test
corepack yarn build
```

Öffentliche Buildvariablen beginnen mit `VITE_`; sie dürfen niemals Geheimnisse
enthalten. Die produktiven Werte werden über die Build-Argumente in
`docker-compose.yml` gesetzt. `VITE_DEV_BACKEND_URL` ändert ausschließlich das
Proxyziel des lokalen Entwicklungsservers.

Der Service Worker hält nur statische Anwendungsdateien offline bereit und
speichert keine API-Antworten.

Bei jedem Build erzeugt Vite `version.json` und einen dazu passenden Service Worker.
HTML und Update-Dateien dürfen nicht lange gecacht werden. Deployment-Prüfung und
Proxy-Regeln: [Update-Anleitung](../UPDATE.md). Passkey-Einrichtung:
[Betreiberkonfiguration](../CONFIGURATION.md). Alle Anleitungen: [Dokumentation](../DOCS.md).
