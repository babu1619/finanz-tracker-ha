"""Annuitätendarlehen: Tilgungsplan, Abgleich mit der Bank, Sondertilgungs-Simulation je Darlehen.

Darlehenskonten zählen nie in Haupt-Dashboard, Summen oder Statistik. Der Plan wird aus den Konditionen
berechnet (Monatsrate, Sollzins, erste Rate). Ein Abgleich (Restschuld laut Bank zu einem Datum) setzt den Plan
ab diesem Monat neu auf; Sondertilgungen werden im jeweiligen Monat abgezogen.
"""
from datetime import date

from ..db import q, q1
from ..util import aktueller_monat, monat_plus, monat_von

MAX_MONATE = 600


def lade(konto_id: int):
    return q1("""SELECT d.*, k.name, k.institut, k.aktiv, i.name AS immobilie_name, z.name AS zahlkonto_name
                 FROM darlehen d JOIN konto k ON k.id = d.konto_id
                 LEFT JOIN immobilie i ON i.id = d.immobilie_id LEFT JOIN konto z ON z.id = d.zahlkonto_id
                 WHERE d.konto_id = ?""", (konto_id,))


def ereignisse(konto_id: int) -> list:
    return q("SELECT * FROM darlehen_ereignis WHERE konto_id = ? ORDER BY datum, id", (konto_id,))


def plan(d, ereig=None, extra: dict | None = None, ab_heute=False) -> list[dict]:
    """Monatlicher Tilgungsplan bis zur vollständigen Rückzahlung.

    extra: zusätzliche (simulierte) Sondertilgungen {monat: cent}.
    Rückgabe je Monat: monat, zins, tilgung, sonder, rest (Restschuld nach der Rate), rate.
    """
    ereig = ereignisse(d["konto_id"]) if ereig is None else ereig
    sonder: dict = {}
    for e in ereig:
        if e["art"] == "sondertilgung":
            m = monat_von(e["datum"])
            sonder[m] = sonder.get(m, 0) + e["betrag_cent"]
    for m, c in (extra or {}).items():
        sonder[m] = sonder.get(m, 0) + c
    abgleiche = {}
    for e in ereig:
        if e["art"] == "abgleich":
            abgleiche[monat_von(e["datum"])] = e["betrag_cent"]  # Restschuld am Ende dieses Monats

    zins_m = d["sollzins"] / 100 / 12
    rest = d["ursprung_cent"]
    m = d["erste_rate"]
    zeilen = []
    for _ in range(MAX_MONATE):
        if rest <= 0:
            break
        zins = round(rest * zins_m)
        rate = d["rate_cent"]
        tilgung = rate - zins
        if tilgung <= 0:  # Rate deckt die Zinsen nicht: Plan endet hier, um Endlosschleifen zu vermeiden
            zeilen.append({"monat": m, "zins": zins, "tilgung": 0, "sonder": 0, "rest": rest, "rate": rate,
                           "fehler": "Die Rate deckt die Zinsen nicht."})
            break
        if tilgung > rest:
            tilgung = rest
            rate = tilgung + zins
        rest -= tilgung
        s = min(sonder.get(m, 0), rest)
        rest -= s
        if m in abgleiche:
            rest = abgleiche[m]
        zeilen.append({"monat": m, "zins": zins, "tilgung": tilgung, "sonder": s, "rest": rest, "rate": rate})
        m = monat_plus(m, 1)
    if ab_heute:
        heute = aktueller_monat()
        zeilen = [z for z in zeilen if z["monat"] >= heute]
    return zeilen


def restschuld(zeilen: list[dict], monat: str, d) -> int:
    """Restschuld am Ende des Monats laut Plan."""
    if monat < d["erste_rate"]:
        return d["ursprung_cent"]
    letzte = d["ursprung_cent"]
    for z in zeilen:
        if z["monat"] > monat:
            break
        letzte = z["rest"]
    return letzte if zeilen and monat <= zeilen[-1]["monat"] else (0 if zeilen else d["ursprung_cent"])


def summiere(zeilen, von: str, bis: str) -> dict:
    t = {"zins": 0, "tilgung": 0, "sonder": 0}
    for z in zeilen:
        if von <= z["monat"] <= bis:
            t["zins"] += z["zins"]
            t["tilgung"] += z["tilgung"]
            t["sonder"] += z["sonder"]
    return t


def sonder_rahmen(d, jahr: int, ereig=None) -> dict:
    """Vertraglicher Sondertilgungsrahmen im Kalenderjahr und bereits genutzter Teil."""
    if not d["sondertilgung_prozent"]:
        return {"rahmen": None, "genutzt": 0, "frei": None}
    ereig = ereignisse(d["konto_id"]) if ereig is None else ereig
    rahmen = round(d["ursprung_cent"] * d["sondertilgung_prozent"] / 100)
    genutzt = sum(e["betrag_cent"] for e in ereig if e["art"] == "sondertilgung" and e["datum"][:4] == str(jahr))
    return {"rahmen": rahmen, "genutzt": genutzt, "frei": max(0, rahmen - genutzt)}


def kennzahlen(d, heute: date | None = None) -> dict:
    heute = heute or date.today()
    monat = monat_von(heute)
    ereig = ereignisse(d["konto_id"])
    zeilen = plan(d, ereig)
    jahr = str(heute.year)
    aktuell = restschuld(zeilen, monat_plus(monat, -1), d)
    ende = zeilen[-1]["monat"] if zeilen else None
    zb = d["zinsbindung_bis"]
    rest_zb = restschuld(zeilen, zb, d) if zb else None
    zinsen_bis_zb = summiere(zeilen, monat, zb)["zins"] if zb else None
    monate_bis_zb = None
    if zb:
        j1, m1 = (int(x) for x in monat.split("-"))
        j2, m2 = (int(x) for x in zb.split("-"))
        monate_bis_zb = (j2 - j1) * 12 + (m2 - m1)
    letzter_abgleich = next((e for e in reversed(ereig) if e["art"] == "abgleich"), None)
    return {
        "d": d, "plan": zeilen, "ereignisse": ereig, "restschuld": aktuell, "ende": ende,
        "jahr": summiere(zeilen, jahr + "-01", jahr + "-12"),
        "gesamt_zins": sum(z["zins"] for z in zeilen if z["monat"] >= monat),
        "rest_zinsbindung": rest_zb, "zinsen_bis_zinsbindung": zinsen_bis_zb, "monate_bis_zinsbindung": monate_bis_zb,
        "zinsbindung_warnung": monate_bis_zb is not None and 0 <= monate_bis_zb <= d["erinnerung_monate"],
        "getilgt_anteil": 1 - aktuell / d["ursprung_cent"] if d["ursprung_cent"] else 0,
        "rahmen": sonder_rahmen(d, heute.year, ereig), "letzter_abgleich": letzter_abgleich,
        "fehler": next((z["fehler"] for z in zeilen if z.get("fehler")), None),
    }


def simuliere(d, betrag_cent: int, monat: str, jaehrlich=False) -> dict:
    """Vergleicht den Plan mit und ohne zusätzliche Sondertilgung(en)."""
    ereig = ereignisse(d["konto_id"])
    basis = plan(d, ereig)
    extra = {}
    if betrag_cent > 0:
        m = monat
        while True:
            extra[m] = extra.get(m, 0) + betrag_cent
            if not jaehrlich:
                break
            m = monat_plus(m, 12)
            if not basis or m > basis[-1]["monat"]:
                break
    mit = plan(d, ereig, extra)
    zb = d["zinsbindung_bis"]
    zins_basis = sum(z["zins"] for z in basis if z["monat"] >= monat)
    zins_mit = sum(z["zins"] for z in mit if z["monat"] >= monat)
    erg = {
        "betrag": betrag_cent, "monat": monat, "jaehrlich": jaehrlich,
        "ende_basis": basis[-1]["monat"] if basis else None, "ende_mit": mit[-1]["monat"] if mit else None,
        "zins_basis": zins_basis, "zins_mit": zins_mit, "ersparnis": zins_basis - zins_mit,
        "eingesetzt": sum(min(c, 10**12) for c in extra.values()),
        "verkuerzung_monate": len(basis) - len(mit),
        "rest_zb_basis": restschuld(basis, zb, d) if zb else None,
        "rest_zb_mit": restschuld(mit, zb, d) if zb else None,
        "zins_zb_basis": summiere(basis, monat, zb)["zins"] if zb else None,
        "zins_zb_mit": summiere(mit, monat, zb)["zins"] if zb else None,
        "rahmen": sonder_rahmen(d, int(monat[:4]), ereig),
    }
    if zb:
        erg["ersparnis_zb"] = erg["zins_zb_basis"] - erg["zins_zb_mit"]
    erg["rendite"] = d["sollzins"]  # Sondertilgung „verzinst“ sich risikofrei mit dem Sollzins
    erg["ueber_rahmen"] = bool(erg["rahmen"]["frei"] is not None and betrag_cent > erg["rahmen"]["frei"])
    return erg


def alle(konten: list[int]) -> list:
    if not konten:
        return []
    marks = ",".join("?" * len(konten))
    return q(f"""SELECT d.*, k.name, k.institut, k.aktiv, i.name AS immobilie_name FROM darlehen d
                 JOIN konto k ON k.id = d.konto_id LEFT JOIN immobilie i ON i.id = d.immobilie_id
                 WHERE d.konto_id IN ({marks}) ORDER BY k.aktiv DESC, k.sortierung, k.name""", konten)


def vergleich(darlehen: list, betrag_cent: int, monat: str) -> list[dict]:
    """Gleiche Sondertilgung in jedes Darlehen: Wo spart sie am meisten (bis Zinsbindungsende)?"""
    erg = []
    for d in darlehen:
        s = simuliere(d, betrag_cent, monat)
        erg.append({"d": d, "s": s})
    erg.sort(key=lambda e: -(e["s"].get("ersparnis_zb") if e["s"].get("ersparnis_zb") is not None else e["s"]["ersparnis"]))
    return erg


def tilgung_im_zeitraum(konten: list[int], von: str, bis: str) -> int:
    """Planmäßige Tilgung + Sondertilgung aller sichtbaren Darlehen (für „Vermögensaufbau“)."""
    summe = 0
    for d in alle(konten):
        t = summiere(plan(d), von, bis)
        summe += t["tilgung"] + t["sonder"]
    return summe


def hat_importierte_buchungen(konto_id: int) -> bool:
    """Kontoauszug des Darlehens importiert? Dann gilt der Kontostand, sonst der Plan."""
    return q1("SELECT 1 FROM buchung WHERE konto_id = ? AND importlauf_id IS NOT NULL LIMIT 1", (konto_id,)) is not None


def erfasse_sondertilgung(konto_id: int, datum: str, betrag_cent: int, notiz=None, buchung_anlegen=True,
                          zahlung_buchung_id=None) -> int:
    """Sondertilgung eintragen: Plan-Ereignis, auf Wunsch Buchung im Darlehenskonto, Zahlung verknüpfen.

    Ohne angegebene Zahlung sucht das Tool im Zahlkonto des Darlehens eine passende Abbuchung (gleicher Betrag,
    ±10 Tage) und verknüpft sie.
    """
    import secrets
    from ..db import exe
    from ..util import partner_key
    d = lade(konto_id)
    if zahlung_buchung_id is None and d and d["zahlkonto_id"]:
        z = q1("""SELECT b.id FROM buchung b WHERE b.konto_id = ? AND b.betrag_cent = ?
                  AND abs(julianday(b.buchungsdatum) - julianday(?)) <= 10
                  AND NOT EXISTS (SELECT 1 FROM darlehen_ereignis e WHERE e.zahlung_buchung_id = b.id)
                  ORDER BY abs(julianday(b.buchungsdatum) - julianday(?)) LIMIT 1""",
               (d["zahlkonto_id"], -betrag_cent, datum, datum))
        zahlung_buchung_id = z["id"] if z else None
    bid = None
    if buchung_anlegen:
        zahl = q1("SELECT k.name FROM buchung b JOIN konto k ON k.id = b.konto_id WHERE b.id = ?",
                  (zahlung_buchung_id,)) if zahlung_buchung_id else None
        bid = exe("""INSERT INTO buchung (konto_id, buchungsdatum, betrag_cent, gegenpartei, verwendungszweck, partner_key,
                     abrechnungsmonat, notiz, dedup_hash, zuordnung_quelle, geprueft, manuell_erfasst)
                     VALUES (?,?,?,?,?,?,?,?,?,'manuell',1,1)""",
                  (konto_id, datum, betrag_cent, "Sondertilgung",
                   f"Sondertilgung aus {zahl['name']}" if zahl else "Sondertilgung (von Hand erfasst)",
                   partner_key("Sondertilgung"), monat_von(datum), notiz, "manuell:" + secrets.token_hex(8)))
    return exe("INSERT INTO darlehen_ereignis (konto_id, datum, art, betrag_cent, notiz, buchung_id, zahlung_buchung_id) "
               "VALUES (?,?,'sondertilgung',?,?,?,?)", (konto_id, datum, betrag_cent, notiz, bid, zahlung_buchung_id))


def loesche_ereignis(konto_id: int, eid: int) -> None:
    from ..db import exe
    e = q1("SELECT * FROM darlehen_ereignis WHERE id = ? AND konto_id = ?", (eid, konto_id))
    if not e:
        return
    if e["buchung_id"]:
        exe("DELETE FROM buchung WHERE id = ? AND manuell_erfasst = 1", (e["buchung_id"],))
    exe("DELETE FROM darlehen_ereignis WHERE id = ?", (eid,))


def sondertilgung_zu_buchung(buchung_id: int):
    return q1("""SELECT e.*, k.name AS darlehen_name FROM darlehen_ereignis e JOIN konto k ON k.id = e.konto_id
                 WHERE e.zahlung_buchung_id = ? OR e.buchung_id = ?""", (buchung_id, buchung_id))
