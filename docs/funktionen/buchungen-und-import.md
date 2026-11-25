# Buchungen und Import

## CSV-Import

Code: `services/csvimport.py`, `services/importer.py`, `views/importe.py`.
Entscheidung: [ADR-0006](../adr/0006-csv-import-mit-importprofilen.md).

1. **Importprofil:** Einmal je Bankformat. Beim Hochladen einer Beispieldatei erkennt die App:
   - Zeichensatz, Trennzeichen, Kopfzeile (auch nach einem Vorspann)
   - Datumsformat, Dezimalformat und Spaltenvorschlag

   Über jeder Spalte wählt man das Feld, eine Live-Vorschau zeigt das Ergebnis. Für den Betrag gibt es drei Modi:
   - Vorzeichen
   - Soll/Haben in zwei Spalten
   - Kennzeichenspalte

   Die Spaltenüberschriften werden gespeichert. Ändert die Bank das Format, meldet der Import
   „Spaltenüberschriften nicht gefunden“, und man lädt im Profil eine neue Beispieldatei hoch.
2. **Konto erkennen:** über eine IBAN im Dateikopf oder einen hinterlegten Erkennungswert. Sonst wählt man das Konto
   von Hand.
3. **Vorschau:** Jede Zeile bekommt einen Duplikat-Schlüssel. Er ist der SHA-256 aus Konto, Datum, Betrag,
   Gegen-IBAN, Verwendungszweck, Gegenpartei und einer laufenden Nummer für gleiche Zeilen in derselben Datei.
   Vorhandene Schlüssel und gelöschte Buchungen aus der Sperrliste gelten als „schon vorhanden“. Die Datei liegt bis
   zum Übernehmen in `/data/tmp`.
4. **Übernehmen:**
   - Die App legt die Buchungen an und protokolliert den Importlauf (Dateiname, Datei-Hash, Anzahl neu/doppelt/fehlerhaft).
   - Danach laufen Umbuchungserkennung und automatische Zuordnung, Vertrags- und Darlehenszuordnung über die
     Gegenpartei.
5. **Saldoabgleich:** Hat die Datei eine Saldo-Spalte, vergleicht die App den Endsaldo mit dem errechneten
   Kontostand an diesem Tag (auf- und absteigend sortierte Exporte werden erkannt). Beim ersten Import eines Kontos
   ergibt sich daraus der Startsaldo. Eine Abweichung erscheint als Warnung im Dashboard.
6. **Rückgängig:** Jeder Importlauf lässt sich zurücknehmen; seine Buchungen werden entfernt.

Überlappende Exporte sind kein Problem, weil Duplikate übersprungen werden. Die Dashboard-Liste „Konten und
Importstand“ erinnert nach `import_erinnerung_tage` an den nächsten Import.

## Kreditkartenabrechnung (PDF) und Screenshots

Code: `services/abrechnung.py`, `services/ocr.py`, `views/importe.py` (`/import/screenshot`).
Entscheidung: [ADR-0007](../adr/0007-kreditkarte-per-pdf-und-lokaler-texterkennung.md).

- **PDF-Abrechnung** (z. B. Hanseatic Bank):
  - Die App liest den Text mit `pdftotext` samt Wortpositionen. Gescannte PDFs werden als Bild an Tesseract
    gegeben.
  - Spalten werden über die Position erkannt: Buchungsdatum, Transaktionsdatum, mehrzeilige Beschreibung, Betrag.
  - Das Buchungsdatum wird Buchungsdatum, das Transaktionsdatum wird Wertstellung und steht im Verwendungszweck.
  - Saldoprüfung: alter Saldo + Umsätze = neuer Saldo. Beim ersten Import wird der Saldo zum Startsaldo, danach
    abgeglichen wie beim CSV.
- **Screenshots der Banking-App:**
  - Bilder auswählen, hineinziehen oder aus der Zwischenablage einfügen.
  - Tesseract erkennt Wörter mit Position. Jeder Betrag verankert einen Umsatz; darüber stehen Name und Kategorie
    der Bank, darunter Datum und Status (gebucht/vorgemerkt). Symbole links neben der Textspalte fallen weg,
    Silbentrennungen werden zusammengeführt.
  - Mehrere, auch überlappende Screenshots werden zusammengeführt.
  - Eine Prüftabelle zeigt jeden Umsatz mit Status:
    - neu
    - schon übernommen (Schlüssel `ocr:…`)
    - „ähnlich“ (gleicher Betrag ±4 Tage)

    Vorgemerkte Umsätze sind nicht vorausgewählt.
  - Schon per Screenshot übernommene Umsätze erscheinen beim späteren PDF-Import als „evtl. vorhanden“.

Alles läuft lokal auf dem Green; kein Bild und kein PDF verlässt das Gerät.

## Buchungsliste

Code: `views/buchungen.py`, `templates/buchungen.html`.

- **Filtern und Sortieren:** über die Spaltenköpfe (Datum von/bis, Abrechnungsmonat, Konto, Gegenpartei/Volltext,
  Kategorie, Person, Tag, Betrag von/bis, Richtung, Art, Status, Vertrag, Darlehen). Aktive Filter erscheinen als entfernbare Chips.
  Die Summenzeile rechnet über das gefilterte Ergebnis.
- **Inline-Bearbeitung:** Kategorie, Person und Tags direkt in der Tabelle, sofort gespeichert
  (`/buchungen/<id>/inline`, JSON). Wählt man die Kategorie „Umbuchung“, fragt die Tabelle nach dem Gegenkonto.
- **Sammelaktionen** für ausgewählte Buchungen:
  - Kategorie, Person oder Abrechnungsmonat setzen
  - verteilen
  - Tag hinzufügen oder entfernen
  - als geprüft bestätigen
  - als Umbuchung markieren
  - zwei Buchungen als Umbuchung verknüpfen
  - Vertrag oder Darlehen zuordnen
  - löschen
- **Detailseite** einer Buchung:
  - alle Felder, Umschalter Ausgabe/Umbuchung mit Gegenkonto
  - Aufteilen auf mehrere Kategorien und Personen (Summe muss stimmen)
  - Verteilen auf 1–60 Monate
  - „bezahlt aus Rücklage“
  - Zuordnung zu Vertrag oder Darlehen
  - „Als Sondertilgung erfassen“
  - „Regel daraus erstellen“
  - Löschen
- **Export:** `/buchungen/export.csv` mit den aktuellen Filtern.
- Auf dem Handy stehen Konto und Kategorie platzsparend unter der Gegenpartei.

## Bar erfassen

`/erfassen/` ist die schnelle Eingabe fürs Handy: Betrag, Richtung, Kategorie, Person, Notiz.
- **Konto:** Vorausgewählt ist das Barkonto. Jedes andere sichtbare Konto außer Darlehen und Krypto geht auch, für
  Konten ohne Import.
- **Kennzeichen:** Die Buchung bekommt `manuell_erfasst = 1`.
- **Kurzbefehl:** Die PWA bietet die Erfassung auf dem Startbildschirm an.

## Buchungen löschen

Code: `services/loeschen.py`. Entscheidung: [ADR-0020](../adr/0020-loeschen-mit-sperrliste.md).

- **Wege:**
  - einzeln auf der Detailseite, mit Rückfrage
  - als Sammelaktion: zusätzlich das Häkchen „Ja, endgültig löschen“ und eine Rückfrage; der Server prüft das
    Häkchen ebenfalls
- **Was mitgeht:** Automatisch angelegte Gegenbuchungen (Bargeld, Depot, Darlehen) werden mit gelöscht. Bei einer
  verknüpften Umbuchung bleibt die andere Seite als Buchung erhalten; nur die Verknüpfung fällt weg. Aufteilungen,
  Tags und Rücklagen-Bewegungen werden entfernt. Sondertilgungen behalten ihr Plan-Ereignis.
- **Sperrliste:** Importierte Buchungen kommen in `buchung_geloescht`. Ein erneuter Import derselben Datei
  überspringt sie. Unter Import → „Gelöschte Buchungen“ hebt „Wieder zulassen“ die Sperre auf.
- **Hinweis:** Nach dem Löschen einer importierten Buchung stimmt der Kontostand nicht mehr mit dem Auszug. Die
  Rückfrage sagt das.
