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


# ---------------------------------------------------------------------------------------------------------------
# Eigene Auswertungen: frei konfigurierbare Diagramme, je Benutzer gespeichert

import json  # noqa: E402

from flask import abort, g, jsonify, redirect, url_for  # noqa: E402

from ..db import exe, commit, jload  # noqa: E402
from ..services import auswertung_daten as ad  # noqa: E402
from . import melde  # noqa: E402


def _ansichten():
    return q("SELECT * FROM auswertung_ansicht WHERE benutzer_id = ? ORDER BY sortierung, id", (g.user["id"],))


@bp.route("/eigene")
@auth.login_required
def eigene():
    ansichten = _ansichten()
    if not ansichten:
        exe("INSERT INTO auswertung_ansicht (benutzer_id, name, diagramme) VALUES (?, 'Übersicht', ?)",
            (g.user["id"], json.dumps(ad.standard_diagramme(), ensure_ascii=False)))
        commit()
        ansichten = _ansichten()
    aid = int_oder_none(request.args.get("ansicht")) or ansichten[0]["id"]
    aktuell = next((x for x in ansichten if x["id"] == aid), ansichten[0])
    konten_sichtbar = auth.sichtbare_konten()
    optionen = {
        "kategorien": [{"id": k["id"], "name": k["pfad"], "ebene": k["ebene"]} for k in kategorien.alle()],
        "tags": [dict(r) for r in q("SELECT id, name FROM tag ORDER BY name")],
        "personen": [dict(r) for r in q("SELECT id, name FROM person WHERE aktiv = 1 ORDER BY name")],
        "konten": [dict(r) for r in q(f"SELECT id, name FROM konto WHERE typ != 'darlehen' AND id IN "
                                      f"({','.join('?' * len(konten_sichtbar)) or 'NULL'}) ORDER BY sortierung, name",
                                      konten_sichtbar)],
        "vertraege": [dict(r) for r in q("SELECT id, name FROM vertrag WHERE art != 'ignoriert' ORDER BY name")],
        "typen": ad.TYPEN, "gruppen": ad.GRUPPEN, "messgroessen": ad.MESSGROESSEN, "zeiten": ad.ZEITEN,
        "zeitraeume": ad.ZEITRAEUME,
    }
    return render_template("auswertung_eigene.html", ansichten=ansichten, aktuell=aktuell,
                           diagramme=jload(aktuell["diagramme"], []), optionen=optionen)


@bp.route("/daten", methods=["POST"])
@auth.login_required
def daten():
    konfig = request.get_json(silent=True) or {}
    konten = statistik.basis_konten(auth.sichtbare_konten())
    try:
        return jsonify(ad.berechne(konten, konfig))
    except (ValueError, KeyError, TypeError) as exc:
        return jsonify({"fehler": f"Einstellung ungültig: {exc}"}), 400


@bp.route("/ansicht", methods=["POST"])
@bp.route("/ansicht/<int:aid>", methods=["POST"])
@auth.login_required
def ansicht(aid=None):
    if aid:
        a = q1("SELECT * FROM auswertung_ansicht WHERE id = ? AND benutzer_id = ?", (aid, g.user["id"]))
        if not a:
            abort(404)
    daten_ = request.get_json(silent=True)
    if daten_ is not None:  # Speichern aus der Seite (JSON)
        if not aid:
            abort(400)
        if "diagramme" in daten_ and isinstance(daten_["diagramme"], list):
            exe("UPDATE auswertung_ansicht SET diagramme = ? WHERE id = ?",
                (json.dumps(daten_["diagramme"][:40], ensure_ascii=False), aid))
        if daten_.get("name", "").strip():
            exe("UPDATE auswertung_ansicht SET name = ? WHERE id = ?", (daten_["name"].strip()[:60], aid))
        commit()
        return jsonify({"ok": True})
    f = request.form
    if f.get("aktion") == "loeschen" and aid:
        exe("DELETE FROM auswertung_ansicht WHERE id = ?", (aid,))
        commit()
        melde("Ansicht gelöscht.")
        return redirect(url_for("auswertung.eigene"))
    if f.get("aktion") == "zuruecksetzen" and aid:
        exe("UPDATE auswertung_ansicht SET diagramme = ? WHERE id = ?",
            (json.dumps(ad.standard_diagramme(), ensure_ascii=False), aid))
        commit()
        melde("Ansicht auf die Standard-Diagramme zurückgesetzt.")
        return redirect(url_for("auswertung.eigene", ansicht=aid))
    name = f.get("name", "").strip()[:60] or "Neue Ansicht"
    if aid:
        exe("UPDATE auswertung_ansicht SET name = ? WHERE id = ?", (name, aid))
    else:
        aid = exe("INSERT INTO auswertung_ansicht (benutzer_id, name, sortierung, diagramme) VALUES (?, ?, ?, '[]')",
                  (g.user["id"], name, len(_ansichten())))
    commit()
    return redirect(url_for("auswertung.eigene", ansicht=aid))
