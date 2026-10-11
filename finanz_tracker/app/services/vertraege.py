"""Erkennung wiederkehrender Zahlungen (Abos, Versicherungen, Fixkosten).

Gruppiert Ausgaben nach Gegenpartei (partner_key) und sucht regelmäßige Abstände: monatlich, vierteljährlich,
halbjährlich, jährlich. Meldet Preisänderungen und ausgebliebene Zahlungen.
"""
from datetime import date, timedelta
from statistics import median

from ..db import q
from ..util import monat_von

RHYTHMEN = [  # (name, Tage, Toleranz, Monate)
    ("monatlich", 30.4, 6, 1),
    ("vierteljährlich", 91.3, 12, 3),
    ("halbjährlich", 182.6, 18, 6),
    ("jährlich", 365.25, 25, 12),
]


def _rhythmus(abstaende):
    if not abstaende:
        return None
    m = median(abstaende)
    for name, tage, tol, monate in RHYTHMEN:
        if abs(m - tage) <= tol:
            passend = sum(1 for a in abstaende if abs(a - tage) <= tol * 1.5)
            if passend / len(abstaende) >= 0.7:
                return name, tage, tol, monate
    return None


def erkenne(konten: list[int], heute: date | None = None) -> list[dict]:
    heute = heute or date.today()
    if not konten:
        return []
    marks = ",".join("?" * len(konten))
    rows = q(f"""SELECT b.id, b.partner_key, b.gegenpartei, b.buchungsdatum, b.betrag_cent, b.kategorie_id, b.konto_id,
                        kat.pfad AS kat_pfad
                 FROM buchung b LEFT JOIN kategorie kat ON kat.id = b.kategorie_id
                 WHERE b.konto_id IN ({marks}) AND b.betrag_cent < 0 AND b.ist_umbuchung = 0 AND b.partner_key != ''
                   AND b.buchungsdatum >= ? ORDER BY b.buchungsdatum""",
             list(konten) + [(heute - timedelta(days=800)).isoformat()])
    markiert = {r["partner_key"]: r for r in q("SELECT * FROM vertrag")}
    gruppen: dict = {}
    for r in rows:
        gruppen.setdefault(r["partner_key"], []).append(r)
    ergebnis = []
    for key, liste in gruppen.items():
        m = markiert.get(key)
        if m and m["art"] == "ignoriert":
            continue
        # mehrere Zahlungen am selben Tag (z. B. zwei Verträge beim selben Versicherer) zusammenfassen
        tage: dict = {}
        for r in liste:
            tage.setdefault(r["buchungsdatum"], []).append(r)
        daten = sorted(tage)
        if len(daten) < 2 and not m:
            continue
        d_objs = [date.fromisoformat(d) for d in daten]
        abstaende = [(b - a).days for a, b in zip(d_objs, d_objs[1:])]
        rh = _rhythmus(abstaende)
        if not rh:
            if not m:
                continue
            rh = ("unregelmäßig", None, None, None)
        name, tage_r, tol, monate = rh
        if not m and monate == 1 and len(daten) < 3:
            continue
        letzte = tage[daten[-1]]
        betrag = -sum(r["betrag_cent"] for r in letzte)
        vorher = -sum(r["betrag_cent"] for r in tage[daten[-2]]) if len(daten) >= 2 else None
        aenderung = None
        if vorher and abs(betrag - vorher) > max(100, vorher * 0.01):
            aenderung = betrag - vorher
        naechste = (d_objs[-1] + timedelta(days=round(tage_r))) if tage_r else None
        ausgeblieben = bool(naechste and heute > naechste + timedelta(days=tol + 3)
                            and (heute - naechste).days < 400)
        kat_zaehler: dict = {}
        for r in liste:
            if r["kategorie_id"]:
                kat_zaehler[(r["kategorie_id"], r["kat_pfad"])] = kat_zaehler.get((r["kategorie_id"], r["kat_pfad"]), 0) + 1
        kat = max(kat_zaehler, key=kat_zaehler.get) if kat_zaehler else (None, None)
        ergebnis.append({
            "partner_key": key, "name": (m["name"] if m and m["name"] else liste[-1]["gegenpartei"]),
            "art": m["art"] if m else None, "rhythmus": name, "monate": monate, "anzahl": len(daten),
            "betrag": betrag, "vorher": vorher, "aenderung": aenderung,
            "monatlich": round(betrag / monate) if monate else None,
            "letzte": daten[-1], "naechste": naechste.isoformat() if naechste else None,
            "ausgeblieben": ausgeblieben, "kategorie_id": kat[0], "kat_pfad": kat[1],
            "konto_id": liste[-1]["konto_id"], "notiz": m["notiz"] if m else None,
        })
    ergebnis.sort(key=lambda v: (v["ausgeblieben"] is False, -(v["monatlich"] or 0)))
    return ergebnis


def erwartet_im_monat(vertraege: list[dict], monat: str, heute: date | None = None) -> list[dict]:
    """Wiederkehrende Zahlungen, die im Monat noch ausstehen (für die Budget-Prognose)."""
    heute = heute or date.today()
    offen = []
    for v in vertraege:
        if not v["naechste"] or v["ausgeblieben"] or v["art"] == "ignoriert":
            continue
        n = date.fromisoformat(v["naechste"])
        if monat_von(n) == monat and n >= heute - timedelta(days=2) and v["letzte"][:7] != monat:
            offen.append(v)
    return offen
