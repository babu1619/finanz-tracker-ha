# Entwicklung

## Lokale Umgebung

```bash
cd finanz_tracker
python3 -m pip install -r requirements.txt pyyaml   # pyyaml nur für tools/pruefen.py
HTTPS=0 DATA_DIR=./data python3 -m app              # http://localhost:8080
```

Ohne `HTTPS=0` legt die App auch lokal eine Heim-CA unter `DATA_DIR/tls` an und startet mit HTTPS (wie im Add-on).
`HTTPS=1` erzwingt HTTPS. Die Umgebungsvariable hat Vorrang vor `options.json`.

- **Python:** 3.12 im Image, lokal getestet bis 3.13.
- **Daten:** liegen in `DATA_DIR`, ohne Angabe in `finanz_tracker/data/` (per `.gitignore` ausgeschlossen).
- **Optionale Werkzeuge:** Für PDF- und Screenshot-Import `tesseract-ocr`, `tesseract-ocr-deu` und `poppler-utils`
  installieren. Fehlen sie, überspringen die Tests die betroffenen Teile.
- **Anmeldung im Browser ohne HTTPS:** Mit `HTTPS=0` setzt die App das Sitzungscookie nicht auf `Secure`, die
  Anmeldung über `http://` funktioniert also.

## Tests

```bash
cd finanz_tracker
python3 -m unittest discover -s tests          # alle Tests
python3 ../tools/pruefen.py                    # Konfiguration + Tests (aus dem Hauptordner: python3 tools/pruefen.py)
```

`tests/test_app.py` enthält drei Klassen:

| Klasse | Inhalt |
| --- | --- |
| `Grundlagen` | Betrags- und Datumsparser, Euro-Format, Partner-Schlüssel, CSV-Analyse, Soll/Haben, Formatwechsel |
| `Ablauf` | `test_ablauf`: ein durchgehender Ablauf mit echter Datenbank in einem temporären Ordner, von der Einrichtung über Import, Zuordnung, Umbuchungen bis zu jedem Funktionsblock je Version (`_v040` … `_v090`); dazu `test_csrf` |
| `Https` | Heim-CA, Serverzertifikat, Umleitung HTTP → HTTPS, Manifest und Service Worker |

**Neue Version:** Für jede Version kommt eine Methode `_vXYZ(self, db)` dazu, aufgerufen am Ende von `test_ablauf`.
Die Tests laufen nacheinander auf derselben Datenbank. Testdaten früherer Schritte sind also vorhanden und können
stören; deshalb räumt jeder Schritt die eigenen Testdaten auf. Beispiel: Kurse in `_v090`.

**Hilfen:**
- `self.get(url)` und `self.post(url, daten, von=…)` holen das CSRF-Token selbst und folgen Weiterleitungen.
- `db` ist eine direkte `sqlite3`-Verbindung zum Prüfen.

## Sichtprüfung im Browser

Für Änderungen an der Oberfläche reicht ein Test nicht:
1. Einen Demo-Server mit Beispieldaten starten, z. B. ein kleines Skript, das per Test-Client die Einrichtung
   durchläuft und Buchungen direkt in die Datenbank schreibt.
2. Mit Playwright Bildschirmfotos machen: Desktop 1360 px und Handy 390 px, hell und dunkel (`colorScheme`).
3. Fehler in der Browser-Konsole sammeln.

Dialoge (`confirm`) mit `page.on("dialog", d => d.accept())` bestätigen.

Was nur nachgebaut und nicht auf dem Green geprüft wurde, steht ausdrücklich im Bericht. Das betrifft vor allem
Docker-Build, HTTPS mit echter Heim-CA auf Android und die Texterkennung mit echten Screenshots.

## Konventionen

- **Sprache:** Oberfläche, Kommentare, Docstrings, Commit-Nachrichten und Dokumentation auf Deutsch. Bezeichner sind
  ebenfalls deutsch (`buchung`, `konto_id`, `berechne`), wie im bestehenden Code. Dateinamen in `docs/` deutsch, ohne
  Umlaute.
- **Beträge:** immer in Cent als `int`. Eingaben über `util.parse_euro_eingabe`, Ausgabe über die Filter `euro`,
  `euro_vz`, `euro_rund`.
- **SQL:** immer mit Parametern (`?`). Listen über `','.join('?' * len(liste))`, leere Listen als `NULL`.
- **Sichtbarkeit:** Jede Abfrage auf Buchungen oder Konten begrenzt auf `auth.sichtbare_konten()`. Für Kennzahlen gilt
  `statistik.basis_konten()` (ohne Darlehen).
- **Kennzahlen:** über `statistik.posten()` und `art_von()`, nie direkt über `buchung`, damit Aufteilungen,
  Verteilungen und Umbuchungen überall gleich behandelt werden.
- **Views:** Nach POST `commit()`, `melde()` und eine Weiterleitung. Änderungen mit `log_aenderung` protokollieren.
- **Templates:**
  - Farben nur als CSS-Variablen, nie fest im Template.
  - Für positive und negative Werte die Klassen `.pos`/`.neg`.
  - Für Text in Grün oder Rot `var(--gut)` bzw. `var(--bad)`.
- **JavaScript:** ohne Bibliotheken, ohne Build. Browser-Speicher nur in `try/catch` und nur für Komfort
  (eingeklappt, Zeitraum, Farbschema). Diagramme über `window.Diagramme`.
- **Migrationen:** neue Datei mit der nächsten Nummer; bestehende nie ändern. `tools/pruefen.py` prüft die
  lückenlose Nummerierung.
- **Abhängigkeiten:** so wenige wie möglich. Neue Python-Pakete in `requirements.txt` mit Versionsgrenzen, neue
  Systempakete im `Dockerfile`. Kein CDN, keine Downloads zur Laufzeit außer dem Kursabruf.

## Version und Auslieferung

- **Version:** steht zweimal und muss gleich sein: `finanz_tracker/config.yaml` (`version`) und
  `finanz_tracker/app/config.py` (`VERSION`). Dazu gehört ein Abschnitt `## x.y.z – Monat Jahr` oben im
  `CHANGELOG.md`; `tools/pruefen.py` prüft beides.
- **Schema:** minor für neue Funktionen (0.8.0 → 0.9.0), patch für Korrekturen (0.7.0 → 0.7.1).
- **Werkzeuge:**
  - `tools/release.py patch|minor "Text"` erhöht die Version, ergänzt den Changelog, prüft, committet mit Tag und
    pusht. Gedacht für Benjamins eigene kleine Änderungen.
  - Liefert Claude eine fertige Version mit bereits erhöhter Nummer, wird nur geprüft, committet und gepusht, nicht
    `release.py` aufgerufen.
- **Arbeitsweise mit Claude:** siehe [`CLAUDE.md`](../CLAUDE.md). Vor jedem Commit und Push fragt Claude nach.

## Definition of Done

Eine Änderung ist fertig, wenn:
1. alle Tests grün sind und neue Funktionen eigene Tests in `_vXYZ` haben,
2. `python3 tools/pruefen.py` ohne Fehler durchläuft,
3. Oberflächenänderungen im Browser geprüft sind (Desktop und Handy, hell und dunkel),
4. Version in `config.yaml` und `app/config.py` erhöht und der `CHANGELOG.md` ergänzt ist, bei Bedarf auch das README
   (Abschnitt „Neu in x.y – kurz erklärt“),
5. `docs/` nachgeführt ist: Funktionsbeschreibung, Datenmodell bei Schemaänderung, Routen bei neuen Adressen,
6. eine ADR existiert, wenn etwas entschieden wurde (siehe [ADR-Regeln](adr/README.md)),
7. umgesetzte Wünsche in der Wunschliste auf „umgesetzt“ mit Version stehen.
