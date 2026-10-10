# Finanz-Tracker – Installation auf dem Home Assistant Green

Version 0.1.0 · Haushaltsbuch für die Familie als Home-Assistant-Add-on.
Die App ist eine eigenständige Webseite (Port 8099); Home Assistant dient nur als Host.
Alle Daten liegen lokal in der SQLite-Datenbank des Add-ons und sind Teil der Home-Assistant-Backups.

## Was im Paket steckt

```
finanz-tracker/
├── repository.yaml          ← macht das GitHub-Repository zum Add-on-Repository
├── README.md                ← diese Anleitung
└── finanz_tracker/          ← das Add-on
    ├── config.yaml          ← Add-on-Beschreibung (Name, Version, Port 8099)
    ├── build.yaml           ← Python-Basis-Image je Architektur
    ├── Dockerfile
    ├── requirements.txt     ← Flask, waitress
    ├── DOCS.md, CHANGELOG.md, icon.png, logo.png
    ├── app/                 ← Programmcode, Vorlagen, Datenbank-Migrationen
    └── tests/               ← automatische Tests und Beispiel-CSV-Dateien
```

## Installation über GitHub (empfohlen)

**1. Paket entpacken.** `finanz-tracker-v0.1.0.zip` auf dem PC entpacken. Du erhältst den Ordner `finanz-tracker`.

**2. Repository auf GitHub anlegen.** Auf github.com › „New repository“, Name `finanz-tracker`,
Sichtbarkeit **Public**. Home Assistant lädt Add-on-Repositories ohne Zugangsdaten; im Repository liegt nur
Programmcode, keine Finanzdaten. Kein README, keine .gitignore anlegen lassen.

**3. Dateien hochladen.** Im neuen Repository „uploading an existing file“ wählen und den **Inhalt** des Ordners
`finanz-tracker` (also `repository.yaml`, `README.md`, `.gitignore` und den Ordner `finanz_tracker`) per Drag & Drop
ins Browserfenster ziehen › „Commit changes“.
Alternativ mit Git:
```
cd finanz-tracker
git init && git add . && git commit -m "Finanz-Tracker 0.1.0"
git branch -M main
git remote add origin https://github.com/DEIN-GITHUB-NAME/finanz-tracker.git
git push -u origin main
```
Optional: In `repository.yaml` und `finanz_tracker/config.yaml` `DEIN-GITHUB-NAME` durch deinen GitHub-Namen ersetzen
(nur ein Link in der Anzeige, für die Funktion nicht nötig).

**4. Repository in Home Assistant eintragen.** Einstellungen › Add-ons › „Add-on Store“ › Menü ⋮ oben rechts ›
„Repositories“ › `https://github.com/DEIN-GITHUB-NAME/finanz-tracker` › „Hinzufügen“ › Schließen.

**5. Add-on installieren.** Seite neu laden (ggf. Menü ⋮ › „Nach Updates suchen“). Unten erscheint der Abschnitt
„Finanz-Tracker“ › Add-on öffnen › „Installieren“. Das Add-on wird auf dem Green gebaut; das dauert beim ersten Mal
einige Minuten, weil das Python-Basis-Image geladen wird.

**6. Starten.** Im Reiter „Info“ „Beim Start starten“ und „Watchdog“ einschalten › „Starten“.
Im Reiter „Protokoll“ sollte stehen: `Finanz-Tracker 0.1.0 startet auf Port 8080, Daten in /data`.

**7. App öffnen.** Im Browser `http://homeassistant.local:8099` aufrufen (oder `http://<IP-des-Green>:8099`;
die IP steht in Home Assistant unter Einstellungen › System › Netzwerk). Tipp: als Lesezeichen bzw. auf dem Handy
„Zum Startbildschirm hinzufügen“.

**8. Ersteinrichtung.** Benutzernamen, deinen Namen als Person und ein Passwort (mindestens 8 Zeichen) eingeben,
Startset an Kategorien angehakt lassen › „Einrichten“.

## Erste Schritte in der App

1. **Importprofil anlegen:** Import › „CSV-Profil anlegen“ › CSV-Export deiner Bank hochladen. Zeichensatz,
   Trennzeichen, Kopfzeile und Zahlenformat werden erkannt. Über jeder Spalte wählst du, was sie enthält; die
   Vorschau darunter zeigt sofort, wie die Buchungen gelesen werden. Speichern.
2. **Konten anlegen:** Konten › „Konto anlegen“ › Name, Typ, **IBAN** (für die automatische Erkennung beim Import
   und die Umbuchungserkennung) und Importprofil. Den Startsaldo kannst du auf 0 lassen: Enthält die erste
   CSV-Datei eine Saldo-Spalte, wird er automatisch berechnet.
3. **Importieren:** Import › Datei wählen › „Vorschau anzeigen“ › „Buchungen übernehmen“. Überlappende Exporte sind
   kein Problem, Duplikate werden erkannt. Jeder Import lässt sich rückgängig machen.
4. **Zuordnen:** Prüfen › Kategorie per Pfadsuche wählen (z. B. „lebens“), bei wiederkehrenden Zahlungen
   „Regel erstellen“ anhaken. Je mehr du bestätigst, desto mehr ordnet das Tool beim nächsten Import selbst zu.
5. **Familie hinzufügen:** Verwaltung › Benutzer anlegen (Rolle Mitglied oder Lesend) und Personen ohne Login,
   z. B. Kinder.

Tipp für den Start: Die letzten 12 Monate importieren und einmal den Prüf-Modus durcharbeiten. Danach gibt es
genug Regeln und Erfahrungswerte für eine weitgehend automatische Zuordnung.

## Updates

Neue Version: Dateien im GitHub-Repository ersetzen (die Versionsnummer in `finanz_tracker/config.yaml` ist dabei
erhöht). In Home Assistant erscheint dann beim Add-on „Aktualisieren“. Die Datenbank bleibt erhalten; nötige
Änderungen am Datenbankschema laufen beim Start automatisch.

## Sicherheit

- **Port 8099 nicht im Router freigeben.** Für den Zugriff von unterwegs das Add-on „Tailscale“ oder „WireGuard“
  installieren und die App über das VPN aufrufen.
- Nach 5 falschen Passworteingaben ist der Benutzername 15 Minuten gesperrt.
- **Passwort vergessen:** Add-on › Reiter „Konfiguration“ › Option `admin_passwort_reset` mit einem neuen Passwort
  (mindestens 8 Zeichen) füllen › Speichern › Add-on neu starten › anmelden › Option wieder leeren und speichern.

## Sicherung

Home-Assistant-Backups enthalten das Add-on samt Datenbank. Zusätzlich: Verwaltung › „Datenbank herunterladen“.
Die Datei ist unverschlüsselt – sicher aufbewahren.

## Fehlerbehebung

| Problem | Lösung |
| --- | --- |
| Add-on erscheint nicht im Store | Repository-URL prüfen; Repository muss öffentlich sein und `repository.yaml` im Hauptordner liegen. Menü ⋮ › „Nach Updates suchen“. |
| Installation bricht ab | Reiter „Protokoll“ des Supervisors prüfen (Einstellungen › System › Protokolle › Supervisor). Meist Internet kurz weg – erneut installieren. |
| Seite nicht erreichbar | Läuft das Add-on? Reiter „Protokoll“ prüfen. Port 8099 belegt? Im Reiter „Konfiguration“ › Netzwerk einen anderen Port eintragen. |
| „Spaltenüberschriften nicht gefunden“ beim Import | Die Bank hat das Exportformat geändert: Import › Profil öffnen › „Neue Beispieldatei“ hochladen, Zuordnung prüfen, speichern. |
| Saldo weicht ab | Meist fehlt ein Zeitraum im Import oder der Startsaldo des Kontos stimmt nicht (Konten › Bearbeiten). |

## Ohne GitHub installieren (lokales Add-on)

1. In Home Assistant das Add-on „Samba share“ installieren und starten.
2. Am PC die Freigabe `\\homeassistant.local\addons` öffnen und dort den Ordner `finanz_tracker` (aus dem Paket)
   hineinkopieren.
3. Add-on Store › Menü ⋮ › „Nach Updates suchen“ › unter „Lokale Add-ons“ erscheint der Finanz-Tracker ›
   Installieren, dann weiter ab Schritt 6.

## Entwicklung und Tests

```
cd finanz_tracker
pip install -r requirements.txt
python -m unittest discover -s tests -v     # automatische Tests
DATA_DIR=./data python -m app                # lokal starten: http://localhost:8080
```
