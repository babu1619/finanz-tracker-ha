# ADR-0024: Auslieferung über GitHub und Arbeitsweise mit Claude

- **Status:** angenommen
- **Datum:** 2026-10-11 (Version 0.2.1); nachträglich dokumentiert am 2026-11-25

## Kontext

Benjamin rollt Updates über Home Assistant aus. Code entsteht überwiegend in Gesprächen mit Claude. Änderungen
sollen nachvollziehbar und kontrolliert ins Repository kommen.

## Entscheidung

- Öffentliches Repository `babu1619/finanz-tracker-ha` als Add-on-Repository; es enthält nur Code, keine Daten.
- Arbeit auf `main`. Claude bereitet Änderungen so vor, dass sie direkt committet und gepusht werden können, und
  fragt vor jedem Commit und Push nach.
- Jede Auslieferung erhöht die Version in `config.yaml` und `app/config.py` gleich und ergänzt den Changelog; sonst
  zeigt Home Assistant kein Update.
- Anforderungen werden in der Wunschliste (Artefakt) geführt; umgesetzte Wünsche bekommen Status und Version.
- Werkzeuge: `tools/pruefen.py` vor jedem Commit, `tools/release.py` für eigene kleine Änderungen.

## Alternativen

- Branches und Pull Requests: für ein Ein-Personen-Projekt mit Auslieferung über `main` mehr Aufwand als Nutzen.

## Folgen

- Es gibt keine GitHub-Workflows; `tools/pruefen.py` ist die einzige Prüfung ([ADR-0026](0026-keine-github-workflows.md)).
- Ein Push auf `main` ist sofort als Update in Home Assistant sichtbar.
