# Funktionen

Fachliche Beschreibung je Bereich: wofür er da ist, wie er rechnet, wo der Code liegt.

| Dokument | Bereiche |
| --- | --- |
| [Buchungen und Import](buchungen-und-import.md) | CSV-, PDF- und Screenshot-Import, Duplikate, Saldoabgleich, Buchungsliste, Aufteilen, Verteilen, Bar erfassen, Löschen, Export |
| [Zuordnung](zuordnung.md) | Kategorien, Regeln, Gedächtnis, Lernmodell, Prüf-Modus, Umbuchungen und Gegenbuchungen, Tags |
| [Dashboard und Auswertung](dashboard-und-auswertung.md) | Dashboard, Nettovermögen, Cashflow, Vermögensaufstellung, Auswertung, eigene Diagramme |
| [Budgets, Sparen, Planung, Verträge](budgets-sparen-planung.md) | Budgets, Sparquote, Rücklagen und Sparziele, Planung, Abos und Verträge |
| [Vermögen und Schulden](vermoegen.md) | Darlehen, Immobilien, Bausparen, Depot, Krypto |
| [Verwaltung und App](verwaltung-und-app.md) | Ersteinrichtung, Benutzer und Personen, Sicherung, HTTPS-Zertifikat, PWA, Farbschema |

Grundsätze für alle Bereiche:
- **Sichtbarkeit:** Jede Seite arbeitet nur mit den Konten aus `auth.sichtbare_konten()`.
- **Darlehen:** Darlehenskonten zählen nicht in Einnahmen und Ausgaben.
- **Umbuchungen:** Sie zählen nie als Einnahme oder Ausgabe.
- **Rechengrundlage:** Kennzahlen rechnen über die Posten (Sicht `posten_monat`), damit Aufteilungen und Verteilungen
  überall gleich wirken.
- **Navigation:** Ein Klick auf eine Zahl führt, wo möglich, zu den passenden Buchungen.
