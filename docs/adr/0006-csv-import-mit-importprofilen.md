# ADR-0006: CSV-Import mit Importprofilen in der App

- **Status:** angenommen
- **Datum:** 2026-10-10 (Version 0.1.0); nachträglich dokumentiert am 2026-11-25

## Kontext

Die Banken der Familie (GLS Bank, Sparkasse, UmweltBank) liefern unterschiedliche CSV-Formate, die sich gelegentlich
ändern. Ein fester Parser je Bank müsste bei jeder Änderung neu ausgeliefert werden.

## Entscheidung

- Formate werden als Importprofile in der App angelegt: Zeichensatz, Trennzeichen, Datums- und Dezimalformat
  werden erkannt, die Spaltenzuordnung wählt der Nutzer mit Live-Vorschau.
- Das Profil merkt sich die Spaltenüberschriften und meldet ein geändertes Format.
- Konten werden über die IBAN im Dateikopf erkannt.
- Duplikate erkennt ein SHA-256-Schlüssel je Zeile (mit laufender Nummer für gleiche Zeilen); überlappende Exporte
  sind erlaubt.
- Saldoabgleich gegen die Saldo-Spalte; der erste Import bestimmt den Startsaldo.
- Jeder Import ist rückgängig machbar.

## Alternativen

- Fester Parser je Bank: Update nötig bei jeder Formatänderung.
- Direkter Abruf per FinTS: zurückgestellt (ADR-0012).

## Folgen

- Neue Banken brauchen keine neue Version, nur ein Profil.
- Gelöschte importierte Buchungen brauchen eine Sperrliste, sonst kämen sie beim nächsten Import wieder (ADR-0020).
