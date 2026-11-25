# Überblick

## Zweck

Die Familie behält mit dem Finanz-Tracker ihre Finanzen im Blick:
- Kontoumsätze aller Konten an einem Ort, mit Kategorien und Personen
- Budgets, Sparquote, Rücklagen und Sparziele
- Immobiliendarlehen und Bausparverträge, Depot und Krypto
- Planung größerer Ausgaben

Die App ersetzt kein Onlinebanking und keine Buchhaltung. Die Kontoumsätze kommen aus den Exporten der Banken.

## Nutzer und Umgebung

- **Haushalt:** eine Familie mit mehreren Personen. Nicht jede Person braucht einen Login; Kinder sind zum Beispiel
  nur Personen, denen Buchungen zugeordnet werden.
- **Banken:**
  - Girokonten bei der GLS Bank und der Sparkasse
  - Tagesgeld bei der UmweltBank
  - Kreditkarte der Hanseatic Bank: nur PDF-Abrechnung bzw. App, kein CSV
- **Geräte:**
  - Home Assistant Green als Server
  - Windows-PC und Android-Handys als Oberfläche; auf dem Handy als installierte App (PWA)
- **Zugriff von unterwegs:** nur über VPN, kein offener Port im Router.

## Funktionsumfang

| Bereich | Kurz | Seit |
| --- | --- | --- |
| Dashboard | Nettovermögen mit Verlauf, Cashflow als Sankey, Ausgaben als Ring, Vermögensaufstellung, Budgets, Sparen, Prüfliste, Importstand; alle Bereiche einklappbar | 0.1.0, neu gestaltet 0.8.0 |
| Buchungen | Liste mit Spaltenfiltern, Inline-Bearbeitung, Sammelaktionen, Aufteilen, Verteilen über Monate, Tags, Löschen, CSV-Export | 0.1.0 |
| Import | CSV mit Importprofilen, Kreditkartenabrechnung als PDF, Screenshots per Texterkennung, Duplikat- und Saldoprüfung, Rückgängig | 0.1.0, PDF/Screenshot 0.4.0/0.5.0 |
| Prüfen | Offene und automatisch zugeordnete Buchungen bestätigen, Regel per Häkchen, Umbuchungsvorschläge, Tabellenansicht | 0.1.0 |
| Kategorien, Regeln, Tags | Kategoriebaum beliebiger Tiefe, Regeln mit Priorität und Test, Tags mit Zeitraum und Budget | 0.1.0, Tags 0.2.0 |
| Budgets | Je Kategorie (inkl. Unterkategorien), je Person, monatlich/jährlich, Übertrag, Prognose | 0.2.0 |
| Sparen | Sparquote mit Ziel, Rücklagen und Sparziele | 0.2.0 |
| Planung | Geplante Ausgaben und Sondereinnahmen, Vermögen nach jedem Posten und zum Stichtag | 0.9.0 |
| Auswertung | Kategorie-Drilldown, Vorjahresvergleich, Personen, Empfänger; frei konfigurierbare Diagramme | 0.2.0, eigene Diagramme 0.6.0 |
| Abos & Verträge | Verträge mit Laufzeit und Kündigungsfrist, Hinweis vor Fristende, erkannte regelmäßige Zahlungen | 0.2.0, als Datensätze 0.6.0 |
| Darlehen | Tilgungsplan, Abgleich mit der Bank, Sondertilgungen, Vergleich, Zinsbindung, Anschlussfinanzierung, Immobilien | 0.2.0 |
| Bausparen | Guthabenprognose, Zuteilung, Bauspardarlehen, Ablösung eines Darlehens | 0.5.0 |
| Depot | Wert = gebuchtes Kapital + Rendite von Hand | 0.4.0 |
| Krypto | Bitcoin- und Ethereum-Bestände, Kurse nachts von CoinGecko, Verlauf je Bestand und gesamt | 0.7.0 |
| Verwaltung | Benutzer, Personen, verschlüsselte Sicherung und Wiederherstellung | 0.1.0, Sicherung 0.2.0 |
| App | HTTPS mit eigener Heim-CA, installierbar als PWA, helles und dunkles Farbschema | 0.2.0, dunkel 0.9.0 |

## Begriffe

| Begriff | Bedeutung |
| --- | --- |
| Buchung | Ein Umsatz auf einem Konto, importiert oder von Hand erfasst. Betrag in Cent, negativ = Abbuchung. |
| Abrechnungsmonat | Monat, in dem eine Buchung zählt. Standard ist der Monat des Buchungsdatums; abweichend z. B. Gehalt vom 28. für den Folgemonat. |
| Verteilung | Eine Buchung wird gleichmäßig auf mehrere Monate verteilt, z. B. eine Jahresversicherung auf 12 Monate. |
| Aufteilung (Split) | Eine Buchung wird auf mehrere Kategorien oder Personen aufgeteilt, z. B. Supermarkt: Lebensmittel und Haushalt. |
| Posten | Rechengrundlage aller Statistiken: je Buchung bzw. je Teil einer Aufteilung, je Monat anteilig verteilt. |
| Umbuchung | Geldbewegung zwischen eigenen Konten. Zählt nie als Einnahme oder Ausgabe. |
| Gegenbuchung | Die andere Seite einer Umbuchung. Bei Konten ohne Import (Bargeld, Depot) legt die App sie automatisch an. |
| Gegenpartei, Partner-Schlüssel | Empfänger bzw. Auftraggeber. Der normalisierte Partner-Schlüssel erkennt „gleicher Empfänger“ für das Gedächtnis, Verträge und Regeln. |
| Importprofil | Beschreibung eines CSV-Formats (Zeichensatz, Trennzeichen, Datums- und Zahlenformat, Spaltenzuordnung). |
| Importlauf | Ein Import einer Datei mit Anzahl neu/doppelt/fehlerhaft und Saldoabgleich; rückgängig machbar. |
| Regel | Bedingungen (Gegenpartei, Text, Betrag, Konto, Richtung …) und Aktionen (Kategorie, Person, Tag, Umbuchung, Monatsversatz, Verteilung). |
| Gedächtnis | Zuordnung aus früher bestätigten Buchungen derselben Gegenpartei. |
| Lernmodell | Naive-Bayes-Modell aus geprüften Buchungen für unbekannte Gegenparteien. |
| Geprüft | Eine Person hat die Zuordnung bestätigt. Automatische Zuordnungen bleiben ungeprüft, bis jemand sie bestätigt. |
| Rücklage | Virtueller Topf auf einem Trägerkonto, z. B. „Auto-Reparatur“ auf dem Tagesgeld. Mit Ziel und Datum wird sie zum Sparziel. |
| Tag | Markierung quer zu Kategorien, z. B. „Urlaub Gardasee 2026“, optional mit Zeitraum und Budget. |
| Vertrag | Abo, Fixkosten oder Vertrag mit Rhythmus, Laufzeit und Kündigungsfrist; Buchungen werden ihm zugeordnet. |
| Plan-Posten | Geplante Ausgabe oder Sondereinnahme in einem Monat (Bereich Planung). |
| Heim-CA | Eigene Zertifizierungsstelle des Add-ons; einmal auf jedem Gerät installiert, damit HTTPS ohne Warnung läuft. |
