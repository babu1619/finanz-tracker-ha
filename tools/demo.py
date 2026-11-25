#!/usr/bin/env python3
"""Demo-Server mit erfundenen Beispieldaten für die Sichtprüfung im Browser.

Aufruf (im Repository-Ordner):
    python3 tools/demo.py                    # Port 8099, Daten in einem temporären Ordner
    python3 tools/demo.py --port 8100
    python3 tools/demo.py --ordner /tmp/ft-demo --behalten   # Ordner nach dem Ende nicht löschen
    python3 tools/demo.py --nur-daten --ordner /tmp/ft-demo  # nur Daten anlegen, keinen Server starten
    python3 tools/demo.py --ordner /tmp/ft-demo --neu        # vorhandenen Demo-Ordner leeren und neu anlegen

Ein angegebener Ordner muss leer sein oder aus einem früheren Demo-Lauf stammen (Datei .finanz-demo); sonst bricht
das Skript ab, damit nie ein echter Datenordner überschrieben wird.

Anmeldung: Benutzer „demo“, Passwort „geheim123“. Der Server läuft ohne HTTPS (http://127.0.0.1:PORT).

Alle Namen und Beträge sind erfunden. Die Daten decken die Bereiche ab, die man beim Prüfen der Oberfläche sehen will:
Giro, Tagesgeld, Kreditkarte, Bargeld, Depot, Krypto mit Kursverlauf, ein Darlehen mit Konditionen, ein
Bausparvertrag, Budgets, ein Sparziel, ein Vertrag, Planposten, Tags und einige offene Buchungen für den Prüf-Modus.
Buchungen liegen in den letzten 26 Monaten bis heute; der Zufall ist fest eingestellt, die Daten sind also bei jedem
Start gleich (relativ zum heutigen Datum).

Screenshots, zum Beispiel mit Playwright (in der Cloud-Umgebung vorinstalliert):
    const p = await (await chromium.launch()).newPage({ viewport: { width: 1360, height: 900 }, colorScheme: "dark" });
    await p.goto("http://127.0.0.1:8099/login"); await p.fill("input[name=name]", "demo");
    await p.fill("input[name=passwort]", "geheim123"); await p.click("button[type=submit]");
"""
import argparse
import math
import os
import random
import re
import shutil
import sqlite3
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BENUTZER, PASSWORT = "demo", "geheim123"


def monate_zurueck(heute: date, n: int):
    """Liste (jahr, monat) der letzten n Monate bis einschließlich heute."""
    erg = []
    for i in range(n - 1, -1, -1):
        j, m = heute.year, heute.month - i
        while m <= 0:
            m += 12
            j -= 1
        erg.append((j, m))
    return erg


def daten_anlegen(ordner: Path):
    os.environ["DATA_DIR"] = str(ordner)
    os.environ["HTTPS"] = "0"
    sys.path.insert(0, str(ROOT / "finanz_tracker"))
    from app import create_app
    from app.util import partner_key

    app = create_app()
    c = app.test_client()
    html = c.get("/einrichtung").get_data(as_text=True)
    m = re.search(r'name="csrf" value="([0-9a-f]+)"', html)
    if not m:
        sys.exit("Ersteinrichtung nicht möglich – der Ordner ist schon eingerichtet.")
    c.post("/einrichtung", data={"csrf": m.group(1), "name": BENUTZER, "person": "Benjamin",
                                 "passwort": PASSWORT, "passwort2": PASSWORT, "startset": "1"})

    db = sqlite3.connect(ordner / "finanz.db")
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    kat = {r["pfad"]: r["id"] for r in db.execute("SELECT id, pfad FROM kategorie")}
    if not kat:
        sys.exit("Ersteinrichtung fehlgeschlagen (keine Kategorien angelegt).")

    def k(name):
        for pfad, i in kat.items():
            if pfad.lower().endswith(name.lower()):
                return i
        raise KeyError(name)

    def konto(name, typ, start=0, privat_person=None):
        return db.execute("""INSERT INTO konto (name, typ, startsaldo_cent, import_erinnerung_tage, sichtbarkeit,
                             eigentuemer_person_id) VALUES (?,?,?,?,?,?)""",
                          (name, typ, start, 30, "privat" if privat_person else "alle", privat_person)).lastrowid

    db.execute("INSERT INTO person (name, farbe) VALUES ('Alex', '#3B6FB6'), ('Kind', '#C98A12')")
    giro = konto("Musterbank Giro", "giro", 250000)
    giro2 = konto("Sparkasse Giro (Beispiel)", "giro", 80000)
    tg = konto("Tagesgeld (Beispiel)", "tagesgeld", 1200000)
    kk = konto("Kreditkarte (Beispiel)", "kreditkarte", 0)
    bar = konto("Bargeld", "bargeld", 15000)
    dep = konto("ETF-Depot (Beispiel)", "depot", 1500000)
    dar = konto("Baufinanzierung (Beispiel)", "darlehen", 0)
    btc = konto("Bitcoin Wallet", "krypto", 0)
    eth = konto("Ethereum Ledger", "krypto", 0)

    heute = date.today()
    random.seed(4)
    zaehler = [0]
    tag_urlaub = db.execute("INSERT INTO tag (name, farbe) VALUES ('Urlaub', '#2F9C9C')").lastrowid

    def buchung(kid, d: date, betrag, partei, kategorie_id, geprueft=1, umbuchung=False, **extra):
        if d > heute:
            return None
        zaehler[0] += 1
        felder = {"konto_id": kid, "buchungsdatum": d.isoformat(), "betrag_cent": betrag, "gegenpartei": partei,
                  "verwendungszweck": partei, "partner_key": partner_key(partei), "abrechnungsmonat": d.strftime("%Y-%m"),
                  "kategorie_id": kategorie_id, "dedup_hash": f"demo:{zaehler[0]}", "geprueft": geprueft,
                  "zuordnung_quelle": "manuell" if kategorie_id else None, "ist_umbuchung": 1 if umbuchung else 0, **extra}
        return db.execute(f"INSERT INTO buchung ({', '.join(felder)}) VALUES ({', '.join('?' * len(felder))})",
                          list(felder.values())).lastrowid

    def umbuchung(von, nach, d, betrag, text):
        a = buchung(von, d, -betrag, text, k("Umbuchung"), umbuchung=True)
        b = buchung(nach, d, betrag, text, k("Umbuchung"), umbuchung=True)
        if a and b:
            db.execute("UPDATE buchung SET umbuchung_partner_id = ? WHERE id = ?", (b, a))
            db.execute("UPDATE buchung SET umbuchung_partner_id = ? WHERE id = ?", (a, b))

    for j, m in monate_zurueck(heute, 26):
        t = lambda tag: date(j, m, tag)  # noqa: E731
        buchung(giro, t(1), 412000 + random.randint(-2000, 2000), "Arbeitgeber Beispiel GmbH", k("Gehalt"))
        buchung(giro2, t(2), 185000, "Teilzeit Beispiel AG", k("Gehalt"))
        buchung(giro, t(15), 25000, "Familienkasse", k("Kindergeld"))
        buchung(giro, t(3), -135000, "Bank Beispiel Darlehen", k("Darlehensrate"), darlehen_konto_id=dar)
        buchung(giro, t(5), -32000, "Stadtwerke Beispiel", k("Energie"))
        buchung(giro, t(6), -4999, "Telefonanbieter Beispiel", k("Kommunikation"))
        buchung(giro, t(7), -18900, "Versicherung Beispiel", k("Versicherungen"))
        buchung(giro, t(9), -1299, "Streamingdienst Beispiel", k("Streaming"))
        for w in range(4):
            buchung(kk, t(8 + w * 5), -random.randint(6000, 16000), random.choice(["Supermarkt A", "Supermarkt B", "Biomarkt"]),
                    k("Lebensmittel"))
        buchung(kk, t(12), -random.randint(5000, 12000), "Tankstelle Beispiel", k("Autos"))
        buchung(kk, t(19), -random.randint(3000, 14000), "Restaurant Beispiel", k("Restaurants"))
        buchung(kk, t(21), -random.randint(2000, 25000), "Versandhandel Beispiel", k("Online-Einkäufe"))
        buchung(giro2, t(20), -random.randint(2000, 9000), "Kita Beispiel", k("Kinder"))
        buchung(bar, t(16), -random.randint(1000, 6000), "Wochenmarkt", k("Lebensmittel"))
        if m in (7, 8):
            bid = buchung(kk, t(25), -random.randint(80000, 160000), "Ferienwohnung Beispiel", k("Urlaub"))
            if bid:
                db.execute("INSERT INTO buchung_tag (buchung_id, tag_id) VALUES (?, ?)", (bid, tag_urlaub))
        umbuchung(giro, tg, t(27), 50000, "Übertrag Tagesgeld")
        umbuchung(giro, dep, t(26), 30000, "Sparplan Depot")
        umbuchung(giro, bar, t(10), 20000, "Geldautomat")
        if t(28) <= heute:
            kkm = db.execute("SELECT COALESCE(SUM(betrag_cent), 0) FROM buchung WHERE konto_id = ? AND abrechnungsmonat = ? "
                             "AND ist_umbuchung = 0", (kk, f"{j:04d}-{m:02d}")).fetchone()[0]
            umbuchung(giro, kk, t(28), -kkm, "Kreditkarte Ausgleich")

    # Offene Buchungen für den Prüf-Modus (ohne Kategorie)
    for i, (partei, betrag) in enumerate([("Baumarkt Beispiel", -8749), ("Apotheke Beispiel", -2390),
                                          ("Erstattung Beispiel", 4500)]):
        buchung(giro, heute - timedelta(days=2 + i), betrag, partei, None, geprueft=0)

    # Depot: Rendite
    db.execute("INSERT INTO depot_bewertung (konto_id, datum, einheit, wert) VALUES (?,?,?,?)",
               (dep, (heute - timedelta(days=200)).isoformat(), "prozent", 800))
    db.execute("INSERT INTO depot_bewertung (konto_id, datum, einheit, wert) VALUES (?,?,?,?)",
               (dep, heute.isoformat(), "prozent", 1450))

    # Krypto mit Kursverlauf über 400 Tage
    db.execute("INSERT INTO krypto (konto_id, coin, menge, einstand_cent) VALUES (?,?,?,?)", (btc, "bitcoin", 0.12, 600000))
    db.execute("INSERT INTO krypto (konto_id, coin, menge, einstand_cent) VALUES (?,?,?,?)", (eth, "ethereum", 2.5, 500000))
    for t in range(400, -1, -1):
        d = (heute - timedelta(days=t)).isoformat()
        db.execute("INSERT INTO krypto_kurs VALUES (?,?,?)",
                   ("bitcoin", d, int((60000 + 15000 * math.sin(t / 50) + random.randint(-1500, 1500)) * 100)))
        db.execute("INSERT INTO krypto_kurs VALUES (?,?,?)",
                   ("ethereum", d, int((2800 + 600 * math.cos(t / 40) + random.randint(-80, 80)) * 100)))

    # Darlehen mit Konditionen (ohne eigene Buchungen: Restschuld laut Plan) und Immobilie
    imm = db.execute("INSERT INTO immobilie (name, kaufpreis_cent, kaufdatum, wert_cent, wert_datum) VALUES (?,?,?,?,?)",
                     ("Haus (Beispiel)", 42000000, f"{heute.year - 6}-04-01", 52000000, heute.isoformat())).lastrowid
    db.execute("""INSERT INTO darlehen (konto_id, immobilie_id, ursprung_cent, sollzins, rate_cent, erste_rate,
                  zinsbindung_bis, sondertilgung_prozent, zahlkonto_id, erinnerung_monate) VALUES (?,?,?,?,?,?,?,?,?,?)""",
               (dar, imm, 30000000, 1.65, 135000, f"{heute.year - 6}-05", f"{heute.year + 2}-04", 5.0, giro, 24))
    db.execute("""INSERT INTO bausparvertrag (name, institut, bausparsumme_cent, beginn, sparrate_cent, guthabenzins,
                  darlehenszins, tilgungsbeitrag_promille, mindestguthaben_prozent, darlehen_konto_id, immobilie_id, aktiv)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?,1)""",
               ("Bausparen (Beispiel)", "Bausparkasse Beispiel", 10000000, f"{heute.year - 3}-01", 40000, 0.1, 2.35,
                6.0, 40.0, dar, imm))

    # Budgets, Sparziel, Vertrag, Planung
    monat = heute.strftime("%Y-%m")
    for name, betrag in [("Lebensmittel", 50000), ("Restaurants", 10000), ("Online-Einkäufe", 15000)]:
        db.execute("INSERT INTO budget (kategorie_id, betrag_cent, rhythmus, gueltig_ab, uebertrag, warnschwelle) "
                   "VALUES (?,?,?,?,0,90)", (k(name), betrag, "monat", f"{heute.year}-01"))
    db.execute("""INSERT INTO ruecklage (name, traeger_konto_id, bezug, ziel_cent, zufuehrung_cent, zieldatum, start_monat)
                  VALUES (?,?,?,?,?,?,?)""",
               ("Neues Auto (Beispiel)", tg, "topf", 2000000, 30000, f"{heute.year + 2}-06", f"{heute.year - 1}-01"))
    db.execute("""INSERT INTO vertrag (name, art, partner_key, kategorie_id, konto_id, betrag_cent, rhythmus_monate, beginn,
                  laufzeit_ende, verlaengerung_monate, kuendigungsfrist, kuendigungsfrist_einheit, aktiv)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1)""",
               ("Streamingdienst Beispiel", "abo", partner_key("Streamingdienst Beispiel"), k("Streaming"), giro, 1299, 1,
                f"{heute.year - 2}-01-01", (heute + timedelta(days=20)).isoformat(), 12, 14, "tage"))
    db.execute("UPDATE buchung SET vertrag_id = (SELECT id FROM vertrag LIMIT 1) WHERE partner_key = ?",
               (partner_key("Streamingdienst Beispiel"),))
    j = heute.year
    for art, name, betrag, mon in [("ausgabe", "Autokauf (Beispiel)", 2200000, f"{j + 1}-04"),
                                   ("ausgabe", "Dachsanierung (Beispiel)", 3500000, f"{j + 2}-06"),
                                   ("einnahme", "Bonus (Beispiel)", 600000, f"{j + 1}-03"),
                                   ("ausgabe", "Küche (Beispiel)", 1500000, f"{j + 1}-10")]:
        db.execute("INSERT INTO plan_posten (art, name, betrag_cent, monat) VALUES (?,?,?,?)", (art, name, betrag, mon))
    db.execute("INSERT OR REPLACE INTO einstellung (schluessel, wert) VALUES ('krypto_letzter_abruf', ?)",
               (f"{heute.isoformat()}T04:00",))
    db.execute("INSERT OR REPLACE INTO einstellung (schluessel, wert) VALUES ('krypto_status', 'Demo-Kurse (erfunden)')")
    db.commit()
    db.close()
    return app


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--port", type=int, default=8099)
    p.add_argument("--ordner", help="Datenordner (Standard: temporär)")
    p.add_argument("--behalten", action="store_true", help="Datenordner nach dem Ende nicht löschen")
    p.add_argument("--nur-daten", action="store_true", help="nur Daten anlegen, keinen Server starten")
    p.add_argument("--neu", action="store_true", help="vorhandenen Demo-Ordner leeren und neu anlegen")
    a = p.parse_args()

    ordner = Path(a.ordner) if a.ordner else Path(tempfile.mkdtemp(prefix="finanz-demo-"))
    if ordner.exists() and any(ordner.iterdir()):
        if not (ordner / ".finanz-demo").exists():
            sys.exit(f"{ordner} ist nicht leer und kein Demo-Ordner – Abbruch, damit keine echten Daten verloren gehen.")
        if not a.neu:
            sys.exit(f"{ordner} enthält schon Demo-Daten. Mit --neu neu anlegen.")
        shutil.rmtree(ordner)
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / ".finanz-demo").write_text("Demo-Daten von tools/demo.py\n")
    try:
        app = daten_anlegen(ordner)
        print(f"Demo-Daten in {ordner}")
        if a.nur_daten:
            return
        app.config["SESSION_COOKIE_SECURE"] = False
        print(f"Demo läuft auf http://127.0.0.1:{a.port}  (Anmeldung: {BENUTZER} / {PASSWORT}, Ende mit Strg+C)")
        app.run(host="127.0.0.1", port=a.port)
    finally:
        if not a.behalten and not a.nur_daten:
            shutil.rmtree(ordner, ignore_errors=True)


if __name__ == "__main__":
    main()
