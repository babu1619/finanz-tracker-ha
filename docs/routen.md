# Seiten und Routen

Alle Adressen der App (Stand 0.9.0), erzeugt aus `app.url_map` und den Dekoratoren der Views.

**Rechte:**

| Recht | Bedeutung |
| --- | --- |
| öffentlich | ohne Anmeldung |
| angemeldet | `login_required`; jede Rolle |
| schreiben | `schreibrecht`; Admin oder Mitglied |
| Admin | `admin_required` |

Einige „angemeldet“-Routen mit GET und POST prüfen beim POST das Schreibrecht in der Funktion selbst
(`auth.darf_schreiben()`), zum Beispiel `buchungen.bearbeiten` und `vertraege.bearbeiten`.
`planung.quellen_speichern` darf jede Rolle, weil es nur die eigene Einstellung speichert.

Jeder POST braucht das CSRF-Token (Formularfeld `csrf` oder Kopf `X-CSRF`). Formulare leiten nach dem Speichern weiter.
JSON liefern:
- `/buchungen/<id>/inline` (POST)
- `/auswertung/daten` (POST)
- `/krypto/verlauf` (GET)

| Route | Methoden | Recht | Funktion |
| --- | --- | --- | --- |
| `/` | GET | angemeldet | `dashboard.index` |
| `/auswertung/` | GET | angemeldet | `auswertung.index` |
| `/auswertung/ansicht` | POST | angemeldet | `auswertung.ansicht` |
| `/auswertung/ansicht/<int:aid>` | POST | angemeldet | `auswertung.ansicht` |
| `/auswertung/daten` | POST | angemeldet | `auswertung.daten` |
| `/auswertung/eigene` | GET | angemeldet | `auswertung.eigene` |
| `/buchungen/` | GET | angemeldet | `buchungen.liste` |
| `/buchungen/<int:bid>` | GET, POST | angemeldet | `buchungen.bearbeiten` |
| `/buchungen/<int:bid>/inline` | POST | schreiben | `buchungen.inline` |
| `/buchungen/<int:bid>/zuordnung` | POST | schreiben | `buchungen.zuordnung_speichern` |
| `/buchungen/export.csv` | GET | angemeldet | `buchungen.export` |
| `/buchungen/sammel` | POST | schreiben | `buchungen.sammel` |
| `/budgets/` | GET | angemeldet | `budgets.index` |
| `/budgets/<int:bid>` | GET, POST | schreiben | `budgets.bearbeiten` |
| `/budgets/neu` | POST | schreiben | `budgets.neu` |
| `/budgets/vorschlaege` | POST | schreiben | `budgets.vorschlaege_uebernehmen` |
| `/darlehen/` | GET | angemeldet | `darlehen.index` |
| `/darlehen/<int:kid>` | GET | angemeldet | `darlehen.detail` |
| `/darlehen/<int:kid>/anschluss` | POST | schreiben | `darlehen.anschluss` |
| `/darlehen/<int:kid>/ereignis` | POST | schreiben | `darlehen.ereignis` |
| `/darlehen/<int:kid>/konditionen` | GET, POST | schreiben | `darlehen.konditionen` |
| `/darlehen/<int:kid>/zahlungen-zuordnen` | POST | schreiben | `darlehen.zahlungen_zuordnen` |
| `/darlehen/anschluss-uebernehmen` | POST | schreiben | `darlehen.anschluss_alle` |
| `/darlehen/bausparen/<int:vid>` | GET | angemeldet | `darlehen.bausparen_detail` |
| `/darlehen/bausparen/<int:vid>/bearbeiten` | GET, POST | schreiben | `darlehen.bausparvertrag` |
| `/darlehen/bausparen/<int:vid>/stand` | POST | schreiben | `darlehen.bauspar_stand` |
| `/darlehen/bausparen/neu` | GET, POST | schreiben | `darlehen.bausparvertrag` |
| `/darlehen/immobilie` | POST | schreiben | `darlehen.immobilie` |
| `/darlehen/sondertilgung-aus-buchung/<int:bid>` | POST | schreiben | `darlehen.sondertilgung_aus_buchung` |
| `/depot/<int:kid>` | GET | angemeldet | `depot.detail` |
| `/depot/<int:kid>/eintrag` | POST | schreiben | `depot.eintrag` |
| `/depot/<int:kid>/rendite` | POST | schreiben | `depot.rendite` |
| `/einrichtung` | GET, POST | öffentlich | `auth_views.einrichtung` |
| `/erfassen/` | GET, POST | schreiben | `erfassen.index` |
| `/favicon.ico` | GET | öffentlich | `pwa.favicon` |
| `/import/` | GET, POST | schreiben | `importe.index` |
| `/import/abbrechen/<token>` | POST | schreiben | `importe.abbrechen` |
| `/import/geloescht/<int:gid>/zulassen` | POST | schreiben | `importe.geloescht_zulassen` |
| `/import/lauf/<int:lid>` | GET | angemeldet | `importe.lauf` |
| `/import/lauf/<int:lid>/rueckgaengig` | POST | schreiben | `importe.rueckgaengig` |
| `/import/profil/<int:pid>` | GET, POST | Admin | `importe.profil` |
| `/import/profil/<int:pid>/datei` | POST | Admin | `importe.profil_datei` |
| `/import/profil/neu` | GET, POST | Admin | `importe.profil_neu` |
| `/import/screenshot` | GET, POST | schreiben | `importe.screenshot` |
| `/import/screenshot/uebernehmen` | POST | schreiben | `importe.screenshot_uebernehmen` |
| `/import/uebernehmen/<token>` | POST | schreiben | `importe.uebernehmen` |
| `/kategorien/` | GET | angemeldet | `kategorien.liste` |
| `/kategorien/<int:kid>` | GET, POST | schreiben | `kategorien.bearbeiten` |
| `/kategorien/neu` | POST | schreiben | `kategorien.neu` |
| `/konten/` | GET | angemeldet | `konten.liste` |
| `/konten/<int:kid>` | GET, POST | Admin | `konten.bearbeiten` |
| `/konten/neu` | GET, POST | Admin | `konten.neu` |
| `/krypto/` | GET | angemeldet | `krypto.index` |
| `/krypto/abrufen` | POST | schreiben | `krypto.abrufen` |
| `/krypto/verlauf` | GET | angemeldet | `krypto.verlauf` |
| `/login` | GET, POST | öffentlich | `auth_views.login` |
| `/logout` | POST | öffentlich | `auth_views.logout` |
| `/manifest.webmanifest` | GET | öffentlich | `pwa.manifest` |
| `/offline` | GET | öffentlich | `pwa.offline` |
| `/passwort` | GET, POST | angemeldet | `auth_views.passwort` |
| `/planung/` | GET | angemeldet | `planung.index` |
| `/planung/posten` | POST | schreiben | `planung.posten_speichern` |
| `/planung/posten/<int:pid>` | POST | schreiben | `planung.posten_speichern` |
| `/planung/quellen` | POST | angemeldet | `planung.quellen_speichern` |
| `/pruefen/` | GET | schreiben | `pruefen.index` |
| `/pruefen/<int:bid>` | POST | schreiben | `pruefen.speichern` |
| `/pruefen/neustart` | POST | schreiben | `pruefen.neustart` |
| `/pruefen/tabelle` | POST | schreiben | `pruefen.tabelle_speichern` |
| `/pruefen/umbuchung/<int:vid>` | POST | schreiben | `pruefen.umbuchung` |
| `/regeln/` | GET | angemeldet | `regeln.liste` |
| `/regeln/<int:rid>` | GET, POST | schreiben | `regeln.bearbeiten` |
| `/regeln/<int:rid>/verschieben` | POST | schreiben | `regeln.verschieben` |
| `/regeln/anwenden` | POST | schreiben | `regeln.anwenden` |
| `/regeln/neu` | GET, POST | schreiben | `regeln.neu` |
| `/sparen/` | GET | angemeldet | `sparen.index` |
| `/sparen/<int:rid>` | GET, POST | angemeldet | `sparen.detail` |
| `/sparen/neu` | POST | schreiben | `sparen.neu` |
| `/sparen/sparquote` | POST | Admin | `sparen.sparquote` |
| `/sw.js` | GET | öffentlich | `pwa.service_worker` |
| `/tags/` | GET | angemeldet | `tags.index` |
| `/tags/<int:tid>` | GET, POST | angemeldet | `tags.detail` |
| `/tags/neu` | POST | schreiben | `tags.neu` |
| `/vertraege/` | GET | angemeldet | `vertraege.index` |
| `/vertraege/<int:vid>` | GET, POST | angemeldet | `vertraege.bearbeiten` |
| `/vertraege/markieren` | POST | schreiben | `vertraege.markieren` |
| `/vertraege/neu` | GET, POST | angemeldet | `vertraege.bearbeiten` |
| `/verwaltung/` | GET | Admin | `admin.index` |
| `/verwaltung/backup` | GET | Admin | `admin.backup` |
| `/verwaltung/benutzer` | POST | Admin | `admin.benutzer` |
| `/verwaltung/person` | POST | Admin | `admin.person` |
| `/verwaltung/sicherung` | POST | Admin | `admin.sicherung` |
| `/verwaltung/wiederherstellen` | POST | Admin | `admin.wiederherstellen` |
| `/zertifikat` | GET | angemeldet | `pwa.zertifikat` |
| `/zertifikat/finanz-tracker-ca.crt` | GET | öffentlich | `pwa.ca_download` |
