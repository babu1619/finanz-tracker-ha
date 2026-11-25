# ADR-0004: Beträge in Cent, Abrechnungsmonat und Posten-Sichten

- **Status:** angenommen
- **Datum:** 2026-10-10 (Version 0.1.0 / 0.2.0); nachträglich dokumentiert am 2026-11-25

## Kontext

Gewünscht war, Buchungen einem anderen Monat als dem Buchungsdatum zuzuordnen (Gehalt vom 28. für den Folgemonat),
Buchungen auf Kategorien aufzuteilen und Jahresbeiträge über Monate zu verteilen. Alle Auswertungen müssen dabei
gleich rechnen.

## Entscheidung

- Beträge sind ganze Cent (`INTEGER`). Abbuchung negativ, Gutschrift positiv.
- Jede Buchung hat einen `abrechnungsmonat` (Standard: Monat des Buchungsdatums), unabhängig vom Buchungsdatum.
- Aufteilungen liegen in `buchung_split`, Verteilungen in `buchung.verteilung_monate` (1–60).
- Die Sicht `posten` liefert je Buchung bzw. je Teil eine Zeile, `posten_monat` verteilt sie auf Monate (Rest im
  ersten Monat). Alle Kennzahlen rechnen über `statistik.posten()` auf dieser Sicht.
- Die Art (Einnahme, Ausgabe, Umbuchung) kommt aus der Kategorie und wird vererbt; unkategorisierte Eingänge zählen
  als Einnahme.

## Alternativen

- Fließkommazahlen: Rundungsfehler.
- Aufteilung und Verteilung in jeder Auswertung einzeln berechnen: doppelte Logik, abweichende Zahlen.

## Folgen

- Neue Auswertungen müssen `statistik.posten()` verwenden, nicht `buchung` direkt.
- Die Buchungsliste zeigt die gebuchten Beträge; Summen in Statistiken können wegen Verteilung davon abweichen.
