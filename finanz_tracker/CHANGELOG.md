# Änderungen

## 0.2.2 – Oktober 2026

- Kopfzeile mit den Reitern bleibt beim Scrollen oben fixiert (PC und Handy)

## 0.2.1 – Oktober 2026

- Werkzeuge wie beim Körperdaten-Tracker: `tools/einrichten.py` (GitHub-Namen eintragen), `tools/pruefen.py` (Konfiguration, Code, Migrationen, Versionen und Tests prüfen), `tools/release.py` (neue Version veröffentlichen)
- Automatische Prüfung auf GitHub bei jedem Hochladen inkl. Probestart des Add-ons mit HTTPS
- Optional vorgebaute Images über GitHub (schnellere Updates auf dem Green)
- `.gitattributes` für einheitliche Zeilenenden unter Windows

## 0.2.0 – Oktober 2026

Phase 3 und 4 des Konzepts, HTTPS und installierbare App.

**Buchungen**
- Bereiche „Suche und Filter“ und „Mehrere Buchungen ändern“ einklappbar; der Zustand bleibt je Gerät gespeichert, beim Ankreuzen von Buchungen öffnet sich der Änderungsbereich automatisch
- Aufteilen einer Buchung auf mehrere Kategorien (und Personen) mit Summenprüfung; Statistik, Budgets, Filter und Export rechnen mit den Teilen
- Verteilen auf mehrere Monate (z. B. Jahresbeitrag auf 12 Monate)
- Tags (z. B. „Urlaub Gardasee 2026“, „Steuer 2026“) mit Zeitraum, Budget, Vorschlägen und CSV-Export
- „Bezahlt aus Rücklage“ je Ausgabe
- Handy-Ansicht der Buchungsliste kompakter (Konto und Kategorie unter der Gegenpartei)
- Neue Sammelaktionen: verteilen, Tag hinzufügen/entfernen

**Planen und Auswerten**
- Budgets je Kategorie (inkl. Unterkategorien), optional je Person, monatlich oder jährlich, mit Übertrag, Warnschwelle, Prognose zum Monatsende und Vorschlägen aus den letzten 6 Monaten
- Sparen: Sparquote mit Ziel, gespart seit Jahresbeginn, Vermögensaufbau inkl. Tilgung
- Rücklagen (virtuelle Töpfe auf einem Konto) und Sparziele mit Plan-Prüfung und Prognose
- Darlehen: eigenes Dashboard, Tilgungsplan aus den Konditionen, Abgleich mit der Restschuld laut Bank, Sondertilgungen, Simulation je Darlehen, Vergleich „wohin mit der Sondertilgung“, Immobilien mit Beleihungsquote, Hinweis vor Ende der Zinsbindung
- Auswertung: Kategorie-Drilldown über 6/12/24 Monate oder Kalenderjahr, Vorjahresvergleich, größte Empfänger, Ausgaben je Person
- Abos & Verträge: wiederkehrende Zahlungen werden erkannt; Preisänderungen und ausgebliebene Zahlungen werden gemeldet
- Dashboard zeigt zusätzlich Budgets, Sparen/Sparziele und Hinweise

**Automatik**
- Lernmodell (Naive Bayes) für unbekannte Gegenparteien: ab 85 % Sicherheit automatisch (ungeprüft), darunter Vorschlag
- Trefferquote der Automatik je Quelle (Regeln, frühere Buchungen, Lernmodell)
- Regeln können zusätzlich einen Tag setzen und auf Monate verteilen

**Erfassen, Sicherheit, App**
- Schnellerfassung (Bargeld) fürs Handy
- HTTPS: eigene Heim-CA mit automatisch erneuertem Serverzertifikat (inkl. IP-Adressen des Home Assistant) oder Zertifikat aus /ssl; alte http://-Adressen werden auf https:// umgeleitet
- Installierbar als App (PWA) in Chrome auf Android und am PC, mit Kurzbefehlen „Bar erfassen“, „Prüfen“, „Buchungen“
- Verschlüsselte Sicherung (.ftbak, AES + scrypt) und Wiederherstellung in der Verwaltung
- Navigation neu: Hauptpunkte oben, Verwaltungsseiten unter „Mehr“

**Fehlerbehebungen**
- Beträge mit Tausenderpunkt ohne Komma (z. B. „1.000“) werden richtig gelesen

Weiterhin offen: PDF-Import der Kreditkarte und CSV-Import der Darlehenskonten – dafür werden Beispieldateien der Bank benötigt.

## 0.1.0 – Oktober 2026

Erste Version (Phase 1 und 2 des Konzepts).

- Ersteinrichtung, Login mit Sperre nach Fehlversuchen, Rollen Admin, Mitglied, Lesend
- Personen (auch ohne Login) und Benutzerverwaltung
- Konten inkl. privater Konten und Darlehenskonten (eigener Bereich, zählen nicht ins Dashboard)
- Importprofile je Konto; CSV-Spaltenzuordnung direkt in der App mit Live-Vorschau
- CSV-Import mit Vorschau, Duplikaterkennung, Saldoabgleich, automatischem Startsaldo und Rückgängig
- Kategorien in beliebiger Tiefe mit Startset
- Regeln mit Priorität, Test gegen bestehende Buchungen und Monatsversatz
- Zuordnung aus früheren Buchungen („Gedächtnis“)
- Umbuchungserkennung zwischen eigenen Konten (Darlehen ausgenommen)
- Prüf-Modus mit Vorschlägen und Regel per Häkchen
- Buchungsliste mit Filtern, Summenzeile, Sammelaktionen und CSV-Export
- Dashboard mit Monatswahl, Personenfilter, Kategorien, 12-Monats-Verlauf, Prüfliste und Importstand
- Datenbank-Download als Sicherung
