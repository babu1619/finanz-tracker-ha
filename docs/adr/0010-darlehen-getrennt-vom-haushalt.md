# ADR-0010: Darlehen getrennt vom Haushalt

- **Status:** angenommen
- **Datum:** 2026-10-11 (Version 0.2.0); nachträglich dokumentiert am 2026-11-25

## Kontext

Immobiliendarlehen haben hohe Salden und eigene Fragen (Restschuld, Zinsbindung, Sondertilgung). Im Haushaltsbudget
interessiert nur die Rate.

## Entscheidung

- Darlehenskonten haben einen eigenen Bereich und zählen nie in Einnahmen, Ausgaben, Budgets oder die
  Monatsstatistik. Die Rate ist eine Ausgabe des Zahlkontos.
- Der Tilgungsplan wird aus den Konditionen gerechnet; Abgleiche mit der Bank setzen ihn neu auf, Sondertilgungen
  werden abgezogen.
- Sind Kontoauszüge des Darlehens importiert, gilt deren Kontostand, sonst der Plan.
- Im Nettovermögen (seit 0.8.0) zählen Darlehen als Schulden.

## Alternativen

- Darlehen als normales Konto: Die Restschuld würde Summen und Sparquote verzerren.

## Folgen

- Eigene Rechenlogik in `services/darlehen.py` (Plan, Simulation, Vergleich, Anschlussfinanzierung).
- Hinweise (Zinsbindung) erscheinen trotzdem im Dashboard.
