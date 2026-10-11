"""Aufteilung einer Buchung auf mehrere Kategorien/Personen (z. B. Supermarkt: Lebensmittel + Haushalt)."""
from ..db import q, exe


class SplitFehler(ValueError):
    pass


def lade(buchung_id) -> list:
    return q("""SELECT s.*, k.pfad AS kat_pfad, p.name AS person_name FROM buchung_split s
                LEFT JOIN kategorie k ON k.id = s.kategorie_id LEFT JOIN person p ON p.id = s.person_id
                WHERE s.buchung_id = ? ORDER BY s.id""", (buchung_id,))


def speichere(b, zeilen: list[dict]) -> None:
    """zeilen: [{betrag_cent, kategorie_id, person_id, notiz}]. Leere Liste hebt die Aufteilung auf.

    Beträge werden mit dem Vorzeichen der Buchung gespeichert; die Summe muss genau dem Buchungsbetrag entsprechen.
    Die Hauptkategorie der Buchung wird auf die Kategorie des größten Teils gesetzt (für Listen und Filter).
    """
    zeilen = [z for z in zeilen if z.get("betrag_cent")]
    exe("DELETE FROM buchung_split WHERE buchung_id = ?", (b["id"],))
    if not zeilen:
        return
    if len(zeilen) < 2:
        raise SplitFehler("Für eine Aufteilung mindestens zwei Teile mit Betrag angeben.")
    vz = -1 if b["betrag_cent"] < 0 else 1
    for z in zeilen:
        z["betrag_cent"] = vz * abs(int(z["betrag_cent"]))
        if not z.get("kategorie_id"):
            raise SplitFehler("Jeder Teil braucht eine Kategorie.")
    summe = sum(z["betrag_cent"] for z in zeilen)
    if summe != b["betrag_cent"]:
        diff = abs(b["betrag_cent"] - summe)
        raise SplitFehler(f"Die Teile ergeben {abs(summe) / 100:.2f} €, die Buchung hat {abs(b['betrag_cent']) / 100:.2f} € "
                          f"(Differenz {diff / 100:.2f} €).".replace(".", ","))
    for z in zeilen:
        exe("INSERT INTO buchung_split (buchung_id, betrag_cent, kategorie_id, person_id, notiz) VALUES (?,?,?,?,?)",
            (b["id"], z["betrag_cent"], z["kategorie_id"], z.get("person_id"), z.get("notiz") or None))
    groesster = max(zeilen, key=lambda z: abs(z["betrag_cent"]))
    exe("UPDATE buchung SET kategorie_id = ?, zuordnung_quelle = 'manuell', geprueft = 1, regel_id = NULL "
        "WHERE id = ?", (groesster["kategorie_id"], b["id"]))


def hat_split(buchung_ids: list[int]) -> set[int]:
    if not buchung_ids:
        return set()
    marks = ",".join("?" * len(buchung_ids))
    return {r["buchung_id"] for r in q(f"SELECT DISTINCT buchung_id FROM buchung_split WHERE buchung_id IN ({marks})",
                                       buchung_ids)}
