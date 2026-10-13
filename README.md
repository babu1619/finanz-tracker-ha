# Finanz-Tracker – Installation auf dem Home Assistant Green

Version 0.5.0 · Haushaltsbuch für die Familie als Home-Assistant-Add-on.
Die App ist eine eigenständige, verschlüsselte Webseite (https, Port 8099), die sich auf dem Handy als App installieren lässt;
Home Assistant dient nur als Host.
Alle Daten liegen lokal in der SQLite-Datenbank des Add-ons und sind Teil der Home-Assistant-Backups.

## Was im Paket steckt

```
finanz-tracker/
├── repository.yaml          ← macht das GitHub-Repository zum Add-on-Repository
├── tools/                   ← einrichten.py, pruefen.py, release.py (siehe „Werkzeuge“)
├── .github/workflows/       ← automatische Prüfung und optional vorgebaute Images auf GitHub
├── README.md                ← diese Anleitung
└── finanz_tracker/          ← das Add-on
    ├── config.yaml          ← Add-on-Beschreibung (Name, Version, Port 8099)
    ├── build.yaml           ← Python-Basis-Image je Architektur
    ├── Dockerfile
    ├── requirements.txt     ← Flask, waitress, cryptography
    ├── translations/        ← Beschriftung der Add-on-Optionen
    ├── DOCS.md, CHANGELOG.md, icon.png, logo.png
    ├── app/                 ← Programmcode, Vorlagen, Datenbank-Migrationen
    └── tests/               ← automatische Tests und Beispiel-CSV-Dateien
```

## Installation über GitHub (empfohlen)

**1. Paket entpacken.** `finanz-tracker-v0.2.0.zip` auf dem PC entpacken. Du erhältst den Ordner `finanz-tracker`.

**2. Repository auf GitHub anlegen.** Auf github.com › „New repository“, Name `finanz-tracker`,
Sichtbarkeit **Public**. Home Assistant lädt Add-on-Repositories ohne Zugangsdaten; im Repository liegt nur
Programmcode, keine Finanzdaten. Kein README, keine .gitignore anlegen lassen.

**3. Dateien hochladen.** Im neuen Repository „uploading an existing file“ wählen und den **Inhalt** des Ordners
`finanz-tracker` (also `repository.yaml`, `README.md`, `.gitignore` und den Ordner `finanz_tracker`) per Drag & Drop
ins Browserfenster ziehen › „Commit changes“.
Alternativ mit Git:
```
cd finanz-tracker
git init && git add . && git commit -m "Finanz-Tracker 0.2.0"
git branch -M main
git remote add origin https://github.com/babu1619/finanz-tracker-ha.git
git push -u origin main
```

**4. Repository in Home Assistant eintragen.** Einstellungen › Add-ons › „Add-on Store“ › Menü ⋮ oben rechts ›
„Repositories“ › `https://github.com/babu1619/finanz-tracker-ha` › „Hinzufügen“ › Schließen.

**5. Add-on installieren.** Seite neu laden (ggf. Menü ⋮ › „Nach Updates suchen“). Unten erscheint der Abschnitt
„Finanz-Tracker“ › Add-on öffnen › „Installieren“. Das Add-on wird auf dem Green gebaut; das dauert beim ersten Mal
einige Minuten, weil das Python-Basis-Image geladen wird.

**6. Starten.** Im Reiter „Info“ „Beim Start starten“ und „Watchdog“ einschalten › „Starten“.
Im Reiter „Protokoll“ sollte stehen: `Finanz-Tracker 0.2.0 startet mit HTTPS (eigenes-Zertifikat) auf Port 8099 …`.

**7. App öffnen.** Im Browser `https://<IP-des-Green>:8099` aufrufen (die IP steht in Home Assistant unter
Einstellungen › System › Netzwerk; `https://homeassistant.local:8099` geht am PC meist auch). Beim allerersten Aufruf
warnt der Browser, weil er das Zertifikat noch nicht kennt – siehe Abschnitt „HTTPS und App auf dem Handy“.
Am PC kannst du die Warnung für die Ersteinrichtung einmal über „Erweitert › Weiter zu …“ überspringen.

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

## Neu in 0.5.0 – kurz erklärt

- **Kreditkartenabrechnung:** Import → „Abrechnung (PDF) oder Screenshot“, PDF der Monatsabrechnung auswählen (oder ein
  Foto davon). Das Tool zeigt alle Umsätze zur Prüfung und rechnet nach: alter Saldo + Umsätze = neuer Saldo. Die
  Gutschrift „Kartenabrechnung“ ist das Gegenstück zur Abbuchung vom Girokonto und wird als Umbuchung erkannt.
- **Regeln nachträglich durchsetzen:** Beim Speichern einer Regel „diese Regel auf alle passenden Buchungen“ wählen –
  dann werden auch manuell zugeordnete Buchungen umgestellt. Vorher mit „Gegen bestehende Buchungen testen“ ansehen,
  was sich ändert. Aufgeteilte Buchungen und verknüpfte Umbuchungen bleiben immer unverändert.
- **Sondertilgung als Buchung:** Auf der Darlehensseite eintragen (mit Haken „Als Buchung im Darlehenskonto anlegen“)
  oder direkt bei der Abbuchung im Girokonto „Als Sondertilgung erfassen“ wählen.
- **Bausparverträge:** Darlehen → „Bausparvertrag anlegen“. Einmal im Jahr den Guthabenstand aus dem Kontoauszug
  eintragen. Wird ein Darlehen zur Ablösung gewählt, zeigt die Seite, ob Guthaben plus Bauspardarlehen zum Ende der
  Zinsbindung reichen (vereinfacht, ohne Bewertungszahl).

## Neu in 0.4.0 – kurz erklärt

- **Dashboard verlinkt:** Ein Tipp auf „Einnahmen“ oder „Ausgaben“ öffnet die passenden Buchungen des Monats, ein Tipp
  auf ein Konto dessen Buchungen. Hauptkategorien mit Unterkategorien haben links einen Pfeil zum Aufklappen.
- **Depot ohne Auszug:** Konto vom Typ „Depot“ anlegen, dann unter Konten → „Rendite & Einträge“ (oder im Dashboard
  auf das Depot tippen). Überweisungen ins Depot im Girokonto als „Umbuchung“ mit Gegenkonto Depot speichern (oder per
  Regel) – die Einzahlung im Depot entsteht automatisch. Gebühren, Erträge und Ein-/Auszahlungen ohne Gegenstück
  trägst du dort von Hand ein. Die aktuelle Rendite aus der Depot-App in % oder € eintragen; der Depotwert
  (Kapital + Rendite) fließt ins Vermögen ein.
- **Kreditkarte per Screenshot:** Import → „Screenshot einlesen“. In der Banking-App Screenshots der Umsatzliste
  machen, dann hier auswählen oder einfügen (Handy: „Aus Zwischenablage einfügen“ oder lange ins Feld tippen →
  Einfügen; PC: Strg+V). Die Texterkennung (Tesseract) läuft im Add-on selbst. Erkannte Umsätze prüfen, Tippfehler
  korrigieren, „Ausgewählte übernehmen“. Vorgemerkte Umsätze sind nicht vorausgewählt; schon übernommene werden
  erkannt. Das Add-on-Image wird dadurch beim Update etwas größer (Neubau dauert einige Minuten).

## Neu in 0.3.0 – kurz erklärt

- **Buchungen direkt in der Tabelle bearbeiten:** Kategorie (Pfad tippen, Enter), Person und Tags lassen sich in der
  Zeile ändern und werden sofort gespeichert – ein grüner Rahmen bestätigt das. Tags haben eine eigene Spalte.
  Aufgeteilte Buchungen und Umbuchungen werden weiter in der Buchung selbst bearbeitet.
- **Sortieren und Filtern in den Spaltenüberschriften:** Klick auf den Spaltennamen sortiert (nochmal klicken dreht
  die Richtung), das Trichter-Symbol öffnet den Filter der Spalte (Datum von/bis, Monat, Konto, Gegenpartei, Kategorie,
  Person, Tag, Betrag von/bis und Richtung). Aktive Filter stehen als Chips über der Tabelle und lassen sich mit ✕ entfernen.
- **Prüf-Modus:** Tags gleich mit vergeben (Vorschläge aus früheren Buchungen derselben Gegenpartei). „Umbuchung“
  wählen und das Gegenkonto festlegen: liegt die Gegenbuchung schon vor, wird sie verknüpft, sonst beim nächsten
  Import automatisch. Umschalter **Tabelle** zeigt alle offenen Buchungen auf einen Blick – Werte zeilenweise ändern
  oder für mehrere angehakte Zeilen auf einmal setzen, dann „Ausgewählte speichern“.
- **Konten:** Die Spalte „Konto“ bleibt beim seitlichen Scrollen stehen; Bearbeiten über den Stift links.
- **Bargeld (0.3.1/0.3.2):** Abhebung als „Umbuchung“ mit Gegenkonto „Bargeld“ speichern – im Prüf-Modus, auf der
  Detailseite der Buchung, direkt in der Buchungstabelle (Kategorie „Umbuchung“ tippen, dann Gegenkonto wählen) oder
  für mehrere Buchungen per Sammelaktion – die Gegenbuchung
  im Barkonto entsteht automatisch. Noch bequemer: Regel „Gegenpartei enthält Geldautomat“ → „Als Umbuchung“ mit
  Gegenkonto „Bargeld“; dann landen Abhebungen schon beim Import im Barkonto. Im Barkonto erfasst du mit „+ Bar“ nur
  noch die Ausgaben, nicht die Abhebung selbst.

## Neu in 0.2.0 – kurz erklärt

- **Buchungen:** Suche/Filter und Sammeländerung sind einklappbar. In einer Buchung „Auf mehrere Kategorien aufteilen“
  anhaken, Teile eintragen („Rest in letzten Teil“ hilft) – die Summe muss stimmen. „Verteilen auf 12 Monate“ für
  Jahresbeiträge. Tags mit Komma trennen.
- **Budgets:** Budgets anlegen oder Vorschläge aus dem 6-Monats-Durchschnitt übernehmen. Ein Budget auf „Mobilität“
  umfasst alle Unterkategorien. Strich = Anteil des Monats, schraffiert = Prognose.
- **Sparen:** Ziel-Sparquote festlegen; Rücklagen (z. B. „Instandhaltung Haus“) und Sparziele mit Zielbetrag und
  -datum auf dem Tagesgeld anlegen. Ausgaben daraus in der Buchung über „Bezahlt aus Rücklage“ markieren.
- **Darlehen:** Konditionen je Darlehenskonto eintragen (Betrag, Sollzins, Rate, erste Rate, Zinsbindung,
  Sondertilgungsrahmen). Danach gibt es Tilgungsplan, Simulation je Darlehen und den Vergleich, wo eine Sondertilgung
  am meisten bringt. Restschuld laut Jahresauszug als „Abgleich“ eintragen.
- **Abos & Verträge** (unter Mehr): erkannte wiederkehrende Zahlungen als Fixkosten oder Abo bestätigen.
- **+ Bar** oben rechts: Bargeldausgaben in Sekunden erfassen (am besten ein Konto vom Typ „Bargeld“ anlegen).

## Update auf 0.2.0

1. Paket `finanz-tracker-v0.2.0.zip` entpacken.
2. Im GitHub-Repository den Ordner `finanz_tracker` durch den neuen ersetzen: „Add file › Upload files“ und den
   **Inhalt** des neuen Pakets (`finanz_tracker`, `README.md`, `repository.yaml`) hineinziehen › „Commit changes“.
   Mit Git: Dateien im lokalen Ordner überschreiben, dann `git add -A && git commit -m "0.2.0" && git push`.
3. Home Assistant › Einstellungen › Add-ons › Add-on Store › Menü ⋮ › „Nach Updates suchen“.
4. Add-on „Finanz-Tracker“ öffnen › „Aktualisieren“. Das Add-on wird neu gebaut (einige Minuten).
5. Reiter „Protokoll“: `Finanz-Tracker 0.2.0 startet mit HTTPS …`. Die Datenbank wird beim Start automatisch auf das
   neue Schema gebracht; alle Buchungen, Regeln und Kategorien bleiben erhalten.
6. Die bisherige Adresse `http://…:8099` leitet automatisch auf `https://…:8099` um. Weiter mit dem nächsten Abschnitt.

Vor dem Update empfiehlt sich eine Sicherung: Verwaltung › „Datenbank herunterladen“ (oder ein Home-Assistant-Backup).

Spätere Updates laufen genauso: Dateien im Repository ersetzen, „Nach Updates suchen“, „Aktualisieren“.

## HTTPS und App auf dem Handy

Das Add-on verschlüsselt jetzt mit einem eigenen Zertifikat. Damit Browser ihm ohne Warnung vertrauen – und
**Chrome auf Android die Seite als App installieren lässt** –, installierst du einmal pro Gerät die „Heim-CA“
des Tools. In der App findest du Download, Fingerabdruck und Anleitung unter **Mehr › App & Zertifikat**.

**Android (Chrome)**
1. Am Handy (im WLAN zu Hause) `https://<IP-des-Green>:8099` öffnen. Warnung „Verbindung ist nicht privat“ ›
   „Erweitert“ › „Weiter zu …“, anmelden, dann Mehr › App & Zertifikat › **Zertifikat herunterladen (.crt)**.
   Alternativ ohne Anmeldung: `https://<IP-des-Green>:8099/zertifikat/finanz-tracker-ca.crt`.
2. Einstellungen › Sicherheit und Datenschutz › Weitere Sicherheitseinstellungen › Verschlüsselung und Anmeldedaten ›
   Zertifikat installieren › **CA-Zertifikat** › „Trotzdem installieren“ › Datei `finanz-tracker-ca.crt` wählen.
   (Samsung: Biometrische Daten und Sicherheit › Andere Sicherheitseinstellungen › Vom Gerätespeicher installieren ›
   CA-Zertifikat. Bei anderen Herstellern in den Einstellungen nach „Zertifikat“ suchen.)
3. Chrome ganz schließen (aus der App-Übersicht wischen) und `https://<IP-des-Green>:8099` neu öffnen – jetzt ohne Warnung.
4. Chrome-Menü ⋮ › **„App installieren“** (bzw. „Zum Startbildschirm hinzufügen“ › „Installieren“). Die App erscheint
   mit eigenem Symbol, startet ohne Adressleiste; langes Drücken aufs Symbol bietet „Bar erfassen“, „Prüfen“, „Buchungen“.

Wichtig: die **IP-Adresse** verwenden, nicht `homeassistant.local` – Android löst `.local`-Namen nicht zuverlässig auf.
Damit die IP gleich bleibt, im Router für den Green eine feste IP-Adresse (DHCP-Reservierung) einstellen. Ändert sich die
IP doch einmal, erzeugt das Add-on beim nächsten Neustart automatisch ein passendes Serverzertifikat; die Heim-CA auf
den Geräten bleibt gültig (10 Jahre).

**Windows-PC:** Zertifikat herunterladen › Doppelklick › „Zertifikat installieren“ › Aktueller Benutzer ›
„Alle Zertifikate in folgendem Speicher speichern“ › **Vertrauenswürdige Stammzertifizierungsstellen** › Fertig stellen.
Chrome/Edge neu starten. Danach lässt sich die App auch am PC über das Symbol in der Adressleiste installieren.

**Zugriff von unterwegs per VPN (Tailscale):** Den Tailscale-Namen oder die Tailscale-IP des Green im Add-on unter
Konfiguration › `zusatz_hostnamen` eintragen (mehrere mit Komma), speichern, Add-on neu starten.

**Add-on-Optionen (Reiter „Konfiguration“)**

| Option | Bedeutung |
| --- | --- |
| `https` | an (Standard) / aus. Ohne HTTPS ist keine App-Installation auf Android möglich. |
| `zertifikat` | `eigenes` (Standard, Heim-CA) oder `homeassistant`: nutzt `fullchain.pem`/`privkey.pem` aus `/ssl`, z. B. von Let's Encrypt/DuckDNS – dann ist keine Installation auf den Geräten nötig, die Adresse muss aber zum Zertifikat passen. |
| `zusatz_hostnamen` | weitere Namen/IPs für das eigene Zertifikat. Die IPs des Green ergänzt das Add-on selbst. |
| `certfile`, `keyfile` | Dateinamen in `/ssl` bei `zertifikat: homeassistant`. |

## Werkzeuge: Updates per Befehl (wie beim Körperdaten-Tracker)

Voraussetzungen am Windows-PC: [Git für Windows](https://git-scm.com/download/win), Python und einmalig
```
python -m pip install pyyaml -r finanz_tracker\requirements.txt
```

**Einmalig umstellen auf Git** (falls du die Dateien bisher über die GitHub-Webseite hochgeladen hast):
1. Repository klonen, z. B. nach `C:\Projekte\finanz-tracker`:
   `git clone https://github.com/babu1619/finanz-tracker-ha.git C:\Projekte\finanz-tracker`
2. Den **Inhalt** dieses Pakets in den Ordner kopieren und Dateien überschreiben (auch die versteckten
   `.gitattributes` und `.github`). Im Explorer: Ansicht › Einblenden › Ausgeblendete Elemente.
3. Im Ordner die Eingabeaufforderung öffnen (Explorer-Adresszeile: `cmd`) und:
   ```
   python tools\einrichten.py babu1619
   python tools\pruefen.py
   git add -A
   git commit -m "Version 0.2.1"
   git push
   ```
4. Home Assistant › Add-on Store › ⋮ › „Nach Updates suchen“ › Finanz-Tracker „Aktualisieren“.

**Was die Skripte tun**

| Befehl | Zweck |
| --- | --- |
| `python tools\einrichten.py NAME` | trägt deinen GitHub-Namen in `repository.yaml`, `config.yaml` und README ein (einmalig) |
| `python tools\pruefen.py` | prüft Konfiguration, Übersetzungen, Python-Code, Nummerierung der Datenbank-Migrationen, gleiche Version in `config.yaml` und `app/config.py`, Änderungsprotokoll – und führt alle automatischen Tests aus (`--ohne-tests` überspringt sie) |
| `python tools\release.py patch "Text"` | erhöht die Version (0.2.1 → 0.2.2, `minor` → 0.3.0), trägt den Text ins Änderungsprotokoll ein, prüft, committet mit Tag und lädt hoch. Schlägt die Prüfung fehl, wird nichts committet und die Version bleibt unverändert. |

**Später, wenn Claude dir ein neues Paket mit bereits erhöhter Version liefert:** Dateien in den Ordner kopieren, dann
`python tools\pruefen.py`, `git add -A`, `git commit -m "Version x.y.z"`, `git push` – nicht `release.py`, sonst würde
die Version ein zweites Mal erhöht. Für eigene kleine Änderungen dagegen `release.py`.

**Auf GitHub** läuft bei jedem Hochladen unter „Actions“ die Prüfung „Prüfen“: Tests, Bau des Images und ein Probestart
des Add-ons mit HTTPS. Ein grüner Haken heißt, das Update kann in Home Assistant installiert werden. Sie warnt auch,
wenn Add-on-Dateien geändert wurden, die Version aber nicht erhöht ist (dann zeigt Home Assistant kein Update an).

**Optional: vorgebaute Images** – der Green muss das Add-on dann nicht mehr selbst bauen:
1. In `finanz_tracker/config.yaml` bei `# image: "ghcr.io/…/finanz-tracker-{arch}"` das `# ` entfernen.
2. `python tools\release.py patch "Vorgebaute Images"`. Unter Actions läuft „Images bauen“ (5–10 Minuten).
3. Einmalig auf GitHub › Profil › Packages › `finanz-tracker-ha-aarch64` › Package settings › Change visibility › **Public**.
4. Erst wenn „Images bauen“ fertig ist, in Home Assistant aktualisieren.

**Nie ändern:** `slug: finanz_tracker` in `config.yaml` (sonst hält Home Assistant das Add-on für ein neues ohne Daten).
Das Add-on nie deinstallieren, um ein Problem zu lösen – das löscht die Datenbank.

## Sicherheit

- **Port 8099 nicht im Router freigeben.** Für den Zugriff von unterwegs das Add-on „Tailscale“ oder „WireGuard“
  installieren und die App über das VPN aufrufen.
- Nach 5 falschen Passworteingaben ist der Benutzername 15 Minuten gesperrt.
- **Passwort vergessen:** Add-on › Reiter „Konfiguration“ › Option `admin_passwort_reset` mit einem neuen Passwort
  (mindestens 8 Zeichen) füllen › Speichern › Add-on neu starten › anmelden › Option wieder leeren und speichern.

## Sicherung

Home-Assistant-Backups enthalten das Add-on samt Datenbank. Zusätzlich in der Verwaltung:
- **Verschlüsselte Sicherung (.ftbak)** mit eigenem Passwort – geeignet für Cloud-Speicher oder USB-Stick.
  Wiederherstellen ebenfalls in der Verwaltung; der vorherige Stand wird dabei automatisch als Kopie im Datenordner abgelegt.
- Unverschlüsselte Datenbank (.db) und alle Buchungen als CSV.

## Fehlerbehebung

| Problem | Lösung |
| --- | --- |
| Add-on erscheint nicht im Store | Repository-URL prüfen; Repository muss öffentlich sein und `repository.yaml` im Hauptordner liegen. Menü ⋮ › „Nach Updates suchen“. |
| Installation bricht ab | Reiter „Protokoll“ des Supervisors prüfen (Einstellungen › System › Protokolle › Supervisor). Meist Internet kurz weg – erneut installieren. |
| Seite nicht erreichbar | Läuft das Add-on? Reiter „Protokoll“ prüfen. Port 8099 belegt? Im Reiter „Konfiguration“ › Netzwerk einen anderen Port eintragen. |
| „Spaltenüberschriften nicht gefunden“ beim Import | Die Bank hat das Exportformat geändert: Import › Profil öffnen › „Neue Beispieldatei“ hochladen, Zuordnung prüfen, speichern. |
| Saldo weicht ab | Meist fehlt ein Zeitraum im Import oder der Startsaldo des Kontos stimmt nicht (Konten › Bearbeiten). |
| „Verbindung ist nicht privat“ trotz installiertem Zertifikat | Seite über die IP-Adresse aufrufen, die unter Mehr › App & Zertifikat bei den Adressen steht; Chrome ganz schließen. Steht die IP nicht dabei: in `zusatz_hostnamen` eintragen und Add-on neu starten. |
| „App installieren“ fehlt im Chrome-Menü | Nur bei vertrauenswürdigem HTTPS möglich. Mehr › App & Zertifikat zeigt, was fehlt. Ist die App schon installiert, steht dort „App öffnen“. |
| Seite lädt nach dem Update nicht mehr | Adresse mit `https://` aufrufen. Notfalls in der Konfiguration `https` ausschalten und Add-on neu starten. |

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
