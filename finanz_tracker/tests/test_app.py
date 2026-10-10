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

    def test_csrf(self):
        r = self.c.post("/login", data={"name": "x", "passwort": "y"})
        self.assertEqual(r.status_code, 400)


if __name__ == "__main__":
    unittest.main()
