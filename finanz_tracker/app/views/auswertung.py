"""Detailansichten: Kategorie-Drilldown über die Zeit, Personen, Gegenparteien, Jahresvergleich."""
from flask import Blueprint, render_template, request

from .. import auth
from ..db import q, q1
from ..services import kategorien, statistik
from ..util import aktueller_monat, ist_monat, monat_plus
from . import int_oder_none

bp = Blueprint("auswertung", __name__, url_prefix="/auswertung")

ZEITRAEUME = {"12": "letzte 12 Monate", "6": "letzte 6 Monate", "24": "letzte 24 Monate", "jahr": "Kalenderjahr"}


@bp.route("/")
@auth.login_required
def index():
    a = request.args
    zeitraum = a.get("zeitraum", "12") if a.get("zeitraum") in ZEITRAEUME else "12"
    bis = a.get("bis") if ist_monat(a.get("bis", "")) else aktueller_monat()
    if zeitraum == "jahr":
        jahr = int_oder_none(a.get("jahr")) or int(bis[:4])
        von, bis = f"{jahr}-01", f"{jahr}-12"
    else:
        von = monat_plus(bis, -(int(zeitraum) - 1))
        jahr = None
    monate = []
    m = von
    while m <= bis:
        monate.append(m)
        m = monat_plus(m, 1)
    person_id = int_oder_none(a.get("person"))
    kat_id = int_oder_none(a.get("kategorie"))
    konten = statistik.basis_konten(auth.sichtbare_konten())
    alle = kategorien.alle()
    nach_id = {k["id"]: k for k in alle}
    kat = nach_id.get(kat_id)
    reihe = statistik.reihe_je_kategorie(konten, von, bis, person_id)

    # Zeilen: Kinder der gewählten Kategorie bzw. oberste Ausgabenkategorien
    if kat:
        kinder = [k for k in alle if k["parent_id"] == kat["id"]]
        eigene = {}  # Buchungen direkt auf der gewählten Kategorie (nicht in Kindern)
        kinder_summe = {mm: sum(reihe.get(k["id"], {}).get(mm, 0) for k in kinder) for mm in monate}
        for mm in monate:
            eigene[mm] = reihe.get(kat["id"], {}).get(mm, 0) - kinder_summe[mm]
        zeilen = [{"id": k["id"], "name": k["name"], "hat_kinder": k["hat_kinder"], "werte": reihe.get(k["id"], {})}
                  for k in kinder]
        if any(eigene.values()):
            zeilen.append({"id": None, "name": f"{kat['name']} (direkt)", "hat_kinder": False, "werte": eigene})
        art = kat["wirksame_art"]
    else:
        art = a.get("art") if a.get("art") in ("ausgabe", "einnahme") else "ausgabe"
        zeilen = [{"id": k["id"], "name": k["name"], "hat_kinder": k["hat_kinder"], "werte": reihe.get(k["id"], {})}
                  for k in alle if k["ebene"] == 0 and k["wirksame_art"] == art]
        ohne = reihe.get(None if art == "ausgabe" else "ein", {})
        if ohne:
            zeilen.append({"id": "ohne", "name": "Ohne Kategorie", "hat_kinder": False, "werte": ohne})
    for z in zeilen:
        z["summe"] = sum(z["werte"].get(mm, 0) for mm in monate)
        z["schnitt"] = z["summe"] / len(monate)
        z["max"] = max([z["werte"].get(mm, 0) for mm in monate] + [1])
    zeilen = [z for z in zeilen if z["summe"]]
    zeilen.sort(key=lambda z: -z["summe"])
    gesamt = {mm: sum(z["werte"].get(mm, 0) for z in zeilen) for mm in monate}
    gesamt_summe = sum(gesamt.values())
    max_gesamt = max(list(gesamt.values()) + [1])

    # Pfad für Brotkrumen
    pfad = []
    cur = kat
    while cur:
        pfad.insert(0, cur)
        cur = nach_id.get(cur["parent_id"]) if cur["parent_id"] else None

    kat_ids = kategorien.nachkommen_ids(kat["id"]) if kat else None
    gegenparteien = statistik.top_gegenparteien(konten, von, bis, kat_ids, 12) if art == "ausgabe" else []
    personen_liste = statistik.ausgaben_je_person(konten, von, bis) if not kat else []

    # Vorjahresvergleich desselben Zeitraums
    # nur wenn der Vorjahreszeitraum vollständig in den Daten liegt, sonst wäre der Vergleich irreführend
    erstes = q1(f"SELECT MIN(abrechnungsmonat) AS m FROM buchung WHERE konto_id IN ({','.join('?' * len(konten)) or 'NULL'})",
                konten)["m"] if konten else None
    vj_vollstaendig = bool(erstes) and erstes <= monat_plus(von, -12)
    vj_reihe = statistik.reihe_je_kategorie(konten, monat_plus(von, -12), monat_plus(bis, -12), person_id) \
        if vj_vollstaendig else {}
    for z in zeilen:
        if vj_vollstaendig and z["id"] and z["id"] != "ohne":
            z["vorjahr"] = sum(vj_reihe.get(z["id"], {}).values())
    jahre = [r["j"] for r in q("SELECT DISTINCT substr(abrechnungsmonat, 1, 4) AS j FROM buchung ORDER BY j DESC")]
    return render_template("auswertung.html", monate=monate, zeilen=zeilen, gesamt=gesamt, gesamt_summe=gesamt_summe,
                           max_gesamt=max_gesamt, kat=kat, pfad=pfad, art=art, zeitraum=zeitraum, zeitraeume=ZEITRAEUME,
                           bis=bis, jahr=jahr, jahre=jahre, von=von, person_id=person_id,
                           personen=q("SELECT * FROM person WHERE aktiv = 1 ORDER BY name"),
                           gegenparteien=gegenparteien, personen_liste=personen_liste,
                           person=q1("SELECT * FROM person WHERE id = ?", (person_id,)) if person_id else None)
