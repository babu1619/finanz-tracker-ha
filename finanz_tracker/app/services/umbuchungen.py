"""Erkennung von Umbuchungen zwischen eigenen Konten.

Paar = Abbuchung auf Konto A und Gutschrift auf Konto B mit gleichem Betrag in einem kurzen Zeitfenster.
Darlehenskonten sind ausgenommen: Zahlungen an ein Darlehen sind Ausgaben, keine Umbuchungen.
"""
from datetime import date

from .. import config
from ..db import q, q1, exe
from ..util import norm_iban
from . import kategorien

STICHWORTE = ("umbuchung", "übertrag", "uebertrag", "kreditkarte", "abrechnung", "eigenes konto", "sparen", "tagesgeld",
              "geldautomat", "bargeld", "auszahlung", "bargeldauszahlung", "atm")
# Konten ohne Import: hier wird die Gegenbuchung einer Umbuchung automatisch angelegt
AUTO_GEGEN_TYPEN = ("bargeld",)


def _eigene_konten():
    return {r["id"]: r for r in q("SELECT * FROM konto WHERE typ != 'darlehen' AND aktiv = 1")}


def _score(a, b, konten) -> float:
    ka, kb = konten[a["konto_id"]], konten[b["konto_id"]]
    tage = abs((date.fromisoformat(a["buchungsdatum"]) - date.fromisoformat(b["buchungsdatum"])).days)
    score = 0.5 - 0.04 * tage
    if (a["gegen_iban"] and norm_iban(kb["iban"]) == a["gegen_iban"]) or \
       (b["gegen_iban"] and norm_iban(ka["iban"]) == b["gegen_iban"]):
        score += 0.45
    text = " ".join((a["gegenpartei"] + " " + a["verwendungszweck"] + " " + b["gegenpartei"] + " " +
                     b["verwendungszweck"]).lower().split())
    if any(w in text for w in STICHWORTE):
        score += 0.2
    if "kreditkarte" in (ka["typ"], kb["typ"]):
        score += 0.1
    return round(min(score, 1.0), 2)


def kandidaten(b, konten):
    fenster = config.UMBUCHUNG_FENSTER_TAGE
    if konten[b["konto_id"]]["typ"] == "kreditkarte":
        fenster = config.UMBUCHUNG_FENSTER_KREDITKARTE_TAGE
    eigene = [k for k in konten if k != b["konto_id"]]
    if not eigene:
        return []
    marks = ",".join("?" * len(eigene))
    rows = q(f"SELECT * FROM buchung WHERE konto_id IN ({marks}) AND betrag_cent = ? AND ist_umbuchung = 0 "
             f"AND umbuchung_partner_id IS NULL AND zuordnung_quelle IS NOT 'manuell' "
             f"AND abs(julianday(buchungsdatum) - julianday(?)) <= ?",
             (*eigene, -b["betrag_cent"], b["buchungsdatum"], max(fenster, config.UMBUCHUNG_FENSTER_KREDITKARTE_TAGE)))
    ergebnis = []
    for r in rows:
        f = fenster
        if konten[r["konto_id"]]["typ"] == "kreditkarte":
            f = config.UMBUCHUNG_FENSTER_KREDITKARTE_TAGE
        if abs((date.fromisoformat(r["buchungsdatum"]) - date.fromisoformat(b["buchungsdatum"])).days) <= f:
            ergebnis.append(r)
    return ergebnis


def verknuepfe(a_id, b_id, benutzer_id=None):
    uk = kategorien.umbuchung_kategorie_id()
    for x, y in ((a_id, b_id), (b_id, a_id)):
        exe("UPDATE buchung SET ist_umbuchung = 1, umbuchung_partner_id = ?, kategorie_id = ?, "
            "zuordnung_quelle = 'umbuchung', geprueft = 1, regel_id = NULL WHERE id = ?", (y, uk, x))
    exe("DELETE FROM umbuchung_vorschlag WHERE buchung_a_id IN (?, ?) OR buchung_b_id IN (?, ?)",
        (a_id, b_id, a_id, b_id))


def markiere(b, gegenkonto_id: int | None) -> str:
    """Buchung manuell als Umbuchung markieren (Prüf-Modus).

    Mit Gegenkonto: passende Gegenbuchung dort suchen (gleicher Betrag mit umgekehrtem Vorzeichen, ±10 Tage) und
    verknüpfen. Gibt es sie noch nicht, wird das Gegenkonto gemerkt; beim späteren Import wird automatisch verknüpft.
    Ohne Gegenkonto: Umbuchung an ein Konto außerhalb des Tools (z. B. Depot).
    Ist das Gegenkonto ein Barkonto (ohne Import), wird die Gegenbuchung dort automatisch angelegt.
    Rückgabe: 'verknuepft', 'angelegt', 'vorgemerkt' oder 'extern'.
    """
    if gegenkonto_id:
        partner = q1("""SELECT * FROM buchung WHERE konto_id = ? AND betrag_cent = ? AND ist_umbuchung = 0
                        AND umbuchung_partner_id IS NULL AND abs(julianday(buchungsdatum) - julianday(?)) <= 10
                        ORDER BY abs(julianday(buchungsdatum) - julianday(?)) LIMIT 1""",
                     (gegenkonto_id, -b["betrag_cent"], b["buchungsdatum"], b["buchungsdatum"]))
        if partner:
            ab, an = (b["id"], partner["id"]) if b["betrag_cent"] < 0 else (partner["id"], b["id"])
            verknuepfe(ab, an)
            return "verknuepft"
    uk = kategorien.umbuchung_kategorie_id()
    exe("UPDATE buchung SET ist_umbuchung = 1, umbuchung_partner_id = NULL, umbuchung_konto_id = ?, kategorie_id = ?, "
        "zuordnung_quelle = 'umbuchung', geprueft = 1, vorschlag_kategorie_id = NULL "
        "WHERE id = ?", (gegenkonto_id, uk, b["id"]))
    exe("DELETE FROM umbuchung_vorschlag WHERE buchung_a_id = ? OR buchung_b_id = ?", (b["id"], b["id"]))
    if gegenkonto_id:
        ziel = q1("SELECT * FROM konto WHERE id = ?", (gegenkonto_id,))
        if ziel and ziel["typ"] in AUTO_GEGEN_TYPEN:
            lege_gegenbuchung_an(b, ziel)
            return "angelegt"
    return "vorgemerkt" if gegenkonto_id else "extern"


MELDUNGEN = {
    "verknuepft": "Als Umbuchung mit der vorhandenen Gegenbuchung verknüpft.",
    "angelegt": "Als Umbuchung gespeichert; die Gegenbuchung im Barkonto wurde automatisch angelegt.",
    "vorgemerkt": "Als Umbuchung markiert. Die Gegenbuchung wird beim nächsten Import des Gegenkontos automatisch verknüpft.",
    "extern": "Als Umbuchung an ein Konto außerhalb des Tools markiert.",
}


def lege_gegenbuchung_an(b, ziel) -> int:
    """Gegenbuchung im Konto ohne Import (Bargeld) anlegen und verknüpfen, z. B. −200 € Geldautomat -> +200 € Bargeld."""
    quelle = q1("SELECT name FROM konto WHERE id = ?", (b["konto_id"],))
    text = ("Abhebung " if b["betrag_cent"] < 0 else "Einzahlung ") + (quelle["name"] if quelle else "")
    vorhanden = q1("SELECT id FROM buchung WHERE konto_id = ? AND dedup_hash = ?", (ziel["id"], f"gegen:{b['id']}"))
    if vorhanden:
        gid = vorhanden["id"]
    else:
        gid = exe("""INSERT INTO buchung (konto_id, buchungsdatum, betrag_cent, gegenpartei, verwendungszweck, partner_key,
                     abrechnungsmonat, kategorie_id, person_id, dedup_hash, zuordnung_quelle, geprueft, ist_umbuchung,
                     umbuchung_konto_id, auto_gegenbuchung) VALUES (?,?,?,?,?,'',?,?,?,?,'umbuchung',1,1,?,1)""",
                  (ziel["id"], b["buchungsdatum"], -b["betrag_cent"], text, "Automatisch aus Umbuchung",
                   b["abrechnungsmonat"], kategorien.umbuchung_kategorie_id(), b["person_id"], f"gegen:{b['id']}",
                   b["konto_id"]))
    exe("UPDATE buchung SET umbuchung_partner_id = ? WHERE id = ?", (gid, b["id"]))
    exe("UPDATE buchung SET umbuchung_partner_id = ? WHERE id = ?", (b["id"], gid))
    return gid


def _vorgemerkte_partner(b):
    """Früher als Umbuchung markierte Buchung, die genau auf diese Gegenbuchung wartet."""
    return q1("""SELECT * FROM buchung WHERE ist_umbuchung = 1 AND umbuchung_partner_id IS NULL
                 AND umbuchung_konto_id = ? AND betrag_cent = ? AND abs(julianday(buchungsdatum) - julianday(?)) <= 10
                 ORDER BY abs(julianday(buchungsdatum) - julianday(?)) LIMIT 1""",
              (b["konto_id"], -b["betrag_cent"], b["buchungsdatum"], b["buchungsdatum"]))


def loese(buchung_id):
    b = q1("SELECT * FROM buchung WHERE id = ?", (buchung_id,))
    if not b:
        return
    ids = [b["id"]] + ([b["umbuchung_partner_id"]] if b["umbuchung_partner_id"] else [])
    for i in list(ids):
        x = q1("SELECT auto_gegenbuchung FROM buchung WHERE id = ?", (i,))
        if x and x["auto_gegenbuchung"]:
            exe("UPDATE buchung SET umbuchung_partner_id = NULL WHERE umbuchung_partner_id = ?", (i,))
            exe("DELETE FROM buchung WHERE id = ?", (i,))
            ids.remove(i)
    for i in ids:
        exe("UPDATE buchung SET ist_umbuchung = 0, umbuchung_partner_id = NULL, kategorie_id = NULL, "
            "zuordnung_quelle = NULL, geprueft = 0, umbuchung_konto_id = NULL WHERE id = ?", (i,))


def erkenne(buchung_ids: list[int]) -> dict:
    konten = _eigene_konten()
    stat = {"auto": 0, "vorschlag": 0}
    if not buchung_ids:
        return stat
    marks = ",".join("?" * len(buchung_ids))
    neue = q(f"SELECT * FROM buchung WHERE id IN ({marks}) AND ist_umbuchung = 0 "
             f"AND COALESCE(zuordnung_quelle,'') != 'manuell'", buchung_ids)
    for b in neue:
        if b["konto_id"] not in konten:
            continue
        b = q1("SELECT * FROM buchung WHERE id = ?", (b["id"],))
        if b["ist_umbuchung"]:
            continue
        wartend = _vorgemerkte_partner(b)
        if wartend:
            ab, an = (b, wartend) if b["betrag_cent"] < 0 else (wartend, b)
            verknuepfe(ab["id"], an["id"])
            stat["auto"] += 1
            continue
        kand = kandidaten(b, konten)
        if not kand:
            continue
        bewertet = sorted(((_score(b, k, konten), k) for k in kand), key=lambda x: -x[0])
        bester_score, bester = bewertet[0]
        eindeutig = len(bewertet) == 1 or bewertet[1][0] < bester_score - 0.15
        if eindeutig and bester_score >= config.UMBUCHUNG_AUTO_SCHWELLE:
            ab, an = (b, bester) if b["betrag_cent"] < 0 else (bester, b)
            verknuepfe(ab["id"], an["id"])
            stat["auto"] += 1
        else:
            for s, k in bewertet[:3]:
                ab, an = (b, k) if b["betrag_cent"] < 0 else (k, b)
                exe("INSERT OR IGNORE INTO umbuchung_vorschlag (buchung_a_id, buchung_b_id, score) VALUES (?,?,?)",
                    (ab["id"], an["id"], s))
                stat["vorschlag"] += 1
    return stat


def offene_vorschlaege(sichtbare_konten: list[int]):
    if not sichtbare_konten:
        return []
    marks = ",".join("?" * len(sichtbare_konten))
    return q(f"""SELECT v.id AS vid, v.score,
                a.id AS a_id, a.buchungsdatum AS a_datum, a.betrag_cent AS a_betrag, a.gegenpartei AS a_partei,
                a.verwendungszweck AS a_zweck, ka.name AS a_konto,
                b.id AS b_id, b.buchungsdatum AS b_datum, b.betrag_cent AS b_betrag, b.gegenpartei AS b_partei,
                b.verwendungszweck AS b_zweck, kb.name AS b_konto
            FROM umbuchung_vorschlag v
            JOIN buchung a ON a.id = v.buchung_a_id JOIN konto ka ON ka.id = a.konto_id
            JOIN buchung b ON b.id = v.buchung_b_id JOIN konto kb ON kb.id = b.konto_id
            WHERE v.status = 'offen' AND a.ist_umbuchung = 0 AND b.ist_umbuchung = 0
              AND a.konto_id IN ({marks}) AND b.konto_id IN ({marks})
            ORDER BY a.buchungsdatum DESC, v.score DESC""", (*sichtbare_konten, *sichtbare_konten))
