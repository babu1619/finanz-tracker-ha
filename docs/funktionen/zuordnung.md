# Zuordnung

Ziel: Nach einigen Wochen ordnet die App die meisten Buchungen selbst zu, und der Mensch bestätigt nur noch.
Entscheidung: [ADR-0008](../adr/0008-zuordnung-regeln-gedaechtnis-lernmodell.md).

## Kategorien

Code: `services/kategorien.py`, `views/kategorien.py`.

- **Baum:** beliebig tief, z. B. „Mobilität › Autos › Peugeot“.
- **Pfad:** Gespeichert wird der ganze Pfad, damit Teilbäume per Präfix abfragbar sind. Beim Umbenennen oder
  Verschieben werden die Pfade der Unterkategorien nachgeführt.
- **Art:** einnahme, ausgabe oder umbuchung. Ohne eigene Angabe erbt eine Kategorie die Art vom Elternteil.
- **Startset:** Bei der Ersteinrichtung legt die App eine übliche Gliederung an, unter anderem „Einnahmen“
  mit Gehalt und Kindergeld, „Wohnen“, „Lebensmittel“, „Mobilität“, „Versicherungen“ und „Umbuchung“.
- **Suche:** Die Suche auf der Kategorienseite zeigt Treffer mit allen Unterkategorien und die Oberkategorien zur
  Einordnung.

## Ablauf der Automatik

`services/zuordnung.py`, `ordne_zu()`, läuft nach jedem Import und auf Wunsch über alle offenen Buchungen. Je
Buchung gilt die erste passende Stufe:

1. **Regeln**
   - In der Reihenfolge der Priorität, die erste passende Regel gewinnt.
   - Bedingungen und Aktionen: siehe [Datenmodell](../datenmodell.md#ordnung-und-automatik).
   - Eine Regel setzt die Zuordnung direkt (Quelle `regel`).
2. **Gedächtnis**
   - Die häufigste bestätigte Kategorie (und Person) früherer Buchungen derselben Gegenpartei (`partner_key`).
   - Haben mindestens zwei frühere Buchungen alle dieselbe Kategorie, gilt die Zuordnung als geprüft; sonst bleibt
     sie ungeprüft.
3. **Lernmodell**
   - Naive Bayes in reinem Python (`services/modell.py`), trainiert auf allen geprüften Buchungen.
   - Merkmale: Wörter aus Gegenpartei und Verwendungszweck (ohne Füllwörter), Konto, Richtung, Betragsgröße.
   - Ab 85 % Wahrscheinlichkeit wird die Kategorie gesetzt, bleibt aber ungeprüft. Zwischen 50 und 85 % erscheint
     sie nur als Vorschlag im Prüf-Modus.

**Geschützt:**
- Manuell zugeordnete Buchungen und Umbuchungen ändern Gedächtnis und Lernmodell nie.
- Regeln überschreiben sie nur, wenn man beim Speichern einer Regel „auf alle passenden Buchungen anwenden“ wählt
  (seit 0.5.0). Der Regeltest zeigt vorher, wie viele davon manuell zugeordnet sind.
- Aufgeteilte Buchungen, verknüpfte Umbuchungen und automatische Gegenbuchungen schreibt die Automatik nie um.

**Trefferquote:**
- `zuordnung_feedback` merkt, ob eine automatische Zuordnung beim Prüfen bestätigt oder geändert wurde.
- Die Seite „Regeln“ zeigt daraus die Trefferquote je Quelle der letzten 6 Monate.

## Regeln

Code: `views/regeln.py`, `templates/regel.html`.

- **Bearbeiten:**
  - Mehrere Bedingungen, alle müssen zutreffen.
  - „Testen“ zeigt die Treffer unter den vorhandenen Buchungen und wie viele anders zugeordnet würden.
  - Priorität per Verschieben; Suche über Name, Bedingungen und Aktionen.
- **Anlegen ohne Formular:**
  - Im Prüf-Modus per Häkchen „Regel erstellen“.
  - Auf der Detailseite einer Buchung mit „Regel daraus erstellen“. Bei Umbuchungen übernimmt sie das Gegenkonto.
- **Beispiel:** „Gegenpartei enthält Geldautomat“ → Umbuchung ins Barkonto. Abhebungen sind dann schon beim Import
  vollständig gebucht.

## Prüf-Modus

Code: `views/pruefen.py`, `templates/pruefen.html`, `pruefen_tabelle.html`.

- **Was:** Buchungen ohne Kategorie und automatisch zugeordnete, die noch ungeprüft sind. Die Zahl steht an
  „Prüfen“ in der Kopfzeile.
- **Einzelansicht:**
  - Kategorie per Pfadsuche, Person, Tags mit Vorschlägen, Notiz
  - Umbuchung mit Gegenkonto
  - Häkchen „Regel erstellen“
  - Vorschläge aus Gedächtnis und Lernmodell
- **Tabellenansicht:** für viele offene Buchungen auf einmal.
- **Umbuchungsvorschläge:** unsichere Paare zum Bestätigen oder Ablehnen.

## Umbuchungen

Code: `services/umbuchungen.py`. Entscheidung: [ADR-0009](../adr/0009-umbuchungen-und-automatische-gegenbuchungen.md).

- **Erkennung:** Abbuchung auf Konto A und Gutschrift auf Konto B mit genau gleichem Betrag, höchstens 3 Tage
  auseinander, bei Kreditkarten 10 Tage.
- **Bewertung:**

  | Merkmal | Punkte |
  | --- | --- |
  | Grundwert | 0,5 |
  | je Tag Abstand | −0,04 |
  | Gegen-IBAN passt zum anderen Konto | +0,45 |
  | Stichwort (z. B. Umbuchung, Übertrag, Geldautomat) | +0,2 |
  | Kreditkarte beteiligt | +0,1 |

- **Ergebnis:** Ab 0,8 und eindeutig (der zweitbeste Kandidat liegt mindestens 0,15 darunter) verknüpft die App
  automatisch; sonst entsteht ein Vorschlag im Prüf-Modus.
- **Darlehen:** Darlehenskonten sind ausgenommen. Eine Rate ist eine Ausgabe des Haushalts, keine Umbuchung.
- **Gegenkonto von Hand:** Eine Buchung lässt sich als Umbuchung mit Gegenkonto markieren, auf der Detailseite, in
  der Tabelle, im Prüf-Modus, per Sammelaktion oder per Regel. Kommt die Gegenbuchung später per Import, wird sie
  verknüpft.
- **Automatische Gegenbuchung:** Bei Konten ohne Import (Bargeld, Depot) legt die App die Gegenbuchung selbst an
  (`auto_gegenbuchung = 1`, `dedup_hash = gegen:<id>`), z. B. −200 € Geldautomat → +200 € Bargeld. Wird die Umbuchung
  gelöst oder die Buchung gelöscht, verschwindet die Gegenbuchung wieder. Eine im Gegenkonto schon von Hand
  erfasste, wartende Gegenbuchung wird gefunden und verknüpft statt doppelt angelegt.

## Tags

Code: `services/tags.py`, `views/tags.py`.

- **Zweck:** Markierungen quer zu den Kategorien, z. B. „Urlaub Gardasee 2026“ oder „Steuer 2026“.
- **Zeitraum und Budget:** optional. Ein Tag mit Zeitraum schlägt passende, noch nicht markierte Buchungen vor.
- **Vergeben:** inline, im Prüf-Modus, per Sammelaktion oder per Regel.
- **Export:** CSV je Tag, etwa für die Steuer.
