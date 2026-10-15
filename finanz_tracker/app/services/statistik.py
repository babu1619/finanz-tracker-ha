"""Kennzahlen für Dashboard, Kategorien, Budgets und Auswertung.

Grundlage ist die Sicht 'posten_monat': Aufteilungen (Splits) zählen je Kategorie, verteilte Zahlungen
(z. B. Jahresbeiträge auf 12 Monate) anteilig je Monat. Umbuchungen und Darlehenskonten zählen nie mit.
"""
from ..db import q
from ..util import monat_plus
from . import kategorien


def _in(werte) -> str:
    return ",".join("?" * len(werte)) or "NULL"


def basis_konten(sichtbar: list[int]) -> list[int]:
    """Sichtbare Konten ohne Darlehen."""
    if not sichtbar:
        return []
    return [r["id"] for r in q(f"SELECT id FROM konto WHERE id IN ({_in(sichtbar)}) AND typ != 'darlehen'", sichtbar)]


def posten(konten: list[int], von: str, bis: str | None = None, person_id=None) -> list:
    """Posten je Monat im Zeitraum [von, bis] (Monate 'YYYY-MM'), ohne Umbuchungen."""
    if not konten:
        return []
    bis = bis or von
    # wie Sicht posten_monat, aber vorab auf den Zeitraum eingeschränkt (schneller bei vielen Buchungen)
    sql = (f"""WITH RECURSIVE n(i) AS (SELECT 0 UNION ALL SELECT i + 1 FROM n WHERE i < 59),
               p AS (SELECT * FROM posten WHERE konto_id IN ({_in(konten)}) AND ist_umbuchung = 0
                     AND abrechnungsmonat BETWEEN ? AND ?{' AND person_id = ?' if person_id else ''}),
               pm AS (SELECT p.*, strftime('%Y-%m', date(p.abrechnungsmonat || '-01', '+' || n.i || ' months')) AS monat,
                      CASE WHEN n.i = 0 THEN p.betrag_cent - (p.betrag_cent / p.verteilung_monate) * (p.verteilung_monate - 1)
                           ELSE p.betrag_cent / p.verteilung_monate END AS betrag
                      FROM p JOIN n ON n.i < p.verteilung_monate)
               SELECT monat, betrag, kategorie_id, person_id, buchung_id, konto_id FROM pm WHERE monat BETWEEN ? AND ?""")
    params = list(konten) + [monat_plus(von, -59), bis] + ([person_id] if person_id else []) + [von, bis]
    return q(sql, params)


def art_von(arten: dict, kategorie_id, betrag: int) -> str:
    """'einnahme', 'ausgabe' oder 'umbuchung'. Unkategorisierte Eingänge gelten als Einnahme."""
    art = arten.get(kategorie_id) if kategorie_id else None
    if art in ("einnahme", "umbuchung"):
        return art
    if art is None and betrag > 0:
        return "einnahme"
    return "ausgabe"


def monatswerte(konten: list[int], monat: str, person_id=None, arten=None) -> dict:
    arten = arten or kategorien.art_map()
    ein = aus = 0
    for r in posten(konten, monat, monat, person_id):
        a = art_von(arten, r["kategorie_id"], r["betrag"])
        if a == "einnahme":
            ein += r["betrag"]
        elif a == "ausgabe":
            aus -= r["betrag"]
    saldo = ein - aus
    return {"einnahmen": ein, "ausgaben": aus, "saldo": saldo, "sparquote": (saldo / ein) if ein > 0 else None}


def verlauf(konten: list[int], bis_monat: str, n=12, person_id=None) -> list[dict]:
    arten = kategorien.art_map()
    von = monat_plus(bis_monat, -(n - 1))
    werte = {monat_plus(von, i): {"einnahmen": 0, "ausgaben": 0} for i in range(n)}
    for r in posten(konten, von, bis_monat, person_id):
        a = art_von(arten, r["kategorie_id"], r["betrag"])
        if a == "einnahme":
            werte[r["monat"]]["einnahmen"] += r["betrag"]
        elif a == "ausgabe":
            werte[r["monat"]]["ausgaben"] -= r["betrag"]
    liste = []
    for m, w in werte.items():
        saldo = w["einnahmen"] - w["ausgaben"]
        liste.append({"monat": m, **w, "saldo": saldo,
                      "sparquote": (saldo / w["einnahmen"]) if w["einnahmen"] > 0 else None})
    return liste


def _gruppe_fn(alle, ebene_parent):
    nach_id = {k["id"]: k for k in alle}

    def gruppe(kid):
        if kid is None:
            return None
        cur = nach_id.get(kid)
        kette = []
        while cur:
            kette.append(cur["id"])
            cur = nach_id.get(cur["parent_id"]) if cur["parent_id"] else None
        kette.reverse()
        if ebene_parent is None:
            return kette[0] if kette else None
        if ebene_parent in kette:
            i = kette.index(ebene_parent)
            return kette[i + 1] if i + 1 < len(kette) else ebene_parent
        return "fremd"
    return gruppe


def ausgaben_nach_kategorie(konten: list[int], monat: str, person_id=None, ebene_parent=None, bis=None) -> list[dict]:
    """Ausgaben je oberster Kategorie (oder je direkter Unterkategorie von ebene_parent), inkl. Teilbaum."""
    alle = kategorien.alle()
    nach_id = {k["id"]: k for k in alle}
    arten = {k["id"]: k["wirksame_art"] for k in alle}
    gruppe = _gruppe_fn(alle, ebene_parent)
    summen: dict = {}
    for r in posten(konten, monat, bis or monat, person_id):
        if art_von(arten, r["kategorie_id"], r["betrag"]) != "ausgabe":
            continue
        g = gruppe(r["kategorie_id"])
        if g == "fremd":
            continue
        summen[g] = summen.get(g, 0) - r["betrag"]
    liste = []
    for g, betrag in summen.items():
        if g is None:
            liste.append({"id": None, "name": "Ohne Kategorie", "pfad": "Ohne Kategorie", "betrag": betrag,
                          "hat_kinder": False})
        else:
            k = nach_id[g]
            liste.append({"id": g, "name": k["name"], "pfad": k["pfad"], "betrag": betrag,
                          "hat_kinder": k["hat_kinder"] and g != ebene_parent})
    liste.sort(key=lambda x: -x["betrag"])
    return liste


def summen_je_kategorie(konten: list[int], von: str, bis: str | None = None, person_id=None) -> dict[int, int]:
    """Summe je Kategorie inkl. aller Unterkategorien (Vorzeichen wie gebucht)."""
    nach_id = {k["id"]: k for k in kategorien.alle()}
    gesamt: dict = {}
    for r in posten(konten, von, bis or von, person_id):
        cur = nach_id.get(r["kategorie_id"])
        while cur:
            gesamt[cur["id"]] = gesamt.get(cur["id"], 0) + r["betrag"]
            cur = nach_id.get(cur["parent_id"]) if cur["parent_id"] else None
    return gesamt


def reihe_je_kategorie(konten: list[int], von: str, bis: str, person_id=None) -> dict:
    """{kategorie_id: {monat: summe}} inkl. Teilbaum, Ausgaben positiv. Schlüssel None = ohne Kategorie."""
    alle = kategorien.alle()
    nach_id = {k["id"]: k for k in alle}
    arten = {k["id"]: k["wirksame_art"] for k in alle}
    erg: dict = {}
    for r in posten(konten, von, bis, person_id):
        a = art_von(arten, r["kategorie_id"], r["betrag"])
        if a == "umbuchung":
            continue
        wert = -r["betrag"] if a == "ausgabe" else r["betrag"]
        if r["kategorie_id"] is None:
            ziel = erg.setdefault(None if a == "ausgabe" else "ein", {})
            ziel[r["monat"]] = ziel.get(r["monat"], 0) + wert
            continue
        cur = nach_id.get(r["kategorie_id"])
        while cur:
            ziel = erg.setdefault(cur["id"], {})
            ziel[r["monat"]] = ziel.get(r["monat"], 0) + wert
            cur = nach_id.get(cur["parent_id"]) if cur["parent_id"] else None
    return erg


def ausgaben_je_person(konten: list[int], von: str, bis: str) -> list[dict]:
    arten = kategorien.art_map()
    namen = {r["id"]: r["name"] for r in q("SELECT id, name FROM person")}
    summen: dict = {}
    for r in posten(konten, von, bis):
        if art_von(arten, r["kategorie_id"], r["betrag"]) == "ausgabe":
            summen[r["person_id"]] = summen.get(r["person_id"], 0) - r["betrag"]
    liste = [{"id": pid, "name": namen.get(pid, "Gemeinsam / ohne Person"), "betrag": b} for pid, b in summen.items()]
    liste.sort(key=lambda x: -x["betrag"])
    return liste


def top_gegenparteien(konten: list[int], von: str, bis: str, kat_ids=None, n=10) -> list:
    if not konten:
        return []
    sql = (f"SELECT b.gegenpartei, COUNT(DISTINCT b.id) AS anzahl, -SUM(p.betrag_monat) AS summe "
           f"FROM posten_monat p JOIN buchung b ON b.id = p.buchung_id "
           f"WHERE p.konto_id IN ({_in(konten)}) AND p.monat BETWEEN ? AND ? AND p.ist_umbuchung = 0 "
           f"AND p.betrag_monat < 0")
    params = list(konten) + [von, bis]
    if kat_ids is not None:
        sql += f" AND p.kategorie_id IN ({_in(kat_ids)})"
        params += list(kat_ids)
    sql += f" GROUP BY b.partner_key ORDER BY summe DESC LIMIT {int(n)}"
    return q(sql, params)


def ausgaben_baum(konten: list[int], monat: str, person_id=None) -> list[dict]:
    """Ausgaben je oberster Kategorie mit den direkten Unterkategorien (je inkl. Teilbaum).

    Ein Eintrag hat 'kinder' (absteigend sortiert); Beträge, die direkt auf der obersten Kategorie gebucht
    sind, erscheinen dort als Kind mit 'direkt': True.
    """
    alle = kategorien.alle()
    nach_id = {k["id"]: k for k in alle}
    arten = {k["id"]: k["wirksame_art"] for k in alle}
    oben: dict = {}
    for r in posten(konten, monat, monat, person_id):
        if art_von(arten, r["kategorie_id"], r["betrag"]) != "ausgabe":
            continue
        kette = []
        cur = nach_id.get(r["kategorie_id"])
        while cur:
            kette.append(cur["id"])
            cur = nach_id.get(cur["parent_id"]) if cur["parent_id"] else None
        kette.reverse()
        top = kette[0] if kette else None
        e = oben.setdefault(top, {"betrag": 0, "kinder": {}})
        e["betrag"] -= r["betrag"]
        if top is not None:
            kind = kette[1] if len(kette) > 1 else "direkt"
            e["kinder"][kind] = e["kinder"].get(kind, 0) - r["betrag"]
    liste = []
    for top, e in oben.items():
        if top is None:
            liste.append({"id": None, "name": "Ohne Kategorie", "pfad": "Ohne Kategorie", "betrag": e["betrag"],
                          "kinder": []})
            continue
        k = nach_id[top]
        kinder = []
        for kid, betrag in e["kinder"].items():
            if kid == "direkt":
                kinder.append({"id": top, "name": f"{k['name']} (direkt)", "pfad": k["pfad"], "betrag": betrag,
                               "direkt": True})
            else:
                kinder.append({"id": kid, "name": nach_id[kid]["name"], "pfad": nach_id[kid]["pfad"],
                               "betrag": betrag, "direkt": False})
        kinder.sort(key=lambda x: -x["betrag"])
        # nur aufklappen, wenn es wirklich etwas aufzuteilen gibt
        if len(kinder) == 1 and kinder[0]["direkt"]:
            kinder = []
        liste.append({"id": top, "name": k["name"], "pfad": k["pfad"], "betrag": e["betrag"], "kinder": kinder})
    liste.sort(key=lambda x: -x["betrag"])
    return liste
