"""Abos, Fixkosten und Verträge.

Ein Vertrag ist ein eigener Datensatz mit Art (Abo, Fixkosten, Vertrag), Zahlungsrhythmus, Laufzeit und
Kündigungsfrist. Buchungen werden ihm zugeordnet – von Hand oder automatisch über die Gegenpartei. Aus den
zugeordneten Buchungen ergeben sich letzte/nächste Zahlung, Preisänderungen und ausgebliebene Zahlungen.

Zusätzlich erkennt das Tool regelmäßige Zahlungen, die noch keinem Vertrag zugeordnet sind (Vorschläge).
"""
import calendar
from datetime import date, timedelta
from statistics import median

from ..db import q, q1, exe
from ..util import monat_von

ARTEN = {"abo": "Abo", "fix": "Fixkosten", "vertrag": "Vertrag"}
RHYTHMUS_NAMEN = {0: "unregelmäßig", 1: "monatlich", 2: "alle 2 Monate", 3: "vierteljährlich", 4: "alle 4 Monate",
                  6: "halbjährlich", 12: "jährlich", 24: "alle 2 Jahre"}
EINHEITEN = {"tage": "Tage", "wochen": "Wochen", "monate": "Monate"}
HINWEIS_TAGE = 31  # so lange vor Ablauf der Kündigungsfrist erscheint der Hinweis

RHYTHMEN = [  # (name, Tage, Toleranz, Monate)
    ("monatlich", 30.4, 6, 1),
    ("vierteljährlich", 91.3, 12, 3),
    ("halbjährlich", 182.6, 18, 6),
    ("jährlich", 365.25, 25, 12),
]


def rhythmus_name(monate) -> str:
    if monate is None:
        return "–"
    return RHYTHMUS_NAMEN.get(monate, f"alle {monate} Monate")


def plus_monate(d: date, n: int) -> date:
    m = d.month - 1 + n
    j = d.year + m // 12
    m = m % 12 + 1
    return date(j, m, min(d.day, calendar.monthrange(j, m)[1]))


# ---------------------------------------------------------------------------------------------------------------
# Laufzeit und Kündigung

def kuendigung(v, heute: date | None = None) -> dict | None:
    """Aktuelles Laufzeitende (mit automatischer Verlängerung) und letzter Kündigungstag."""
    heute = heute or date.today()
    if not v["laufzeit_ende"]:
        return None
    ende = date.fromisoformat(v["laufzeit_ende"])
    verl = v["verlaengerung_monate"] or 0
    frist = v["kuendigungsfrist"] or 0

    def bis(e):
        if v["kuendigungsfrist_einheit"] == "tage":
            return e - timedelta(days=frist)
        if v["kuendigungsfrist_einheit"] == "wochen":
            return e - timedelta(weeks=frist)
        return plus_monate(e, -frist)

    # solange die Kündigungsfrist für diese Laufzeit schon vorbei ist, gilt die nächste Verlängerung
    schritte = 0
    while verl and bis(ende) < heute and schritte < 600:
        ende = plus_monate(ende, verl)
        schritte += 1
    letzter_tag = bis(ende)
    gekuendigt = v["gekuendigt_zum"]
    tage = (letzter_tag - heute).days
    return {
        "ende": ende, "kuendigen_bis": letzter_tag, "tage": tage, "gekuendigt": gekuendigt,
        "abgelaufen": ende < heute and not verl,
        "hinweis": not gekuendigt and 0 <= tage <= HINWEIS_TAGE and v["aktiv"],
        "verpasst": not gekuendigt and tage < 0 and not verl and ende >= heute,
    }


def faellige_kuendigungen(heute: date | None = None) -> list[dict]:
    """Für den Hinweis oben auf jeder Seite: Kündigungsfrist endet in höchstens einem Monat."""
    erg = []
    for v in q("SELECT * FROM vertrag WHERE aktiv = 1 AND laufzeit_ende IS NOT NULL AND gekuendigt_zum IS NULL "
               "AND art != 'ignoriert'"):
        k = kuendigung(v, heute)
        if k and k["hinweis"]:
            erg.append({"v": v, "k": k})
    erg.sort(key=lambda e: e["k"]["kuendigen_bis"])
    return erg


# ---------------------------------------------------------------------------------------------------------------
# Verträge mit ihren Zahlungen

def _zahlungen(vid: int, konten: list[int]):
    marks = ",".join("?" * len(konten)) or "NULL"
    return q(f"""SELECT b.id, b.buchungsdatum, b.betrag_cent, b.gegenpartei, b.konto_id FROM buchung b
                 WHERE b.vertrag_id = ? AND b.konto_id IN ({marks}) ORDER BY b.buchungsdatum""", [vid] + list(konten))


def liste(konten: list[int], heute: date | None = None, mit_inaktiven=False) -> list[dict]:
    """Alle Verträge (ohne ausgeblendete) mit Kennzahlen aus den zugeordneten Buchungen."""
    heute = heute or date.today()
    sql = """SELECT v.*, kat.pfad AS kat_pfad, k.name AS konto_name FROM vertrag v
             LEFT JOIN kategorie kat ON kat.id = v.kategorie_id LEFT JOIN konto k ON k.id = v.konto_id
             WHERE v.art != 'ignoriert'"""
    if not mit_inaktiven:
        sql += " AND v.aktiv = 1"
    erg = []
    for v in q(sql + " ORDER BY v.aktiv DESC, v.name COLLATE NOCASE"):
        zahl = _zahlungen(v["id"], konten)
        # mehrere Zahlungen am selben Tag zusammenfassen
        tage: dict = {}
        for r in zahl:
            tage[r["buchungsdatum"]] = tage.get(r["buchungsdatum"], 0) - r["betrag_cent"]
        daten = sorted(tage)
        betrag = tage[daten[-1]] if daten else (v["betrag_cent"] or 0)
        vorher = tage[daten[-2]] if len(daten) >= 2 else None
        aenderung = None
        if vorher and abs(betrag - vorher) > max(100, vorher * 0.01):
            aenderung = betrag - vorher
        monate = v["rhythmus_monate"]
        naechste = None
        if daten and monate:
            naechste = plus_monate(date.fromisoformat(daten[-1]), monate)
        elif v["beginn"] and monate:
            n = date.fromisoformat(v["beginn"])
            while n < heute:
                n = plus_monate(n, monate)
            naechste = n
        toleranz = 7 if monate == 1 else 20
        ausgeblieben = bool(daten and naechste and heute > naechste + timedelta(days=toleranz)
                            and (heute - naechste).days < 400 and not v["gekuendigt_zum"])
        k = kuendigung(v, heute)
        erg.append({
            "v": v, "id": v["id"], "name": v["name"], "art": v["art"], "rhythmus": rhythmus_name(monate),
            "monate": monate, "anzahl": len(daten), "betrag": betrag, "vorher": vorher, "aenderung": aenderung,
            "monatlich": round(betrag / monate) if monate else None,
            "letzte": daten[-1] if daten else None, "naechste": naechste.isoformat() if naechste else None,
            "ausgeblieben": ausgeblieben, "kategorie_id": v["kategorie_id"], "kat_pfad": v["kat_pfad"],
            "kuendigung": k, "partner_key": v["partner_key"],
        })
    return erg


def erwartet_im_monat(vertraege: list[dict], monat: str, heute: date | None = None) -> list[dict]:
    """Wiederkehrende Zahlungen, die im Monat noch ausstehen (für die Budget-Prognose)."""
    heute = heute or date.today()
    offen = []
    for v in vertraege:
        if not v["naechste"] or v["ausgeblieben"] or v["art"] == "ignoriert":
            continue
        n = date.fromisoformat(v["naechste"])
        if monat_von(n) == monat and n >= heute - timedelta(days=2) and (v["letzte"] or "")[:7] != monat:
            offen.append(v)
    return offen


# ---------------------------------------------------------------------------------------------------------------
# Zuordnung von Buchungen

def zuordnen(buchung_ids: list[int] | None = None) -> int:
    """Buchungen ohne Vertrag über die Gegenpartei einem Vertrag zuordnen. Gibt die Anzahl zurück."""
    sql = """UPDATE buchung SET vertrag_id = (SELECT v.id FROM vertrag v WHERE v.partner_key = buchung.partner_key
                                             AND v.art != 'ignoriert' AND v.aktiv = 1 ORDER BY v.id LIMIT 1)
             WHERE vertrag_id IS NULL AND ist_umbuchung = 0 AND partner_key != ''
               AND EXISTS (SELECT 1 FROM vertrag v WHERE v.partner_key = buchung.partner_key
                           AND v.art != 'ignoriert' AND v.aktiv = 1)"""
    params: list = []
    if buchung_ids is not None:
        if not buchung_ids:
            return 0
        sql += f" AND id IN ({','.join('?' * len(buchung_ids))})"
        params = list(buchung_ids)
    vorher = q1("SELECT COUNT(*) AS n FROM buchung WHERE vertrag_id IS NOT NULL")["n"]
    exe(sql, params)
    return q1("SELECT COUNT(*) AS n FROM buchung WHERE vertrag_id IS NOT NULL")["n"] - vorher


def aus_buchung_anlegen(b, art: str, rhythmus_monate: int, name: str | None = None) -> int:
    """Neuen Vertrag aus einer Buchung anlegen und alle Buchungen derselben Gegenpartei zuordnen."""
    vid = exe("""INSERT INTO vertrag (name, art, partner_key, kategorie_id, konto_id, betrag_cent, rhythmus_monate)
                 VALUES (?,?,?,?,?,?,?)""",
              ((name or b["gegenpartei"] or "Vertrag").strip(), art if art in ARTEN else "vertrag",
               b["partner_key"] or None, b["kategorie_id"], b["konto_id"], abs(b["betrag_cent"]), rhythmus_monate))
    exe("UPDATE buchung SET vertrag_id = ? WHERE id = ?", (vid, b["id"]))
    if b["partner_key"]:
        exe("""UPDATE buchung SET vertrag_id = ? WHERE vertrag_id IS NULL AND partner_key = ? AND betrag_cent < 0
               AND ist_umbuchung = 0""", (vid, b["partner_key"]))
    return vid


# ---------------------------------------------------------------------------------------------------------------
# Vorschläge: regelmäßige Zahlungen ohne Vertrag

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
    """Regelmäßige Ausgaben, die noch keinem Vertrag zugeordnet und nicht ausgeblendet sind."""
    heute = heute or date.today()
    if not konten:
        return []
    marks = ",".join("?" * len(konten))
    rows = q(f"""SELECT b.id, b.partner_key, b.gegenpartei, b.buchungsdatum, b.betrag_cent, b.kategorie_id, b.konto_id,
                        kat.pfad AS kat_pfad
                 FROM buchung b LEFT JOIN kategorie kat ON kat.id = b.kategorie_id
                 WHERE b.konto_id IN ({marks}) AND b.betrag_cent < 0 AND b.ist_umbuchung = 0 AND b.partner_key != ''
                   AND b.vertrag_id IS NULL AND b.darlehen_konto_id IS NULL AND b.buchungsdatum >= ?
                 ORDER BY b.buchungsdatum""",
             list(konten) + [(heute - timedelta(days=800)).isoformat()])
    ausgeblendet = {r["partner_key"] for r in q("SELECT partner_key FROM vertrag WHERE art = 'ignoriert'")}
    gruppen: dict = {}
    for r in rows:
        if r["partner_key"] not in ausgeblendet:
            gruppen.setdefault(r["partner_key"], []).append(r)
    ergebnis = []
    for key, liste_ in gruppen.items():
        tage: dict = {}
        for r in liste_:
            tage.setdefault(r["buchungsdatum"], []).append(r)
        daten = sorted(tage)
        if len(daten) < 2:
            continue
        d_objs = [date.fromisoformat(d) for d in daten]
        rh = _rhythmus([(b - a).days for a, b in zip(d_objs, d_objs[1:])])
        if not rh:
            continue
        name, tage_r, tol, monate = rh
        if monate == 1 and len(daten) < 3:
            continue
        letzte = tage[daten[-1]]
        betrag = -sum(r["betrag_cent"] for r in letzte)
        naechste = d_objs[-1] + timedelta(days=round(tage_r))
        kat_zaehler: dict = {}
        for r in liste_:
            if r["kategorie_id"]:
                kat_zaehler[(r["kategorie_id"], r["kat_pfad"])] = kat_zaehler.get((r["kategorie_id"], r["kat_pfad"]), 0) + 1
        kat = max(kat_zaehler, key=kat_zaehler.get) if kat_zaehler else (None, None)
        ergebnis.append({
            "partner_key": key, "name": liste_[-1]["gegenpartei"], "rhythmus": name, "monate": monate,
            "anzahl": len(daten), "betrag": betrag, "monatlich": round(betrag / monate),
            "letzte": daten[-1], "naechste": naechste.isoformat(), "kategorie_id": kat[0], "kat_pfad": kat[1],
            "konto_id": liste_[-1]["konto_id"], "buchung_id": liste_[-1]["id"],
        })
    ergebnis.sort(key=lambda v: -(v["monatlich"] or 0))
    return ergebnis
