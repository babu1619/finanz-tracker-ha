"""Rücklagen und Sparziele.

Eine Rücklage ist ein virtueller Topf auf einem Trägerkonto (z. B. Tagesgeld): „Auto-Reparatur“, „Urlaub“.
Monatliche Zuführungen werden automatisch gutgeschrieben; Ausgaben, die als „aus Rücklage bezahlt“ markiert
sind, werden entnommen. Mit Zielbetrag und Zieldatum wird die Rücklage zum Sparziel (mit Plan-Prüfung).
Bezug „konto“: Der Stand ist einfach der Kontostand des Trägerkontos (z. B. eigenes Sparkonto für ein Ziel).
"""
from ..db import q, q1, exe
from ..util import aktueller_monat, monat_plus, jetzt
from . import importer


def buche_zufuehrungen(bis_monat: str | None = None) -> int:
    """Trägt fehlende monatliche Zuführungen bis einschließlich bis_monat ein (idempotent)."""
    bis_monat = bis_monat or aktueller_monat()
    n = 0
    for r in q("SELECT * FROM ruecklage WHERE aktiv = 1 AND bezug = 'topf' AND zufuehrung_cent > 0"):
        letzte = q1("SELECT MAX(monat) AS m FROM ruecklage_bewegung WHERE ruecklage_id = ? AND art = 'zufuehrung' "
                    "AND buchung_id IS NULL AND notiz = 'monatlich'", (r["id"],))["m"]
        m = monat_plus(letzte, 1) if letzte else r["start_monat"]
        while m <= bis_monat:
            if r["ziel_cent"] and stand(r) >= r["ziel_cent"]:
                break
            exe("INSERT INTO ruecklage_bewegung (ruecklage_id, datum, monat, betrag_cent, art, notiz) "
                "VALUES (?,?,?,?, 'zufuehrung', 'monatlich')", (r["id"], m + "-01", m, r["zufuehrung_cent"]))
            n += 1
            m = monat_plus(m, 1)
    return n


def stand(r) -> int:
    if r["bezug"] == "konto":
        return importer.kontostand(r["traeger_konto_id"])
    return q1("SELECT COALESCE(SUM(betrag_cent), 0) AS s FROM ruecklage_bewegung WHERE ruecklage_id = ?",
              (r["id"],))["s"]


def entnahme_fuer_buchung(buchung_id: int, ruecklage_id: int | None) -> None:
    """Verknüpft eine Ausgabe mit einer Rücklage (oder löst die Verknüpfung)."""
    exe("DELETE FROM ruecklage_bewegung WHERE buchung_id = ?", (buchung_id,))
    exe("UPDATE buchung SET ruecklage_id = ? WHERE id = ?", (ruecklage_id, buchung_id))
    if ruecklage_id:
        b = q1("SELECT * FROM buchung WHERE id = ?", (buchung_id,))
        r = q1("SELECT * FROM ruecklage WHERE id = ?", (ruecklage_id,))
        if r and r["bezug"] == "topf":
            exe("INSERT INTO ruecklage_bewegung (ruecklage_id, datum, monat, betrag_cent, art, buchung_id, notiz) "
                "VALUES (?,?,?,?, 'entnahme', ?, ?)",
                (ruecklage_id, b["buchungsdatum"], b["abrechnungsmonat"], b["betrag_cent"], buchung_id,
                 (b["gegenpartei"] or "")[:80]))


def monate_zwischen(von: str, bis: str) -> int:
    j1, m1 = (int(x) for x in von.split("-"))
    j2, m2 = (int(x) for x in bis.split("-"))
    return (j2 - j1) * 12 + (m2 - m1)


def auswertung(r, monat: str | None = None) -> dict:
    monat = monat or aktueller_monat()
    s = stand(r)
    erg = {"r": r, "stand": s, "ziel": r["ziel_cent"], "fortschritt": None, "rate_noetig": None,
           "im_plan": None, "erreicht_am": None, "fehlt": None}
    if r["ziel_cent"]:
        erg["fortschritt"] = max(0.0, min(1.0, s / r["ziel_cent"])) if r["ziel_cent"] > 0 else 1.0
        erg["fehlt"] = max(0, r["ziel_cent"] - s)
        if erg["fehlt"] == 0:
            erg["im_plan"] = True
        if r["zieldatum"] and erg["fehlt"] > 0:
            rest = monate_zwischen(monat, r["zieldatum"])
            erg["rate_noetig"] = erg["fehlt"] if rest <= 0 else -(-erg["fehlt"] // rest)
            erg["im_plan"] = rest > 0 and (r["zufuehrung_cent"] or 0) >= erg["rate_noetig"]
        if erg["fehlt"] > 0 and r["zufuehrung_cent"]:
            erg["erreicht_am"] = monat_plus(monat, -(-erg["fehlt"] // r["zufuehrung_cent"]))
    return erg


def uebersicht(konten: list[int]) -> dict:
    buche_zufuehrungen()
    if not konten:
        return {"liste": [], "traeger": []}
    marks = ",".join("?" * len(konten))
    rows = q(f"""SELECT r.*, k.name AS konto_name, kat.pfad AS kat_pfad FROM ruecklage r
                 JOIN konto k ON k.id = r.traeger_konto_id LEFT JOIN kategorie kat ON kat.id = r.kategorie_id
                 WHERE r.traeger_konto_id IN ({marks}) ORDER BY r.aktiv DESC, r.sortierung, r.name""", konten)
    liste = [auswertung(r) for r in rows]
    traeger = {}
    for e in liste:
        if e["r"]["bezug"] != "topf" or not e["r"]["aktiv"]:
            continue
        t = traeger.setdefault(e["r"]["traeger_konto_id"], {"konto_name": e["r"]["konto_name"], "verplant": 0,
                                                             "saldo": importer.kontostand(e["r"]["traeger_konto_id"])})
        t["verplant"] += e["stand"]
    for t in traeger.values():
        t["frei"] = t["saldo"] - t["verplant"]
    return {"liste": liste, "traeger": list(traeger.values())}


def bewegungen(ruecklage_id: int) -> list:
    return q("SELECT * FROM ruecklage_bewegung WHERE ruecklage_id = ? ORDER BY datum DESC, id DESC LIMIT 200",
             (ruecklage_id,))


def korrektur(ruecklage_id: int, betrag_cent: int, notiz: str, art="korrektur") -> None:
    m = aktueller_monat()
    exe("INSERT INTO ruecklage_bewegung (ruecklage_id, datum, monat, betrag_cent, art, notiz) VALUES (?,?,?,?,?,?)",
        (ruecklage_id, jetzt()[:10], m, betrag_cent, art, notiz or None))
