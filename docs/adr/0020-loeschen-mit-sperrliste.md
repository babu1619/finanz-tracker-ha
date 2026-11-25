# ADR-0020: Buchungen löschen mit Sperrliste für Importe

- **Status:** angenommen
- **Datum:** 2026-11-25 (Version 0.9.0); nachträglich dokumentiert am 2026-11-25

## Kontext

Bis 0.8.0 ließen sich nur bar erfasste Buchungen löschen. Gewünscht war Löschen aller Buchungen mit Bestätigung.
Eine gelöschte importierte Buchung würde beim nächsten Import derselben Datei wieder angelegt, weil ihr
Duplikat-Schlüssel fehlt.

## Entscheidung

- Jede Buchung ist löschbar, einzeln mit Rückfrage, als Sammelaktion mit Häkchen „Ja, endgültig löschen“ und
  Rückfrage; der Server prüft das Häkchen auch.
- Importierte Buchungen kommen in die Sperrliste `buchung_geloescht` (Konto + Duplikat-Schlüssel). CSV-, PDF- und
  Screenshot-Import behandeln sie wie vorhandene Buchungen.
- „Wieder zulassen“ unter Import hebt die Sperre auf.
- Automatische Gegenbuchungen werden mitgelöscht; bei verknüpften Umbuchungen bleibt die andere Seite erhalten.

## Alternativen

- Weiches Löschen (Kennzeichen „gelöscht“): jede Abfrage müsste filtern.
- Nur manuelle Buchungen löschbar: Wunsch nicht erfüllt.

## Folgen

- Nach dem Löschen einer importierten Buchung weicht der Saldoabgleich ab; die Rückfrage weist darauf hin.
