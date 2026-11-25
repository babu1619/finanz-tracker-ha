# ADR-0017: Keine Belege im Finanz-Tracker

- **Status:** angenommen
- **Datum:** 2026-10-10 (Version 0.1.0); nachträglich dokumentiert am 2026-11-25

## Kontext

Rechnungen, Kassenbons und Verträge sollen archiviert werden. Ein Archiv hat andere Anforderungen (Texterkennung,
Volltextsuche, lange Aufbewahrung).

## Entscheidung

Der Finanz-Tracker speichert keine Belege. Dafür gibt es ein eigenes System (Familienarchiv: Paperless-ngx mit
Begleitdienst). Der Finanz-Tracker wird nur für eine spätere Verknüpfung vorbereitet.

## Alternativen

- Belege als Anhang an Buchungen: Datenbank wächst, keine Archivfunktionen.

## Folgen

- Eine Kopplung (Kategorien als `kat:`-Tags, Beleg ↔ Buchung) ist als Idee notiert, nicht umgesetzt.
