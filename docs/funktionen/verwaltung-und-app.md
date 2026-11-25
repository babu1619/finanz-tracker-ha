# Verwaltung und App

## Ersteinrichtung und Anmeldung

Code: `views/auth_views.py`, `auth.py`. Entscheidung: [ADR-0005](../adr/0005-eigener-login-rollen-private-konten.md).

- **Ersteinrichtung:** Beim allerersten Aufruf legt man den Admin an: Benutzername, eigene Person, Passwort mit
  mindestens 8 Zeichen, optional das Startset an Kategorien. Danach ist `/einrichtung` gesperrt.
- **Login:**
  - Nach 5 Fehlversuchen ist der Benutzername 15 Minuten gesperrt. Die Sperre liegt im Speicher und endet mit einem
    Neustart.
  - Die Sitzung hält 30 Tage.
- **Passwort:** Jeder ändert sein Passwort unter `/passwort` (Klick auf den eigenen Namen).
- **Notfall:** Die Add-on-Option `admin_passwort_reset` setzt beim Start das Passwort des ersten Admins. Danach die
  Option wieder leeren.

## Benutzer, Personen, Rechte

Code: `views/admin.py` (Seite „Verwaltung“, nur Admins).

- **Personen:** Familienmitglieder mit Farbe, auch ohne Login (z. B. Kinder). Buchungen, Aufteilungen, Budgets und
  Rücklagen lassen sich Personen zuordnen. Das Dashboard filtert nach Person.
- **Benutzer:** Login mit Rolle und verknüpfter Person.

| Rolle | Darf |
| --- | --- |
| Admin | alles, Verwaltung, sieht alle Konten auch privat |
| Mitglied | lesen und schreiben; sieht gemeinsame Konten und private Konten der eigenen Person |
| Lesend | nur lesen, sonst wie Mitglied |

- **Private Konten:** `sichtbarkeit = privat` mit Eigentümer-Person. Andere Mitglieder sehen weder das Konto noch
  seine Buchungen; auch in Summen, Statistiken und Planung fehlt es.
- **Konten anlegen:** nur Admins (`/konten/neu`).

## Sicherung und Wiederherstellung

Code: `services/sicherung.py`, `views/admin.py`. Entscheidung: [ADR-0018](../adr/0018-verschluesselte-sicherung.md).

- **Home-Assistant-Backups** enthalten das Add-on samt `/data`, also auch die Datenbank.
- **Verschlüsselte Sicherung (.ftbak):**
  - Konsistente Kopie per SQLite-Backup-API.
  - Verschlüsselt mit Fernet (AES-128-CBC + HMAC-SHA256); der Schlüssel wird mit scrypt aus einem Passwort abgeleitet.
  - Format: `FTBAK1` + 16 Byte Salz + Token.
  - Gedacht für Cloud-Speicher oder USB-Stick.
- **Wiederherstellen:**
  - In der Verwaltung mit Passwort.
  - Geprüft wird die Integrität der Datenbank und ob mindestens ein aktiver Admin enthalten ist.
  - Der vorherige Stand bleibt als `/data/vor-wiederherstellung-<Zeitpunkt>.db` liegen. Diese Kopien werden nicht
    automatisch gelöscht.
  - Eine Sicherung mit älterem Schema wird gleich nach dem Einspielen migriert.
- **Ohne Verschlüsselung:** Datenbank als `.db` herunterladen (`/verwaltung/backup`) oder alle Buchungen als CSV.

## HTTPS und Zertifikat

Code: `tls.py`, `server.py`, `views/pwa.py` (Seite „App & Zertifikat“). Entscheidung:
[ADR-0014](../adr/0014-https-mit-heim-ca.md).

- **Heim-CA (Standard):**
  - Beim ersten Start erzeugt das Add-on eine eigene Zertifizierungsstelle (10 Jahre) und ein Serverzertifikat
    (825 Tage).
  - Das Serverzertifikat enthält `homeassistant.local`, `homeassistant`, `localhost`, die IPs des Green vom
    Supervisor, den Hostnamen des Containers und die Namen aus `zusatz_hostnamen`.
  - Beim Start erneuert das Add-on das Serverzertifikat, wenn Namen oder IPs fehlen oder es in weniger als 60 Tagen
    abläuft. Die CA auf den Geräten bleibt gültig.
- **Alternative:** `zertifikat: homeassistant` nutzt `fullchain.pem`/`privkey.pem` aus `/ssl` (z. B. Let's Encrypt).
- **HTTP auf demselben Port** wird per 301 auf HTTPS umgeleitet. So funktionieren alte Lesezeichen weiter.
- **Seite „App & Zertifikat“:**
  - CA zum Herunterladen, auch ohne Anmeldung unter `/zertifikat/finanz-tracker-ca.crt`
  - Fingerabdruck und Gültigkeit
  - Adressen, für die das Zertifikat gilt
  - Anleitung für Android und Windows
  - Hinweis, was für die App-Installation noch fehlt
- **Ohne HTTPS:** Schlägt die Einrichtung fehl, startet das Add-on per HTTP, damit es erreichbar bleibt.

## Installierbare App (PWA)

Code: `views/pwa.py`, `templates/sw.js`. Entscheidung: [ADR-0015](../adr/0015-pwa-ohne-daten-im-cache.md).

- **Manifest:** Name „Finanzen“, Symbole, Kurzbefehle „Bar erfassen“, „Prüfen“, „Buchungen“.
- **Service Worker:**
  - Seiten kommen immer frisch vom Server; ohne Netz erscheint die Offline-Seite.
  - Im Cache liegen nur CSS, JS, Symbole und die Offline-Seite, je Version.
- **Voraussetzung auf Android:** vertrauenswürdiges HTTPS, also installierte Heim-CA. Die Adresse ist die IP des
  Green, weil Android `.local`-Namen nicht zuverlässig auflöst.

## Farbschema

Entscheidung: [ADR-0022](../adr/0022-dunkles-farbschema.md).

- **Standard:** Die App folgt der Einstellung des Geräts (hell oder dunkel).
- **Umschalter:** oben rechts, System → Hell → Dunkel. Die Wahl liegt je Gerät im `localStorage` (`farbschema`).
- **Kein Aufblitzen:** Ein kleines Skript im `<head>` setzt das Schema, bevor die Seite gezeichnet wird.
