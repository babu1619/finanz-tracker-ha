"""Ende-zu-Ende-Tests mit Flask-Testclient. Start: python -m unittest discover -s tests -v"""
import io
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HIER = Path(__file__).resolve().parent
TMP = tempfile.mkdtemp(prefix="finanz-test-")
os.environ["DATA_DIR"] = TMP
sys.path.insert(0, str(HIER.parent))

from app import create_app  # noqa: E402
from app.services import csvimport  # noqa: E402
from app.util import partner_key, euro  # noqa: E402


def csrf(html: str) -> str:
    m = re.search(r'name="csrf" value="([0-9a-f]+)"', html)
    return m.group(1) if m else ""


class Grundlagen(unittest.TestCase):
    def test_betrag(self):
        self.assertEqual(csvimport.parse_betrag("-1.234,56"), -123456)
        self.assertEqual(csvimport.parse_betrag("1.234,56-"), -123456)
        self.assertEqual(csvimport.parse_betrag("+12,5"), 1250)
        self.assertEqual(csvimport.parse_betrag("1,234.56", "."), 123456)
        self.assertIsNone(csvimport.parse_betrag(""))
        with self.assertRaises(ValueError):
            csvimport.parse_betrag("abc")

    def test_euro_eingabe(self):
        from app.util import parse_euro_eingabe
        self.assertEqual(parse_euro_eingabe("1.000"), 100000)
        self.assertEqual(parse_euro_eingabe("300.000"), 30000000)
        self.assertEqual(parse_euro_eingabe("1.234,56"), 123456)
        self.assertEqual(parse_euro_eingabe("12.50"), 1250)
        self.assertEqual(parse_euro_eingabe("-17,99"), -1799)

    def test_euro(self):
        self.assertEqual(euro(-123456), "−1.234,56 €")
        self.assertEqual(euro(5, vorzeichen=True), "+0,05 €")

    def test_partner_key(self):
        self.assertEqual(partner_key("SUPERMARKT MUSTER GMBH Fil. 123"), partner_key("Supermarkt Muster GmbH"))

    def test_analyse_giro(self):
        a = csvimport.analysiere((HIER / "beispiel_giro.csv").read_bytes())
        self.assertEqual(a["einstellungen"]["delimiter"], ";")
        self.assertEqual(a["kopfzeile"], 4)
        self.assertEqual(a["felder"], ["datum", "valuta", "partei", "zweck", "zweck", "iban", "betrag", "saldo"])
        self.assertEqual(a["einstellungen"]["decimal"], ",")

    def test_analyse_tagesgeld(self):
        a = csvimport.analysiere((HIER / "beispiel_tagesgeld.csv").read_bytes())
        self.assertEqual(a["einstellungen"]["delimiter"], ",")
        self.assertEqual(a["einstellungen"]["date_format"], "JJJJ-MM-TT")
        self.assertEqual(a["einstellungen"]["decimal"], ".")
        self.assertIn("betrag", a["felder"])

    def test_soll_haben(self):
        raw = "Datum;Text;Soll;Haben\n01.10.2026;Miete;1.280,00;\n02.10.2026;Gehalt;;4.000,00\n".encode()
        a = csvimport.analysiere(raw)
        self.assertEqual(a["betrag_modus"], "soll_haben")
        profil = {"einstellungen": a["einstellungen"], "betrag_modus": "soll_haben",
                  "spalten": [{"index": i, "header": h, "feld": f} for i, (h, f) in enumerate(zip(a["headers"], a["felder"]))]}
        erg = csvimport.lese_datei(raw, profil)
        self.assertEqual([d["betrag_cent"] for d in erg["datensaetze"]], [-128000, 400000])

    def test_formatwechsel(self):
        a = csvimport.analysiere((HIER / "beispiel_giro.csv").read_bytes())
        profil = {"einstellungen": a["einstellungen"], "betrag_modus": "vorzeichen",
                  "spalten": [{"index": i, "header": h, "feld": f} for i, (h, f) in enumerate(zip(a["headers"], a["felder"]))]}
        geaendert = (HIER / "beispiel_giro.csv").read_text(encoding="utf-8").replace('"Betrag (EUR)"', '"Umsatz"')
        with self.assertRaises(csvimport.ProfilFehler):
            csvimport.lese_datei(geaendert.encode(), profil)


class Ablauf(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app({"TESTING": True})
        cls.c = cls.app.test_client()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TMP, ignore_errors=True)

    def get(self, url, ok=200):
        r = self.c.get(url, follow_redirects=True)
        self.assertEqual(r.status_code, ok, url)
        return r.get_data(as_text=True)

    def post(self, url, data, ok=200, von=None):
        html = self.get(von or url) if von is not False else ""
        data = dict(data)
        data.setdefault("csrf", csrf(html) or self._csrf)
        r = self.c.post(url, data=data, follow_redirects=True, content_type="multipart/form-data")
        self.assertEqual(r.status_code, ok, f"{url}: {r.get_data(as_text=True)[:400]}")
        html = r.get_data(as_text=True)
        self._csrf = csrf(html) or self._csrf
        return html

    _csrf = ""

    def test_ablauf(self):
        # 1. Einrichtung
        html = self.get("/")
        self.assertIn("Willkommen", html)
        html = self.post("/einrichtung", {"name": "benjamin", "person": "Benjamin", "passwort": "geheim123",
                                          "passwort2": "geheim123", "startset": "1"})
        self.assertIn("Konten", html)

        # 2. Profil aus Beispieldatei
        html = self.post("/import/profil/neu", {"name": "Musterbank CSV",
                                                "datei": (io.BytesIO((HIER / "beispiel_giro.csv").read_bytes()), "giro.csv")})
        self.assertIn("Spalten zuordnen", html)
        self.assertIn("Pflichtfelder zugeordnet", html)
        pid_giro = int(re.search(r"/import/profil/(\d+)/datei", html).group(1))
        html = self.post("/import/profil/neu", {"name": "Tagesgeld CSV",
                                                "datei": (io.BytesIO((HIER / "beispiel_tagesgeld.csv").read_bytes()), "tg.csv")})
        pid_tg = int(re.search(r"/import/profil/(\d+)/datei", html).group(1))

        # 3. Konten
        self.post("/konten/neu", {"name": "Girokonto", "typ": "giro", "iban": "DE12 3456 7890 1234 5678 90",
                                  "importprofil_id": str(pid_giro), "startsaldo": "0", "sichtbarkeit": "alle", "aktiv": "1"})
        self.post("/konten/neu", {"name": "Tagesgeld", "typ": "tagesgeld", "iban": "DE98 7654 3210 9876 5432 10",
                                  "importprofil_id": str(pid_tg), "startsaldo": "0", "sichtbarkeit": "alle", "aktiv": "1"})
        self.post("/konten/neu", {"name": "Baudarlehen", "typ": "darlehen", "startsaldo": "-274.225,37",
                                  "sichtbarkeit": "alle", "aktiv": "1"})
        html = self.get("/konten/")
        self.assertIn("Musterbank CSV", html)

        # 4. Import Giro (Konto automatisch über IBAN erkannt)
        html = self.post("/import/", {"konto_id": "", "datei": (io.BytesIO((HIER / "beispiel_giro.csv").read_bytes()), "giro.csv")})
        self.assertIn("6 Buchungen übernehmen", html)
        token = re.search(r"/import/uebernehmen/([0-9a-f]+)", html).group(1)
        html = self.post(f"/import/uebernehmen/{token}", {}, von=False)
        self.assertIn("Saldoabgleich stimmt", html)

        # Doppelter Import erkennt Duplikate
        html = self.post("/import/", {"konto_id": "", "datei": (io.BytesIO((HIER / "beispiel_giro.csv").read_bytes()), "giro.csv")})
        self.assertIn("0 Buchungen übernehmen", html)

        # 5. Tagesgeld-Import -> Umbuchung wird automatisch erkannt
        html = self.post("/import/", {"konto_id": "", "datei": (io.BytesIO((HIER / "beispiel_tagesgeld.csv").read_bytes()), "tg.csv")})
        self.assertIn("nicht automatisch erkannt", html)  # Datei ohne IBAN
        html = self.post("/import/", {"konto_id": "2", "datei": (io.BytesIO((HIER / "beispiel_tagesgeld.csv").read_bytes()), "tg.csv")})
        token = re.search(r"/import/uebernehmen/([0-9a-f]+)", html).group(1)
        html = self.post(f"/import/uebernehmen/{token}", {}, von=False)
        self.assertRegex(html, r"Umbuchungen</div><div class=\"wert\">1<")

        # 6. Prüf-Modus: Supermarkt zuordnen und Regel anlegen
        html = self.get("/pruefen/")
        self.assertIn("Prüf-Modus", html)
        from app.db import connect
        db = connect()
        kat_lebensmittel = db.execute("SELECT id FROM kategorie WHERE name = 'Lebensmittel'").fetchone()["id"]
        kat_gehalt = db.execute("SELECT id FROM kategorie WHERE name = 'Gehalt'").fetchone()["id"]
        kat_rate = db.execute("SELECT id FROM kategorie WHERE name = 'Darlehensrate'").fetchone()["id"]
        markt = db.execute("SELECT id FROM buchung WHERE gegenpartei LIKE 'SUPERMARKT%' ORDER BY buchungsdatum DESC").fetchone()["id"]
        html = self.post(f"/pruefen/{markt}", {"kategorie_id": str(kat_lebensmittel), "abrechnungsmonat": "2026-10",
                                               "regel": "1", "regel_feld": "gegenpartei", "regel_text": "supermarkt"},
                         von="/pruefen/")
        self.assertIn("Regel angelegt", html)
        andere = db.execute("SELECT kategorie_id, zuordnung_quelle FROM buchung WHERE gegenpartei LIKE 'SUPERMARKT%' "
                            "AND id != ?", (markt,)).fetchone()
        self.assertEqual(andere["kategorie_id"], kat_lebensmittel)
        self.assertEqual(andere["zuordnung_quelle"], "regel")

        # 7. Regel für Gehalt mit Monatsversatz +1 und für die Darlehensrate (Ausgabe, keine Umbuchung)
        self.post("/regeln/neu", {"name": "Gehalt", "feld0": "gegenpartei", "op0": "enthaelt", "wert0": "arbeitgeber",
                                  "kategorie_id": str(kat_gehalt), "monat_versatz": "1", "anwenden": "1",
                                  "aktion": "speichern", "aktiv": "1"})
        self.post("/regeln/neu", {"name": "Darlehensrate", "feld0": "verwendungszweck", "op0": "enthaelt",
                                  "wert0": "darlehen", "kategorie_id": str(kat_rate), "anwenden": "1",
                                  "aktion": "speichern", "aktiv": "1"})
        gehalt = db.execute("SELECT abrechnungsmonat FROM buchung WHERE gegenpartei LIKE 'ARBEITGEBER%'").fetchone()
        self.assertEqual(gehalt["abrechnungsmonat"], "2026-10")
        rate = db.execute("SELECT ist_umbuchung, kategorie_id FROM buchung WHERE verwendungszweck LIKE '%Darlehen%'").fetchone()
        self.assertEqual((rate["ist_umbuchung"], rate["kategorie_id"]), (0, kat_rate))

        # Regeltest
        html = self.post("/regeln/neu", {"name": "Test", "feld0": "gegenpartei", "op0": "enthaelt", "wert0": "supermarkt",
                                         "kategorie_id": str(kat_gehalt), "aktion": "testen"})
        self.assertIn("Trifft <b>2</b> Buchungen", html)

        # 8. Dashboard Oktober: Einnahmen 4.120, Ausgaben 86,40 + 980 = 1.066,40; Umbuchung zählt nicht
        html = self.get("/?monat=2026-10")
        self.assertIn("4.120 €", html)
        self.assertIn("1.066 €", html)
        # Vermögen: Giro 4.296,95 + Tagesgeld 18.500 (Darlehen zählt nicht)
        self.assertIn("22.797 €", html)

        # 9. Kategorie tief verschachteln und umbenennen
        mob = db.execute("SELECT id FROM kategorie WHERE name = 'Autos'").fetchone()["id"]
        self.post("/kategorien/neu", {"name": "Peugeot", "parent_id": str(mob)}, von="/kategorien/")
        peu = db.execute("SELECT id, pfad FROM kategorie WHERE name = 'Peugeot'").fetchone()
        self.assertEqual(peu["pfad"], "Mobilität › Autos › Peugeot")
        self.post("/kategorien/neu", {"name": "Tanken", "parent_id": str(peu["id"])}, von="/kategorien/")
        self.post(f"/kategorien/{mob}", {"name": "Fahrzeuge", "parent_id": db.execute(
            "SELECT id FROM kategorie WHERE name='Mobilität'").fetchone()["id"], "art": ""}, von=f"/kategorien/{mob}")
        tank = db.execute("SELECT pfad FROM kategorie WHERE name = 'Tanken'").fetchone()
        self.assertEqual(tank["pfad"], "Mobilität › Fahrzeuge › Peugeot › Tanken")

        # 10. Buchungsliste, Export, Seiten erreichbar
        html = self.get("/buchungen/?monat=alle")
        self.assertIn("Buchungen", html)
        r = self.c.get("/buchungen/export.csv?monat=alle")
        self.assertEqual(r.status_code, 200)
        self.assertIn("SUPERMARKT", r.get_data(as_text=True))
        for url in ("/regeln/", "/kategorien/", "/import/", "/verwaltung/", "/konten/", f"/import/profil/{pid_giro}"):
            self.get(url)
        r = self.c.get("/verwaltung/backup")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data.startswith(b"SQLite format 3"))

        # 10b. Version 0.2: Aufteilung, Verteilung, Tags, Budgets, Rücklagen, Darlehen, Auswertung, Schnellerfassung
        self._phase34(db, markt, kat_lebensmittel)
        self._v03(db, kat_lebensmittel)
        self._v031(db)

        # 11. Import rückgängig
        lauf = db.execute("SELECT id FROM importlauf WHERE anzahl_neu = 2").fetchone()["id"]
        html = self.post(f"/import/lauf/{lauf}/rueckgaengig", {}, von=f"/import/lauf/{lauf}")
        self.assertIn("2 Buchungen entfernt", html)
        self.assertEqual(db.execute("SELECT COUNT(*) AS n FROM buchung WHERE ist_umbuchung = 1").fetchone()["n"], 0)

        # 12. Rollen: lesender Benutzer darf nichts ändern
        self.post("/verwaltung/benutzer", {"aktion": "neu", "name": "kind", "passwort": "kindpass1", "rolle": "lesend",
                                           "neue_person": "1"}, von="/verwaltung/")
        self.post("/logout", {}, von="/")
        html = self.post("/login", {"name": "kind", "passwort": "kindpass1"})
        self.assertNotIn(">Import<", html)
        r = self.c.get("/import/")
        self.assertEqual(r.status_code, 403)

        # 13. Login-Sperre nach Fehlversuchen
        self.post("/logout", {}, von="/")
        for _ in range(5):
            self.post("/login", {"name": "benjamin", "passwort": "falsch"})
        html = self.post("/login", {"name": "benjamin", "passwort": "geheim123"})
        self.assertIn("Zu viele Fehlversuche", html)
        db.close()

    def _phase34(self, db, markt, kat_lebensmittel):
        from app.services import statistik, darlehen as dl, modell, zuordnung
        from app.util import aktueller_monat
        kat_haushalt = db.execute("SELECT id FROM kategorie WHERE name = 'Haushalt'").fetchone()["id"]
        kat_streaming = db.execute("SELECT id FROM kategorie WHERE name = 'Streaming'").fetchone()["id"]

        # Aufteilung mit falscher Summe wird abgelehnt
        html = self.post(f"/buchungen/{markt}", {"aufteilen": "1", "split_betrag": ["60,00", "20,00"],
                                                 "split_kategorie": [str(kat_lebensmittel), str(kat_haushalt)],
                                                 "split_person": ["", ""], "split_notiz": ["", ""],
                                                 "kategorie_id": str(kat_lebensmittel), "abrechnungsmonat": "2026-10",
                                                 "verteilung_monate": "1", "tags": ""}, von=f"/buchungen/{markt}")
        self.assertIn("Differenz", html)
        self.assertEqual(db.execute("SELECT COUNT(*) AS n FROM buchung_split").fetchone()["n"], 0)
        # richtige Aufteilung 60,00 + 26,40 und Tag
        html = self.post(f"/buchungen/{markt}", {"aufteilen": "1", "split_betrag": ["60,00", "26,40"],
                                                 "split_kategorie": [str(kat_lebensmittel), str(kat_haushalt)],
                                                 "split_person": ["", ""], "split_notiz": ["", "Putzmittel"],
                                                 "abrechnungsmonat": "2026-10", "verteilung_monate": "1",
                                                 "tags": "Steuer 2026"}, von=f"/buchungen/{markt}")
        self.assertIn("Buchung gespeichert", html)
        teile = db.execute("SELECT betrag_cent FROM buchung_split WHERE buchung_id = ? ORDER BY id", (markt,)).fetchall()
        self.assertEqual([t["betrag_cent"] for t in teile], [-6000, -2640])
        with self.app.app_context():
            kat = {k["name"]: k["betrag"] for k in statistik.ausgaben_nach_kategorie([1, 2], "2026-10")}
        self.assertEqual(kat.get("Lebensmittel"), 6000)
        self.assertEqual(kat.get("Haushalt"), 2640)
        html = self.get(f"/buchungen/?kategorie={kat_haushalt}&monat=alle")
        self.assertIn("SUPERMARKT", html)
        self.assertIn("Aufgeteilt", html)
        self.assertIn('<details class="karte klappe" id="suche"', html)  # Suche einklappbar
        self.assertIn('id="aenderung"', html)  # Sammeländerung einklappbar
        # Umsatzsummen im Monat bleiben gleich (Split ändert nur die Verteilung auf Kategorien)
        self.assertIn("1.066 €", self.get("/?monat=2026-10"))

        # Jahresabo auf 12 Monate verteilen (17,99 € -> 1,49 € je Monat, Rest 1,60 € im ersten Monat)
        abo = db.execute("SELECT id FROM buchung WHERE gegenpartei = 'STREAMING DIENST'").fetchone()["id"]
        self.post(f"/buchungen/{abo}", {"kategorie_id": str(kat_streaming), "abrechnungsmonat": "2026-09",
                                         "verteilung_monate": "12", "tags": ""}, von=f"/buchungen/{abo}")
        with self.app.app_context():
            sep = {k["name"]: k["betrag"] for k in statistik.ausgaben_nach_kategorie([1, 2], "2026-09")}
            okt = {k["name"]: k["betrag"] for k in statistik.ausgaben_nach_kategorie([1, 2], "2026-10")}
            summe = sum(r["betrag"] for r in statistik.posten([1, 2], "2026-01", "2028-12") if r["buchung_id"] == abo)
        self.assertEqual(sep.get("Freizeit"), 160)
        self.assertEqual(okt.get("Freizeit"), 149)
        self.assertEqual(summe, -1799)

        # Tags und Steuer-Export
        html = self.get("/tags/")
        self.assertIn("Steuer 2026", html)
        tid = db.execute("SELECT id FROM tag WHERE name = 'Steuer 2026'").fetchone()["id"]
        self.get(f"/tags/{tid}")
        r = self.c.get(f"/buchungen/export.csv?tag={tid}&monat=alle")
        text = r.get_data(as_text=True)
        self.assertIn("aufgeteilt", text)
        self.assertIn("steuer-2026.csv", r.headers["Content-Disposition"])

        # Budget: Lebensmittel 50 € im Oktober -> überschritten (60 €)
        self.post("/budgets/neu", {"kategorie_id": str(kat_lebensmittel), "betrag": "50", "rhythmus": "monat",
                                   "gueltig_ab": "2026-10", "warnschwelle": "90", "monat": "2026-10"}, von="/budgets/")
        html = self.get("/budgets/?monat=2026-10")
        self.assertIn("10 € drüber", html)

        # Rücklage/Sparziel auf dem Tagesgeld, Entnahme über Buchung
        jetzt = aktueller_monat()
        self.post("/sparen/neu", {"name": "Neues Auto", "traeger_konto_id": "2", "bezug": "topf", "zufuehrung": "100",
                                  "startbetrag": "400", "ziel": "1.000", "zieldatum": "2027-12", "start_monat": jetzt},
                  von="/sparen/")
        self.get("/sparen/")
        self.get("/sparen/")  # Zuführungen sind idempotent
        rid = db.execute("SELECT id FROM ruecklage").fetchone()["id"]
        stand = db.execute("SELECT SUM(betrag_cent) AS s FROM ruecklage_bewegung WHERE ruecklage_id = ?", (rid,)).fetchone()["s"]
        self.assertEqual(stand, 50000)
        self.post(f"/buchungen/{abo}", {"kategorie_id": str(kat_streaming), "abrechnungsmonat": "2026-09",
                                         "verteilung_monate": "12", "tags": "", "ruecklage_id": str(rid)},
                  von=f"/buchungen/{abo}")
        stand = db.execute("SELECT SUM(betrag_cent) AS s FROM ruecklage_bewegung WHERE ruecklage_id = ?", (rid,)).fetchone()["s"]
        self.assertEqual(stand, 50000 - 1799)
        html = self.get(f"/sparen/{rid}")
        self.assertIn("Neues Auto", html)
        self.assertIn("frei verfügbar", self.get("/sparen/"))

        # Darlehen: Konditionen, Plan, Simulation; zählt nicht ins Dashboard
        self.post("/darlehen/3/konditionen", {"ursprung": "300.000", "sollzins": "1,5", "rate": "1.200",
                                              "erste_rate": "2020-01", "zinsbindung_bis": "2030-12",
                                              "sondertilgung_prozent": "5", "erinnerung_monate": "24"},
                  von="/darlehen/3/konditionen")
        with self.app.app_context():
            d = dl.lade(3)
            plan = dl.plan(d)
            self.assertEqual(plan[0]["zins"], 37500)
            self.assertEqual(plan[0]["tilgung"], 82500)
            self.assertEqual(plan[-1]["rest"], 0)
            sim = dl.simuliere(d, 1000000, "2027-01")
            self.assertGreater(sim["ersparnis"], 0)
            self.assertGreater(sim["verkuerzung_monate"], 0)
            self.assertEqual(sim["rest_zb_basis"] - sim["rest_zb_mit"] > 1000000, True)  # inkl. gesparter Zinsen
        html = self.get("/darlehen/3?sim_betrag=10.000&sim_monat=2027-01")
        self.assertIn("früher", html)
        self.get("/darlehen/")
        html = self.get("/?monat=2026-10")
        self.assertIn("4.120 €", html)

        # Auswertung, Verträge, Zertifikatseite
        self.assertIn("Lebensmittel", self.get("/auswertung/?zeitraum=12&bis=2026-10"))
        mob = db.execute("SELECT id FROM kategorie WHERE name = 'Mobilität'").fetchone()["id"]
        self.get(f"/auswertung/?kategorie={mob}&zeitraum=jahr&jahr=2026")
        self.get("/vertraege/")
        self.get("/zertifikat")

        # Schnellerfassung Bargeld
        html = self.post("/erfassen/", {"konto_id": "1", "betrag": "12,50", "gegenpartei": "Bäcker",
                                        "kategorie_id": str(kat_lebensmittel), "datum": "2026-10-05", "richtung": "aus"},
                         von="/erfassen/")
        self.assertIn("Erfasst: Bäcker 12,50", html)
        bar = db.execute("SELECT * FROM buchung WHERE manuell_erfasst = 1").fetchone()
        self.assertEqual((bar["betrag_cent"], bar["kategorie_id"]), (-1250, kat_lebensmittel))
        self.post(f"/buchungen/{bar['id']}", {"aktion": "loeschen"}, von=f"/buchungen/{bar['id']}")
        self.assertIsNone(db.execute("SELECT 1 FROM buchung WHERE manuell_erfasst = 1").fetchone())

        # Lernmodell: ähnliche Texte, neue Gegenpartei
        for i in range(24):
            name, zweck, kat = (("BAECKEREI SONNE", "Kartenzahlung Baeckerei Sonne Broetchen", kat_lebensmittel) if i % 2
                                else ("ARAL TANKSTELLE", "Kartenzahlung Tankstelle Super", kat_haushalt))
            db.execute("INSERT INTO buchung (konto_id, buchungsdatum, betrag_cent, gegenpartei, verwendungszweck, partner_key, "
                       "abrechnungsmonat, kategorie_id, dedup_hash, zuordnung_quelle, geprueft) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, 'manuell', 1)",
                       (f"2025-0{1 + i % 9}-1{i % 9}", -1000 - i, name, zweck, name.lower(), f"2025-0{1 + i % 9}",
                        kat, f"lern{i}"))
        neu = db.execute("INSERT INTO buchung (konto_id, buchungsdatum, betrag_cent, gegenpartei, verwendungszweck, partner_key, "
                         "abrechnungsmonat, dedup_hash) VALUES (1, '2025-10-01', -480, 'SONNE BACKWAREN KG', "
                         "'Baeckerei Sonne Broetchen', 'sonne backwaren', '2025-10', 'lern-neu')").lastrowid
        db.commit()
        with self.app.app_context():
            stat = zuordnung.ordne_zu([neu])
            from app.db import commit
            commit()
        self.assertEqual(stat["modell"] + stat["offen"], 1)
        b = db.execute("SELECT kategorie_id, vorschlag_kategorie_id, zuordnung_quelle FROM buchung WHERE id = ?", (neu,)).fetchone()
        self.assertEqual(b["kategorie_id"] or b["vorschlag_kategorie_id"], kat_lebensmittel)
        # Bestätigen erzeugt Feedback für die Trefferquote
        self.post(f"/pruefen/{neu}", {"kategorie_id": str(kat_lebensmittel), "abrechnungsmonat": "2025-10"}, von="/pruefen/")
        with self.app.app_context():
            quoten = modell.trefferquoten()
        self.assertTrue(any(qq["n"] >= 1 for qq in quoten))
        self.assertIn("Trefferquote", self.get("/regeln/"))
        db.execute("DELETE FROM buchung WHERE dedup_hash LIKE 'lern%'")
        db.commit()

        # Verschlüsselte Sicherung und Wiederherstellung
        r = self.c.post("/verwaltung/sicherung", data={"passwort": "sicher123", "csrf": self._csrf})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data.startswith(b"FTBAK1"))
        self.assertNotIn(b"SQLite format 3", r.data)
        sicherung = r.data
        db.execute("UPDATE konto SET name = 'Umbenannt' WHERE id = 1")
        db.commit()
        html = self.post("/verwaltung/wiederherstellen", {"passwort": "falsch123",
                                                          "datei": (io.BytesIO(sicherung), "s.ftbak")}, von="/verwaltung/")
        self.assertIn("Passwort falsch", html)
        html = self.post("/verwaltung/wiederherstellen", {"passwort": "sicher123",
                                                          "datei": (io.BytesIO(sicherung), "s.ftbak")}, von="/verwaltung/")
        self.assertIn("Sicherung wiederhergestellt", html)
        self.assertEqual(db.execute("SELECT name FROM konto WHERE id = 1").fetchone()["name"], "Girokonto")
        self.post("/login", {"name": "benjamin", "passwort": "geheim123"})

    def _v03(self, db, kat_lebensmittel):
        """0.3.0: Konten-Tabelle, Inline-Bearbeitung, Sortieren/Filtern, Prüf-Modus mit Tags/Gegenkonto/Tabelle."""
        import json
        from app.services import umbuchungen
        html = self.get("/konten/")
        self.assertIn('class="stift"', html)
        self.assertIn('fix-links', html)

        # Sortieren und Spaltenfilter
        html = self.get("/buchungen/?monat=alle&sort=betrag")
        self.assertLess(html.index("MUSTERBANK DARLEHEN"), html.index("STREAMING DIENST"))
        html = self.get("/buchungen/?monat=alle&sort=-betrag")
        self.assertLess(html.index("ARBEITGEBER"), html.index("MUSTERBANK DARLEHEN"))
        html = self.get("/buchungen/?monat=alle&partei=supermarkt")
        self.assertIn("SUPERMARKT", html)
        self.assertNotIn(">ARBEITGEBER", html)
        self.assertIn("Gegenpartei enthält", html)  # Filter-Chip
        html = self.get("/buchungen/?monat=alle&min=500&richtung=aus")
        self.assertIn("MUSTERBANK DARLEHEN", html)
        self.assertNotIn("SUPERMARKT", html.split("<tbody>")[1])
        self.get("/buchungen/?monat=alle&sort=tags")
        self.get("/buchungen/?monat=alle&von=2026-10-01&bis=2026-10-31&sort=kategorie")

        # Direkte Bearbeitung in der Tabelle
        gehalt = db.execute("SELECT id FROM buchung WHERE gegenpartei LIKE 'ARBEITGEBER%'").fetchone()["id"]
        kat_sonst = db.execute("SELECT id FROM kategorie WHERE name = 'Sonstiges'").fetchone()["id"]
        self.get("/buchungen/?monat=alle")

        def inline(bid, feld, wert, ok=200):
            r = self.c.post(f"/buchungen/{bid}/inline", data=json.dumps({"feld": feld, "wert": wert}),
                            content_type="application/json", headers={"X-CSRF": self._csrf})
            self.assertEqual(r.status_code, ok, r.get_data(as_text=True))
            return r.get_json()
        self.assertEqual(inline(gehalt, "kategorie", str(kat_sonst))["anzeige"], "Sonstiges")
        self.assertEqual(db.execute("SELECT kategorie_id, zuordnung_quelle FROM buchung WHERE id = ?", (gehalt,)).fetchone()[:],
                         (kat_sonst, "manuell"))
        self.assertEqual(inline(gehalt, "tags", "Steuer 2026, Arbeit")["anzeige"], "Arbeit, Steuer 2026")
        pid = db.execute("SELECT id FROM person LIMIT 1").fetchone()["id"]
        self.assertEqual(inline(gehalt, "person", str(pid))["anzeige"], "Benjamin")
        inline(gehalt, "feld_gibt_es_nicht", "x", ok=400)
        markt_split = db.execute("SELECT buchung_id FROM buchung_split LIMIT 1").fetchone()["buchung_id"]
        inline(markt_split, "kategorie", str(kat_sonst), ok=400)  # aufgeteilt -> nur in der Buchung
        r = self.c.post(f"/buchungen/{gehalt}/inline", data=json.dumps({"feld": "tags", "wert": "x"}),
                        content_type="application/json")
        self.assertEqual(r.status_code, 400)  # ohne CSRF-Token
        html = self.get("/buchungen/?monat=alle&sort=tags")
        self.assertIn('data-feld="tags"', html)
        self.assertIn("Arbeit, Steuer 2026", html)
        self.assertIn("STREAMING DIENST", html)

        # Prüf-Modus: Umbuchung mit Gegenkonto, Gegenbuchung folgt später
        offen = db.execute("INSERT INTO buchung (konto_id, buchungsdatum, betrag_cent, gegenpartei, verwendungszweck, "
                           "partner_key, abrechnungsmonat, dedup_hash) VALUES (1, '2026-10-05', -30000, 'Benjamin Muster', "
                           "'Rücklage', 'benjamin muster', '2026-10', 'v03-a')").lastrowid
        db.commit()
        html = self.get("/pruefen/?ansicht=einzeln")
        self.assertIn("Gegenkonto", html)
        self.assertIn('name="tags"', html)
        html = self.post(f"/pruefen/{offen}", {"art": "umbuchung", "gegenkonto": "2", "tags": "Sparen",
                                               "abrechnungsmonat": "2026-10"}, von="/pruefen/")
        self.assertIn("beim nächsten Import des Gegenkontos", html)
        b = db.execute("SELECT ist_umbuchung, umbuchung_konto_id, umbuchung_partner_id FROM buchung WHERE id = ?", (offen,)).fetchone()
        self.assertEqual(tuple(b), (1, 2, None))
        self.assertEqual(db.execute("SELECT t.name FROM buchung_tag bt JOIN tag t ON t.id = bt.tag_id WHERE bt.buchung_id = ?",
                                    (offen,)).fetchone()["name"], "Sparen")
        gegen = db.execute("INSERT INTO buchung (konto_id, buchungsdatum, betrag_cent, gegenpartei, verwendungszweck, "
                           "partner_key, abrechnungsmonat, dedup_hash) VALUES (2, '2026-10-06', 30000, 'Gutschrift', '', "
                           "'gutschrift', '2026-10', 'v03-b')").lastrowid
        db.commit()
        with self.app.app_context():
            from app.db import commit
            umbuchungen.erkenne([gegen])
            commit()
        self.assertEqual(db.execute("SELECT umbuchung_partner_id FROM buchung WHERE id = ?", (offen,)).fetchone()[0], gegen)
        self.assertIn("Umbuchung mit Tagesgeld", self.get(f"/buchungen/{offen}"))

        # Prüf-Modus als Tabelle: Massenbearbeitung
        a = db.execute("INSERT INTO buchung (konto_id, buchungsdatum, betrag_cent, gegenpartei, verwendungszweck, partner_key, "
                       "abrechnungsmonat, dedup_hash) VALUES (1, '2026-10-07', -1200, 'KIOSK', '', 'kiosk', '2026-10', 'v03-c')").lastrowid
        c2 = db.execute("INSERT INTO buchung (konto_id, buchungsdatum, betrag_cent, gegenpartei, verwendungszweck, partner_key, "
                        "abrechnungsmonat, dedup_hash) VALUES (1, '2026-10-08', -900, 'KIOSK 2', '', 'kiosk', '2026-10', 'v03-d')").lastrowid
        db.commit()
        html = self.get("/pruefen/?ansicht=tabelle")
        self.assertIn("Für ausgewählte Zeilen setzen", html)
        self.assertIn(f'name="kat_{a}"', html)
        html = self.post("/pruefen/tabelle", {"ids": [str(a), str(c2)], f"kat_{a}": str(kat_lebensmittel), f"tags_{a}": "Kiosk",
                                              f"person_{a}": "", f"gegen_{a}": "", f"kat_{c2}": "", f"gegen_{c2}": "extern"},
                         von="/pruefen/")
        self.assertIn("1 zugeordnet", html)
        self.assertEqual(db.execute("SELECT kategorie_id, geprueft FROM buchung WHERE id = ?", (a,)).fetchone()[:], (kat_lebensmittel, 1))
        self.assertEqual(db.execute("SELECT ist_umbuchung, umbuchung_konto_id FROM buchung WHERE id = ?", (c2,)).fetchone()[:], (1, None))
        self.get("/pruefen/?ansicht=einzeln")
        for x in ("v03-a", "v03-b", "v03-c", "v03-d"):
            db.execute("DELETE FROM buchung WHERE dedup_hash = ?", (x,))
        db.commit()

    def _v031(self, db):
        """0.3.1: Umbuchung ins Barkonto legt die Gegenbuchung dort automatisch an (Prüf-Modus und Regel)."""
        from app.services import importer, statistik, zuordnung
        self.post("/konten/neu", {"name": "Bargeld", "typ": "bargeld", "startsaldo": "0", "sichtbarkeit": "alle", "aktiv": "1"})
        bar = db.execute("SELECT id FROM konto WHERE typ = 'bargeld'").fetchone()["id"]
        ab = db.execute("INSERT INTO buchung (konto_id, buchungsdatum, betrag_cent, gegenpartei, verwendungszweck, partner_key, "
                        "abrechnungsmonat, dedup_hash) VALUES (1, '2026-10-09', -20000, 'GELDAUTOMAT SPARKASSE', 'Auszahlung', "
                        "'geldautomat sparkasse', '2026-10', 'v031-a')").lastrowid
        db.commit()
        html = self.post(f"/pruefen/{ab}", {"art": "umbuchung", "gegenkonto": str(bar), "abrechnungsmonat": "2026-10"},
                         von="/pruefen/?ansicht=einzeln")
        self.assertIn("Gegenbuchung im Barkonto wurde automatisch angelegt", html)
        g = db.execute("SELECT * FROM buchung WHERE konto_id = ?", (bar,)).fetchone()
        self.assertEqual((g["betrag_cent"], g["ist_umbuchung"], g["auto_gegenbuchung"], g["umbuchung_partner_id"]),
                         (20000, 1, 1, ab))
        self.assertEqual(db.execute("SELECT umbuchung_partner_id FROM buchung WHERE id = ?", (ab,)).fetchone()[0], g["id"])
        with self.app.app_context():
            self.assertEqual(importer.kontostand(bar), 20000)
            vorher = statistik.monatswerte([1, 2, bar], "2026-10")
        self.assertIn("Automatisch angelegte Gegenbuchung", self.get(f"/buchungen/{g['id']}"))
        # Lösen entfernt die automatisch angelegte Gegenbuchung wieder
        self.post(f"/buchungen/{ab}", {"aktion": "umbuchung_loesen"}, von=f"/buchungen/{ab}")
        self.assertIsNone(db.execute("SELECT 1 FROM buchung WHERE konto_id = ?", (bar,)).fetchone())
        self.assertEqual(db.execute("SELECT ist_umbuchung FROM buchung WHERE id = ?", (ab,)).fetchone()[0], 0)

        # Regel: Geldautomat -> Umbuchung mit Barkonto (künftige Abhebungen ganz ohne Prüf-Modus)
        self.post("/regeln/neu", {"name": "Geldautomat", "feld0": "gegenpartei", "op0": "enthaelt", "wert0": "geldautomat",
                                  "als_umbuchung": "1", "umbuchung_konto_id": str(bar), "aktion": "speichern", "aktiv": "1"})
        self.assertIn("als Umbuchung mit Bargeld", self.get("/regeln/"))
        with self.app.app_context():
            from app.db import commit
            zuordnung.ordne_zu([ab])
            commit()
            self.assertEqual(importer.kontostand(bar), 20000)
            nachher = statistik.monatswerte([1, 2, bar], "2026-10")
        self.assertEqual((vorher["einnahmen"], vorher["ausgaben"]), (nachher["einnahmen"], nachher["ausgaben"]))
        self.assertEqual(db.execute("SELECT zuordnung_quelle FROM buchung WHERE konto_id = ?", (bar,)).fetchone()[0], "umbuchung")
        # Import-artige Löschung räumt mit auf
        self.post(f"/buchungen/{ab}", {"aktion": "umbuchung_loesen"}, von=f"/buchungen/{ab}")
        db.execute("DELETE FROM regel WHERE name = 'Geldautomat'")
        db.execute("DELETE FROM buchung WHERE dedup_hash = 'v031-a'")
        db.commit()

        # 0.3.2: dieselbe Umbuchung auch auf der Detailseite, direkt in der Tabelle und als Sammelaktion
        import json

        def neue(hash_, betrag=-5000):
            i = db.execute("INSERT INTO buchung (konto_id, buchungsdatum, betrag_cent, gegenpartei, verwendungszweck, partner_key, "
                           "abrechnungsmonat, dedup_hash) VALUES (1, '2026-10-09', ?, 'GA AUSZAHLUNG', '', 'ga auszahlung', "
                           "'2026-10', ?)", (betrag, hash_)).lastrowid
            db.commit()
            return i

        def gegen(bid):
            return db.execute("SELECT g.konto_id, g.betrag_cent, g.auto_gegenbuchung FROM buchung b "
                              "JOIN buchung g ON g.id = b.umbuchung_partner_id WHERE b.id = ?", (bid,)).fetchone()

        d1 = neue("v032-a")
        html = self.get(f"/buchungen/{d1}")
        self.assertIn('name="gegenkonto"', html)
        self.assertIn("Gegenbuchung wird automatisch angelegt", html)
        html = self.post(f"/buchungen/{d1}", {"art": "umbuchung", "gegenkonto": str(bar), "abrechnungsmonat": "2026-10",
                                              "tags": "", "notiz": ""}, von=f"/buchungen/{d1}")
        self.assertIn("automatisch angelegt", html)
        self.assertEqual(tuple(gegen(d1)), (bar, 5000, 1))
        # ohne JavaScript: Kategorie „Umbuchung“ gewählt reicht ebenfalls
        d2 = neue("v032-b", -7000)
        uk = db.execute("SELECT id FROM kategorie WHERE art = 'umbuchung'").fetchone()["id"]
        self.post(f"/buchungen/{d2}", {"kategorie_id": str(uk), "gegenkonto": str(bar), "abrechnungsmonat": "2026-10"},
                  von=f"/buchungen/{d2}")
        self.assertEqual(tuple(gegen(d2)), (bar, 7000, 1))

        # direkt in der Tabelle
        d3 = neue("v032-c", -3000)
        self.get("/buchungen/?monat=alle")
        r = self.c.post(f"/buchungen/{d3}/inline", data=json.dumps({"feld": "kategorie", "wert": str(uk)}),
                        content_type="application/json", headers={"X-CSRF": self._csrf})
        self.assertEqual(r.status_code, 409)
        self.assertTrue(r.get_json()["frage_gegenkonto"])
        r = self.c.post(f"/buchungen/{d3}/inline", data=json.dumps({"feld": "umbuchung", "wert": str(bar)}),
                        content_type="application/json", headers={"X-CSRF": self._csrf})
        self.assertEqual(r.get_json()["ergebnis"], "angelegt")
        self.assertEqual(tuple(gegen(d3)), (bar, 3000, 1))
        html = self.get("/buchungen/?monat=alle")
        self.assertIn('id="gegenkonto-vorlage"', html)

        # Sammelaktion
        d4, d5 = neue("v032-d", -1000), neue("v032-e", -2000)
        html = self.post("/buchungen/sammel", {"ids": [str(d4), str(d5)], "aktion": "als_umbuchung", "gegenkonto": str(bar),
                                               "zurueck": "/buchungen/?monat=alle"}, von="/buchungen/?monat=alle")
        self.assertIn("2 Buchungen als Umbuchung markiert (2 im Barkonto gegengebucht)", html)
        self.assertEqual(tuple(gegen(d5)), (bar, 2000, 1))
        with self.app.app_context():
            self.assertEqual(importer.kontostand(bar), 5000 + 7000 + 3000 + 1000 + 2000)
        # Regel aus einer Umbuchung übernimmt Gegenkonto
        html = self.get(f"/regeln/neu?von_buchung={d1}")
        self.assertIn(f'<option value="{bar}" selected', html)
        for i in (d1, d2, d3, d4, d5):
            self.post(f"/buchungen/{i}", {"aktion": "umbuchung_loesen"}, von=f"/buchungen/{i}")
        for i in (d1, d2, d3, d4, d5):
            db.execute("DELETE FROM buchung WHERE id = ?", (i,))
        db.commit()
        self.assertIsNone(db.execute("SELECT 1 FROM buchung WHERE konto_id = ?", (bar,)).fetchone())

    def test_csrf(self):
        r = self.c.post("/login", data={"name": "x", "passwort": "y"})
        self.assertEqual(r.status_code, 400)


class Https(unittest.TestCase):
    """Zertifikate erzeugen, HTTPS-Server mit HTTP-Umleitung, PWA-Dateien."""

    def test_tls_und_pwa(self):
        import http.client
        import ssl
        import threading
        from app import config, tls
        from app.server import HttpsServer
        config.ensure_dirs()
        z = tls.bereite_vor()
        self.assertEqual(z["quelle"], "eigenes")
        alt = tls.SRV_CRT.stat().st_mtime_ns
        tls.bereite_vor()
        self.assertEqual(tls.SRV_CRT.stat().st_mtime_ns, alt, "Zertifikat darf nicht unnötig neu erzeugt werden")
        info = tls.ca_info()
        self.assertIn("localhost", info["server_namen"])
        self.assertIn("127.0.0.1", info["server_namen"])

        app = create_app({"TESTING": True})
        server = HttpsServer("127.0.0.1", 0, app, tls.ssl_kontext(z))
        port = server.server_address[1]
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        try:
            ctx = ssl.create_default_context(cafile=str(tls.CA_CRT))
            for host in ("localhost", "127.0.0.1"):
                con = http.client.HTTPSConnection(host, port, context=ctx, timeout=10)
                con.request("GET", "/manifest.webmanifest")
                r = con.getresponse()
                self.assertEqual(r.status, 200)
                self.assertIn("application/manifest+json", r.getheader("Content-Type"))
                import json
                m = json.loads(r.read())
                self.assertEqual(m["display"], "standalone")
                self.assertEqual({i["sizes"] for i in m["icons"]}, {"192x192", "512x512"})
                con.close()
            con = http.client.HTTPSConnection("localhost", port, context=ctx, timeout=10)
            con.request("GET", "/sw.js")
            r = con.getresponse()
            self.assertEqual(r.status, 200)
            self.assertIn("javascript", r.getheader("Content-Type"))
            self.assertIn(b"addEventListener(\"fetch\"", r.read())
            con.close()
            # unverschlüsselte Anfrage auf demselben Port -> Umleitung auf https
            con = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            con.request("GET", "/buchungen/?monat=alle")
            r = con.getresponse()
            self.assertEqual(r.status, 301)
            self.assertEqual(r.getheader("Location"), f"https://127.0.0.1:{port}/buchungen/?monat=alle")
            con.close()
        finally:
            server.shutdown()
            server.server_close()
        c = app.test_client()
        r = c.get("/zertifikat/finanz-tracker-ca.crt")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data[:1], b"\x30")  # DER
        self.assertEqual(c.get("/offline").status_code, 200)
        for name in ("icon-192.png", "icon-512.png", "maskable-512.png"):
            self.assertEqual(c.get(f"/static/icons/{name}").status_code, 200)


if __name__ == "__main__":
    unittest.main()
