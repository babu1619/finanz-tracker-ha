"""Budgets je Kategorie (inkl. Unterkategorien), optional je Person, monatlich oder jährlich.

- Übertrag: nicht verbrauchtes (oder überzogenes) Monatsbudget wird innerhalb des Kalenderjahrs mitgenommen.
- Hierarchie: Ein Budget auf „Mobilität“ umfasst auch „Mobilität › Autos“. In der Gesamtsumme zählen nur Budgets
  ohne budgetierte Oberkategorie, damit nichts doppelt gezählt wird.
- Prognose (laufender Monat): bisherige Ausgaben + noch ausstehende wiederkehrende Zahlungen + hochgerechneter
  variabler Anteil.
"""
import calendar
import math
from datetime import date

from ..db import q
from ..util import aktueller_monat, monat_plus
from . import kategorien, statistik, vertraege as vertraege_mod


def _monate(von: str, bis: str) -> list[str]:
    erg, m = [], von
    while m <= bis and len(erg) < 240:
        erg.append(m)
        m = monat_plus(m, 1)
    return erg


def vorschlag(reihe: dict, monat: str, n=6) -> int:
    """Durchschnitt der letzten n Monate, auf 10 € aufgerundet."""
    werte = [reihe.get(monat_plus(monat, -i), 0) for i in range(1, n + 1)]
    schnitt = max(0, sum(werte) / n)
    return int(math.ceil(schnitt / 1000.0) * 1000)


def uebersicht(konten: list[int], monat: str, heute: date | None = None) -> dict:
    heute = heute or date.today()
    alle = kategorien.alle()
    nach_id = {k["id"]: k for k in alle}
    reihenfolge = {k["id"]: i for i, k in enumerate(alle)}
    budgets = q("SELECT b.*, p.name AS person_name FROM budget b LEFT JOIN person p ON p.id = b.person_id "
                "WHERE b.aktiv = 1 AND b.gueltig_ab <= ?", (monat,))
    jahr_start = monat[:4] + "-01"
    von = min([jahr_start, monat_plus(monat, -6)] + [b["gueltig_ab"] for b in budgets if b["gueltig_ab"] >= jahr_start])
    reihen = {None: statistik.reihe_je_kategorie(konten, von, monat)}
    for pid in {b["person_id"] for b in budgets if b["person_id"]}:
        reihen[pid] = statistik.reihe_je_kategorie(konten, von, monat, pid)

    laufend = monat == aktueller_monat()
    # bestätigte Verträge plus erkannte regelmäßige Zahlungen
    vlist = (vertraege_mod.liste(konten, heute) +
             [dict(v, art=None, ausgeblieben=False) for v in vertraege_mod.erkenne(konten, heute)]) if laufend else []
    offen_fix = vertraege_mod.erwartet_im_monat(vlist, monat, heute) if laufend else []
    fix_keys = {v["partner_key"] for v in vlist if v.get("partner_key")} or {""}
    vertrag_ids = {v["id"] for v in vlist if v.get("id")} or {0}
    fix_bezahlt = {}
    if laufend and konten and vlist:
        marks, vmarks, kmarks = ",".join("?" * len(fix_keys)), ",".join("?" * len(vertrag_ids)), ",".join("?" * len(konten))
        for r in q(f"""SELECT p.kategorie_id, -SUM(p.betrag_monat) AS s FROM posten_monat p JOIN buchung b ON b.id = p.buchung_id
                       WHERE p.monat = ? AND p.konto_id IN ({kmarks}) AND p.ist_umbuchung = 0
                         AND (b.partner_key IN ({marks}) OR b.vertrag_id IN ({vmarks}))
                       GROUP BY p.kategorie_id""", [monat] + list(konten) + list(fix_keys) + list(vertrag_ids)):
            fix_bezahlt[r["kategorie_id"]] = r["s"]
    tage_monat = calendar.monthrange(int(monat[:4]), int(monat[5:]))[1]
    faktor = tage_monat / max(heute.day, 1) if laufend else 1

    budgetiert = {b["kategorie_id"] for b in budgets}
    zeilen = []
    for b in budgets:
        kid = b["kategorie_id"]
        if kid not in nach_id:
            continue
        reihe = reihen[b["person_id"]].get(kid, {})
        teilbaum = set(kategorien_teilbaum(alle, kid))
        if b["rhythmus"] == "jahr":
            start = max(jahr_start, b["gueltig_ab"])
            ist = sum(reihe.get(m, 0) for m in _monate(start, monat))
            soll = b["betrag_cent"]
            anteil_zeit = int(monat[5:]) / 12
            uebertrag = 0
        else:
            ist = reihe.get(monat, 0)
            uebertrag = 0
            if b["uebertrag"]:
                start = max(jahr_start, b["gueltig_ab"])
                for m in _monate(start, monat_plus(monat, -1)):
                    uebertrag += b["betrag_cent"] - reihe.get(m, 0)
            soll = b["betrag_cent"] + uebertrag
            anteil_zeit = (heute.day / tage_monat) if laufend else 1
        prognose = None
        if laufend:
            fix_offen = sum(v["betrag"] for v in offen_fix if v["kategorie_id"] in teilbaum)
            fix_ist = sum(fix_bezahlt.get(k, 0) for k in teilbaum) if not b["person_id"] else 0
            variabel = max(0, ist - fix_ist)
            if b["rhythmus"] == "monat":
                prognose = ist + fix_offen + round(variabel * (faktor - 1))
            else:
                monate_rest = 12 - int(monat[5:])
                schnitt = ist / max(int(monat[5:]), 1)
                prognose = ist + round(schnitt * monate_rest)
        quote = ist / soll if soll > 0 else (1.5 if ist > 0 else 0)
        if quote > 1:
            status = "ueber"
        elif quote * 100 >= b["warnschwelle"] or (prognose is not None and prognose > soll):
            status = "warn"
        else:
            status = "ok"
        k = nach_id[kid]
        oben = k["parent_id"]
        hat_oberbudget = False
        while oben:
            if oben in budgetiert:
                hat_oberbudget = True
                break
            oben = nach_id[oben]["parent_id"] if oben in nach_id else None
        zeilen.append({"b": b, "k": k, "ist": ist, "soll": soll, "basis": b["betrag_cent"], "uebertrag": uebertrag,
                       "quote": quote, "prognose": prognose, "status": status, "anteil_zeit": anteil_zeit,
                       "rest": soll - ist, "unterbudget": hat_oberbudget,
                       "vorschlag": vorschlag(reihen[b["person_id"]].get(kid, {}), monat)})
    zeilen.sort(key=lambda z: (reihenfolge.get(z["k"]["id"], 0), z["b"]["person_id"] or 0))
    oben_z = [z for z in zeilen if not z["unterbudget"] and z["b"]["rhythmus"] == "monat"]
    summe = {"soll": sum(z["soll"] for z in oben_z), "ist": sum(z["ist"] for z in oben_z),
             "prognose": sum((z["prognose"] if z["prognose"] is not None else z["ist"]) for z in oben_z)}
    return {"zeilen": zeilen, "summe": summe, "offen_fix": offen_fix, "laufend": laufend,
            "anteil_zeit": (heute.day / tage_monat) if laufend else 1}


def kategorien_teilbaum(alle, kid) -> list[int]:
    kinder: dict = {}
    for k in alle:
        kinder.setdefault(k["parent_id"], []).append(k["id"])
    erg, stapel = [], [kid]
    while stapel:
        x = stapel.pop()
        erg.append(x)
        stapel.extend(kinder.get(x, []))
    return erg


def vorschlaege_ohne_budget(konten: list[int], monat: str) -> list[dict]:
    """Oberste Ausgabenkategorien ohne Budget mit Durchschnitt der letzten 6 Monate."""
    alle = kategorien.alle()
    reihe = statistik.reihe_je_kategorie(konten, monat_plus(monat, -6), monat_plus(monat, -1))
    vorhanden = {r["kategorie_id"] for r in q("SELECT kategorie_id FROM budget WHERE aktiv = 1 AND person_id IS NULL")}
    erg = []
    for k in alle:
        if k["ebene"] > 1 or k["wirksame_art"] != "ausgabe" or k["id"] in vorhanden:
            continue
        v = vorschlag(reihe.get(k["id"], {}), monat)
        if v >= 2000:
            erg.append({"k": k, "vorschlag": v})
    return erg
