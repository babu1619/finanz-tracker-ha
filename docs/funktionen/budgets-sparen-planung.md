# Budgets, Sparen, Planung, Verträge

## Budgets

Code: `services/budgets.py`, `views/budgets.py`.

- **Umfang:** je Kategorie inklusive aller Unterkategorien, optional je Person, monatlich oder jährlich, gültig ab
  einem Monat.
- **Übertrag:** Nicht verbrauchtes oder überzogenes Monatsbudget wird innerhalb des Kalenderjahrs mitgenommen.
- **Warnschwelle:** Standard 90 %. Darüber oder bei einer Prognose über dem Budget wird das Budget gelb, über 100 % rot.
- **Prognose im laufenden Monat:** bisherige Ausgaben + noch ausstehende wiederkehrende Zahlungen aus den Verträgen +
  der variable Anteil, hochgerechnet auf den ganzen Monat. Bei Jahresbudgets wird der Monatsdurchschnitt
  hochgerechnet.
- **Hierarchie:** Ein Budget auf „Mobilität“ umfasst „Mobilität › Autos“. In der Gesamtsumme zählen nur Budgets ohne
  budgetierte Oberkategorie, damit nichts doppelt zählt.
- **Vorschläge:** Durchschnitt der letzten 6 Monate, auf 10 € aufgerundet, für oberste Ausgabenkategorien ohne
  Budget. Auf Knopfdruck werden sie übernommen.

## Sparen

Code: `views/sparen.py`, `services/ruecklagen.py`.

- **Sparquote:** (Einnahmen − Ausgaben) / Einnahmen des Monats. Das Ziel ist einstellbar (`einstellung.sparquote_ziel`,
  Standard 25 %).
- **Gespart seit Jahresbeginn:** dazu die planmäßige Tilgung und die Sondertilgungen aller sichtbaren Darlehen
  („Vermögensaufbau inkl. Tilgung“).
- **Rücklagen:** virtuelle Töpfe auf einem Trägerkonto, z. B. „Auto-Reparatur“ auf dem Tagesgeld.
  - Monatliche Zuführungen bucht die App automatisch und idempotent beim Öffnen von Sparseite und Dashboard.
  - Ausgaben mit „bezahlt aus Rücklage“ werden entnommen; Korrekturen sind möglich.
  - Bezug „Konto“: Der Stand ist einfach der Kontostand des Trägerkontos.
- **Sparziele:** Rücklagen mit Zielbetrag und Zieldatum.
  - Prüfung: Reicht die Zuführung bis zum Ziel? Wenn nicht, zeigt die App die nötige Rate.
  - Prognose: der voraussichtliche Monat, in dem das Ziel erreicht ist.

## Planung

Code: `services/planung.py`, `views/planung.py`, `templates/planung.html`.
Entscheidung: [ADR-0021](../adr/0021-planung-von-ausgaben-und-sondereinnahmen.md).

Frage: Was bleibt vom Vermögen, wenn wir Auto, Dach und Küche kaufen und mit Bonus und Steuererstattung rechnen?

- **Plan-Posten:** Ausgabe oder Sondereinnahme mit Monat, Betrag, optional Kategorie und Notiz. Sie sind gemeinsam für
  alle Benutzer sichtbar.
- **Ausgangsvermögen:**
  - Konten der Vermögensseite, gruppiert wie in der Vermögensaufstellung, einzeln oder je Gruppe wählbar.
  - Vorauswahl ohne Einstellung: alle außer Depots, Krypto und Bausparen, weil dieses Vermögen gebunden ist.
  - Die Auswahl gilt je Benutzer (`einstellung` `planung_auswahl:<id>`).
- **Laufender Überschuss:**
  - Optional, je Benutzer (`planung_sparrate:<id>`).
  - Vorschlag: Ø (Einnahmen − Ausgaben) der letzten 12 abgeschlossenen Monate mit Daten.
  - Zählt ab dem Folgemonat.
- **Rechnung (`berechne`):**
  - Monat für Monat ab heute bis zum spätesten Posten bzw. Stichtag, mindestens 12 Monate, höchstens 15 Jahre.
  - Im selben Monat zählen Einnahmen vor Ausgaben.
  - Offene Posten aus vergangenen Monaten zählen im aktuellen Monat und sind als „offen“ markiert.
  - Erledigte Posten zählen nicht mehr, weil sie schon im Kontostand stecken.
- **Anzeige:**
  - Vermögen nach jedem Posten (rot und „reicht nicht“ unter 0)
  - tiefster Stand mit Warnung
  - Vermögen zum Stichtag (Standard: Monat des letzten offenen Posten, sonst Dezember nächsten Jahres)
  - Verlauf als Fläche
  - Übersicht je Jahr
- **Grenzen:** keine Zinsen, keine Kursentwicklung, keine Inflation.

## Abos und Verträge

Code: `services/vertraege.py`, `views/vertraege.py`.

- **Vertrag als Datensatz** (seit 0.6.0):
  - Art Abo, Fixkosten oder Vertrag
  - Betrag und Zahlungsrhythmus (unregelmäßig, monatlich … alle 2 Jahre)
  - Beginn, Laufzeitende, automatische Verlängerung um n Monate
  - Kündigungsfrist in Tagen, Wochen oder Monaten, „gekündigt zum“
- **Zuordnung:** Buchungen werden einem Vertrag von Hand zugeordnet (Detailseite, Sammelaktion). Zahlungen derselben
  Gegenpartei folgen automatisch, auch bei künftigen Importen.
- **Kennzahlen aus den Zahlungen:**
  - letzte und nächste Zahlung, Betrag pro Monat (Jahresbeiträge anteilig)
  - Preisänderung gegenüber vorher
  - ausgebliebene Zahlung
- **Kündigung:**
  - Die App rechnet das aktuelle Laufzeitende samt Verlängerungen und den letzten Kündigungstag.
  - 31 Tage vorher erscheint oben auf jeder Seite ein Hinweis, bis „gekündigt“ vermerkt ist.
  - Ist die Frist ohne Verlängerung verpasst, wird das angezeigt.
- **Erkannte regelmäßige Zahlungen:** Wiederkehrende Abbuchungen ohne Vertrag erscheinen als Vorschlag. Man übernimmt
  sie mit einem Klick als Abo, Fixkosten oder Vertrag, oder blendet die Gegenpartei dauerhaft aus („kein Vertrag“).
- **Budgets:** Für die Prognose nutzen sie die im Monat noch ausstehenden Vertragszahlungen.
