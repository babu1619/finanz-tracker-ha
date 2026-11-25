# Vermögen und Schulden

## Darlehen

Code: `services/darlehen.py`, `views/darlehen.py`, `templates/darlehen*.html`.
Entscheidung: [ADR-0010](../adr/0010-darlehen-getrennt-vom-haushalt.md).

Darlehenskonten (Typ `darlehen`) haben einen eigenen Bereich und zählen nie in Einnahmen, Ausgaben oder Budgets. Die
monatliche Rate ist eine Ausgabe des Zahlkontos.

- **Konditionen:**
  - Ursprungsbetrag, Sollzins, Monatsrate, erste Rate, Zinsbindung bis, Zahlkonto
  - Sondertilgungsrahmen in % je Jahr oder als fester €-Betrag; der €-Betrag hat Vorrang
  - Hinweisvorlauf vor Ende der Zinsbindung (Standard 24 Monate)
  - optional Immobilie
- **Tilgungsplan:** Annuitätendarlehen, monatlich aus den Konditionen bis zur vollständigen Rückzahlung.
  - Sondertilgungen werden im jeweiligen Monat abgezogen.
  - Ein **Abgleich** (Restschuld laut Bank zu einem Datum) setzt den Plan ab diesem Monat neu auf.
- **Kontostand oder Plan:** Sind Kontoauszüge des Darlehens importiert, gilt der Kontostand. Sonst gilt die
  Restschuld laut Plan.
- **Sondertilgung:**
  - Als Ereignis erfassen; auf Wunsch legt die App eine Buchung im Darlehenskonto an und verknüpft die Abbuchung
    im Zahlkonto.
  - Auf der Detailseite einer Abbuchung gibt es „Als Sondertilgung erfassen“.
  - Wird die Sondertilgung gelöscht, verschwindet auch die angelegte Buchung.
- **Raten zuordnen:** Abbuchungen im Zahlkonto mit dem Betrag der Monatsrate werden automatisch ihrem Darlehen
  zugeordnet. Die Detailseite zeigt die gezahlten Beträge je Jahr neben dem Plan.
- **Simulation je Darlehen:** zusätzliche Sondertilgungen. Ergebnis: Ersparnis an Zinsen und früheres Ende.
- **„Wohin mit einer Sondertilgung?“** (korrigiert in 0.7.1):
  - Jedes Darlehen wird höchstens mit dem im Jahr noch freien Sondertilgungsrahmen und der Restschuld gerechnet.
  - Verglichen wird fair bis zum frühesten Ende einer Zinsbindung, dazu die Ersparnis je 1.000 €.
  - Eine Empfehlung verteilt den Betrag nach dem höchsten Zins zuerst; der Teil, der im Jahr nicht mehr
    sondergetilgt werden kann, wird ausgewiesen.
- **Zinsbindungsenden:**
  - Tabelle mit kumulierter Restschuld zu jedem Ende einer Zinsbindung, dazu Bausparguthaben und Netto.
  - Je Termin zwei editierbare Spalten (Sollzins, Monatsrate) simulieren die Anschlussfinanzierung: Ergebnis
    Schuldenfrei-Termin, Zinsen, anfängliche Tilgung. Spätere Termine rechnen mit dem Ergebnis weiter.
  - „Als Planannahme übernehmen“ speichert die Werte (`anschluss_sollzins`, `anschluss_rate_cent`). Plan,
    Restschuld-Übersicht und Bausparvergleich rechnen danach damit.
- **Übersicht:**
  - Monatsrate gesamt, aufgeteilt in Darlehen und Bausparen
  - Restschuld abzüglich Bausparguthaben = Netto
  - Restschuld-Verlauf je Jahr
- **Hinweis im Dashboard:** Endet eine Zinsbindung innerhalb des Vorlaufs, steht ein Hinweis unter „Zu prüfen“.
- **Immobilien:** Kaufpreis bzw. geschätzter Wert. Daraus ergeben sich Eigenanteil und Beleihungsquote
  (Restschuld / Wert).

## Bausparen

Code: `services/bausparen.py`, Seiten unter `/darlehen/bausparen/…`.
Entscheidung: [ADR-0011](../adr/0011-depot-und-bausparen-vereinfacht.md).

Ein Bausparvertrag ist kein Konto, sondern ein eigener Datensatz im Bereich Darlehen. Das Modell ist vereinfacht,
für die Planung genau genug, nicht für den Cent:

- **Guthaben:** Ausgangspunkt ist der jüngste eingetragene Guthabenstand (Jahreskontoauszug), sonst 0 € zu
  Vertragsbeginn.
- **Sparphase:** monatlich die Sparrate. Guthabenzinsen laufen monatlich anteilig auf und werden zum Jahresende
  gutgeschrieben.
- **Zuteilung:** Der Vertrag ist zuteilungsreif, sobald das Mindestsparguthaben erreicht ist (z. B. 40 % der
  Bausparsumme), frühestens zum gewünschten Termin. Die Bewertungszahl der Bausparkasse wird nicht nachgebildet.
- **Bauspardarlehen:**
  - Höhe: Bausparsumme − Guthaben.
  - Monatsrate: Tilgungsbeitrag in ‰ der Bausparsumme; der Zins wird monatlich gerechnet.
  - Erste Rate im Monat nach der Zuteilung.
- **Ablösung:** Ein Vertrag kann einem Darlehen zugeordnet sein. Die Detailseite zeigt, ob und wann das Darlehen
  damit abgelöst werden kann.
- **Rate heute:** In der Sparphase die Sparrate, danach Zins- und Tilgungsbeitrag. Sie fließt in die Monatsrate
  „inkl. Bausparen“.

## Depot

Code: `services/depot.py`, `views/depot.py`. Entscheidung: [ADR-0011](../adr/0011-depot-und-bausparen-vereinfacht.md).

Es gibt keinen Kontoauszug und keine Einzelwerte. Erfasst wird nur, was für den Wert nötig ist:

- **Gebuchtes Kapital:**
  - Startsaldo + Einzahlungen − Auszahlungen − Gebühren + Erträge, jeweils als Buchung im Depotkonto.
  - Eine Umbuchung aus einem importierten Konto ins Depot legt die Einzahlung automatisch an.
- **Rendite:** von Hand aus der Depot-App, in % auf das gebuchte Kapital oder in €. Es gilt der jüngste Eintrag;
  ältere bleiben als Verlauf.
- **Depotwert:** gebuchtes Kapital + Rendite.

## Krypto

Code: `services/krypto.py`, `views/krypto.py`. Entscheidung: [ADR-0013](../adr/0013-krypto-kurse-von-coingecko.md).

- **Bestand:** Konto vom Typ `krypto` mit Coin (Bitcoin oder Ethereum), Menge, optional Einstand. Je Bestand ist
  einstellbar, ob er im Dashboard zum Vermögen zählt (`im_vermoegen`).
- **Kurse:**
  - Quelle: CoinGecko in Euro, ohne API-Schlüssel, ein Kurs je Tag (`krypto_kurs`).
  - Abruf jede Nacht ab 4 Uhr (Zeitzone des Add-ons, sonst Europe/Berlin) und auf Knopfdruck; fehlender Verlauf
    bis 365 Tage wird nachgeholt.
  - Nach einem Fehlschlag frühestens 30 Minuten später neu. Der letzte Abruf steht oben auf der Seite.
- **Seite:**
  - Wert aller Bestände, Kurs je Coin, Gewinn gegenüber Einstand, Veränderung zum Vortag
  - Verlauf mit Zeitraum (7 Tage bis alles) für:
    - Gesamtwert aller Bestände (Standard, kumuliert; fehlende Tageskurse vom Vortag)
    - Gesamtwert und einzelne Bestände als Linien
    - Wert eines Bestands
    - Kurs eines Coins
