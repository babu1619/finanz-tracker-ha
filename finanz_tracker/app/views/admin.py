import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

from flask import Blueprint, abort, g, redirect, render_template, request, send_file, url_for

from .. import auth, config
from ..db import q, q1, exe, commit, log_aenderung
from . import melde, int_oder_none

bp = Blueprint("admin", __name__, url_prefix="/verwaltung")


@bp.route("/")
@auth.admin_required
def index():
    benutzer = q("SELECT b.*, p.name AS person_name FROM benutzer b LEFT JOIN person p ON p.id = b.person_id ORDER BY b.name")
    personen = q("""SELECT p.*, (SELECT COUNT(*) FROM buchung WHERE person_id = p.id) AS n,
                           (SELECT name FROM benutzer WHERE person_id = p.id LIMIT 1) AS login
                    FROM person p ORDER BY p.aktiv DESC, p.name""")
    groesse = config.DB_PATH.stat().st_size if config.DB_PATH.exists() else 0
    return render_template("verwaltung.html", benutzer=benutzer, personen=personen, rollen=auth.ROLLEN,
                           groesse=groesse, data_dir=str(config.DATA_DIR))


@bp.route("/benutzer", methods=["POST"])
@auth.admin_required
def benutzer():
    f = request.form
    bid = int_oder_none(f.get("id"))
    rolle = f.get("rolle") if f.get("rolle") in auth.ROLLEN else "mitglied"
    person_id = int_oder_none(f.get("person_id"))
    if f.get("aktion") == "neu":
        name, pw = f.get("name", "").strip(), f.get("passwort", "")
        if not name or len(pw) < 8:
            melde("Benutzername und Passwort (mindestens 8 Zeichen) angeben.", "warn")
        elif q1("SELECT 1 FROM benutzer WHERE name = ?", (name,)):
            melde("Diesen Benutzernamen gibt es schon.", "warn")
        else:
            if not person_id and f.get("neue_person"):
                person_id = exe("INSERT INTO person (name) VALUES (?)", (name,))
            bid = exe("INSERT INTO benutzer (name, passwort_hash, rolle, person_id) VALUES (?,?,?,?)",
                      (name, auth.hash_passwort(pw), rolle, person_id))
            log_aenderung(g.user["id"], "benutzer", bid, "angelegt", {"name": name, "rolle": rolle})
            melde(f"Benutzer „{name}“ angelegt.")
    elif bid:
        u = q1("SELECT * FROM benutzer WHERE id = ?", (bid,))
        if not u:
            abort(404)
        admins = q1("SELECT COUNT(*) AS n FROM benutzer WHERE rolle = 'admin' AND aktiv = 1")["n"]
        aktiv = 0 if f.get("aktiv") == "0" else 1
        if u["rolle"] == "admin" and admins <= 1 and (rolle != "admin" or not aktiv):
            melde("Es muss mindestens ein aktiver Admin bleiben.", "warn")
        else:
            exe("UPDATE benutzer SET rolle = ?, person_id = ?, aktiv = ? WHERE id = ?", (rolle, person_id, aktiv, bid))
            if f.get("passwort"):
                if len(f["passwort"]) < 8:
                    melde("Neues Passwort braucht mindestens 8 Zeichen.", "warn")
                else:
                    exe("UPDATE benutzer SET passwort_hash = ? WHERE id = ?", (auth.hash_passwort(f["passwort"]), bid))
            log_aenderung(g.user["id"], "benutzer", bid, "geaendert", {"rolle": rolle, "aktiv": aktiv})
            melde(f"Benutzer „{u['name']}“ gespeichert.")
    commit()
    return redirect(url_for("admin.index"))


@bp.route("/person", methods=["POST"])
@auth.admin_required
def person():
    f = request.form
    pid = int_oder_none(f.get("id"))
    name = f.get("name", "").strip()
    if pid:
        exe("UPDATE person SET name = ?, aktiv = ? WHERE id = ?", (name or "Person", 0 if f.get("aktiv") == "0" else 1, pid))
    elif name:
        exe("INSERT INTO person (name) VALUES (?)", (name,))
    commit()
    melde("Person gespeichert.")
    return redirect(url_for("admin.index"))


@bp.route("/backup")
@auth.admin_required
def backup():
    """Konsistente Kopie der Datenbank (SQLite-Backup-API) zum Herunterladen."""
    ziel = Path(tempfile.mkdtemp(dir=config.TMP_DIR)) / f"finanz-backup-{datetime.now():%Y%m%d-%H%M}.db"
    quelle = sqlite3.connect(str(config.DB_PATH))
    kopie = sqlite3.connect(str(ziel))
    with kopie:
        quelle.backup(kopie)
    quelle.close()
    kopie.close()
    log_aenderung(g.user["id"], "system", None, "backup")
    commit()
    return send_file(ziel, as_attachment=True, download_name=ziel.name)


@bp.route("/sicherung", methods=["POST"])
@auth.admin_required
def sicherung():
    from flask import Response
    from ..services import sicherung as sich
    try:
        daten = sich.erstelle(request.form.get("passwort", ""))
    except sich.SicherungsFehler as exc:
        melde(str(exc), "warn")
        return redirect(url_for("admin.index"))
    log_aenderung(g.user["id"], "system", None, "sicherung_verschluesselt")
    commit()
    return Response(daten, mimetype="application/octet-stream",
                    headers={"Content-Disposition": f"attachment; filename=finanz-{datetime.now():%Y%m%d-%H%M}.ftbak"})


@bp.route("/wiederherstellen", methods=["POST"])
@auth.admin_required
def wiederherstellen():
    from flask import session
    from ..db import close_db
    from ..services import sicherung as sich
    datei = request.files.get("datei")
    if not datei:
        melde("Bitte eine Sicherungsdatei wählen.", "warn")
        return redirect(url_for("admin.index"))
    daten = datei.read()
    try:
        sich.entschluessele(daten, request.form.get("passwort", ""))  # erst prüfen, dann den aktuellen Stand sichern
    except sich.SicherungsFehler as exc:
        melde(str(exc), "bad")
        return redirect(url_for("admin.index"))
    vorher = config.DATA_DIR / f"vor-wiederherstellung-{datetime.now():%Y%m%d-%H%M%S}.db"
    quelle = sqlite3.connect(str(config.DB_PATH))
    kopie = sqlite3.connect(str(vorher))
    with kopie:
        quelle.backup(kopie)
    quelle.close()
    kopie.close()
    close_db()
    try:
        sich.stelle_wieder_her(daten, request.form.get("passwort", ""))
    except sich.SicherungsFehler as exc:
        melde(str(exc), "bad")
        return redirect(url_for("admin.index"))
    session.clear()
    melde(f"Sicherung wiederhergestellt. Der vorherige Stand liegt als {vorher.name} im Datenordner. Bitte neu anmelden.")
    return redirect(url_for("auth.login"))
