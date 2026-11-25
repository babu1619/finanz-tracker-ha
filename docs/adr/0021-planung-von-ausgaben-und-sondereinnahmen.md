# ADR-0021: Planung von Ausgaben und Sondereinnahmen

- **Status:** angenommen
- **Datum:** 2026-11-25 (Version 0.9.0); nachträglich dokumentiert am 2026-11-25

## Kontext

Gewünscht: größere Ausgaben (Autokauf, Hausinvestitionen) und Sondereinnahmen für die kommenden Jahre planen, das
verfügbare Vermögen aus wählbaren Vermögenskategorien nehmen und das Vermögen nach jeder Ausgabe und zu einem
Stichtag sehen.

## Entscheidung

- Eigener Bereich „Planung“ mit Tabelle `plan_posten` (Ausgabe/Einnahme, Monat, Betrag, Kategorie, erledigt).
- Ausgangsvermögen aus den Konten der Vermögensaufstellung, einzeln oder je Gruppe wählbar. Vorauswahl ohne Depot,
  Krypto und Bausparen. Gespeichert je Benutzer in `einstellung`.
- Optional ein laufender monatlicher Überschuss (Vorschlag: Ø der letzten 12 Monate), je Benutzer.
- Rechnung Monat für Monat ohne Zinsen; erledigte Posten zählen nicht mehr.

## Alternativen

- Planposten als Budgets oder Sparziele: passt nicht zu einmaligen Beträgen in fernen Jahren.
- Kontoauswahl gemeinsam: Mitglieder sehen nicht dieselben Konten (private Konten).

## Folgen

- Die Planung zeigt eine Größenordnung, keine Prognose der Kontostände.
- Posten sind für alle sichtbar, die Kontoauswahl nicht.
