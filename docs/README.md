# Dokumentation Finanz-Tracker

Stand: Version 0.9.0, 25.11.2026.

Der Finanz-Tracker ist das Haushaltsbuch der Familie. Er läuft als Home-Assistant-Add-on auf dem Home Assistant Green,
ist aber eine eigenständige Webseite mit eigenem Login. Die Daten bleiben lokal in einer SQLite-Datenbank.

## Inhalt

| Dokument | Inhalt |
| --- | --- |
| [Überblick](ueberblick.md) | Zweck, Nutzer, Funktionsumfang, Begriffe |
| [Architektur](architektur.md) | Aufbau, Schichten, Ablauf einer Anfrage, Hintergrundaufgaben, Sicherheit |
| [Datenmodell](datenmodell.md) | Tabellen, Sichten, Migrationen, Konventionen |
| [Funktionen](funktionen/README.md) | Fachliche Beschreibung je Bereich mit Rechenregeln |
| [Seiten und Routen](routen.md) | Alle Adressen der App mit Methode und Rechten |
| [Betrieb](betrieb.md) | Installation, Update, Optionen, HTTPS, Sicherung, Fehlerbehebung |
| [Entwicklung](entwicklung.md) | Lokale Umgebung, Tests, Werkzeuge, Konventionen, Definition of Done |
| [Entscheidungen (ADRs)](adr/README.md) | Alle getroffenen Entscheidungen mit Begründung |
| [Offene Punkte](offene-punkte.md) | Zurückgestellte Wünsche, bekannte Grenzen, Abweichungen |

Die Installationsanleitung für Home Assistant steht im [README im Hauptordner](../README.md). Die Kurzbeschreibung
im Add-on-Store kommt aus [`finanz_tracker/DOCS.md`](../finanz_tracker/DOCS.md). Die Änderungen je Version stehen in
[`finanz_tracker/CHANGELOG.md`](../finanz_tracker/CHANGELOG.md).

## Maßgebliche Quellen

Bei Widerspruch gilt der Code, danach diese Dokumentation, danach das Gedächtnis eines Gesprächs.

- **Anforderungen:** Die Wunschliste ist ein Artefakt in Claude
  ([Wunschliste Finanz-Tracker](https://claude.ai/artifact/HRqtB7zQjouTtD5TUtonMP)). Jeder Wunsch hat Status
  (offen, umgesetzt, zurückgestellt) und die Version, in der er umgesetzt wurde.
- **Entscheidungen:** [`docs/adr/`](adr/README.md).
- **Schema:** die Migrationen unter `finanz_tracker/app/migrations/`.
- **Arbeitsregeln für Claude Code:** [`CLAUDE.md`](../CLAUDE.md) im Hauptordner.

## Lesereihenfolge für Neue

1. [Überblick](ueberblick.md)
2. [Architektur](architektur.md)
3. [Datenmodell](datenmodell.md), vor allem die Abschnitte zu `buchung` und den Sichten `posten`/`posten_monat`
4. Die [Funktionen](funktionen/README.md) des Bereichs, an dem gearbeitet wird
5. [Entwicklung](entwicklung.md)
