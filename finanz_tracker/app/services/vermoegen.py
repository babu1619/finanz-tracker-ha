"""Nettovermögen über die Zeit, Vermögensaufstellung und Cashflow für das Dashboard (0.8.0).

Monatsendstände je Konto werden aus Startsaldo und Buchungen rekonstruiert. Vereinfachungen:
  * Depot: gebuchtes Kapital zum Monatsende + die bis dahin jüngste Rendite-Eintragung.
  * Krypto: heutige Menge × Kurs zum Monatsende (vor dem ersten bekannten Kurs: erster Kurs).
  * Darlehen ohne importierte Buchungen: Restschuld laut Tilgungsplan.
  * Bausparen: Guthaben laut Stand bzw. Prognose (vor dem jüngsten Stand: dieser Stand).
"""
from datetime import date

from ..db import q, q1
from ..util import aktueller_monat, monat_plus
from . import bausparen as bs, darlehen as dl, depot, kategorien, krypto, statistik

GRUPPEN = {  # Typ -> (Gruppe, Seite)
    "giro": ("Girokonten", "aktiva"), "tagesgeld": ("Tagesgeld", "aktiva"), "bargeld": ("Bargeld", "aktiva"),
    "depot": ("Depots", "aktiva"), "krypto": ("Krypto", "aktiva"), "sonstiges": ("Sonstiges", "aktiva"),
    "bausparen": ("Bausparen", "aktiva"),
    "kreditkarte": ("Kreditkarten", "passiva"), "darlehen": ("Darlehen", "passiva"),
}
GRUPPEN_FARBEN = {
    "Girokonten": "#3B6FB6", "Tagesgeld": "#0F6B5C", "Bargeld": "#8A9A2B", "Depots": "#7A5BA8", "Krypto": "#C98A12",
    "Bausparen": "#2F9C9C", "Sonstiges": "#5E6B66", "Kreditkarten": "#B5475A", "Darlehen": "#A0662E",
}
MAX_MONATE = 120


def _monate(von: str, bis: str) -> list[str]:
    erg, m = [], von
    while m <= bis and len(erg) <= MAX_MONATE * 2:
        erg.append(m)
        m = monat_plus(m, 1)
    return erg


def _monatsende(monat: str) -> str:
    return date.fromordinal(date.fromisoformat(monat_plus(monat, 1) + "-01").toordinal() - 1).isoformat()


def _kumuliert(konto_id: int, start: int, monate: list[str], summen: dict) -> list[int]:
    vorher = q1("SELECT COALESCE(SUM(betrag_cent), 0) AS s FROM buchung WHERE konto_id = ? AND buchungsdatum < ?",
                (konto_id, monate[0] + "-01"))["s"]
    stand, werte = start + vorher, []
    for m in monate:
        stand += summen.get((konto_id, m), 0)
        werte.append(stand)
    return werte


def verlauf_je_konto(sichtbar: list[int], bis: str | None = None) -> dict:
    """{'monate': [...], 'konten': [{id, name, typ, gruppe, seite, werte, link}], ...} – Monatsendstände."""
    bis = bis or aktueller_monat()
    if not sichtbar:
        return {"monate": [bis], "konten": []}
    marks = ",".join("?" * len(sichtbar))
    konten = q(f"SELECT * FROM konto WHERE id IN ({marks}) AND aktiv = 1 ORDER BY sortierung, name", sichtbar)
    erste = q1(f"SELECT MIN(buchungsdatum) AS d FROM buchung WHERE konto_id IN ({marks})", sichtbar)["d"]
    # Verlauf ab der ersten Buchung (Darlehen allein sollen ihn nicht in Jahre ohne Kontodaten verlängern)
    von = max(min(erste[:7] if erste else bis, monat_plus(bis, -11)), monat_plus(bis, -(MAX_MONATE - 1)))
    monate = _monate(von, bis)
    summen = {(r["konto_id"], r["m"]): r["s"] for r in q(
        f"""SELECT konto_id, substr(buchungsdatum, 1, 7) AS m, SUM(betrag_cent) AS s FROM buchung
            WHERE konto_id IN ({marks}) AND buchungsdatum >= ? GROUP BY konto_id, m""", list(sichtbar) + [von + "-01"])}
    enden = [_monatsende(m) for m in monate]
    erg = []
    for k in konten:
        gruppe, seite = GRUPPEN.get(k["typ"], ("Sonstiges", "aktiva"))
        werte = _kumuliert(k["id"], k["startsaldo_cent"] or 0, monate, summen)
        link = None
        if k["typ"] == "depot":
            bew = q("SELECT * FROM depot_bewertung WHERE konto_id = ? ORDER BY datum, id", (k["id"],))
            neu = []
            for kapital, ende in zip(werte, enden):
                letzte = None
                for b in bew:
                    if b["datum"] <= ende:
                        letzte = b
                neu.append(kapital + depot.rendite_cent(letzte, kapital))
            werte = neu
            werte[-1] = depot.wert(k["id"])
        elif k["typ"] == "krypto":
            x = q1("SELECT * FROM krypto WHERE konto_id = ?", (k["id"],))
            if not x or not x["im_vermoegen"]:
                continue
            erster = q1("SELECT * FROM krypto_kurs WHERE coin = ? ORDER BY datum LIMIT 1", (x["coin"],))
            neu = []
            for ende in enden:
                kurs = krypto.kurs_am(x["coin"], ende) or erster
                neu.append(round(x["menge"] * kurs["preis_cent"]) if kurs else 0)
            werte = neu
            werte[-1] = krypto.wert(k["id"])
        elif k["typ"] == "darlehen" and not dl.hat_importierte_buchungen(k["id"]):
            d = dl.lade(k["id"])
            if d:
                zeilen = dl.plan(d, dl.ereignisse(k["id"]))
                werte = [-dl.restschuld(zeilen, m, d) for m in monate]
                werte[-1] = -dl.kennzahlen(d)["restschuld"]
        if k["typ"] == "darlehen":
            link = ("darlehen.detail", {"kid": k["id"]})
        elif k["typ"] == "depot":
            link = ("depot.detail", {"kid": k["id"]})
        elif k["typ"] == "krypto":
            link = ("krypto.index", {})
        else:
            link = ("buchungen.liste", {"konto": k["id"], "monat": "alle"})
        erg.append({"id": k["id"], "name": k["name"], "typ": k["typ"], "gruppe": gruppe, "seite": seite,
                    "werte": werte, "link": link})
    for v in bs.alle(nur_aktive=True):
        werte = [bs.guthaben_im(v, m) if m >= (v["beginn"] or "") else 0 for m in monate]
        erg.append({"id": f"bs{v['id']}", "name": v["name"], "typ": "bausparen", "gruppe": "Bausparen",
                    "seite": "aktiva", "werte": werte, "link": ("darlehen.bausparen_detail", {"vid": v["id"]})})
    return {"monate": monate, "konten": erg}


def nettovermoegen(daten: dict) -> dict:
    """Reihen Vermögen, Schulden und Netto je Monat."""
    n = len(daten["monate"])
    aktiva, passiva = [0] * n, [0] * n
    for k in daten["konten"]:
        for i, w in enumerate(k["werte"]):
            # Kreditkarten mit Guthaben zählen als Vermögen, Girokonten im Minus als Schulden
            if k["seite"] == "passiva" or w < 0:
                passiva[i] += -w if w < 0 else 0
                if w > 0:
                    aktiva[i] += w
            else:
                aktiva[i] += w
    return {"monate": daten["monate"], "aktiva": aktiva, "passiva": passiva,
            "netto": [a - p for a, p in zip(aktiva, passiva)]}


def bilanz(daten: dict, n_spark: int = 12) -> dict:
    """Vermögensaufstellung: je Seite Gruppen mit Konten, Summe, Anteil und 12-Monats-Verlauf."""
    seiten = {"aktiva": {}, "passiva": {}}
    for k in daten["konten"]:
        wert = k["werte"][-1] if k["werte"] else 0
        if wert == 0 and not any(k["werte"][-n_spark:]):
            continue
        seite = k["seite"]
        if seite == "aktiva" and wert < 0:
            seite = "passiva"
        elif seite == "passiva" and wert > 0:
            seite = "aktiva"
        g = seiten[seite].setdefault(k["gruppe"], {"name": k["gruppe"], "konten": [], "summe": 0,
                                                    "farbe": GRUPPEN_FARBEN.get(k["gruppe"], "#5E6B66"),
                                                    "verlauf": [0] * min(n_spark, len(k["werte"]))})
        betrag = abs(wert)
        g["summe"] += betrag
        spark = [abs(w) for w in k["werte"][-n_spark:]]
        g["verlauf"] = [a + b for a, b in zip(g["verlauf"], spark)]
        g["konten"].append({**k, "betrag": betrag, "spark": spark})
    erg = {}
    for seite, gruppen in seiten.items():
        summe = sum(g["summe"] for g in gruppen.values())
        liste = sorted(gruppen.values(), key=lambda g: -g["summe"])
        for g in liste:
            g["anteil"] = g["summe"] / summe if summe else 0
            g["konten"].sort(key=lambda k: -k["betrag"])
            for k in g["konten"]:
                k["anteil"] = k["betrag"] / summe if summe else 0
        erg[seite] = {"summe": summe, "gruppen": liste}
    return erg


def _top_kategorie(nach_id: dict, kid):
    cur = nach_id.get(kid)
    while cur and cur["parent_id"]:
        cur = nach_id.get(cur["parent_id"])
    return cur


def _zweite_ebene(nach_id: dict, kid):
    """Einnahmen liegen meist unter einer Sammelkategorie „Einnahmen“ – dann deren Unterkategorie nehmen."""
    kette, cur = [], nach_id.get(kid)
    while cur:
        kette.append(cur)
        cur = nach_id.get(cur["parent_id"]) if cur["parent_id"] else None
    return kette[-2] if len(kette) >= 2 else None


def cashflow(konten: list[int], von: str, bis: str, person_id=None, max_ziele: int = 8) -> dict:
    """Daten für das Sankey-Diagramm: Einnahmen je oberster Kategorie -> Ausgaben je oberster Kategorie + Gespart."""
    alle = kategorien.alle()
    nach_id = {k["id"]: k for k in alle}
    arten = {k["id"]: k["wirksame_art"] for k in alle}
    ein, aus = {}, {}
    for r in statistik.posten(konten, von, bis, person_id):
        art = statistik.art_von(arten, r["kategorie_id"], r["betrag"])
        if art == "umbuchung":
            continue
        top = _top_kategorie(nach_id, r["kategorie_id"])
        if art == "einnahme":
            top = _zweite_ebene(nach_id, r["kategorie_id"]) or top
        schl = (top["id"], top["name"]) if top else (None, "Ohne Kategorie")
        if art == "einnahme":
            ein[schl] = ein.get(schl, 0) + r["betrag"]
        else:
            aus[schl] = aus.get(schl, 0) - r["betrag"]
    quellen = [{"id": k[0], "name": k[1], "wert": v} for k, v in ein.items() if v > 0]
    ziele = [{"id": k[0], "name": k[1], "wert": v} for k, v in aus.items() if v > 0]
    quellen.sort(key=lambda x: -x["wert"])
    ziele.sort(key=lambda x: -x["wert"])
    if len(quellen) > 6:
        rest = sum(x["wert"] for x in quellen[5:])
        quellen = quellen[:5] + [{"id": "sonstige", "name": "Weitere Einnahmen", "wert": rest}]
    if len(ziele) > max_ziele:
        rest = sum(x["wert"] for x in ziele[max_ziele - 1:])
        ziele = ziele[:max_ziele - 1] + [{"id": "sonstige", "name": "Weitere Ausgaben", "wert": rest}]
    summe_ein = sum(x["wert"] for x in quellen)
    summe_aus = sum(x["wert"] for x in ziele)
    if summe_ein > summe_aus:
        ziele.append({"id": "gespart", "name": "Gespart", "wert": summe_ein - summe_aus})
    elif summe_aus > summe_ein:
        quellen.append({"id": "reserve", "name": "Aus Ersparnissen", "wert": summe_aus - summe_ein})
    return {"quellen": quellen, "ziele": ziele, "einnahmen": summe_ein, "ausgaben": summe_aus,
            "von": von, "bis": bis}
