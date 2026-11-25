"""Buchungen löschen (0.9.0).

Gelöscht wird jede Art von Buchung. Importierte Buchungen hinterlassen einen Eintrag in buchung_geloescht,
damit sie beim nächsten Import derselben Datei nicht wieder angelegt werden. Automatisch angelegte
Gegenbuchungen (Bargeld, Depot, Darlehen) verschwinden mit; bei einer verknüpften Umbuchung bleibt die
andere Seite als Buchung erhalten.
"""
from ..db import q, q1, exe


def _importiert(b) -> bool:
    h = b["dedup_hash"] or ""
    return not (b["manuell_erfasst"] or b["auto_gegenbuchung"] or h.startswith(("manuell:", "gegen:")))


def _weg(bid: int):
    exe("UPDATE buchung SET umbuchung_partner_id = NULL WHERE umbuchung_partner_id = ?", (bid,))
    exe("DELETE FROM ruecklage_bewegung WHERE buchung_id = ?", (bid,))
    exe("DELETE FROM buchung WHERE id = ?", (bid,))


def loesche(ids: list[int], benutzer_id: int | None) -> dict:
    """Löscht die Buchungen; Rückgabe: Anzahl gelöscht, davon importiert, mitgelöschte Gegenbuchungen."""
    erg = {"geloescht": 0, "importiert": 0, "gegenbuchungen": 0}
    erledigt: set[int] = set()
    for bid in ids:
        if bid in erledigt:
            continue
        b = q1("SELECT * FROM buchung WHERE id = ?", (bid,))
        if not b:
            continue
        # automatisch erzeugte Gegenbuchungen dieser Buchung
        gegen = {r["id"] for r in q("SELECT id FROM buchung WHERE dedup_hash = ? AND auto_gegenbuchung = 1",
                                    (f"gegen:{bid}",))}
        if b["umbuchung_partner_id"]:
            p = q1("SELECT id, auto_gegenbuchung FROM buchung WHERE id = ?", (b["umbuchung_partner_id"],))
            if p and p["auto_gegenbuchung"] and not b["auto_gegenbuchung"]:
                gegen.add(p["id"])
        for gid in gegen - erledigt - {bid}:
            _weg(gid)
            erledigt.add(gid)
            erg["gegenbuchungen"] += 1
        if _importiert(b):
            exe("""INSERT OR IGNORE INTO buchung_geloescht (konto_id, dedup_hash, buchungsdatum, betrag_cent, gegenpartei,
                   benutzer_id) VALUES (?,?,?,?,?,?)""",
                (b["konto_id"], b["dedup_hash"], b["buchungsdatum"], b["betrag_cent"], b["gegenpartei"], benutzer_id))
            erg["importiert"] += 1
        _weg(bid)
        erledigt.add(bid)
        erg["geloescht"] += 1
    return erg


def geloeschte_hashes(konto_id: int) -> set[str]:
    return {r["dedup_hash"] for r in q("SELECT dedup_hash FROM buchung_geloescht WHERE konto_id = ?", (konto_id,))}


def liste(konten: list[int]) -> list:
    if not konten:
        return []
    return q(f"""SELECT g.*, k.name AS konto_name FROM buchung_geloescht g JOIN konto k ON k.id = g.konto_id
                 WHERE g.konto_id IN ({','.join('?' * len(konten))}) ORDER BY g.geloescht_am DESC, g.id DESC LIMIT 200""",
             list(konten))


def zulassen(gid: int, konten: list[int]) -> bool:
    """Entfernt die Sperre: die Buchung wird beim nächsten Import wieder angelegt."""
    r = q1("SELECT konto_id FROM buchung_geloescht WHERE id = ?", (gid,))
    if not r or r["konto_id"] not in konten:
        return False
    exe("DELETE FROM buchung_geloescht WHERE id = ?", (gid,))
    return True
