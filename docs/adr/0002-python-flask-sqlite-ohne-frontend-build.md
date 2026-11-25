# ADR-0002: Python, Flask und SQLite ohne Frontend-Build

- **Status:** angenommen
- **Datum:** 2026-10-10 (Version 0.1.0); nachträglich dokumentiert am 2026-11-25

## Kontext

Der Green ist ein kleines ARM-Gerät. Wenige Nutzer, eine Familie. Gepflegt wird die App überwiegend von Claude in
Gesprächen, Benjamin muss Änderungen nachvollziehen und ausrollen können.

## Entscheidung

- Backend: Python mit Flask, Server waitress bzw. ein eigener HTTPS-Server auf Basis von Werkzeug.
- Datenbank: SQLite in einer Datei, Zugriff mit reinem SQL (`db.q`, `db.q1`, `db.exe`), ohne ORM.
- Oberfläche: serverseitig gerenderte Jinja-Vorlagen, eigenes CSS und JavaScript ohne Framework und ohne Build-Schritt.

## Alternativen

- PostgreSQL oder MariaDB: eigener Dienst auf dem Green, mehr Betrieb, für eine Familie unnötig.
- ORM (SQLAlchemy): mehr Abhängigkeiten, die Abfragen sind überschaubar.
- SPA mit React oder Vue: Build-Kette, npm-Abhängigkeiten, schwerer zu prüfen.

## Folgen

- Wenige Abhängigkeiten (Flask, waitress, cryptography, Pillow, tzdata), schneller Bau auf dem Green.
- Ein Prozess, keine Warteschlange: Import und Texterkennung laufen in der Anfrage.
- Seiten funktionieren ohne JavaScript; Komfort und Diagramme kommen per JavaScript dazu.
