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


def _anschluss(d, anschluss):
    """Konditionen nach Ende der Zinsbindung: übergeben, gespeichert oder (ohne Angabe) wie bisher."""
    if anschluss == "keine" or not d["zinsbindung_bis"]:
        return None
    if isinstance(anschluss, dict):
        return anschluss
    keys = d.keys() if hasattr(d, "keys") else d
    if "anschluss_sollzins" in keys and d["anschluss_sollzins"] is not None and d["anschluss_rate_cent"]:
        return {"zins": d["anschluss_sollzins"], "rate": d["anschluss_rate_cent"]}
    return None


def plan(d, ereig=None, extra: dict | None = None, ab_heute=False, anschluss="gespeichert") -> list[dict]:
    """Monatlicher Tilgungsplan bis zur vollständigen Rückzahlung.

    extra: zusätzliche (simulierte) Sondertilgungen {monat: cent}.
    anschluss: Konditionen ab dem Monat nach Ende der Zinsbindung – {"zins": %, "rate": cent}, "gespeichert"
    (Planannahme aus den Konditionen, sonst gleicher Zins und gleiche Rate) oder "keine".
    Rückgabe je Monat: monat, zins, tilgung, sonder, rest (Restschuld nach der Rate), rate.
    """
    ansch = _anschluss(d, anschluss)
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
        neu = bool(ansch and m > d["zinsbindung_bis"])
        zins = round(rest * ((ansch["zins"] / 100 / 12) if neu else zins_m))
        rate = ansch["rate"] if neu else d["rate_cent"]
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
    max_cent = d["sondertilgung_max_cent"] if "sondertilgung_max_cent" in d.keys() else None
    if not d["sondertilgung_prozent"] and not max_cent:
        return {"rahmen": None, "genutzt": 0, "frei": None}
    ereig = ereignisse(d["konto_id"]) if ereig is None else ereig
    rahmen = max_cent or round(d["ursprung_cent"] * d["sondertilgung_prozent"] / 100)
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


def vergleich(darlehen: list, betrag_cent: int, monat: str) -> dict:
    """Wohin mit einer Sondertilgung? Vergleicht die Darlehen fair und hält den Sondertilgungsrahmen ein.

    * Jedes Darlehen wird nur mit dem Betrag simuliert, der im Kalenderjahr noch möglich ist (freier Rahmen) und
      höchstens mit seiner Restschuld.
    * Verglichen wird die Zinsersparnis bis zu einem gemeinsamen Stichtag – dem frühesten Ende einer Zinsbindung
      nach dem Sondertilgungsmonat. Bis dahin sind alle Zinsen vertraglich fest; danach hängt alles von
      Annahmen ab. (Ein Vergleich „bis zur jeweils eigenen Zinsbindung“ würde Darlehen mit langer Zinsbindung
      bevorzugen, nur weil der Zeitraum länger ist.)
    * Zusätzlich eine Empfehlung, wie sich der Betrag auf die Darlehen verteilen lässt, wenn ein Rahmen nicht
      reicht: zuerst das Darlehen mit dem höchsten Zins, dann das nächste.
    """
    jahr = int(monat[:4])
    zb_termine = sorted(d["zinsbindung_bis"] for d in darlehen if d["zinsbindung_bis"] and d["zinsbindung_bis"] >= monat)
    stichtag = zb_termine[0] if zb_termine else None
    zeilen = []
    for d in darlehen:
        ereig = ereignisse(d["konto_id"])
        basis = plan(d, ereig)
        rest = restschuld(basis, monat_plus(monat, -1), d)
        rahmen = sonder_rahmen(d, jahr, ereig)
        moeglich = min(betrag_cent, rest)
        if rahmen["frei"] is not None:
            moeglich = min(moeglich, rahmen["frei"])
        z = {"d": d, "rahmen": rahmen, "rest": rest, "moeglich": max(0, moeglich),
             "gekappt": moeglich < betrag_cent}
        if z["moeglich"] > 0:
            s = simuliere(d, z["moeglich"], monat)
            z["s"] = s
            if stichtag:
                mit = plan(d, ereig, {monat: z["moeglich"]})
                z["ersparnis_stichtag"] = summiere(basis, monat, stichtag)["zins"] - summiere(mit, monat, stichtag)["zins"]
            else:
                z["ersparnis_stichtag"] = s["ersparnis"]
            # Ersparnis je 1.000 € eingesetzt – macht Darlehen mit unterschiedlich freiem Rahmen vergleichbar
            z["je_1000"] = z["ersparnis_stichtag"] * 100000 / z["moeglich"]
        else:
            z["s"] = None
            z["ersparnis_stichtag"] = 0
            z["je_1000"] = 0
        zeilen.append(z)
    zeilen.sort(key=lambda z: (-z["je_1000"], -z["d"]["sollzins"]))

    # Empfehlung: Betrag nach Zinshöhe auf die freien Rahmen verteilen
    offen = betrag_cent
    aufteilung = []
    for z in sorted(zeilen, key=lambda z: (-z["d"]["sollzins"], -z["je_1000"])):
        if offen <= 0 or z["moeglich"] <= 0:
            continue
        teil = min(offen, z["moeglich"])
        ereig = ereignisse(z["d"]["konto_id"])
        basis = plan(z["d"], ereig)
        mit = plan(z["d"], ereig, {monat: teil})
        bis = stichtag or (basis[-1]["monat"] if basis else monat)
        aufteilung.append({"d": z["d"], "betrag": teil,
                           "ersparnis": summiere(basis, monat, bis)["zins"] - summiere(mit, monat, bis)["zins"],
                           "ersparnis_gesamt": sum(x["zins"] for x in basis if x["monat"] >= monat)
                           - sum(x["zins"] for x in mit if x["monat"] >= monat)})
        offen -= teil
    return {"zeilen": zeilen, "stichtag": stichtag, "monat": monat, "betrag": betrag_cent,
            "aufteilung": aufteilung, "nicht_moeglich": max(0, offen),
            "summe_ersparnis": sum(a["ersparnis"] for a in aufteilung)}


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
    if zahlung_buchung_id:
        exe("UPDATE buchung SET darlehen_konto_id = ? WHERE id = ? AND darlehen_konto_id IS NULL",
            (konto_id, zahlung_buchung_id))
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


def zahlungen_zuordnen(buchung_ids: list[int] | None = None, konto_id: int | None = None) -> int:
    """Raten im Zahlkonto (Betrag = Monatsrate) automatisch ihrem Darlehen zuordnen. Gibt die Anzahl zurück."""
    from ..db import exe
    n = 0
    for d in q("SELECT d.*, k.aktiv FROM darlehen d JOIN konto k ON k.id = d.konto_id WHERE d.zahlkonto_id IS NOT NULL"
               + (" AND d.konto_id = ?" if konto_id else ""), (konto_id,) if konto_id else ()):
        sql = ("UPDATE buchung SET darlehen_konto_id = ? WHERE konto_id = ? AND betrag_cent = ? "
               "AND darlehen_konto_id IS NULL AND ist_umbuchung = 0")
        params: list = [d["konto_id"], d["zahlkonto_id"], -d["rate_cent"]]
        if buchung_ids is not None:
            if not buchung_ids:
                return 0
            sql += f" AND id IN ({','.join('?' * len(buchung_ids))})"
            params += list(buchung_ids)
        vorher = q1("SELECT COUNT(*) AS n FROM buchung WHERE darlehen_konto_id = ?", (d["konto_id"],))["n"]
        exe(sql, params)
        n += q1("SELECT COUNT(*) AS n FROM buchung WHERE darlehen_konto_id = ?", (d["konto_id"],))["n"] - vorher
    return n


def zahlungen(konto_id: int, sichtbar: list[int]) -> dict:
    """Dem Darlehen zugeordnete Zahlungen (z. B. Raten vom Girokonto) je Jahr, verglichen mit dem Plan."""
    marks = ",".join("?" * len(sichtbar)) or "NULL"
    rows = q(f"""SELECT b.*, k.name AS konto_name FROM buchung b JOIN konto k ON k.id = b.konto_id
                 WHERE b.darlehen_konto_id = ? AND b.konto_id IN ({marks}) ORDER BY b.buchungsdatum DESC""",
             [konto_id] + list(sichtbar))
    jahre: dict = {}
    for r in rows:
        j = jahre.setdefault(r["buchungsdatum"][:4], {"summe": 0, "anzahl": 0})
        j["summe"] -= r["betrag_cent"]
        j["anzahl"] += 1
    return {"liste": rows[:24], "anzahl": len(rows), "jahre": dict(sorted(jahre.items(), reverse=True)),
            "summe": -sum(r["betrag_cent"] for r in rows)}



def simuliere_anschluss(d, zins: float, rate_cent: int) -> dict:
    """Anschlussfinanzierung: ab Ende der Zinsbindung neue Rate und neuer Sollzins, verglichen mit „weiter wie bisher“."""
    zb = d["zinsbindung_bis"]
    ereig = ereignisse(d["konto_id"])
    bisher = plan(d, ereig, anschluss="keine")
    neu = plan(d, ereig, anschluss={"zins": zins, "rate": rate_cent})
    rest_zb = restschuld(bisher, zb, d)
    zins_m = zins / 100 / 12
    mindest = round(rest_zb * zins_m) + 1
    def nach(zeilen):
        return [z for z in zeilen if z["monat"] > zb]
    n_neu, n_bisher = nach(neu), nach(bisher)
    erg = {
        "zins": zins, "rate": rate_cent, "monat": zb, "rest_zb": rest_zb,
        "ende_neu": neu[-1]["monat"] if neu else None, "ende_bisher": bisher[-1]["monat"] if bisher else None,
        "zinsen_neu": sum(z["zins"] for z in n_neu), "zinsen_bisher": sum(z["zins"] for z in n_bisher),
        "monate_neu": len(n_neu), "monate_bisher": len(n_bisher),
        "anfangstilgung": ((rate_cent * 12 - rest_zb * zins / 100) / rest_zb * 100) if rest_zb else None,
        "mindestrate": mindest, "fehler": next((z["fehler"] for z in neu if z.get("fehler")), None),
        "rest_10": restschuld(neu, monat_plus(zb, 120), d),
    }
    erg["zinsen_differenz"] = erg["zinsen_neu"] - erg["zinsen_bisher"]
    return erg


def restschuld_zu_zinsbindungsenden(darlehen: list, anschluss: dict | None = None,
                                    bauspar_guthaben=None) -> list[dict]:
    """Kumulierte Restschuld aller Darlehen zu jedem Zinsbindungsende (sortiert).

    anschluss: {zinsbindungsende "YYYY-MM": {"zins": %, "rate": cent}} – simulierte Anschlussfinanzierung für die
    Summe, die zu diesem Termin neu zu finanzieren ist. Die Rate wird auf die betroffenen Darlehen im Verhältnis
    ihrer Restschuld verteilt; spätere Zeilen rechnen mit dem Ergebnis weiter.
    bauspar_guthaben: Funktion monat -> Bausparguthaben (Summe) zu diesem Zeitpunkt, für die Netto-Spalte.
    """
    anschluss = anschluss or {}
    termine = sorted({d["zinsbindung_bis"] for d in darlehen if d["zinsbindung_bis"]})
    # Restschuld zum eigenen Zinsbindungsende ist von der Anschlussannahme unabhängig
    rest_zb = {d["konto_id"]: restschuld(plan(d, anschluss="keine"), d["zinsbindung_bis"], d)
               for d in darlehen if d["zinsbindung_bis"]}
    eigene: dict = {}
    for t in termine:
        sim = anschluss.get(t)
        if not sim:
            continue
        betroffen = [d for d in darlehen if d["zinsbindung_bis"] == t]
        summe = sum(rest_zb[d["konto_id"]] for d in betroffen) or 1
        for d in betroffen:
            eigene[d["konto_id"]] = {"zins": sim["zins"], "rate": round(sim["rate"] * rest_zb[d["konto_id"]] / summe)}
    plaene = {d["konto_id"]: plan(d, anschluss=eigene.get(d["konto_id"], "gespeichert")) for d in darlehen}
    erg = []
    for t in termine:
        je = [{"d": d, "rest": restschuld(plaene[d["konto_id"]], t, d), "endet": d["zinsbindung_bis"] == t}
              for d in darlehen]
        zeile = {"monat": t, "je": je, "summe": sum(x["rest"] for x in je),
                 "faellig": sum(x["rest"] for x in je if x["endet"]), "sim": None}
        if bauspar_guthaben:
            zeile["bauspar"] = bauspar_guthaben(t)
            zeile["netto"] = zeile["summe"] - zeile["bauspar"]
        sim = anschluss.get(t)
        if sim:
            betroffen = [x["d"] for x in je if x["endet"]]
            danach = [z for d in betroffen for z in plaene[d["konto_id"]] if z["monat"] > t]
            ende = max((plaene[d["konto_id"]][-1]["monat"] for d in betroffen if plaene[d["konto_id"]]), default=None)
            mindest = round(zeile["faellig"] * sim["zins"] / 100 / 12) + 1
            fehler = sim["rate"] < mindest
            j1, m1 = (int(x) for x in t.split("-"))
            monate = None
            if ende and not fehler:
                j2, m2 = (int(x) for x in ende.split("-"))
                monate = (j2 - j1) * 12 + (m2 - m1)
            zeile["sim"] = {**sim, "ende": None if fehler else ende, "monate": monate,
                            "zinsen": sum(z["zins"] for z in danach), "mindestrate": mindest, "fehler": fehler,
                            "tilgung": ((sim["rate"] * 12 - zeile["faellig"] * sim["zins"] / 100) / zeile["faellig"] * 100)
                            if zeile["faellig"] else None}
        erg.append(zeile)
    return erg
