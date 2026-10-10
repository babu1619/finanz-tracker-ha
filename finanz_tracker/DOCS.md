# Finanz-Tracker

Haushaltsbuch für die Familie. Läuft als eigenständige Webseite auf dem Home Assistant Green;
alle Daten bleiben lokal in `/data/finanz.db` und sind Teil jedes Home-Assistant-Backups dieses Add-ons.

## Aufruf

`http://homeassistant.local:8099` (oder `http://<IP-des-Green>:8099`). Beim ersten Aufruf wird der Admin angelegt.

## Erste Schritte

1. **Importprofil anlegen:** Import › „CSV-Profil anlegen“ › CSV-Export der Bank hochladen › Spalten prüfen › speichern.
2. **Konto anlegen:** Konten › „Konto anlegen“ › IBAN eintragen und Importprofil wählen.
3. **Importieren:** Import › Datei wählen › Vorschau › übernehmen.
4. **Zuordnen:** Prüfen › Kategorie wählen, bei wiederkehrenden Zahlungen „Regel erstellen“ anhaken.

## Zugriff von unterwegs

Den Port 8099 nicht im Router freigeben. Für den Zugriff von außen ein VPN nutzen
(z. B. das Add-on „Tailscale“ oder „WireGuard“).

## Sicherung

Verwaltung › „Datenbank herunterladen“ erzeugt eine Kopie. Zusätzlich sichert Home Assistant das Add-on
in seinen normalen Backups.
