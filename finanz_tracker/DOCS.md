# Finanz-Tracker

Haushaltsbuch für die Familie. Läuft als eigenständige Webseite auf dem Home Assistant Green;
alle Daten bleiben lokal in `/data/finanz.db` und sind Teil jedes Home-Assistant-Backups dieses Add-ons.

## Aufruf

`https://<IP-des-Green>:8099` (http:// wird automatisch umgeleitet). Beim ersten Aufruf wird der Admin angelegt.

Damit Browser dem eigenen Zertifikat vertrauen und Chrome auf Android die Seite als App installieren kann, einmal pro
Gerät die Heim-CA installieren: in der App unter **Mehr › App & Zertifikat** (Download und Schritt-für-Schritt-Anleitung).

## Optionen

- `https` – Verschlüsselung an/aus (Standard: an)
- `zertifikat` – `eigenes` (Heim-CA des Add-ons) oder `homeassistant` (Zertifikat aus `/ssl`, z. B. Let's Encrypt)
- `zusatz_hostnamen` – weitere Namen oder IPs für das eigene Zertifikat, mit Komma getrennt (z. B. Tailscale)
- `certfile`, `keyfile` – Dateinamen in `/ssl` bei `zertifikat: homeassistant`
- `admin_passwort_reset` – Notfall: neues Admin-Passwort, Add-on neu starten, Option wieder leeren

## Erste Schritte

1. **Importprofil anlegen:** Import › „CSV-Profil anlegen“ › CSV-Export der Bank hochladen › Spalten prüfen › speichern.
2. **Konto anlegen:** Konten › „Konto anlegen“ › IBAN eintragen und Importprofil wählen.
3. **Importieren:** Import › Datei wählen › Vorschau › übernehmen.
4. **Zuordnen:** Prüfen › Kategorie wählen, bei wiederkehrenden Zahlungen „Regel erstellen“ anhaken.

## Zugriff von unterwegs

Den Port 8099 nicht im Router freigeben. Für den Zugriff von außen ein VPN nutzen
(z. B. das Add-on „Tailscale“ oder „WireGuard“).

## Sicherung

Verwaltung › „Verschlüsselte Sicherung“ (.ftbak, mit Passwort) oder „Datenbank herunterladen“. Zusätzlich sichert
Home Assistant das Add-on in seinen normalen Backups.
