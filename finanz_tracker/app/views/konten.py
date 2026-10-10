from flask import Blueprint, abort, g, redirect, render_template, request, url_for

from .. import auth
from ..db import q, q1, exe, commit, log_aenderung
from ..services import importer
from ..util import parse_euro_eingabe, norm_iban
from . import melde, int_oder_none

bp = Blueprint("konten", __name__, url_prefix="/konten")

TYPEN = {"giro": "Girokonto", "tagesgeld": "Tagesgeld", "kreditkarte": "Kreditkarte", "bargeld": "Bargeld",
         "depot": "Depot (nur Saldo)", "darlehen": "Darlehen (eigener Bereich)", "sonstiges": "Sonstiges"}


@bp.route("/")
@auth.login_required
def liste():
    sichtbar = auth.sichtbare_konten()
    rows = []
    if sichtbar:
        marks = ",".join("?" * len(sichtbar))
        for k in q(f"""SELECT k.*, p.name AS eigentuemer, ip.name AS profil_name, kp.erkennungswert
                       FROM konto k LEFT JOIN person p ON p.id = k.eigentuemer_person_id
                       LEFT JOIN konto_importprofil kp ON kp.konto_id = k.id AND kp.rolle = 'buchungen'
                       LEFT JOIN importprofil ip ON ip.id = kp.importprofil_id
                       WHERE k.id IN ({marks}) ORDER BY k.typ = 'darlehen', k.aktiv DESC, k.sortierung, k.name""",
                   sichtbar):
            letzter = importer.letzter_import(k["id"])
            anzahl = q1("SELECT COUNT(*) AS n FROM buchung WHERE konto_id = ?", (k["id"],))["n"]
            rows.append({"k": k, "saldo": importer.kontostand(k["id"]), "letzter": letzter, "anzahl": anzahl,
                         "tage": importer.tage_seit(letzter["zeitpunkt"]) if letzter else None})
    summe = sum(r["saldo"] for r in rows if r["k"]["typ"] != "darlehen" and r["k"]["aktiv"])
    return render_template("konten.html", rows=rows, summe=summe, typen=TYPEN)


def _form(k=None, kp=None):
    return render_template("konto.html", k=k, kp=kp, typen=TYPEN,
                           personen=q("SELECT * FROM person WHERE aktiv = 1 ORDER BY name"),
                           profile=q("SELECT * FROM importprofil ORDER BY name"))


def _speichern(kid):
    f = request.form
    name = f.get("name", "").strip()
    if not name:
        melde("Name fehlt.", "warn")
        return None
    try:
        startsaldo = parse_euro_eingabe(f.get("startsaldo", "0"))
    except ValueError as exc:
        melde(str(exc), "warn")
        return None
    werte = (name, f.get("typ", "giro") if f.get("typ") in TYPEN else "giro", norm_iban(f.get("iban")),
             f.get("institut", "").strip() or None, int_oder_none(f.get("eigentuemer_person_id")),
             "privat" if f.get("sichtbarkeit") == "privat" else "alle", startsaldo,
             int_oder_none(f.get("import_erinnerung_tage")) or 7, 0 if f.get("aktiv") == "0" else 1)
    if kid:
        exe("UPDATE konto SET name=?, typ=?, iban=?, institut=?, eigentuemer_person_id=?, sichtbarkeit=?, "
            "startsaldo_cent=?, import_erinnerung_tage=?, aktiv=? WHERE id = ?", (*werte, kid))
    else:
        kid = exe("INSERT INTO konto (name, typ, iban, institut, eigentuemer_person_id, sichtbarkeit, startsaldo_cent, "
                  "import_erinnerung_tage, aktiv) VALUES (?,?,?,?,?,?,?,?,?)", werte)
    profil_id = int_oder_none(f.get("importprofil_id"))
    exe("DELETE FROM konto_importprofil WHERE konto_id = ? AND rolle = 'buchungen'", (kid,))
    if profil_id:
        exe("INSERT INTO konto_importprofil (konto_id, importprofil_id, rolle, erkennungswert) VALUES (?,?,?,?)",
            (kid, profil_id, "buchungen", f.get("erkennungswert", "").strip() or None))
    log_aenderung(g.user["id"], "konto", kid, "gespeichert", dict(f))
    commit()
    return kid


@bp.route("/neu", methods=["GET", "POST"])
@auth.admin_required
def neu():
    if request.method == "POST":
        if _speichern(None):
            melde("Konto angelegt.")
            return redirect(url_for("konten.liste"))
    return _form()


@bp.route("/<int:kid>", methods=["GET", "POST"])
@auth.admin_required
def bearbeiten(kid):
    k = q1("SELECT * FROM konto WHERE id = ?", (kid,))
    if not k:
        abort(404)
    if request.method == "POST":
        if request.form.get("aktion") == "loeschen":
            if q1("SELECT 1 FROM buchung WHERE konto_id = ? LIMIT 1", (kid,)):
                melde("Konto hat Buchungen und kann nicht gelöscht werden. Stattdessen deaktivieren.", "warn")
                return redirect(url_for("konten.bearbeiten", kid=kid))
            exe("DELETE FROM konto WHERE id = ?", (kid,))
            commit()
            melde("Konto gelöscht.")
            return redirect(url_for("konten.liste"))
        if _speichern(kid):
            melde("Konto gespeichert.")
            return redirect(url_for("konten.liste"))
    kp = q1("SELECT * FROM konto_importprofil WHERE konto_id = ? AND rolle = 'buchungen'", (kid,))
    return _form(k, kp)
