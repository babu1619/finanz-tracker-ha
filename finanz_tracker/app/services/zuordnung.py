"""Automatische Zuordnung: 1. Regeln (sicher), 2. Gedächtnis (gleiche Gegenpartei wie bestätigte Buchungen),
3. Lernmodell (ähnliche Texte). Manuell zugeordnete oder aufgeteilte Buchungen werden nie überschrieben.
"""
import re
from collections import Counter

from ..db import q, q1, exe, jload, jdump
from ..util import monat_von, monat_plus, parse_euro_eingabe
from . import kategorien

BEDINGUNGS_FELDER = {
    "gegenpartei": "Gegenpartei",
    "verwendungszweck": "Verwendungszweck",
    "gegen_iban": "Gegen-IBAN",
    "betrag": "Betrag (ohne Vorzeichen, €)",
    "richtung": "Richtung",
    "konto": "Konto",
    "tag": "Tag im Monat",
}
OPERATOREN = {
    "enthaelt": "enthält",
    "gleich": "ist gleich",
    "beginnt": "beginnt mit",
    "regex": "regulärer Ausdruck",
    "min": "mindestens",
    "max": "höchstens",
    "ab": "ab Tag",
    "bis": "bis Tag",
}


def _text(b, feld):
    return (b[feld] or "").lower()


def bedingung_trifft(c: dict, b) -> bool:
    feld, op, wert = c.get("feld"), c.get("op"), str(c.get("wert", "")).strip()
    try:
        if feld in ("gegenpartei", "verwendungszweck", "gegen_iban"):
            t = _text(b, feld)
            w = wert.lower()
            if feld == "gegen_iban":
                t, w = t.replace(" ", ""), w.replace(" ", "")
            if op == "enthaelt":
                return w in t
            if op == "gleich":
                return t == w
            if op == "beginnt":
                return t.startswith(w)
            if op == "regex":
                return re.search(wert, b[feld] or "", re.IGNORECASE) is not None
            return False
        if feld == "betrag":
            betrag = abs(b["betrag_cent"])
            grenze = abs(parse_euro_eingabe(wert))
            if op == "min":
                return betrag >= grenze
            if op == "max":
                return betrag <= grenze
            if op == "gleich":
                return betrag == grenze
            return False
        if feld == "richtung":
            return (b["betrag_cent"] > 0) if wert == "eingang" else (b["betrag_cent"] < 0)
        if feld == "konto":
            return str(b["konto_id"]) == wert
        if feld == "tag":
            tag = int(str(b["buchungsdatum"])[8:10])
            return tag >= int(wert) if op == "ab" else tag <= int(wert)
    except (ValueError, re.error, TypeError):
        return False
    return False


def regel_trifft(regel, b) -> bool:
    bed = jload(regel["bedingungen"], [])
    return bool(bed) and all(bedingung_trifft(c, b) for c in bed)


def aktive_regeln():
    return q("SELECT * FROM regel WHERE aktiv = 1 ORDER BY prioritaet, id")


def zielwerte(regel, b) -> dict:
    a = jload(regel["aktionen"], {})
    werte = {}
    if a.get("kategorie_id"):
        werte["kategorie_id"] = int(a["kategorie_id"])
    if a.get("person_id"):
        werte["person_id"] = int(a["person_id"])
    versatz = int(a.get("monat_versatz") or 0)
    werte["abrechnungsmonat"] = monat_plus(monat_von(b["buchungsdatum"]), versatz)
    if a.get("tag_id"):
        werte["tag_id"] = int(a["tag_id"])
    if a.get("verteilung_monate"):
        werte["verteilung_monate"] = max(1, min(60, int(a["verteilung_monate"])))
    if a.get("als_umbuchung"):
        werte["ist_umbuchung"] = 1
        if a.get("umbuchung_konto_id"):
            werte["umbuchung_konto_id"] = int(a["umbuchung_konto_id"])
        uk = kategorien.umbuchung_kategorie_id()
        if uk:
            werte["kategorie_id"] = uk
    return werte


def gedaechtnis_vorschlag(b):
    """Häufigste bestätigte Kategorie für dieselbe Gegenpartei. -> (kategorie_id, person_id, anzahl, gesamt)"""
    if not b["partner_key"]:
        return None
    rows = q("SELECT kategorie_id, person_id FROM buchung WHERE partner_key = ? AND geprueft = 1 "
             "AND kategorie_id IS NOT NULL AND ist_umbuchung = 0 AND id != ? "
             "AND NOT EXISTS (SELECT 1 FROM buchung_split s WHERE s.buchung_id = buchung.id) "
             "ORDER BY buchungsdatum DESC LIMIT 20",
             (b["partner_key"], b["id"]))
    if not rows:
        return None
    zaehler = Counter((r["kategorie_id"], r["person_id"]) for r in rows)
    (kat, person), anzahl = zaehler.most_common(1)[0]
    return {"kategorie_id": kat, "person_id": person, "anzahl": anzahl, "gesamt": len(rows)}


def _wende_regel_an(regel, b) -> None:
    w = zielwerte(regel, b)
    ist_umb = w.get("ist_umbuchung", b["ist_umbuchung"])
    if b["ist_umbuchung"] and not w.get("ist_umbuchung") and w.get("kategorie_id") and not b["umbuchung_partner_id"]:
        ist_umb = 0  # vorgemerkte Umbuchung wird per Regel zur normalen Ausgabe/Einnahme
        exe("UPDATE buchung SET umbuchung_konto_id = NULL WHERE id = ?", (b["id"],))
    exe("UPDATE buchung SET kategorie_id = COALESCE(?, kategorie_id), person_id = COALESCE(?, person_id), "
        "abrechnungsmonat = ?, ist_umbuchung = ?, verteilung_monate = COALESCE(?, verteilung_monate), "
        "zuordnung_quelle = 'regel', regel_id = ?, geprueft = 1, konfidenz = NULL, "
        "vorschlag_kategorie_id = NULL WHERE id = ?",
        (w.get("kategorie_id"), w.get("person_id"), w["abrechnungsmonat"], ist_umb,
         w.get("verteilung_monate"), regel["id"], b["id"]))
    if w.get("tag_id"):
        exe("INSERT OR IGNORE INTO buchung_tag (buchung_id, tag_id) VALUES (?, ?)", (b["id"], w["tag_id"]))
    if w.get("umbuchung_konto_id") and w["umbuchung_konto_id"] != b["konto_id"] and not b["umbuchung_partner_id"]:
        from . import umbuchungen
        umbuchungen.markiere(q1("SELECT * FROM buchung WHERE id = ?", (b["id"],)), w["umbuchung_konto_id"])


def _gesperrt(b) -> bool:
    """Nie automatisch umschreiben: aufgeteilte Buchungen, verknüpfte Umbuchungen, automatische Gegenbuchungen."""
    if b["umbuchung_partner_id"] or b["auto_gegenbuchung"]:
        return True
    return q1("SELECT 1 FROM buchung_split WHERE buchung_id = ? LIMIT 1", (b["id"],)) is not None


def ordne_zu(buchung_ids: list[int] | None = None, ueberschreiben=False, auch_manuell=False,
             nur_regel_id: int | None = None) -> dict:
    """Wendet Regeln, Gedächtnis und Lernmodell an. Ohne buchung_ids: alle noch nicht zugeordneten Buchungen
    (mit ueberschreiben=True auch bereits automatisch zugeordnete).

    auch_manuell=True: zusätzlich manuell oder per anderer Regel zugeordnete Buchungen umschreiben, sofern eine Regel
    trifft (Gedächtnis und Lernmodell ändern manuelle Zuordnungen nie). Aufgeteilte Buchungen und verknüpfte
    Umbuchungen bleiben unangetastet.
    nur_regel_id: nur diese eine Regel anwenden (Speichern einer Regel mit „auf alle passenden anwenden“).
    """
    from . import modell as modell_mod
    regeln = aktive_regeln()
    if nur_regel_id is not None:
        regeln = [r for r in regeln if r["id"] == nur_regel_id] or \
                 [r for r in q("SELECT * FROM regel WHERE id = ?", (nur_regel_id,))]
    if buchung_ids is None:
        if auch_manuell:
            rows = q("SELECT * FROM buchung")
        else:
            rows = q("SELECT * FROM buchung WHERE COALESCE(zuordnung_quelle,'') NOT IN ('manuell','umbuchung')")
    else:
        if not buchung_ids:
            return {"regel": 0, "gedaechtnis": 0, "modell": 0, "offen": 0, "manuell_ueberschrieben": 0}
        marks = ",".join("?" * len(buchung_ids))
        rows = q(f"SELECT * FROM buchung WHERE id IN ({marks})", buchung_ids)
    stat = {"regel": 0, "gedaechtnis": 0, "modell": 0, "offen": 0, "manuell_ueberschrieben": 0}
    lern = None
    for b in rows:
        geschuetzt = b["zuordnung_quelle"] in ("manuell", "umbuchung")
        if geschuetzt and not auch_manuell:
            continue
        if b["zuordnung_quelle"] and not ueberschreiben and not auch_manuell and buchung_ids is None:
            continue
        treffer = next((r for r in regeln if regel_trifft(r, b)), None)
        if treffer:
            if auch_manuell and _gesperrt(b):
                continue
            if b["zuordnung_quelle"] == "regel" and b["regel_id"] == treffer["id"] and nur_regel_id is None \
                    and not ueberschreiben and buchung_ids is None:
                continue
            _wende_regel_an(treffer, b)
            stat["regel"] += 1
            if geschuetzt or (b["zuordnung_quelle"] == "regel" and b["regel_id"] != treffer["id"]):
                stat["manuell_ueberschrieben"] += 1
            continue
        if geschuetzt or nur_regel_id is not None or b["ist_umbuchung"]:
            continue
        g = gedaechtnis_vorschlag(b)
        if g:
            sicher = g["anzahl"] >= 2 and g["anzahl"] == g["gesamt"]
            exe("UPDATE buchung SET kategorie_id = ?, person_id = COALESCE(?, person_id), zuordnung_quelle = 'gedaechtnis', "
                "regel_id = NULL, geprueft = ?, konfidenz = ?, vorschlag_kategorie_id = NULL WHERE id = ?",
                (g["kategorie_id"], g["person_id"], 1 if sicher else 0, g["anzahl"] / g["gesamt"], b["id"]))
            stat["gedaechtnis"] += 1
            continue
        if lern is None:
            lern = modell_mod.Modell().trainiere()
        kat, p = lern.vorhersage(b)
        if kat and p >= modell_mod.SICHER:
            exe("UPDATE buchung SET kategorie_id = ?, zuordnung_quelle = 'modell', regel_id = NULL, geprueft = 0, "
                "konfidenz = ?, vorschlag_kategorie_id = NULL WHERE id = ?", (kat, round(p, 3), b["id"]))
            stat["modell"] += 1
        else:
            if kat and p >= modell_mod.VORSCHLAG:
                exe("UPDATE buchung SET vorschlag_kategorie_id = ?, konfidenz = ? WHERE id = ?", (kat, round(p, 3), b["id"]))
            stat["offen"] += 1
    return stat


def feedback(b, neue_kategorie_id) -> None:
    """Merkt, ob die automatische Zuordnung oder der Vorschlag richtig war (für die Trefferquote)."""
    if b["zuordnung_quelle"] == "regel" and b["kategorie_id"]:
        if b["kategorie_id"] != neue_kategorie_id:  # Regeltreffer gelten als richtig, solange niemand korrigiert
            exe("INSERT INTO zuordnung_feedback (buchung_id, quelle, korrekt) VALUES (?, 'regel', 0)", (b["id"],))
    elif b["zuordnung_quelle"] in ("gedaechtnis", "modell") and b["kategorie_id"] and not b["geprueft"]:
        exe("INSERT INTO zuordnung_feedback (buchung_id, quelle, konfidenz, korrekt) VALUES (?,?,?,?)",
            (b["id"], b["zuordnung_quelle"], b["konfidenz"], int(b["kategorie_id"] == neue_kategorie_id)))
    elif not b["kategorie_id"] and b["vorschlag_kategorie_id"]:
        exe("INSERT INTO zuordnung_feedback (buchung_id, quelle, konfidenz, korrekt) VALUES (?,?,?,?)",
            (b["id"], "vorschlag", b["konfidenz"], int(b["vorschlag_kategorie_id"] == neue_kategorie_id)))


def teste_regel(bedingungen: list, aktionen: dict, sichtbare_konten: list[int]) -> dict:
    """Wie viele bestehende Buchungen trifft die Regel, und wie viele würden anders zugeordnet?"""
    pseudo = {"bedingungen": jdump(bedingungen), "aktionen": jdump(aktionen)}
    if not sichtbare_konten:
        return {"treffer": 0, "anders": 0, "beispiele": []}
    marks = ",".join("?" * len(sichtbare_konten))
    rows = q(f"SELECT b.*, k.pfad AS kat_pfad FROM buchung b LEFT JOIN kategorie k ON k.id = b.kategorie_id "
             f"WHERE b.konto_id IN ({marks}) ORDER BY b.buchungsdatum DESC", sichtbare_konten)
    treffer, anders, beispiele = 0, 0, []
    manuell = andere_regel = 0
    ziel_kat = int(aktionen["kategorie_id"]) if aktionen.get("kategorie_id") else None
    for b in rows:
        if regel_trifft(pseudo, b):
            treffer += 1
            if ziel_kat and b["kategorie_id"] != ziel_kat:
                anders += 1
                if b["zuordnung_quelle"] in ("manuell", "umbuchung"):
                    manuell += 1
                elif b["zuordnung_quelle"] == "regel":
                    andere_regel += 1
                if len(beispiele) < 8:
                    beispiele.append(b)
    return {"treffer": treffer, "anders": anders, "beispiele": beispiele, "manuell": manuell,
            "andere_regel": andere_regel}


def regel_statistik() -> dict[int, dict]:
    rows = q("SELECT regel_id, COUNT(*) AS n, MAX(buchungsdatum) AS zuletzt FROM buchung "
             "WHERE regel_id IS NOT NULL AND buchungsdatum >= date('now','-12 months') GROUP BY regel_id")
    return {r["regel_id"]: {"n": r["n"], "zuletzt": r["zuletzt"]} for r in rows}


def naechste_prioritaet() -> int:
    r = q1("SELECT COALESCE(MAX(prioritaet), 0) + 10 AS p FROM regel")
    return r["p"]
