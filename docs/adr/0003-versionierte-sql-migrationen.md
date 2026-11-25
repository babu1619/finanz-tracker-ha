# ADR-0003: Versionierte SQL-Migrationen beim Start

- **Status:** angenommen
- **Datum:** 2026-10-10 (Version 0.1.0); nachträglich dokumentiert am 2026-11-25

## Kontext

Die Datenbank liegt beim Nutzer und muss jedes Update ohne Datenverlust und ohne Handarbeit überstehen.

## Entscheidung

- Schemaänderungen als Dateien `app/migrations/NNN_name.sql`, lückenlos nummeriert.
- `db.migrate()` spielt beim Start alle noch nicht angewendeten Dateien ein, jede in einer Transaktion, und merkt den
  Stand in `schema_version`.
- Während der Migration sind Fremdschlüssel aus, damit Tabellen neu aufgebaut werden können (SQLite kann
  CHECK-Bedingungen und Spalten nicht ändern).
- Eingespielte Migrationen werden nie verändert.

## Alternativen

- Alembic: setzt SQLAlchemy voraus (ADR-0002).
- Schema im Code vergleichen und automatisch anpassen: fehleranfällig bei SQLite.

## Folgen

- Eine Wiederherstellung aus einer älteren Sicherung wird nach dem Einspielen migriert.
- `tools/pruefen.py` prüft die Nummerierung.
- Datenkorrekturen beim Update (z. B. nachträgliche Gegenbuchungen in 004/005) stehen ebenfalls in Migrationen.
