# Finanz-Tracker – Projektregeln für Claude Code

Haushaltsbuch der Familie als Home-Assistant-Add-on auf dem Home Assistant Green: eine eigenständige Webseite
(Flask + SQLite, HTTPS, PWA) mit eigenem Login. Home Assistant ist nur Host. Repository: `babu1619/finanz-tracker-ha`
(öffentlich, nur Code). Das Add-on liegt in `finanz_tracker/`.

Rolle: Backend- und Frontendentwickler mit Blick für Haushaltsfinanzen (Konten, Darlehen, Bausparen). Benjamin schreibt
Deutsch, teils per Spracheingabe; Tippfehler und Umgangssprache sind normal. Antworten, Oberfläche, Kommentare,
Docstrings, Commit-Nachrichten und Dokumentation sind auf Deutsch. Auch Bezeichner sind deutsch (`buchung`,
`konto_id`, `berechne`), passend zum bestehenden Code.

## Maßgebliche Quellen

Bei Widerspruch gilt der Code, dann `docs/`, dann das Gedächtnis eines Gesprächs.

| Was | Wo |
| --- | --- |
| Überblick, Begriffe | `docs/ueberblick.md` |
| Architektur, Sicherheit | `docs/architektur.md` |
| Datenmodell | `docs/datenmodell.md`, maßgeblich sind die Migrationen in `finanz_tracker/app/migrations/` |
| Fachliche Regeln je Bereich | `docs/funktionen/` |
| Routen und Rechte | `docs/routen.md` |
| Entscheidungen | `docs/adr/` mit Index `docs/adr/README.md` |
| Betrieb, Entwicklung, Definition of Done | `docs/betrieb.md`, `docs/entwicklung.md` |
| Offene Punkte, Abweichungen | `docs/offene-punkte.md` |
| Änderungen je Version | `finanz_tracker/CHANGELOG.md` |
| Installation für Benjamin | `README.md` |
| Anforderungen | Wunschliste: Artefakt `https://claude.ai/artifact/HRqtB7zQjouTtD5TUtonMP`, Datenbank-Sammlung `wuensche` (Felder `titel`, `bereich`, `prio`, `beschreibung`, `status` ∈ offen/umgesetzt/zurueckgestellt, `version`, `erstellt`, `geaendert`) |

## Arbeitsweise (verbindlich)

- **Vor jedem Commit und Push nachfragen** (AskUserQuestion: „Ja, committen und pushen“ / „Noch nicht“). Änderungen
  so vorbereiten, dass sie direkt committet und gepusht werden können. Bei „Noch nicht“ wird nicht committet, auch
  wenn ein Hook auf ungesicherte Änderungen hinweist.
- **Gearbeitet wird auf `main`.** Vorher `git fetch origin main` und auf den aktuellen Stand bringen. Ein Push auf
  `main` ist sofort als Update in Home Assistant sichtbar, deshalb nur geprüfte Stände pushen. Tags setzt nur
  `tools/release.py`.
- **Version bei jeder Auslieferung erhöhen**, gleich in `finanz_tracker/config.yaml` (`version`) und
  `finanz_tracker/app/config.py` (`VERSION`). Sonst zeigt Home Assistant kein Update. minor für neue Funktionen,
  patch für Korrekturen. Abschnitt `## x.y.z – Monat Jahr` oben im `CHANGELOG.md`, bei neuen Funktionen auch
  „Neu in x.y – kurz erklärt“ im README.
- **Wunschliste pflegen:** „Setze die Wunschliste um“ heißt alle Wünsche mit Status `offen`, ohne `zurueckgestellt`.
  Nach dem Push umgesetzte Wünsche auf `status: umgesetzt` und `version` setzen (mit `ifVersion` aus dem letzten
  Lesen).
- **Entscheidungen** bekommen eine ADR unter `docs/adr/` (Vorlage `0000-vorlage.md`, nächste freie Nummer, Eintrag
  im Index). Kleinigkeiten stehen nur im Changelog.
- **Dokumentation nachführen** im selben Commit: `docs/funktionen/`, `docs/datenmodell.md` bei Schemaänderungen,
  `docs/routen.md` bei neuen Adressen, `docs/offene-punkte.md`.
- **Definition of Done** (`docs/entwicklung.md`):
  - Tests grün, neue Funktionen mit eigener Methode `_vXYZ` in `tests/test_app.py`
  - `python3 tools/pruefen.py` ohne Fehler
  - Oberfläche im Browser geprüft (Desktop und Handy, hell und dunkel)
  - Version, Changelog, Dokumentation, ADR falls nötig, Wunschliste
- **Ehrlich berichten, was nicht geprüft ist:** vor allem Docker-Build auf dem Green, HTTPS mit echter Heim-CA auf
  Android, Texterkennung mit echten Screenshots und Abrechnungen, Kursabruf bei CoinGecko. Ausdrücklich sagen, was
  nur mit Beispieldaten nachgebaut wurde.
- **Nie ändern:** `slug: finanz_tracker`. Nie zum Deinstallieren des Add-ons raten, das löscht die Datenbank.
- **Git-Identität:** Commits nie mit privater E-Mail-Adresse. Die Commit-Nachricht endet mit der
  `Co-Authored-By`-Zeile, wie die Umgebung sie vorgibt.
- **Nichts Destruktives ohne ausdrückliche Zustimmung:** kein Force-Push und kein Umschreiben der Historie.

## Technische Regeln

- **Beträge** immer in Cent als `int`. Eingaben über `util.parse_euro_eingabe`, Anzeige über die Jinja-Filter
  `euro`, `euro_vz`, `euro_rund`.
- **Kennzahlen** nur über `statistik.posten()` und `statistik.art_von()` (Sicht `posten_monat`). So wirken
  Aufteilungen, Verteilungen und der Abrechnungsmonat überall gleich. Umbuchungen und Darlehenskonten zählen nie in
  Einnahmen und Ausgaben.
- **Sichtbarkeit:** Jede Abfrage auf Konten oder Buchungen läuft über `auth.sichtbare_konten()`; Kennzahlen über
  `statistik.basis_konten()`. Private Konten anderer Personen dürfen nirgends auftauchen, auch nicht in Summen.
- **Schichten:**
  - `views/` liest den Request, prüft die Rechte (`login_required`, `schreibrecht`, `admin_required`), ruft Services
    und macht `commit()`, `melde()`, Weiterleitung.
  - `services/` enthält die Fachlogik ohne `request` und ohne `commit()`.
- **SQL** mit Parametern, ohne ORM. Schemaänderungen nur als neue Migration `NNN_name.sql`, bestehende nie ändern.
  Eine CHECK-Bedingung ändert man nur über den Neuaufbau der Tabelle (Beispiel: Migration 008).
- **CSRF:** Jedes POST-Formular nutzt das Makro `csrf()`, JavaScript schickt den Kopf `X-CSRF`.
- **Oberfläche:**
  - kein Framework, kein Build, kein CDN
  - Diagramme über `window.Diagramme` (`static/diagramme.js`)
  - Farben nur als CSS-Variablen, für Text in Grün oder Rot `var(--gut)` und `var(--bad)`, damit das dunkle Schema
    funktioniert
  - Browser-Speicher nur in `try/catch` und nur für Komfort
- **Abhängigkeiten** sparsam: Python-Pakete mit Versionsgrenzen in `requirements.txt`, Systempakete im `Dockerfile`.
  Lizenzen ohne Copyleft-Pflicht für die App. Keinen Code aus AGPL-Projekten wie Sure übernehmen (ADR-0019).
- **Netz:** Nur der Krypto-Kursabruf darf ins Internet. Texterkennung und PDF-Lesen bleiben lokal.

## Befehle

```bash
git fetch origin main && git status -sb
cd finanz_tracker && python3 -m unittest discover -s tests    # alle Tests
python3 tools/pruefen.py                                      # aus dem Hauptordner: Konfiguration + Tests
HTTPS=0 DATA_DIR=./data python3 -m app                        # lokal starten, http://localhost:8080
```

- **Sichtprüfung:** Demo-Server mit Beispieldaten (Einrichtung per Test-Client, Buchungen per SQL), Screenshots mit
  Playwright. Chromium ist in der Cloud-Umgebung vorinstalliert, `require('playwright')` funktioniert ohne
  Installation.
- **Demo-Skripte** gehören nicht ins Repository; sie liegen in einem Ordner außerhalb (z. B. `/home/claude/pruef`).
- **In der Cloud-Umgebung** sind npm- und pip-Downloads oft gesperrt. Keine Bibliotheken nachladen, sondern mit dem
  Vorhandenen bauen.

## Aktuelle Festlegungen

Stand 2026-11-25, Version 0.9.0. Details in den ADRs.

- **Banken:**
  - GLS Bank und Sparkasse (Giro), UmweltBank (Tagesgeld) per CSV-Profil
  - Hanseatic-Kreditkarte per PDF-Abrechnung oder Screenshot (lokale Texterkennung)
- **FinTS ist zurückgestellt** (ADR-0012).
- **Darlehen** haben einen eigenen Bereich. Bausparverträge sind Datensätze, keine Konten. Das Depot ist nur ein
  Saldo mit Rendite von Hand.
- **Dashboard** im Stil von Sure, alle Bereiche einklappbar (ADR-0019).
- **Planung:** Kontoauswahl und Überschuss je Benutzer, Posten gemeinsam (ADR-0021).
- **Belege** gehören nicht in den Finanz-Tracker, sondern ins Familienarchiv (ADR-0017).

## Offene Punkte

Siehe `docs/offene-punkte.md`, unter anderem:
- `.github/workflows` fehlen, obwohl README und `tools/pruefen.py` sie beschreiben
- README-Installationsteil nennt noch 0.2.0
- keine Versions-Tags
- Commit-Historie enthält einen fremd zugeordneten Commit und eine private E-Mail-Adresse; Bereinigung nicht entschieden
