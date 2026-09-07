# Verschlüsseltes Backup und Restore

## Einmalige Vorbereitung

```bash
sudo install -d -m 700 /etc/tls-arena
sudo sh -c 'umask 077; openssl rand -base64 48 > /etc/tls-arena/backup-password'
sudo install -d -m 700 /opt/tls-arena/backups
```

Die Passwortdatei und `SETTINGS_ENCRYPTION_KEY` separat in einem vertrauenswürdigen Passwort-
oder Secret-Store sichern. Ohne diese Werte sind Backups beziehungsweise gespeicherte
Integrationszugänge nicht wiederherstellbar.

## Backup

```bash
BACKUP_DIR=/opt/tls-arena/backups bash scripts/backup.sh
```

Das Skript authentifiziert sich an MongoDB und erzeugt AES-256-CBC/PBKDF2-verschlüsselte Archive
für Datenbank und Uploads sowie ein Manifest mit Prüfsummen. Unverschlüsselte Zwischenarchive
werden nicht angelegt. `RETENTION_DAYS` ist standardmäßig 14.

Für eine Offsite-Kopie zuerst ein rclone-Remote konfigurieren und danach zum Beispiel:

```bash
BACKUP_REMOTE=secure-remote:tls-production bash scripts/backup.sh
```

Ein Backup auf demselben Server ist kein ausreichender Schutz.

## Zeitplan mit systemd

Repository-Pfad in den Dateien unter `deploy/systemd/` anpassen und installieren:

```bash
sudo cp deploy/systemd/tls-backup.* /etc/systemd/system/
sudo cp deploy/systemd/tls-restore-drill.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tls-backup.timer tls-restore-drill.timer
systemctl list-timers 'tls-*'
```

Fehler prüfen:

```bash
journalctl -u tls-backup.service -u tls-restore-drill.service --since '7 days ago'
```

## Integrität und nicht-destruktiver Restore-Drill

```bash
bash scripts/restore-check.sh \
  /opt/tls-arena/backups/tls_tls_arena_YYYYMMDD_HHMMSS.archive.gz.enc \
  /opt/tls-arena/backups/tls_uploads_YYYYMMDD_HHMMSS.tar.gz.enc

bash scripts/restore-drill.sh \
  /opt/tls-arena/backups/tls_tls_arena_YYYYMMDD_HHMMSS.archive.gz.enc
```

Der Drill restauriert in eine temporäre Datenbank, prüft Collections und entfernt die
Drill-Datenbank wieder. Er verändert die Produktivdaten nicht.

## Destruktiver Restore

Nur bei bestätigtem Datenverlust und in einem Wartungsfenster. Beide Dateien müssen aus demselben
Backup-Satz stammen:

```bash
export DB_NAME=tls_arena
export RESTORE_CONFIRM=tls_arena
bash scripts/restore.sh \
  /opt/tls-arena/backups/tls_tls_arena_YYYYMMDD_HHMMSS.archive.gz.enc \
  /opt/tls-arena/backups/tls_uploads_YYYYMMDD_HHMMSS.tar.gz.enc
unset RESTORE_CONFIRM
```

Das Skript validiert beide Archive, erstellt standardmäßig ein zusätzliches Sicherheitsbackup,
restauriert MongoDB mit `--drop`, ersetzt das Upload-Volume und startet Web/API neu. Danach
Readiness, Adminlogin, Uploads, ein historisches Turnier, Mailqueue und Auditlog prüfen.

`SKIP_PRE_RESTORE_BACKUP=true` nur verwenden, wenn der aktuelle Zustand nachweislich unbrauchbar
ist und nicht mehr forensisch gesichert werden soll.
