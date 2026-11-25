# ADR-0023: Zustand der Oberfläche je Gerät im Browser

- **Status:** angenommen
- **Datum:** 2026-10-11 (Version 0.2.0); nachträglich dokumentiert am 2026-11-25

## Kontext

Eingeklappte Bereiche, gewählte Zeiträume und Ähnliches sollen erhalten bleiben. Am Handy und am PC sind oft
andere Einstellungen sinnvoll.

## Entscheidung

Solcher Zustand liegt im `localStorage` des Browsers, immer in `try/catch`. Ohne gespeicherten Wert gilt ein
sinnvoller Standard. Fachliche Einstellungen, zum Beispiel die Kontoauswahl der Planung, liegen dagegen in der
Datenbank.

## Alternativen

- Alles in der Datenbank je Benutzer: unnötige Schreibzugriffe, gleiche Ansicht auf allen Geräten.

## Folgen

- Im privaten Modus oder nach dem Löschen der Website-Daten gelten wieder die Standards.
