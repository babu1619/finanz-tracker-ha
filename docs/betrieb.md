# Betrieb

Die ausführliche Schritt-für-Schritt-Anleitung steht im [README](../README.md). Hier steht das Wesentliche für den
Betrieb und die Gründe dahinter.

## Umgebung

| Was | Wert |
| --- | --- |
| Host | Home Assistant Green (aarch64); `amd64` wird ebenfalls gebaut |
| Add-on-Slug | `finanz_tracker`, nie ändern (sonst hält Home Assistant es für ein neues Add-on ohne Daten) |
| Repository | `https://github.com/babu1619/finanz-tracker-ha` (öffentlich, nur Code, keine Daten) |
| Basis-Image | `python:3.12-slim-bookworm` je Architektur (`build.yaml`), dazu `tesseract-ocr`, `tesseract-ocr-deu`, `poppler-utils` |
| Python-Pakete | Flask 3.1, waitress, cryptography, Pillow, tzdata (`requirements.txt`) |
| Port | intern 8080, nach außen 8099 (`config.yaml` → `ports`) |
| Daten | `/data/finanz.db`, `/data/secret_key`, `/data/tls/`, `/data/tmp/`, `/data/options.json` (von Home Assistant) |
| Zertifikate | optional `/ssl` (gemappt, nur lesend genutzt) |

Das Image wird auf dem Green gebaut. Vorgebaute Images über `ghcr.io` sind vorbereitet, aber abgeschaltet: die Zeile
`image:` in `config.yaml` ist auskommentiert.

## Installation, Update

- **Installation:**
  1. Repository in Home Assistant unter Add-on-Store → Repositories eintragen.
  2. „Finanz-Tracker“ installieren, „Beim Start starten“ und „Watchdog“ einschalten, starten.
  3. `https://<IP-des-Green>:8099` öffnen und die Ersteinrichtung durchlaufen.
- **Update:**
  - Eine neue Version erscheint in Home Assistant, sobald `version` in `config.yaml` erhöht und gepusht ist.
  - Dann „Nach Updates suchen“ und „Aktualisieren“; das Add-on wird neu gebaut.
  - Die Datenbank migriert beim Start automatisch.
- **Vor einem Update:** Sicherung empfohlen (Verwaltung → Datenbank herunterladen oder Home-Assistant-Backup).
- **Nie deinstallieren,** um ein Problem zu lösen. Das löscht `/data` und damit die Datenbank.

## Optionen

| Option | Bedeutung |
| --- | --- |
| `https` | an (Standard) oder aus. Ohne HTTPS keine App-Installation auf Android. |
| `zertifikat` | `eigenes` (Heim-CA) oder `homeassistant` (Dateien aus `/ssl`) |
| `zusatz_hostnamen` | weitere Namen oder IPs für das eigene Zertifikat, mit Komma getrennt, z. B. der VPN-Name des Green |
| `certfile`, `keyfile` | Dateinamen in `/ssl` bei `zertifikat: homeassistant` |
| `admin_passwort_reset` | Notfall: neues Passwort für den ersten Admin; nach dem Neustart wieder leeren |

## Zugriff

- **Zu Hause:** über die IP des Green; im Router eine feste IP per DHCP-Reservierung vergeben.
- **Unterwegs:** nur über VPN, der Port wird nicht im Router freigegeben. Die Namen bzw. IPs des VPN gehören in
  `zusatz_hostnamen`, damit das Zertifikat passt.
- **Einmal je Gerät:** die Heim-CA installieren (Seite „App & Zertifikat“), danach lässt sich die App in Chrome
  installieren.

## Sicherung

| Weg | Inhalt | Wiederherstellen |
| --- | --- | --- |
| Home-Assistant-Backup | ganzes Add-on inkl. `/data` | über Home Assistant |
| Verschlüsselte Sicherung `.ftbak` | Datenbank, mit Passwort | Verwaltung → Wiederherstellen |
| Datenbank `.db` | unverschlüsselte Kopie | von Hand nach `/data/finanz.db` |
| CSV-Export | alle Buchungen mit Filtern | nicht vorgesehen |

## Überwachung

- **Protokoll:** Der Reiter „Protokoll“ des Add-ons zeigt Start (Version, HTTPS-Quelle, Port), Migrationen,
  Kursabrufe und Fehler. Anfragen werden nur bei Serverfehlern (5xx) protokolliert.
- **In der App:** Das Dashboard zeigt fällige Importe und Saldoabweichungen; die Krypto-Seite zeigt den letzten
  Kursabruf.

## Fehlerbehebung

Die Tabelle im [README](../README.md#fehlerbehebung) deckt die üblichen Fälle ab:
- Add-on fehlt im Store
- Installation bricht ab
- Seite nicht erreichbar
- Format der Bank hat sich geändert
- Saldo weicht ab
- Zertifikatswarnung
- „App installieren“ fehlt

Zusätzlich:

| Problem | Ursache, Lösung |
| --- | --- |
| Anmeldung schlägt sofort fehl | 5 Fehlversuche → 15 Minuten warten oder Add-on neu starten (die Sperre liegt im Speicher) |
| Gelöschte Buchung kommt nicht wieder | Sie steht auf der Sperrliste: Import → „Gelöschte Buchungen“ → „Wieder zulassen“, dann neu importieren |
| Krypto-Kurse veraltet | „Jetzt abrufen“; schlägt das fehl, ist CoinGecko nicht erreichbar oder begrenzt die Anfragen |
| Screenshot-Import erkennt nichts | Tesseract fehlt nur bei einem lokal gestarteten Add-on ohne Docker; im Image ist es enthalten. Größere oder schärfere Screenshots helfen. |
