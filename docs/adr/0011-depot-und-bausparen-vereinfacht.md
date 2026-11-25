# ADR-0011: Depot und Bausparen als vereinfachte Modelle

- **Status:** angenommen
- **Datum:** 2026-10-12 (Version 0.4.0 / 0.5.0); nachträglich dokumentiert am 2026-11-25

## Kontext

Für Depot und Bausparvertrag gibt es keinen importierbaren Kontoauszug. Die Familie will den Wert sehen, nicht
einzelne Wertpapiere oder die Bewertungszahl der Bausparkasse nachbilden.

## Entscheidung

- **Depot** ist ein Konto: Ein- und Auszahlungen, Gebühren und Erträge sind Buchungen, die Rendite trägt man von Hand
  in % oder € ein. Wert = gebuchtes Kapital + Rendite. Keine Einzelpositionen.
- **Bausparvertrag** ist ein eigener Datensatz im Bereich Darlehen (kein Konto): Guthaben aus dem jüngsten Stand,
  Sparrate, Guthabenzins zum Jahresende, Zuteilung bei Mindestguthaben, Bauspardarlehen mit Tilgungsbeitrag.
  Keine Bewertungszahl.

## Alternativen

- Wertpapiere einzeln mit Kursen: viel Pflege, Kursquelle nötig.
- Bausparen als Konto mit Buchungen: ohne Auszug wenig Nutzen.

## Folgen

- Für die Planung genau genug, nicht für den Cent.
- Der Vermögensverlauf (0.8.0) nutzt für das Depot die jeweils letzte Rendite-Eintragung.
