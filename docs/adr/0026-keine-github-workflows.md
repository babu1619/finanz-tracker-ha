# ADR-0026: Keine GitHub-Workflows, Prüfung lokal

- **Status:** angenommen
- **Datum:** 2026-11-25 (nach Version 0.9.0)

## Kontext

README und `tools/pruefen.py` beschrieben seit 0.2.1 eine automatische Prüfung auf GitHub („Actions“: Tests, Bau des
Images, Probestart mit HTTPS) und einen Workflow für vorgebaute Images auf `ghcr.io`. Im Repository gab es diese
Workflows nie; vermutlich gingen sie beim Hochladen über die GitHub-Webseite verloren. Aufgefallen ist das beim
Erstellen der Dokumentation.

## Entscheidung

Benjamin hat entschieden, die Workflows nicht nachzuholen.
- Geprüft wird lokal vor jedem Push mit `python3 tools/pruefen.py` (Konfiguration, Code, Migrationen, Versionen,
  Changelog, alle Tests).
- Das Image baut Home Assistant beim Installieren und Aktualisieren auf dem Green. Die auskommentierte Zeile
  `image:` für vorgebaute Images wurde aus `config.yaml` entfernt.
- README und `tools/pruefen.py` beschreiben keine Workflows mehr.

## Alternativen

- Workflows nachholen: Tests und Probestart auf GitHub bei jedem Push, dazu schnellere Updates mit vorgebauten
  Images. Mehr Pflege, für ein Familienprojekt mit lokaler Prüfung nicht nötig.

## Folgen

- Ein Push ohne vorherige lokale Prüfung kann ein fehlerhaftes Update in Home Assistant auslösen. Deshalb gehört
  `tools/pruefen.py` zur Definition of Done und steht in `CLAUDE.md`.
- Der Docker-Build wird erst auf dem Green geprüft. Bei Änderungen an `Dockerfile` oder `requirements.txt` muss das
  im Bericht ausdrücklich stehen.
- Updates dauern auf dem Green einige Minuten, weil das Image dort gebaut wird.
