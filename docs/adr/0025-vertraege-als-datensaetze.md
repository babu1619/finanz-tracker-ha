# ADR-0025: Verträge als eigene Datensätze

- **Status:** angenommen
- **Datum:** 2026-10-15 (Version 0.6.0); nachträglich dokumentiert am 2026-11-25

## Kontext

Bis 0.5.0 wurden Abos und Fixkosten nur aus regelmäßigen Zahlungen erkannt und markiert. Gewünscht waren Laufzeit,
Kündigungsfrist mit Hinweis, frei wählbarer Rhythmus und die Zuordnung von Buchungen.

## Entscheidung

- `vertrag` ist ein eigener Datensatz (Abo, Fixkosten, Vertrag) mit Rhythmus, Laufzeit, Verlängerung,
  Kündigungsfrist und „gekündigt zum“.
- Buchungen werden über `buchung.vertrag_id` zugeordnet; Zahlungen derselben Gegenpartei folgen automatisch.
- 31 Tage vor Ende der Kündigungsfrist erscheint ein Hinweis auf jeder Seite.
- Erkannte regelmäßige Zahlungen bleiben als Vorschläge; „kein Vertrag“ blendet eine Gegenpartei aus
  (`art = 'ignoriert'`).
- Alte Markierungen wurden bei der Migration 007 übernommen.

## Alternativen

- Nur Erkennung ohne Datensatz: keine Laufzeit und Kündigungsfrist möglich.

## Folgen

- Budgets nutzen ausstehende Vertragszahlungen für ihre Prognose.
