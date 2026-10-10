"""Kennzahlen für Dashboard und Kategorien. Umbuchungen und Darlehenskonten zählen nie mit."""
from ..db import q
from ..util import monat_plus
from . import kategorien


def _konten_filter(konten: list[int]):
    if not konten:
        return "1 = 0", []
    return f"b.konto_id IN ({','.join('?' * len(konten))})", list(konten)


def basis_konten(sichtbar: list[int]) -> list[int]:
    """Sichtbare Konten ohne Darlehen."""
    if not sichtbar:
        return []
    marks = ",".join("?" * len(sichtbar))
    return [r["id"] for r in q(f"SELECT id FROM konto WHERE id IN ({marks}) AND typ != 'darlehen'", sichtbar)]


def monatswerte(konten: list[int], monat: str, person_id=None) -> dict:
    """Einnahmen = Kategorie-Art Einnahme (oder unkategorisierte Eingänge); Ausgaben = alles andere."""
    arten = kategorien.art_map()
    where, params = _konten_filter(konten)
    sql = (f"SELECT b.betrag_cent, b.kategorie_id FROM buchung b WHERE {where} AND b.abrechnungsmonat = ? "
           f"AND b.ist_umbuchung = 0")
    params = params + [monat]
    if person_id:
        sql += " AND b.person_id = ?"
        params.append(person_id)
    ein = aus = 0
    for r in q(sql, params):
        art = arten.get(r["kategorie_id"]) if r["kategorie_id"] else None
        if art == "umbuchung":
            continue
        if art == "einnahme" or (art is None and r["betrag_cent"] > 0):
            ein += r["betrag_cent"]
        else:
            aus -= r["betrag_cent"]
    saldo = ein - aus
    quote = (saldo / ein) if ein > 0 else None
    return {"einnahmen": ein, "ausgaben": aus, "saldo": saldo, "sparquote": quote}


def verlauf(konten: list[int], bis_monat: str, n=12, person_id=None) -> list[dict]:
    return [dict(monat=m, **monatswerte(konten, m, person_id))
            for m in (monat_plus(bis_monat, -i) for i in range(n - 1, -1, -1))]


def ausgaben_nach_kategorie(konten: list[int], monat: str, person_id=None, ebene_parent=None) -> list[dict]:
    """Ausgaben je oberster Kategorie (oder je direkter Unterkategorie von ebene_parent), inkl. Teilbaum."""
    alle = kategorien.alle()
    nach_id = {k["id"]: k for k in alle}
    arten = {k["id"]: k["wirksame_art"] for k in alle}
    where, params = _konten_filter(konten)
    sql = (f"SELECT b.betrag_cent, b.kategorie_id FROM buchung b WHERE {where} AND b.abrechnungsmonat = ? "
           f"AND b.ist_umbuchung = 0")
    params = params + [monat]
    if person_id:
        sql += " AND b.person_id = ?"
        params.append(person_id)

    def gruppe(kid):
        if kid is None:
            return None
        cur = nach_id.get(kid)
        kette = []
        while cur:
            kette.append(cur["id"])
            cur = nach_id.get(cur["parent_id"]) if cur["parent_id"] else None
        kette.reverse()  # Wurzel zuerst
        if ebene_parent is None:
            return kette[0]
        if ebene_parent in kette and kette.index(ebene_parent) + 1 < len(kette):
            return kette[kette.index(ebene_parent) + 1]
        if ebene_parent in kette:
            return ebene_parent
        return "fremd"

    summen: dict = {}
    for r in q(sql, params):
        art = arten.get(r["kategorie_id"])
        if art in ("einnahme", "umbuchung"):
            continue
        if art is None and r["betrag_cent"] > 0:
            continue
        g = gruppe(r["kategorie_id"])
        if g == "fremd":
            continue
        summen[g] = summen.get(g, 0) - r["betrag_cent"]
    liste = []
    for g, betrag in summen.items():
        if g is None:
            liste.append({"id": None, "name": "Ohne Kategorie", "betrag": betrag, "hat_kinder": False})
        else:
            k = nach_id[g]
            liste.append({"id": g, "name": k["name"], "pfad": k["pfad"], "betrag": betrag, "hat_kinder": k["hat_kinder"]})
    liste.sort(key=lambda x: -x["betrag"])
    return liste


def summen_je_kategorie(konten: list[int], monat: str) -> dict[int, int]:
    """Ausgaben/Einnahmen je Kategorie inkl. aller Unterkategorien (Vorzeichen wie gebucht)."""
    alle = kategorien.alle()
    nach_id = {k["id"]: k for k in alle}
    where, params = _konten_filter(konten)
    direkt: dict = {}
    for r in q(f"SELECT b.kategorie_id, SUM(b.betrag_cent) AS s FROM buchung b WHERE {where} "
               f"AND b.abrechnungsmonat = ? AND b.kategorie_id IS NOT NULL GROUP BY b.kategorie_id",
               params + [monat]):
        direkt[r["kategorie_id"]] = r["s"]
    gesamt: dict = {}
    for kid, s in direkt.items():
        cur = nach_id.get(kid)
        while cur:
            gesamt[cur["id"]] = gesamt.get(cur["id"], 0) + s
            cur = nach_id.get(cur["parent_id"]) if cur["parent_id"] else None
    return gesamt
