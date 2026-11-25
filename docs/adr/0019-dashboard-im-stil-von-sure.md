# ADR-0019: Dashboard im Stil von Sure, ohne fremden Code

- **Status:** angenommen
- **Datum:** 2026-11-11 (Version 0.8.0); nachträglich dokumentiert am 2026-11-25

## Kontext

Benjamin gefallen Design und Diagramme der Open-Source-Finanz-App Sure (Fortführung von Maybe Finance, AGPLv3).
Gewünscht waren das Aussehen und die Diagramme, nicht ein Umstieg.

## Entscheidung

- Das Dashboard übernimmt Gestaltungsideen von Sure:
  - Nettovermögen mit Verlauf und Zeitraumwahl
  - Cashflow als Sankey
  - Ausgaben als Ring
  - Vermögensaufstellung nach Kontoart mit Anteilsbalken und Mini-Verläufen
  - ruhige Karten mit großen Zahlen
- Es wird kein Code aus Sure übernommen; alles ist neu gebaut (Lizenz AGPLv3).
- Alle Bereiche sind ein- und ausklappbar, der Zustand bleibt je Gerät.
- Das Nettovermögen wird aus Startsaldo und Buchungen je Monat rekonstruiert, mit den Vereinfachungen aus
  `services/vermoegen.py`.

## Alternativen

- Sure selbst betreiben: Ruby on Rails, PostgreSQL, Redis; Kontoabruf vor allem für den US-Markt; kein
  Darlehens- und Bausparmodell.
- Code von Sure übernehmen: AGPL würde die ganze App betreffen.

## Folgen

- Neue Abhängigkeit zwischen Dashboard und Vermögensdiensten (Darlehen, Bausparen, Depot, Krypto).
- Der Verlauf ist eine Annäherung (siehe Offene Punkte).
