# ADR-0015: Installierbare App (PWA) ohne Finanzdaten im Cache

- **Status:** angenommen
- **Datum:** 2026-10-11 (Version 0.2.0); nachträglich dokumentiert am 2026-11-25

## Kontext

Auf dem Handy soll die App wie eine App starten (eigenes Symbol, Kurzbefehle). Finanzdaten sollen nicht unkontrolliert
auf dem Gerät liegen.

## Entscheidung

- Manifest mit Kurzbefehlen „Bar erfassen“, „Prüfen“, „Buchungen“.
- Der Service Worker speichert nur CSS, JS, Symbole und eine Offline-Seite, je Version; Seiten kommen immer frisch
  vom Server.

## Alternativen

- Offline-fähige App mit lokaler Datenhaltung: Synchronisation und Konflikte, Daten auf dem Gerät.
- Native App: zu viel Aufwand.

## Folgen

- Ohne Verbindung zum Green zeigt die App nur die Offline-Seite.
- Neue statische Dateien müssen nicht in den Cache; Versionswechsel leert ihn.
