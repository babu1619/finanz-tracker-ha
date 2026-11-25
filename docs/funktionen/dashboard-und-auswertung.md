# Dashboard und Auswertung

## Dashboard

Code: `views/dashboard.py`, `services/vermoegen.py`, `templates/dashboard.html`, `static/dashboard.js`.
Gestaltung angelehnt an die Finanz-App Sure ([ADR-0019](../adr/0019-dashboard-im-stil-von-sure.md)).

**Kopf:**
- Monatswahl (Abrechnungsmonat) und Personenfilter
- „Alle einklappen“ und „Alle ausklappen“
- „Bar erfassen“ und „Datei importieren“

**Bereiche:** Jeder Bereich klappt per Klick auf seine Überschrift ein und aus. Eingeklappt bleibt eine Kurzinfo
sichtbar, zum Beispiel „Saldo 3.471 €“. Der Zustand wird je Gerät gespeichert (`localStorage`, Schlüssel
`dashboard-bereiche-zu`).

| Bereich | Inhalt |
| --- | --- |
| Nettovermögen | Vermögen minus Schulden heute, Veränderung im gewählten Zeitraum (6 M, 1 J, 3 J, 5 J, alles) in € und %, Linie der Monatsendstände, darunter Vermögen und Schulden |
| Zu prüfen | Buchungen ohne Kategorie, ungeprüfte automatische Zuordnungen, Umbuchungsvorschläge, Vertragshinweise (Preisänderung, ausgebliebene Zahlung), Darlehenshinweise (Zinsbindung), Saldoabweichungen |
| Cashflow | Einnahmen, Ausgaben, Saldo und Sparquote; Sankey-Diagramm für Monat, laufendes Jahr oder 12 Monate |
| Ausgaben nach Kategorie | Ring mit Summe in der Mitte, daneben die Kategorienliste mit Balken, Δ zum Vormonat und aufklappbaren Unterkategorien; gleiche Farbe je Kategorie in Ring, Liste und Sankey |
| Sparen | Sparquote des Monats mit Ziel, gespart seit Jahresbeginn (+ Tilgung), bis zu vier Sparziele |
| Vermögensaufstellung | Reiter Vermögen und Schulden: Summe, Anteilsbalken nach Kontoart, Tabelle mit Anteil, 12-Monats-Verlauf und Wert je Gruppe; Gruppen aufklappbar zu den Konten |
| Budgets | die wichtigsten Budgets mit Fortschritt, Prognose und Zeitmarke |
| Einnahmen und Ausgaben, 12 Monate | Säulen je Monat; Klick wechselt in den Monat |
| Konten und Importstand | Saldo, letzter Import, Status (Saldo stimmt, weicht ab, Import fällig, ohne Abgleich) |

**Klickziele:**
- Einnahmen, Ausgaben, Kategorien, Sankey-Knoten und Ringsegmente öffnen die passenden Buchungen.
- Konten öffnen ihre Buchungen. Depot, Darlehen und Krypto öffnen ihre eigene Seite.

### Nettovermögen rekonstruieren

`vermoegen.verlauf_je_konto()` rechnet Monatsendstände je Konto. Der Zeitraum reicht ab der ersten Buchung, mindestens
12 und höchstens 120 Monate.

| Kontoart | Monatsendstand |
| --- | --- |
| Giro, Tagesgeld, Kreditkarte, Bargeld, Sonstiges | Startsaldo + Summe aller Buchungen bis Monatsende |
| Depot | gebuchtes Kapital bis Monatsende + Rendite laut jüngster Eintragung bis dahin; aktueller Monat = `depot.wert()` |
| Krypto (nur `im_vermoegen`) | heutige Menge × Kurs am Monatsende (vor dem ersten Kurs: erster Kurs) |
| Darlehen mit importierten Buchungen | Kontostand (negativ) |
| Darlehen ohne Buchungen | −Restschuld laut Tilgungsplan |
| Bausparvertrag | Guthaben laut Stand bzw. Prognose (vor Vertragsbeginn 0) |

Zuordnung zu den Seiten der Aufstellung:
- Vermögen: Giro, Tagesgeld, Bargeld, Depot, Krypto, Sonstiges, Bausparen.
- Schulden: Kreditkarte, Darlehen.
- Ein Konto wechselt die Seite, wenn sein Vorzeichen nicht passt, etwa ein Girokonto im Minus.

### Cashflow (Sankey)

`vermoegen.cashflow()` rechnet über die Posten des Zeitraums.

- **Links:** Einnahmen je Kategorie. Liegen die Einnahmen unter einer Sammelkategorie „Einnahmen“, nimmt die App
  deren Unterkategorien (Gehalt, Kindergeld …). Höchstens sechs Quellen; bei mehr werden alle ab der sechsten zu
  „Weitere Einnahmen“ zusammengefasst.
- **Rechts:** Ausgaben je oberster Kategorie, höchstens acht Ziele; bei mehr werden alle ab der achten zu „Weitere
  Ausgaben“ zusammengefasst.
- **Ausgleich:** Überschuss → „Gespart“. Fehlbetrag → links „Aus Ersparnissen“.
- **Gleichgewicht:** Quellen und Ziele sind immer gleich groß; ein Test prüft das.

## Auswertung

Code: `views/auswertung.py`, `services/auswertung_daten.py`, `static/auswertung.js`.

**Seite „Auswertung“:**
- Zeitraum: 6, 12 oder 24 Monate oder ein Kalenderjahr.
- Kategorie-Drilldown: oberste Kategorien bzw. die Unterkategorien der gewählten Kategorie je Monat.
- Vorjahresvergleich.
- Größte Empfänger und Ausgaben je Person.

**Eigene Auswertungen** (seit 0.6.0): Jeder Benutzer legt Ansichten mit beliebig vielen Diagrammen an
(`auswertung_ansicht`). Ein Diagramm wird als JSON beschrieben:

| Einstellung | Werte |
| --- | --- |
| Messgröße | Ausgaben, Einnahmen, Saldo, Anzahl Buchungen |
| Gruppe | gesamt, Einnahmen und Ausgaben, Kategorien, Unterkategorien einer Kategorie, Tags, Personen, Konten, Gegenparteien, Verträge, Vertragsart |
| Zeit | je Monat, Quartal, Jahr oder Summe |
| Zeitraum | 3, 6, 12, 24, 36 Monate, 5 Jahre, dieses Jahr, letztes Jahr, eigener Zeitraum |
| Darstellung | Säulen, gestapelt, Balken waagerecht, Linie, Fläche, Ring, Torte, Tabelle, Kennzahl, Wärmekarte |
| Extras | Vorjahresvergleich, kumuliert, Top-N mit „Sonstige“, Auswahl einzelner IDs, Breite halb/voll |

Was gezeigt wird, berechnet der Server (`/auswertung/daten`); wie es aussieht, entscheidet der Browser. Ein Klick
auf einen Wert öffnet die Buchungen.
