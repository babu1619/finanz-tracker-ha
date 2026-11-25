"""Planung: geplante Ausgaben und Sondereinnahmen, Vermögen nach jeder Ausgabe und zum Stichtag."""
from flask import Blueprint, abort, g, redirect, render_template, request, url_for

from .. import auth
from ..db import q1, exe, commit, log_aenderung
from ..services import kategorien, planung, statistik
from ..util import aktueller_monat, ist_monat, monat_plus, parse_euro_eingabe
from . import melde, int_oder_none

bp = Blueprint("planung", __name__, url_prefix="/planung")


def _stichtag(roh: str | None, liste) -> str:
    heute = aktueller_monat()
    if ist_monat(roh or ""):
        return min(max(roh, heute), monat_plus(heute, planung.MAX_MONATE))
    offen = [p["monat"] for p in liste if not p["erledigt"] and p["monat"] >= heute]
    return max(offen) if offen else f"{int(heute[:4]) + 1}-12"


@bp.route("/")
@auth.login_required
def index():
    sichtbar = auth.sichtbare_konten()
    quellen = planung.quellen(sichtbar)
    gewaehlt = planung.auswahl(g.user["id"], quellen)
    start = sum(k["betrag"] for gr in quellen for k in gr["konten"] if k["schluessel"] in gewaehlt)
    vorschlag = planung.sparrate_vorschlag(statistik.basis_konten(sichtbar))
    rate = planung.sparrate(g.user["id"])
    liste = planung.posten()
    stichtag = _stichtag(request.args.get("stichtag"), liste)
    erg = planung.berechne(start, liste, rate or 0, stichtag)
    bearbeiten = q1("SELECT * FROM plan_posten WHERE id = ?", (int_oder_none(request.args.get("bearbeiten")),)) \
        if request.args.get("bearbeiten") else None
    diagramm = {"labels": erg["monate"], "einheit": "€", "reihen": [{"name": "Vermögen", "werte": erg["werte"]}],
                "marken": [{"monat": z["wirksam"], "name": z["name"], "art": z["art"]} for z in erg["zeitplan"]]}
    return render_template("planung.html", quellen=quellen, gewaehlt=gewaehlt, start=start, rate=rate,
                           vorschlag=vorschlag, liste=liste, erg=erg, stichtag=stichtag, heute=aktueller_monat(),
                           bearbeiten=bearbeiten, kategorien=kategorien.alle(), diagramm=diagramm)


@bp.route("/quellen", methods=["POST"])
@auth.login_required
def quellen_speichern():
    f = request.form
    rate = None
    if f.get("mit_rate"):
        try:
            rate = parse_euro_eingabe(f.get("sparrate", "") or "0")
        except ValueError:
            melde("Monatlichen Überschuss prüfen.", "warn")
            return redirect(url_for("planung.index"))
    planung.speichere_auswahl(g.user["id"], f.getlist("quelle"), rate)
    commit()
    melde("Ausgangsvermögen gespeichert.")
    return redirect(url_for("planung.index", stichtag=f.get("stichtag")) + "#quellen")


@bp.route("/posten", methods=["POST"])
@bp.route("/posten/<int:pid>", methods=["POST"])
@auth.schreibrecht
def posten_speichern(pid=None):
    f = request.form
    p = q1("SELECT * FROM plan_posten WHERE id = ?", (pid,)) if pid else None
    if pid and not p:
        abort(404)
    if f.get("aktion") == "loeschen" and p:
        exe("DELETE FROM plan_posten WHERE id = ?", (pid,))
        log_aenderung(g.user["id"], "plan_posten", pid, "geloescht", dict(p))
        commit()
        melde(f"„{p['name']}“ entfernt.")
        return redirect(url_for("planung.index"))
    if f.get("aktion") == "erledigt" and p:
        exe("UPDATE plan_posten SET erledigt = 1 - erledigt WHERE id = ?", (pid,))
        commit()
        melde(f"„{p['name']}“ " + ("wieder offen." if p["erledigt"] else "als erledigt markiert – zählt jetzt nicht mehr in die Planung."))
        return redirect(url_for("planung.index") + "#zeitplan")
    name = f.get("name", "").strip()
    try:
        betrag = abs(parse_euro_eingabe(f.get("betrag", "")))
    except ValueError:
        betrag = 0
    monat = f.get("monat", "")
    if not name or not betrag or not ist_monat(monat):
        melde("Bitte Bezeichnung, Betrag und Monat angeben.", "warn")
        return redirect(url_for("planung.index", bearbeiten=pid) + "#posten")
    werte = (f.get("art") if f.get("art") in ("ausgabe", "einnahme") else "ausgabe", name, betrag, monat,
             int_oder_none(f.get("kategorie_id")), f.get("notiz", "").strip() or None)
    if p:
        exe("UPDATE plan_posten SET art = ?, name = ?, betrag_cent = ?, monat = ?, kategorie_id = ?, notiz = ? WHERE id = ?",
            werte + (pid,))
    else:
        pid = exe("INSERT INTO plan_posten (art, name, betrag_cent, monat, kategorie_id, notiz) VALUES (?,?,?,?,?,?)", werte)
    log_aenderung(g.user["id"], "plan_posten", pid, "gespeichert", dict(f))
    commit()
    melde(f"„{name}“ gespeichert.")
    return redirect(url_for("planung.index") + "#zeitplan")
