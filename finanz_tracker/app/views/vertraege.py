"""Abos, Versicherungen und Fixkosten – automatisch erkannt, manuell bestätigt oder ausgeblendet."""
from flask import Blueprint, redirect, render_template, request, url_for

from .. import auth
from ..db import exe, commit
from ..services import statistik, vertraege as vt
from . import melde

bp = Blueprint("vertraege", __name__, url_prefix="/vertraege")


@bp.route("/")
@auth.login_required
def index():
    konten = statistik.basis_konten(auth.sichtbare_konten())
    liste = vt.erkenne(konten)
    bestaetigt = [v for v in liste if v["art"] in ("fix", "abo")]
    erkannt = [v for v in liste if not v["art"]]
    summe = sum(v["monatlich"] or 0 for v in bestaetigt)
    return render_template("vertraege.html", bestaetigt=bestaetigt, erkannt=erkannt, summe_monat=summe,
                           summe_abo=sum(v["monatlich"] or 0 for v in bestaetigt if v["art"] == "abo"),
                           hinweise=[v for v in bestaetigt if v["aenderung"] or v["ausgeblieben"]])


@bp.route("/markieren", methods=["POST"])
@auth.schreibrecht
def markieren():
    key = request.form.get("partner_key", "")
    art = request.form.get("art")
    if not key:
        return redirect(url_for("vertraege.index"))
    if art in ("fix", "abo", "ignoriert"):
        exe("INSERT INTO vertrag (partner_key, name, art, notiz) VALUES (?,?,?,?) ON CONFLICT(partner_key) DO UPDATE "
            "SET art = excluded.art, name = COALESCE(excluded.name, vertrag.name), notiz = COALESCE(excluded.notiz, vertrag.notiz)",
            (key, request.form.get("name", "").strip() or None, art, request.form.get("notiz", "").strip() or None))
        melde({"fix": "Als Fixkosten markiert.", "abo": "Als Abo markiert.", "ignoriert": "Ausgeblendet."}[art])
    elif art == "zuruecksetzen":
        exe("DELETE FROM vertrag WHERE partner_key = ?", (key,))
        melde("Markierung entfernt.")
    commit()
    return redirect(url_for("vertraege.index"))
