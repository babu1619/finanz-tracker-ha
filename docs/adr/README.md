# Entscheidungen (ADRs)

Jede Entscheidung, die Daten, Schnittstellen, Betrieb oder Arbeitsweise betrifft, steht hier als Architecture
Decision Record. Die ADRs 0001–0025 wurden am 2026-11-25 nachträglich aus Code, Changelog, README und Gesprächen
zusammengetragen; das Datum in jeder ADR ist das der ursprünglichen Entscheidung. Der Abschnitt „Alternativen“
ist dabei teilweise nachträglich ergänzt: Nicht jede dort genannte Alternative wurde damals ausdrücklich besprochen.

## Regeln

- Neue Entscheidung: Kopie von [`0000-vorlage.md`](0000-vorlage.md) mit der nächsten freien Nummer, Eintrag in diese
  Tabelle im selben Commit.
- Nummern werden nie neu vergeben und nie umnummeriert.
- Eine überholte Entscheidung bekommt den Status „ersetzt durch ADR-XXXX“ und bleibt stehen; die neue ADR verweist
  zurück.
- Kleinigkeiten ohne Folgen für Daten, Schnittstellen oder Betrieb brauchen keine ADR; sie stehen im Changelog.
- Status: vorgeschlagen, angenommen, zurückgestellt, ersetzt.

## Übersicht

| Nr. | Titel | Status | Datum | Version |
| --- | --- | --- | --- | --- |
| [0001](0001-eigenstaendige-web-app-auf-home-assistant.md) | Eigenständige Web-App mit Home Assistant Green als Host | angenommen | 2026-10-10 | 0.1.0 |
| [0002](0002-python-flask-sqlite-ohne-frontend-build.md) | Python, Flask und SQLite ohne Frontend-Build | angenommen | 2026-10-10 | 0.1.0 |
| [0003](0003-versionierte-sql-migrationen.md) | Versionierte SQL-Migrationen beim Start | angenommen | 2026-10-10 | 0.1.0 |
| [0004](0004-betraege-in-cent-und-abrechnungsmonat.md) | Beträge in Cent, Abrechnungsmonat und Posten-Sichten | angenommen | 2026-10-10 | 0.1.0 / 0.2.0 |
| [0005](0005-eigener-login-rollen-private-konten.md) | Eigener Login, Rollen, Personen und private Konten | angenommen | 2026-10-10 | 0.1.0 |
| [0006](0006-csv-import-mit-importprofilen.md) | CSV-Import mit Importprofilen in der App | angenommen | 2026-10-10 | 0.1.0 |
| [0007](0007-kreditkarte-per-pdf-und-lokaler-texterkennung.md) | Kreditkarte per PDF und Screenshot mit lokaler Texterkennung | angenommen | 2026-10-12 | 0.4.0 / 0.5.0 |
| [0008](0008-zuordnung-regeln-gedaechtnis-lernmodell.md) | Automatische Zuordnung: Regeln, Gedächtnis, Lernmodell | angenommen | 2026-10-11 | 0.1.0 / 0.2.0 / 0.5.0 |
| [0009](0009-umbuchungen-und-automatische-gegenbuchungen.md) | Umbuchungen und automatische Gegenbuchungen | angenommen | 2026-10-10 | 0.1.0 / 0.3.1 / 0.4.0 |
| [0010](0010-darlehen-getrennt-vom-haushalt.md) | Darlehen getrennt vom Haushalt | angenommen | 2026-10-11 | 0.2.0 |
| [0011](0011-depot-und-bausparen-vereinfacht.md) | Depot und Bausparen als vereinfachte Modelle | angenommen | 2026-10-12 | 0.4.0 / 0.5.0 |
| [0012](0012-kein-fints-vorerst.md) | Kein FinTS vorerst | zurückgestellt | 2026-10-12 | – |
| [0013](0013-krypto-kurse-von-coingecko.md) | Krypto-Kurse von CoinGecko, nächtlicher Abruf | angenommen | 2026-10-20 | 0.7.0 / 0.9.0 |
| [0014](0014-https-mit-heim-ca.md) | HTTPS mit eigener Heim-CA, Zugriff von außen nur per VPN | angenommen | 2026-10-11 | 0.2.0 |
| [0015](0015-pwa-ohne-daten-im-cache.md) | Installierbare App (PWA) ohne Finanzdaten im Cache | angenommen | 2026-10-11 | 0.2.0 |
| [0016](0016-eigene-diagramm-bibliothek.md) | Eigene SVG-Diagramm-Bibliothek | angenommen | 2026-10-15 | 0.6.0 |
| [0017](0017-keine-belege-im-finanz-tracker.md) | Keine Belege im Finanz-Tracker | angenommen | 2026-10-10 | 0.1.0 |
| [0018](0018-verschluesselte-sicherung.md) | Verschlüsselte Sicherung zusätzlich zu Home-Assistant-Backups | angenommen | 2026-10-11 | 0.2.0 |
| [0019](0019-dashboard-im-stil-von-sure.md) | Dashboard im Stil von Sure, ohne fremden Code | angenommen | 2026-11-11 | 0.8.0 |
| [0020](0020-loeschen-mit-sperrliste.md) | Buchungen löschen mit Sperrliste für Importe | angenommen | 2026-11-25 | 0.9.0 |
| [0021](0021-planung-von-ausgaben-und-sondereinnahmen.md) | Planung von Ausgaben und Sondereinnahmen | angenommen | 2026-11-25 | 0.9.0 |
| [0022](0022-dunkles-farbschema.md) | Dunkles Farbschema über CSS-Variablen | angenommen | 2026-11-25 | 0.9.0 |
| [0023](0023-oberflaechenzustand-je-geraet.md) | Zustand der Oberfläche je Gerät im Browser | angenommen | 2026-10-11 | 0.2.0 |
| [0024](0024-auslieferung-und-arbeitsweise.md) | Auslieferung über GitHub und Arbeitsweise mit Claude | angenommen | 2026-10-11 | 0.2.1 |
| [0025](0025-vertraege-als-datensaetze.md) | Verträge als eigene Datensätze | angenommen | 2026-10-15 | 0.6.0 |
| [0026](0026-keine-github-workflows.md) | Keine GitHub-Workflows, Prüfung lokal | angenommen | 2026-11-25 | – |
