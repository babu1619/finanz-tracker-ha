# ADR-0022: Dunkles Farbschema über CSS-Variablen

- **Status:** angenommen
- **Datum:** 2026-11-25 (Version 0.9.0); nachträglich dokumentiert am 2026-11-25

## Kontext

Gewünscht war ein Dark Mode. Viele Farben standen fest im CSS und in Vorlagen.

## Entscheidung

- Alle Farben laufen über CSS-Variablen in `:root`. Das dunkle Schema setzt sie neu:
  - automatisch über `prefers-color-scheme`, solange nichts gewählt ist
  - fest über `data-theme="dark"` bzw. `"light"`
- Umschalter in der Kopfzeile: System → Hell → Dunkel, gespeichert je Gerät. Ein Skript im `<head>` setzt das Schema
  vor dem ersten Zeichnen.
- Text in Grün und Rot nutzt `--gut` und `--bad`, damit er in beiden Schemata lesbar ist.

## Alternativen

- Schema am Benutzer in der Datenbank: Handy und PC wollen oft unterschiedliche Einstellungen.

## Folgen

- Neue Vorlagen dürfen keine festen Farben enthalten.
