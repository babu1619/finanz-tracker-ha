from flask import Blueprint, abort, g, redirect, render_template, request, url_for

from .. import auth
from ..db import q, q1, exe, commit, log_aenderung
from ..services import budgets, kategorien, statistik
from ..util import ist_monat, monat_plus, parse_euro_eingabe
from . import melde, monat_param, int_oder_none

bp = Blueprint("budgets", __name__, url_prefix="/budgets")


@bp.route("/")
@auth.login_required
def index():
    monat = monat_param()
    konten = statistik.basis_konten(auth.sichtbare_konten())
    ue = budgets.uebersicht(konten, monat)
    return render_template("budgets.html", monat=monat, vor=monat_plus(monat, -1), nach=monat_plus(monat, 1), ue=ue,
                           vorschlaege=budgets.vorschlaege_ohne_budget(konten, monat) if auth.darf_schreiben() else [],
                           kategorien=kategorien.alle(), personen=q("SELECT * FROM person WHERE aktiv = 1 ORDER BY name"))


def _werte():
    f = request.form
    kat = int_oder_none(f.get("kategorie_id"))
    if not kat:
        raise ValueError("Bitte eine Kategorie wählen.")
    betrag = abs(parse_euro_eingabe(f.get("betrag", "")))
    if betrag <= 0:
        raise ValueError("Bitte einen Betrag größer 0 eingeben.")
    ab = f.get("gueltig_ab", "")
    if not ist_monat(ab):
        ab = monat_param()
    schwelle = int_oder_none(f.get("warnschwelle")) or 90
    return (kat, int_oder_none(f.get("person_id")), betrag, "jahr" if f.get("rhythmus") == "jahr" else "monat", ab,
            1 if f.get("uebertrag") else 0, max(50, min(100, schwelle)))


@bp.route("/neu", methods=["POST"])
@auth.schreibrecht
def neu():
    try:
        w = _werte()
    except ValueError as exc:
        melde(str(exc), "warn")
        return redirect(url_for("budgets.index", monat=request.form.get("monat")))
    if q1("SELECT 1 FROM budget WHERE kategorie_id = ? AND COALESCE(person_id, 0) = COALESCE(?, 0) AND aktiv = 1", (w[0], w[1])):
        melde("Für diese Kategorie (und Person) gibt es schon ein Budget – bitte dort ändern.", "warn")
        return redirect(url_for("budgets.index", monat=request.form.get("monat")))
    bid = exe("INSERT INTO budget (kategorie_id, person_id, betrag_cent, rhythmus, gueltig_ab, uebertrag, warnschwelle) "
              "VALUES (?,?,?,?,?,?,?)", w)
    log_aenderung(g.user["id"], "budget", bid, "angelegt", dict(request.form))
    commit()
    melde("Budget angelegt.")
    return redirect(url_for("budgets.index", monat=request.form.get("monat")))


@bp.route("/<int:bid>", methods=["GET", "POST"])
@auth.schreibrecht
def bearbeiten(bid):
    b = q1("SELECT b.*, k.pfad FROM budget b JOIN kategorie k ON k.id = b.kategorie_id WHERE b.id = ?", (bid,))
    if not b:
        abort(404)
    if request.method == "POST":
        if request.form.get("aktion") == "loeschen":
            exe("DELETE FROM budget WHERE id = ?", (bid,))
            melde("Budget gelöscht.")
        else:
            try:
                w = _werte()
            except ValueError as exc:
                melde(str(exc), "warn")
                return redirect(url_for("budgets.bearbeiten", bid=bid))
            exe("UPDATE budget SET kategorie_id=?, person_id=?, betrag_cent=?, rhythmus=?, gueltig_ab=?, uebertrag=?, "
                "warnschwelle=? WHERE id = ?", (*w, bid))
            melde("Budget gespeichert.")
        log_aenderung(g.user["id"], "budget", bid, request.form.get("aktion") or "gespeichert", dict(request.form))
        commit()
        return redirect(url_for("budgets.index"))
    return render_template("budget.html", b=b, kategorien=kategorien.alle(),
                           personen=q("SELECT * FROM person WHERE aktiv = 1 ORDER BY name"))


@bp.route("/vorschlaege", methods=["POST"])
@auth.schreibrecht
def vorschlaege_uebernehmen():
    monat = monat_param()
    konten = statistik.basis_konten(auth.sichtbare_konten())
    gewaehlt = {int(i) for i in request.form.getlist("kat") if i.isdigit()}
    n = 0
    for v in budgets.vorschlaege_ohne_budget(konten, monat):
        if v["k"]["id"] in gewaehlt:
            exe("INSERT INTO budget (kategorie_id, betrag_cent, rhythmus, gueltig_ab, uebertrag) VALUES (?,?,?,?,0)",
                (v["k"]["id"], v["vorschlag"], "monat", monat))
            n += 1
    commit()
    melde(f"{n} Budgets aus dem Durchschnitt der letzten 6 Monate angelegt.")
    return redirect(url_for("budgets.index", monat=monat))
