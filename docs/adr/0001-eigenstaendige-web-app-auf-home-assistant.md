# ADR-0001: Eigenständige Web-App mit Home Assistant Green als Host

- **Status:** angenommen
- **Datum:** 2026-10-10 (Version 0.1.0); nachträglich dokumentiert am 2026-11-25

## Kontext

Die Familie wollte ein Haushaltsbuch nach dem Vorbild des Körperdaten-Trackers: eine SQL-Datenbank unter Python
auf dem vorhandenen Home Assistant Green, mit Nutzerverwaltung und CSV-Import. Home Assistant läuft dort ohnehin
dauerhaft und wird gesichert.

## Entscheidung

Der Finanz-Tracker ist eine eigenständige Webseite mit eigenem Login. Er wird als Home-Assistant-Add-on
ausgeliefert; Home Assistant dient nur als Host (Container, Backups, Optionen). Es gibt keine Integration in Home
Assistant: keine Entitäten, keine Lovelace-Karten, keine Anmeldung über Home Assistant.

## Alternativen

- Integration in Home Assistant (Sensoren, Panels): Familienmitglieder bräuchten Home-Assistant-Konten, und
  Finanzdaten lägen in der Hausautomation.
- Eigener Server oder Raspberry Pi: zusätzliches Gerät, eigene Backups.
- Fertige Software (z. B. Firefly III, Actual Budget): kein Bankformat-Import für die Familie ohne Anpassung, kein
  Darlehens- und Bausparmodell in der gewünschten Form; bei Firefly zusätzlich eine Datenbank.

## Folgen

- Auslieferung über ein GitHub-Repository als Add-on-Repository, Updates über den Add-on-Store.
- Daten unter `/data` sind Teil der Home-Assistant-Backups.
- Der Slug `finanz_tracker` darf sich nie ändern.
- Login, Rollen und HTTPS muss die App selbst mitbringen (ADR-0005, ADR-0014).
