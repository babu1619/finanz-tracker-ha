"""Depot ohne Kontoauszug: Wert = gebuchtes Kapital (Ein-/Auszahlungen, Gebühren, Erträge) + Rendite von Hand.

Die Rendite wird als Prozent auf das gebuchte Kapital oder als Eurobetrag eingetragen. Maßgeblich ist der jüngste
Eintrag; ältere bleiben als Verlauf erhalten.
"""
from ..db import q, q1
from . import importer


def bewertungen(konto_id) -> list:
    return q("SELECT * FROM depot_bewertung WHERE konto_id = ? ORDER BY datum DESC, id DESC", (konto_id,))


def letzte_bewertung(konto_id):
    return q1("SELECT * FROM depot_bewertung WHERE konto_id = ? ORDER BY datum DESC, id DESC LIMIT 1", (konto_id,))


def rendite_cent(bewertung, kapital: int) -> int:
    if not bewertung:
        return 0
    if bewertung["einheit"] == "betrag":
        return bewertung["wert"]
    return round(kapital * bewertung["wert"] / 10000)


def kennzahlen(konto_id) -> dict:
    k = q1("SELECT startsaldo_cent FROM konto WHERE id = ?", (konto_id,))
    s = q1("""SELECT COALESCE(SUM(CASE WHEN ist_umbuchung = 1 AND betrag_cent > 0 THEN betrag_cent END), 0) AS ein,
                     COALESCE(SUM(CASE WHEN ist_umbuchung = 1 AND betrag_cent < 0 THEN betrag_cent END), 0) AS aus,
                     COALESCE(SUM(CASE WHEN ist_umbuchung = 0 AND betrag_cent < 0 THEN betrag_cent END), 0) AS kosten,
                     COALESCE(SUM(CASE WHEN ist_umbuchung = 0 AND betrag_cent > 0 THEN betrag_cent END), 0) AS ertraege
              FROM buchung WHERE konto_id = ?""", (konto_id,))
    kapital = importer.kontostand(konto_id)
    b = letzte_bewertung(konto_id)
    rendite = rendite_cent(b, kapital)
    return {"start": k["startsaldo_cent"] if k else 0, "einzahlungen": s["ein"], "auszahlungen": -s["aus"],
            "kosten": -s["kosten"], "ertraege": s["ertraege"], "kapital": kapital, "bewertung": b,
            "rendite": rendite, "rendite_prozent": (rendite / kapital * 100) if kapital else None,
            "wert": kapital + rendite}


def wert(konto_id) -> int:
    """Aktueller Depotwert für Dashboard und Kontenübersicht."""
    kapital = importer.kontostand(konto_id)
    return kapital + rendite_cent(letzte_bewertung(konto_id), kapital)
