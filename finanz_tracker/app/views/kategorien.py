from flask import Blueprint, abort, g, redirect, render_template, request, url_for

from .. import auth
from ..db import q, q1, exe, commit, log_aenderung
from ..services import kategorien, statistik
from . import melde, monat_param, int_oder_none

bp = Blueprint("kategorien", __name__, url_prefix="/kategorien")


@bp.route("/")
@auth.login_required
def liste():
    monat = monat_param()
    konten = statistik.basis_konten(auth.sichtbare_konten())
    summen = statistik.summen_je_kategorie(konten, monat)
    anzahl = {r["kategorie_id"]: r["n"] for r in q("SELECT kategorie_id, COUNT(*) AS n FROM buchung "
                                                    "WHERE kategorie_id IS NOT NULL GROUP BY kategorie_id")}
    return render_template("kategorien.html", kategorien=kategorien.alle(), summen=summen, anzahl=anzahl, monat=monat)


@bp.route("/neu", methods=["POST"])
@auth.schreibrecht
def neu():
    name = request.form.get("name", "").strip()
    if not name:
        melde("Name fehlt.", "warn")
    else:
        kid = kategorien.anlegen(name, int_oder_none(request.form.get("parent_id")), request.form.get("art") or None)
        log_aenderung(g.user["id"], "kategorie", kid, "angelegt", {"name": name})
        commit()
        melde(f"Kategorie „{name}“ angelegt.")
    return redirect(url_for("kategorien.liste"))


@bp.route("/<int:kid>", methods=["GET", "POST"])
@auth.schreibrecht
def bearbeiten(kid):
    k = q1("SELECT * FROM kategorie WHERE id = ?", (kid,))
    if not k:
        abort(404)
    if request.method == "POST":
        if request.form.get("aktion") == "loeschen":
            if q1("SELECT 1 FROM kategorie WHERE parent_id = ?", (kid,)):
                melde("Kategorie hat Unterkategorien – erst diese verschieben oder löschen.", "warn")
                return redirect(url_for("kategorien.bearbeiten", kid=kid))
            ziel = int_oder_none(request.form.get("ziel_id"))
            exe("UPDATE buchung SET kategorie_id = ? WHERE kategorie_id = ?", (ziel, kid))
            exe("UPDATE buchung_split SET kategorie_id = ? WHERE kategorie_id = ?", (ziel, kid))
            exe("UPDATE budget SET aktiv = 0 WHERE kategorie_id = ?", (kid,))
            exe("DELETE FROM kategorie WHERE id = ?", (kid,))
            log_aenderung(g.user["id"], "kategorie", kid, "geloescht", {"ziel": ziel})
            commit()
            melde(f"Kategorie „{k['name']}“ gelöscht.")
            return redirect(url_for("kategorien.liste"))
        try:
            kategorien.aktualisiere(kid, request.form.get("name", k["name"]), int_oder_none(request.form.get("parent_id")),
                                    request.form.get("art") or None)
            log_aenderung(g.user["id"], "kategorie", kid, "geaendert", dict(request.form))
            commit()
            melde("Kategorie gespeichert.")
            return redirect(url_for("kategorien.liste"))
        except ValueError as exc:
            melde(str(exc), "warn")
    alle = kategorien.alle()
    gesperrt = set(kategorien.nachkommen_ids(kid))
    n = q1("SELECT COUNT(*) AS n FROM buchung WHERE kategorie_id = ?", (kid,))["n"]
    return render_template("kategorie.html", k=k, kategorien=alle, gesperrt=gesperrt, anzahl=n)
