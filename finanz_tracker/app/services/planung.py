"""Ausgaben- und Sondereinnahmenplanung (0.9.0).

Ausgangspunkt ist das heute verfügbare Vermögen aus wählbaren Konten bzw. Vermögensgruppen. Darauf werden
geplante Ausgaben (Autokauf, Sanierung …) und erwartete Sondereinnahmen (Bonus, Erbe, Steuererstattung …)
Monat für Monat angerechnet, optional zuzüglich eines laufenden monatlichen Überschusses. Daraus ergeben sich
das Vermögen nach jeder Ausgabe, der tiefste Stand und das Vermögen zu einem frei wählbaren Stichtag.
"""
import json

from ..db import q, einstellung, setze_einstellung
from ..util import aktueller_monat, monat_plus
from . import statistik, vermoegen as vm

MAX_MONATE = 15 * 12


def quellen(sichtbar: list[int]) -> list[dict]:
    """Vermögensgruppen mit Konten und heutigem Betrag (nur Vermögensseite der Aufstellung)."""
    bil = vm.bilanz(vm.verlauf_je_konto(sichtbar))
    return [{"name": g["name"], "farbe": g["farbe"], "summe": g["summe"],
             "konten": [{"schluessel": str(k["id"]), "name": k["name"], "betrag": k["betrag"]} for k in g["konten"]]}
            for g in bil["aktiva"]["gruppen"]]


def auswahl(benutzer_id: int, alle: list[dict]) -> set[str]:
    """Gewählte Konten; ohne Einstellung alle außer Depots, Krypto und Bausparen (gebundenes Vermögen)."""
    roh = einstellung(f"planung_auswahl:{benutzer_id}")
    if roh:
        try:
            return set(json.loads(roh))
        except ValueError:
            pass
    return {k["schluessel"] for g in alle if g["name"] not in ("Depots", "Krypto", "Bausparen") for k in g["konten"]}


def speichere_auswahl(benutzer_id: int, schluessel: list[str], sparrate_cent: int | None):
    setze_einstellung(f"planung_auswahl:{benutzer_id}", json.dumps(sorted(set(schluessel))))
    setze_einstellung(f"planung_sparrate:{benutzer_id}", "" if sparrate_cent is None else str(sparrate_cent))


def sparrate(benutzer_id: int) -> int | None:
    roh = einstellung(f"planung_sparrate:{benutzer_id}")
    return int(roh) if roh not in (None, "") else None


def sparrate_vorschlag(konten: list[int]) -> int:
    """Ø Überschuss (Einnahmen − Ausgaben) der letzten 12 abgeschlossenen Monate."""
    v = statistik.verlauf(konten, monat_plus(aktueller_monat(), -1), 12)
    mit_daten = [x for x in v if x["einnahmen"] or x["ausgaben"]]
    return round(sum(x["saldo"] for x in mit_daten) / len(mit_daten)) if mit_daten else 0


def posten() -> list:
    return q("""SELECT p.*, k.pfad AS kat_pfad FROM plan_posten p LEFT JOIN kategorie k ON k.id = p.kategorie_id
                ORDER BY p.monat, p.art DESC, p.id""")


def berechne(start_cent: int, liste: list, rate_cent: int, stichtag: str) -> dict:
    """Monatliche Entwicklung ab dem aktuellen Monat bis zum Horizont.

    Offene Posten in der Vergangenheit werden im aktuellen Monat angerechnet; erledigte Posten nicht mehr
    (sie stecken schon im Kontostand). Der laufende Überschuss zählt ab dem Folgemonat.
    """
    heute = aktueller_monat()
    offen = [dict(p) for p in liste if not p["erledigt"]]
    for p in offen:
        p["wirksam"] = max(p["monat"], heute)
        p["vorzeichen"] = -1 if p["art"] == "ausgabe" else 1
    letzte = max([p["wirksam"] for p in offen] + [stichtag, monat_plus(heute, 11)])
    ende = min(letzte, monat_plus(heute, MAX_MONATE))
    monate, werte, zeitplan = [], [], []
    stand, m, i = start_cent, heute, 0
    while m <= ende:
        if i:
            stand += rate_cent
        for p in sorted((x for x in offen if x["wirksam"] == m), key=lambda x: (-x["vorzeichen"], x["id"])):
            stand += p["vorzeichen"] * p["betrag_cent"]
            zeitplan.append({**p, "danach": stand, "ueberfaellig": p["monat"] < heute})
        monate.append(m)
        werte.append(stand)
        m, i = monat_plus(m, 1), i + 1
    tief = min(range(len(werte)), key=lambda j: werte[j]) if werte else None
    bis_stichtag = [p for p in offen if p["wirksam"] <= stichtag]
    idx = monate.index(stichtag) if stichtag in monate else None
    jahre = {}
    for p in offen:
        j = jahre.setdefault(p["wirksam"][:4], {"jahr": p["wirksam"][:4], "ausgaben": 0, "einnahmen": 0, "ende": None})
        j["ausgaben" if p["art"] == "ausgabe" else "einnahmen"] += p["betrag_cent"]
    for mo, w in zip(monate, werte):
        if mo[:4] in jahre or mo.endswith("-12"):
            jahre.setdefault(mo[:4], {"jahr": mo[:4], "ausgaben": 0, "einnahmen": 0, "ende": None})["ende"] = w
    return {
        "start": start_cent, "rate": rate_cent, "monate": monate, "werte": werte, "zeitplan": zeitplan,
        "tief": {"monat": monate[tief], "wert": werte[tief]} if tief is not None else None,
        "stichtag": stichtag, "stichtag_wert": werte[idx] if idx is not None else None,
        "ausgaben_bis": sum(p["betrag_cent"] for p in bis_stichtag if p["art"] == "ausgabe"),
        "einnahmen_bis": sum(p["betrag_cent"] for p in bis_stichtag if p["art"] == "einnahme"),
        "ueberschuss_bis": rate_cent * max(0, (monate.index(stichtag) if stichtag in monate else 0)),
        "jahre": [jahre[j] for j in sorted(jahre)],
    }
