"""Tags: Querschnitts-Markierungen wie „Urlaub Italien 2026“ oder „Steuer 2026“, unabhängig von der Kategorie."""
from ..db import q, q1, exe


def alle(konten: list[int]) -> list:
    marks = ",".join("?" * len(konten)) or "NULL"
    return q(f"""SELECT t.*, COUNT(b.id) AS anzahl,
                       COALESCE(-SUM(CASE WHEN b.ist_umbuchung = 0 THEN b.betrag_cent END), 0) AS summe
                FROM tag t LEFT JOIN buchung_tag bt ON bt.tag_id = t.id
                LEFT JOIN buchung b ON b.id = bt.buchung_id AND b.konto_id IN ({marks})
                GROUP BY t.id ORDER BY COALESCE(t.start, '9999') DESC, t.name""", konten)


def fuer_buchungen(ids: list[int]) -> dict[int, list]:
    if not ids:
        return {}
    marks = ",".join("?" * len(ids))
    erg: dict = {}
    for r in q(f"SELECT bt.buchung_id, t.id, t.name, t.farbe FROM buchung_tag bt JOIN tag t ON t.id = bt.tag_id "
               f"WHERE bt.buchung_id IN ({marks}) ORDER BY t.name", ids):
        erg.setdefault(r["buchung_id"], []).append(r)
    return erg


def finde_oder_lege_an(name: str) -> int | None:
    name = (name or "").strip()
    if not name:
        return None
    r = q1("SELECT id FROM tag WHERE name = ? COLLATE NOCASE", (name,))
    return r["id"] if r else exe("INSERT INTO tag (name) VALUES (?)", (name[:60],))


def setze(buchung_id: int, namen: list[str]) -> None:
    """Ersetzt die Tags einer Buchung durch die angegebenen (fehlende werden angelegt)."""
    exe("DELETE FROM buchung_tag WHERE buchung_id = ?", (buchung_id,))
    for n in namen:
        tid = finde_oder_lege_an(n)
        if tid:
            exe("INSERT OR IGNORE INTO buchung_tag (buchung_id, tag_id) VALUES (?, ?)", (buchung_id, tid))


def hinzufuegen(buchung_ids: list[int], tag_id: int) -> int:
    n = 0
    for bid in buchung_ids:
        n += exe_count("INSERT OR IGNORE INTO buchung_tag (buchung_id, tag_id) VALUES (?, ?)", (bid, tag_id))
    return n


def exe_count(sql, params) -> int:
    from ..db import get_db
    return get_db().execute(sql, params).rowcount


def kandidaten(tag, konten: list[int]) -> list:
    """Buchungen im Zeitraum des Tags, die den Tag noch nicht haben (Vorschlag zum Markieren)."""
    if not tag["start"] or not konten:
        return []
    marks = ",".join("?" * len(konten))
    return q(f"""SELECT b.*, k.name AS konto_name, kat.pfad AS kat_pfad FROM buchung b
                 JOIN konto k ON k.id = b.konto_id LEFT JOIN kategorie kat ON kat.id = b.kategorie_id
                 WHERE b.konto_id IN ({marks}) AND b.ist_umbuchung = 0 AND b.betrag_cent < 0
                   AND b.buchungsdatum BETWEEN ? AND ?
                   AND NOT EXISTS (SELECT 1 FROM buchung_tag bt WHERE bt.buchung_id = b.id AND bt.tag_id = ?)
                 ORDER BY b.buchungsdatum LIMIT 300""",
             list(konten) + [tag["start"], tag["ende"] or tag["start"], tag["id"]])
