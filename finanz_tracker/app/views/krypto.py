"""Krypto: Bestände, aktueller Wert, Kursverlauf; Abruf nachts um 4 Uhr oder auf Knopfdruck."""
from flask import Blueprint, abort, jsonify, redirect, render_template, request, url_for

from .. import auth
from ..services import krypto
from . import melde, int_oder_none

bp = Blueprint("krypto", __name__, url_prefix="/krypto")

ZEITRAEUME = {"7": "7 Tage", "30": "30 Tage", "90": "3 Monate", "180": "6 Monate", "365": "1 Jahr", "alle": "alles"}


@bp.route("/")
@auth.login_required
def index():
    bestaende = krypto.bestaende(auth.sichtbare_konten())
    aktiv = [b for b in bestaende if b["aktiv"]]
    return render_template("krypto.html", bestaende=bestaende, coins=krypto.COINS, status=krypto.status(),
                           summe=sum(b["wert"] or 0 for b in aktiv),
                           summe_vermoegen=sum(b["wert"] or 0 for b in aktiv if b["im_vermoegen"]),
                           einstand=sum(b["einstand_cent"] or 0 for b in aktiv if b["einstand_cent"]),
                           gewinn=sum(b["gewinn"] for b in aktiv if b["gewinn"] is not None),
                           zeitraeume=ZEITRAEUME, kurse={c: krypto.kurs(c) for c in krypto.COINS})


@bp.route("/verlauf")
@auth.login_required
def verlauf():
    coin = request.args.get("coin", "bitcoin")
    if coin not in krypto.COINS:
        abort(404)
    tage = None if request.args.get("tage") == "alle" else (int_oder_none(request.args.get("tage")) or 365)
    menge = None
    kid = int_oder_none(request.args.get("bestand"))
    if kid:
        b = next((x for x in krypto.bestaende(auth.sichtbare_konten()) if x["id"] == kid), None)
        if not b:
            abort(404)
        coin, menge = b["coin"], b["menge"]
    return jsonify(krypto.verlauf(coin, tage, menge))


@bp.route("/abrufen", methods=["POST"])
@auth.schreibrecht
def abrufen():
    erg = krypto.abrufen()
    melde(erg["meldung"] + (f" ({erg['neu']} Tageskurse)" if erg["ok"] else ""), "ok" if erg["ok"] else "warn")
    return redirect(url_for("krypto.index"))
