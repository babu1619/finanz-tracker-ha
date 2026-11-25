# ADR-0009: Umbuchungen und automatische Gegenbuchungen

- **Status:** angenommen
- **Datum:** 2026-10-10 (Version 0.1.0 / 0.3.1 / 0.4.0); nachträglich dokumentiert am 2026-11-25

## Kontext

Geld zwischen eigenen Konten (Tagesgeld, Kreditkartenausgleich, Bargeld, Depot) ist weder Einnahme noch Ausgabe und
würde sonst alle Kennzahlen verfälschen. Bargeld und Depot haben keinen Import.

## Entscheidung

- Umbuchungen werden als Paar erkannt: gleicher Betrag, entgegengesetztes Vorzeichen, kurzer Abstand (3 Tage,
  Kreditkarte 10), bewertet mit IBAN, Stichworten und Abstand; ab 0,8 und eindeutig automatisch, sonst Vorschlag.
- Darlehenskonten sind ausgenommen: Raten sind Ausgaben (ADR-0010).
- Eine Buchung kann von Hand als Umbuchung mit Gegenkonto markiert werden; die Gegenbuchung wird beim Import
  verknüpft.
- Für Konten ohne Import (Bargeld, Depot) legt die App die Gegenbuchung automatisch an und entfernt sie wieder, wenn
  die Umbuchung gelöst oder gelöscht wird.

## Alternativen

- Umbuchungen nur von Hand: fehleranfällig, viel Arbeit.
- Bargeld nicht führen: Barausgaben fehlen in der Auswertung.

## Folgen

- Umbuchungen zählen nirgends als Einnahme oder Ausgabe.
- Geldautomaten-Abhebungen lassen sich per Regel komplett automatisieren.
