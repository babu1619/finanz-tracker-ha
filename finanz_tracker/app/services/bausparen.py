"""Bausparverträge: Guthaben-Prognose, Zuteilung, Bauspardarlehen und Ablösung eines Darlehens.

Vereinfachtes Modell (ausreichend für die Planung, nicht für den Cent):
  * Ausgangspunkt ist der jüngste eingetragene Guthabenstand (Jahreskontoauszug), sonst 0 € zu Vertragsbeginn.
  * Danach monatlich die Sparrate; Guthabenzinsen werden monatlich anteilig berechnet und zum Jahresende gutgeschrieben.
  * Zuteilungsreif, sobald das Mindestsparguthaben (z. B. 40 % der Bausparsumme) erreicht ist – frühestens zum
    gewünschten Zuteilungstermin, falls angegeben. Die Bewertungszahl der Bausparkasse wird nicht nachgebildet.
  * Bauspardarlehen = Bausparsumme − Guthaben, Monatsrate = Tilgungsbeitrag (‰ der Bausparsumme), Zins monatlich.
"""
from datetime import date

from ..db import q, q1
from ..util import aktueller_monat, monat_plus, monat_von
from . import darlehen as dl

MAX_MONATE = 600


def alle(nur_aktive=False, darlehen_konto_id=None) -> list:
    sql = """SELECT v.*, k.name AS darlehen_name, i.name AS immobilie_name FROM bausparvertrag v
             LEFT JOIN konto k ON k.id = v.darlehen_konto_id LEFT JOIN immobilie i ON i.id = v.immobilie_id WHERE 1=1"""
    params: list = []
    if nur_aktive:
        sql += " AND v.aktiv = 1"
    if darlehen_konto_id:
        sql += " AND v.darlehen_konto_id = ?"
        params.append(darlehen_konto_id)
    return q(sql + " ORDER BY v.aktiv DESC, v.name", params)


def lade(vid: int):
    return q1("""SELECT v.*, k.name AS darlehen_name, i.name AS immobilie_name FROM bausparvertrag v
                 LEFT JOIN konto k ON k.id = v.darlehen_konto_id LEFT JOIN immobilie i ON i.id = v.immobilie_id
                 WHERE v.id = ?""", (vid,))


def staende(vid: int) -> list:
    return q("SELECT * FROM bauspar_stand WHERE vertrag_id = ? ORDER BY datum DESC, id DESC", (vid,))


def _monate(von: str, bis: str) -> int:
    j1, m1 = (int(x) for x in von.split("-"))
    j2, m2 = (int(x) for x in bis.split("-"))
    return (j2 - j1) * 12 + (m2 - m1)


def sparplan(v, bis: str | None = None) -> list[dict]:
    """Monatliche Guthabenentwicklung ab dem jüngsten Stand: [{monat, einzahlung, zins, guthaben}]."""
    letzter = q1("SELECT * FROM bauspar_stand WHERE vertrag_id = ? ORDER BY datum DESC, id DESC LIMIT 1", (v["id"],))
    if letzter:
        monat = monat_plus(monat_von(letzter["datum"]), 1)
        guthaben = letzter["guthaben_cent"]
    else:
        monat = v["beginn"]
        guthaben = 0
    bis = bis or monat_plus(aktueller_monat(), 12 * 40)
    zins_m = (v["guthabenzins"] or 0) / 100 / 12
    offen_zins = 0.0
    zeilen = []
    for _ in range(MAX_MONATE):
        if monat > bis:
            break
        offen_zins += guthaben * zins_m
        guthaben += v["sparrate_cent"]
        zins = 0
        if monat.endswith("-12"):
            zins = round(offen_zins)
            guthaben += zins
            offen_zins = 0.0
        zeilen.append({"monat": monat, "einzahlung": v["sparrate_cent"], "zins": zins, "guthaben": guthaben})
        monat = monat_plus(monat, 1)
    return zeilen


def guthaben_im(v, monat: str) -> int:
    """Guthaben am Ende des Monats laut Stand bzw. Prognose."""
    letzter = q1("SELECT * FROM bauspar_stand WHERE vertrag_id = ? ORDER BY datum DESC, id DESC LIMIT 1", (v["id"],))
    if letzter and monat_von(letzter["datum"]) >= monat:
        return letzter["guthaben_cent"]
    if not letzter and monat < v["beginn"]:
        return 0
    plan = sparplan(v, monat)
    return plan[-1]["guthaben"] if plan else (letzter["guthaben_cent"] if letzter else 0)


def darlehensphase(v, darlehen_cent: int, start: str) -> list[dict]:
    """Tilgung des Bauspardarlehens ab Zuteilung (erste Rate im Folgemonat)."""
    rate = round(v["bausparsumme_cent"] * (v["tilgungsbeitrag_promille"] or 0) / 1000)
    zins_m = (v["darlehenszins"] or 0) / 100 / 12
    rest = darlehen_cent
    monat = monat_plus(start, 1)
    zeilen = []
    if rate <= 0:
        return zeilen
    for _ in range(MAX_MONATE):
        if rest <= 0:
            break
        zins = round(rest * zins_m)
        tilgung = min(rate - zins, rest)
        if tilgung <= 0:
            zeilen.append({"monat": monat, "zins": zins, "tilgung": 0, "rest": rest, "fehler": True})
            break
        rest -= tilgung
        zeilen.append({"monat": monat, "zins": zins, "tilgung": tilgung, "rest": rest})
        monat = monat_plus(monat, 1)
    return zeilen


def kennzahlen(v, heute: date | None = None) -> dict:
    heute = heute or date.today()
    monat = monat_von(heute)
    letzter = q1("SELECT * FROM bauspar_stand WHERE vertrag_id = ? ORDER BY datum DESC, id DESC LIMIT 1", (v["id"],))
    plan = sparplan(v)
    aktuell = guthaben_im(v, monat_plus(monat, -1))
    mindest = round(v["bausparsumme_cent"] * (v["mindestguthaben_prozent"] or 0) / 100)
    frueheste = v["zuteilung_gewuenscht"] or v["beginn"]
    # Darlehen, das abgelöst werden soll: Zuteilung zum Ende der Zinsbindung anstreben
    d = dl.lade(v["darlehen_konto_id"]) if v["darlehen_konto_id"] else None
    if d and d["zinsbindung_bis"] and not v["zuteilung_gewuenscht"]:
        frueheste = d["zinsbindung_bis"]
    zuteilung = next((z for z in plan if z["guthaben"] >= mindest and z["monat"] >= frueheste), None)
    erg = {
        "v": v, "letzter_stand": letzter, "guthaben": aktuell, "mindest": mindest,
        "anteil": min(1.0, aktuell / mindest) if mindest else 1.0,
        "zuteilung": zuteilung, "plan": plan, "rate": round(v["bausparsumme_cent"] * (v["tilgungsbeitrag_promille"] or 0) / 1000),
        "darlehen": d, "abloesung": None, "darlehensphase": [], "bauspardarlehen": None, "ende": None,
        "einzahlungen_jahr": v["sparrate_cent"] * 12,
    }
    if zuteilung:
        bd = max(0, v["bausparsumme_cent"] - zuteilung["guthaben"])
        erg["bauspardarlehen"] = bd
        erg["darlehensphase"] = darlehensphase(v, bd, zuteilung["monat"])
        erg["ende"] = erg["darlehensphase"][-1]["monat"] if erg["darlehensphase"] else zuteilung["monat"]
        erg["zinsen_darlehen"] = sum(z["zins"] for z in erg["darlehensphase"])
        erg["fehler"] = any(z.get("fehler") for z in erg["darlehensphase"])
    if d:
        k = dl.kennzahlen(d)
        stichtag = d["zinsbindung_bis"] or (zuteilung["monat"] if zuteilung else None)
        if stichtag:
            rest = dl.restschuld(k["plan"], stichtag, d)
            verfuegbar = v["bausparsumme_cent"] if zuteilung and zuteilung["monat"] <= stichtag else guthaben_im(v, stichtag)
            zugeteilt = bool(zuteilung and zuteilung["monat"] <= stichtag)
            noetig = None
            if not zugeteilt:
                # grob: Sparrate, mit der das Mindestguthaben bis zum Stichtag erreicht wird (Zinsen vernachlässigt)
                basis = q1("SELECT * FROM bauspar_stand WHERE vertrag_id = ? ORDER BY datum DESC, id DESC LIMIT 1", (v["id"],))
                ab = monat_von(basis["datum"]) if basis else v["beginn"]
                monate = _monate(ab, stichtag)
                fehlt = mindest - (basis["guthaben_cent"] if basis else 0)
                if monate > 0 and fehlt > 0:
                    noetig = -(-fehlt // monate)
            erg["abloesung"] = {"monat": stichtag, "restschuld": rest, "verfuegbar": verfuegbar,
                                "luecke": rest - verfuegbar, "zugeteilt": zugeteilt,
                                "guthaben": guthaben_im(v, stichtag), "noetige_sparrate": noetig}
    # Jahresübersicht: Guthaben je Jahresende bis zur Zuteilung, danach Restschuld des Bauspardarlehens
    jahre: dict = {}
    for z in plan:
        if zuteilung and z["monat"] > zuteilung["monat"]:
            break
        j = jahre.setdefault(z["monat"][:4], {"einzahlung": 0, "zins": 0, "guthaben": 0, "darlehen_rest": None,
                                               "darlehen_zins": 0, "darlehen_tilgung": 0})
        j["einzahlung"] += z["einzahlung"]
        j["zins"] += z["zins"]
        j["guthaben"] = z["guthaben"]
    for z in erg["darlehensphase"]:
        j = jahre.setdefault(z["monat"][:4], {"einzahlung": 0, "zins": 0, "guthaben": 0, "darlehen_rest": None,
                                               "darlehen_zins": 0, "darlehen_tilgung": 0})
        j["darlehen_zins"] += z["zins"]
        j["darlehen_tilgung"] += z["tilgung"]
        j["darlehen_rest"] = z["rest"]
    erg["jahre"] = jahre
    return erg


def summe_guthaben(heute: date | None = None) -> int:
    monat = monat_plus(monat_von(heute or date.today()), -1)
    return sum(guthaben_im(v, monat) for v in alle(nur_aktive=True))
