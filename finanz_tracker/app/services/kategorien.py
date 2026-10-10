"""Kategoriebaum beliebiger Tiefe. Pfad wird gespeichert, damit Teilbäume per Präfix abfragbar sind."""
from ..db import q, q1, exe

TRENNER = " › "

STARTSET = [
    ("Einnahmen", "einnahme", ["Gehalt", "Kindergeld", "Erstattungen", "Sonstige Einnahmen"]),
    ("Wohnen", "ausgabe", ["Miete", "Darlehensrate", "Energie", "Nebenkosten", "Kommunikation"]),
    ("Lebensmittel", "ausgabe", []),
    ("Haushalt", "ausgabe", ["Online-Einkäufe", "Einrichtung"]),
    ("Mobilität", "ausgabe", ["Autos", "ÖPNV", "Fahrrad"]),
    ("Versicherungen", "ausgabe", []),
    ("Kinder", "ausgabe", []),
    ("Gesundheit", "ausgabe", []),
    ("Freizeit", "ausgabe", ["Restaurants", "Streaming", "Urlaub", "Sport"]),
    ("Bankgebühren", "ausgabe", []),
    ("Sonstiges", "ausgabe", []),
    ("Umbuchung", "umbuchung", []),
]


def lege_startset_an():
    if q1("SELECT 1 FROM kategorie LIMIT 1"):
        return
    for i, (name, art, kinder) in enumerate(STARTSET):
        pid = anlegen(name, None, art, sortierung=i)
        for j, k in enumerate(kinder):
            anlegen(k, pid, None, sortierung=j)


def anlegen(name, parent_id, art=None, sortierung=0) -> int:
    name = name.strip()
    if parent_id:
        p = q1("SELECT pfad, ebene FROM kategorie WHERE id = ?", (parent_id,))
        pfad, ebene = p["pfad"] + TRENNER + name, p["ebene"] + 1
    else:
        pfad, ebene = name, 0
    return exe("INSERT INTO kategorie (parent_id, name, pfad, ebene, art, sortierung) VALUES (?,?,?,?,?,?)",
               (parent_id, name, pfad, ebene, art, sortierung))


def nachkommen_ids(kat_id) -> list[int]:
    k = q1("SELECT pfad FROM kategorie WHERE id = ?", (kat_id,))
    if not k:
        return []
    rows = q("SELECT id FROM kategorie WHERE pfad = ? OR pfad LIKE ?", (k["pfad"], k["pfad"] + TRENNER + "%"))
    return [r["id"] for r in rows]


def aktualisiere(kat_id, name, parent_id, art):
    """Umbenennen/verschieben inkl. Nachführen aller Unterkategorie-Pfade."""
    if parent_id and int(parent_id) in nachkommen_ids(kat_id):
        raise ValueError("Eine Kategorie kann nicht unter sich selbst oder ihre Unterkategorien verschoben werden.")
    alt = q1("SELECT * FROM kategorie WHERE id = ?", (kat_id,))
    if parent_id:
        p = q1("SELECT pfad, ebene FROM kategorie WHERE id = ?", (parent_id,))
        neu_pfad, neu_ebene = p["pfad"] + TRENNER + name.strip(), p["ebene"] + 1
    else:
        neu_pfad, neu_ebene = name.strip(), 0
    diff = neu_ebene - alt["ebene"]
    for r in q("SELECT id, pfad, ebene FROM kategorie WHERE pfad LIKE ?", (alt["pfad"] + TRENNER + "%",)):
        exe("UPDATE kategorie SET pfad = ?, ebene = ? WHERE id = ?",
            (neu_pfad + r["pfad"][len(alt["pfad"]):], r["ebene"] + diff, r["id"]))
    exe("UPDATE kategorie SET name = ?, parent_id = ?, pfad = ?, ebene = ?, art = ? WHERE id = ?",
        (name.strip(), parent_id or None, neu_pfad, neu_ebene, art or None, kat_id))


def alle() -> list:
    """Alle Kategorien in Baum-Reihenfolge mit wirksamer Art."""
    rows = q("SELECT * FROM kategorie")
    nach_parent: dict = {}
    for r in rows:
        nach_parent.setdefault(r["parent_id"], []).append(r)
    ergebnis = []

    def lauf(pid, erbt):
        for r in sorted(nach_parent.get(pid, []), key=lambda x: (x["sortierung"], x["name"].lower())):
            art = r["art"] or erbt or "ausgabe"
            d = dict(r)
            d["wirksame_art"] = art
            d["hat_kinder"] = bool(nach_parent.get(r["id"]))
            ergebnis.append(d)
            lauf(r["id"], art)

    lauf(None, None)
    return ergebnis


def art_map() -> dict[int, str]:
    return {k["id"]: k["wirksame_art"] for k in alle()}


def umbuchung_kategorie_id() -> int | None:
    r = q1("SELECT id FROM kategorie WHERE art = 'umbuchung' AND parent_id IS NULL ORDER BY id LIMIT 1")
    return r["id"] if r else None


def wurzel_id_map() -> dict[int, int]:
    """kategorie_id -> id der obersten Kategorie."""
    rows = {r["id"]: r for r in q("SELECT id, parent_id FROM kategorie")}
    ergebnis = {}
    for kid in rows:
        cur = kid
        seen = 0
        while rows[cur]["parent_id"] and seen < 50:
            cur = rows[cur]["parent_id"]
            seen += 1
        ergebnis[kid] = cur
    return ergebnis
