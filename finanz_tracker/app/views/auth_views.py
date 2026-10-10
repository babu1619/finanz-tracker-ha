from flask import Blueprint, g, redirect, render_template, request, session, url_for

from .. import auth
from ..db import q1, exe, commit, log_aenderung
from ..services import kategorien
from . import melde

bp = Blueprint("auth", __name__)


def _anmelden(u):
    session.clear()
    session.permanent = True
    session["uid"] = u["id"]
    session["pw"] = u["passwort_hash"][-12:]


@bp.route("/einrichtung", methods=["GET", "POST"])
def einrichtung():
    if q1("SELECT 1 FROM benutzer LIMIT 1"):
        return redirect(url_for("dashboard.index"))
    fehler = None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        person = request.form.get("person", "").strip() or name
        pw, pw2 = request.form.get("passwort", ""), request.form.get("passwort2", "")
        if not name or len(pw) < 8:
            fehler = "Benutzername angeben und ein Passwort mit mindestens 8 Zeichen wählen."
        elif pw != pw2:
            fehler = "Die Passwörter stimmen nicht überein."
        else:
            pid = exe("INSERT INTO person (name) VALUES (?)", (person,))
            exe("INSERT INTO person (name) VALUES ('Familie')")
            uid = exe("INSERT INTO benutzer (name, passwort_hash, rolle, person_id) VALUES (?,?,?,?)",
                      (name, auth.hash_passwort(pw), "admin", pid))
            if request.form.get("startset"):
                kategorien.lege_startset_an()
            commit()
            _anmelden(q1("SELECT * FROM benutzer WHERE id = ?", (uid,)))
            melde("Willkommen! Als Nächstes Konten anlegen und ein Importprofil einrichten.")
            return redirect(url_for("konten.liste"))
    return render_template("einrichtung.html", fehler=fehler)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if not q1("SELECT 1 FROM benutzer LIMIT 1"):
        return redirect(url_for("auth.einrichtung"))
    fehler = None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if auth.gesperrt_bis(name):
            fehler = "Zu viele Fehlversuche. Bitte später erneut versuchen."
        else:
            u = q1("SELECT * FROM benutzer WHERE name = ? AND aktiv = 1", (name,))
            if u and auth.pruefe_passwort(request.form.get("passwort", ""), u["passwort_hash"]):
                auth.erfolg(name)
                _anmelden(u)
                ziel = request.args.get("next") or ""
                if not ziel.startswith("/") or ziel.startswith("//"):
                    ziel = url_for("dashboard.index")
                return redirect(ziel)
            auth.fehlversuch(name)
            fehler = "Benutzername oder Passwort falsch."
    return render_template("login.html", fehler=fehler)


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@bp.route("/passwort", methods=["GET", "POST"])
@auth.login_required
def passwort():
    fehler = None
    if request.method == "POST":
        alt, neu, neu2 = (request.form.get(x, "") for x in ("alt", "neu", "neu2"))
        if not auth.pruefe_passwort(alt, g.user["passwort_hash"]):
            fehler = "Das bisherige Passwort stimmt nicht."
        elif len(neu) < 8 or neu != neu2:
            fehler = "Das neue Passwort braucht mindestens 8 Zeichen und muss zweimal gleich eingegeben werden."
        else:
            h = auth.hash_passwort(neu)
            exe("UPDATE benutzer SET passwort_hash = ? WHERE id = ?", (h, g.user["id"]))
            log_aenderung(g.user["id"], "benutzer", g.user["id"], "passwort")
            commit()
            session["pw"] = h[-12:]
            melde("Passwort geändert.")
            return redirect(url_for("dashboard.index"))
    return render_template("passwort.html", fehler=fehler)
