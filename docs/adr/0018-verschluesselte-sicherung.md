# ADR-0018: Verschlüsselte Sicherung zusätzlich zu Home-Assistant-Backups

- **Status:** angenommen
- **Datum:** 2026-10-11 (Version 0.2.0); nachträglich dokumentiert am 2026-11-25

## Kontext

Home-Assistant-Backups sichern das Add-on, liegen aber oft unverschlüsselt. Eine Kopie außer Haus (Cloud, USB-Stick)
soll ohne Passwort nicht lesbar sein.

## Entscheidung

- Sicherung `.ftbak`: konsistente Kopie per SQLite-Backup-API, verschlüsselt mit Fernet (AES-128-CBC + HMAC-SHA256),
  Schlüssel per scrypt aus einem Passwort.
- Wiederherstellung in der Verwaltung mit Integritätsprüfung, Prüfung auf aktiven Admin und Kopie des vorherigen
  Stands.

## Alternativen

- Nur Home-Assistant-Backups: keine eigene Verschlüsselung.
- ZIP mit Passwort: schwache Verschlüsselung.

## Folgen

- Passwort verloren heißt Sicherung verloren.
- Vorherige Stände liegen als `vor-wiederherstellung-*.db` in `/data` und werden nicht automatisch gelöscht.
