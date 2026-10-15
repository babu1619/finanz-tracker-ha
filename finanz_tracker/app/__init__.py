"""Finanz-Tracker – Haushaltsbuch für die Familie (Flask + SQLite)."""
import secrets
from datetime import timedelta

from flask import Flask, abort, g, render_template, request, session

from . import auth, config, db, util


def _aufraeumen():
    """Abgebrochene Import-Vorschauen und alte Backup-Kopien nach einem Tag entfernen."""
    import shutil
    import time
    grenze = time.time() - 86400
    for p in config.TMP_DIR.glob("*"):
        if p.name.startswith("profil_"):
            continue
        try:
            if p.stat().st_mtime < grenze:
                shutil.rmtree(p) if p.is_dir() else p.unlink()
        except OSError:
            pass


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=config.secret_key(),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=timedelta(days=config.SITZUNG_TAGE),
        MAX_CONTENT_LENGTH=20 * 1024 * 1024,
        SESSION_COOKIE_SECURE=config.HTTPS,
    )
    if test_config:
        app.config.update(test_config)

    db.migrate()
    _aufraeumen()
    app.teardown_appcontext(db.close_db)

    @app.before_request
    def vor_jeder_anfrage():
        auth.lade_benutzer()
        if "csrf" not in session:
            session["csrf"] = secrets.token_hex(16)
        if request.method == "POST" and not app.config.get("TESTING_NO_CSRF"):
            token = request.form.get("csrf") or request.headers.get("X-CSRF")
            if not token or not secrets.compare_digest(token, session["csrf"]):
                abort(400, description="Sicherheitsprüfung fehlgeschlagen. Bitte die Seite neu laden und erneut senden.")

    @app.context_processor
    def globale_werte():
        from .services import umbuchungen
        offen = None
        kuendigungen = []
        if g.get("user"):
            konten = auth.sichtbare_konten()
            if konten:
                marks = ",".join("?" * len(konten))
                r = db.q1(f"SELECT COUNT(*) AS n FROM buchung WHERE konto_id IN ({marks}) AND ist_umbuchung = 0 "
                          f"AND (kategorie_id IS NULL OR geprueft = 0)", konten)
                offen = {"pruefen": r["n"], "umbuchungen": len(umbuchungen.offene_vorschlaege(konten))}
            from .services import vertraege as _vt
            kuendigungen = _vt.faellige_kuendigungen()
        return {
            "csrf_token": session.get("csrf", ""),
            "user": g.get("user"),
            "darf_schreiben": auth.darf_schreiben(),
            "version": config.VERSION,
            "offen": offen,
            "kuendigungs_hinweise": kuendigungen,
            "https": config.HTTPS,
        }

    app.jinja_env.filters.update(
        euro=util.euro,
        euro_vz=lambda c: util.euro(c, vorzeichen=True),
        euro_rund=lambda c: util.euro(c, nachkomma=False),
        datum=util.datum_de,
        monat=util.monat_name,
        monat_kurz=util.monat_kurz,
        dict_ohne=lambda d, schluessel: {k: v for k, v in d.items() if k not in schluessel},
    )

    from .views import (auth_views, dashboard, buchungen, pruefen, kategorien, regeln, konten, importe, admin,
                        budgets, sparen, darlehen, auswertung, tags, vertraege, erfassen, pwa, depot)
    for bp in (auth_views.bp, dashboard.bp, buchungen.bp, pruefen.bp, kategorien.bp, regeln.bp,
               konten.bp, importe.bp, admin.bp, budgets.bp, sparen.bp, darlehen.bp, auswertung.bp, tags.bp,
               vertraege.bp, erfassen.bp, pwa.bp, depot.bp):
        app.register_blueprint(bp)

    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    def fehlerseite(e):
        texte = {400: "Ungültige Anfrage", 403: "Keine Berechtigung", 404: "Nicht gefunden"}
        return render_template("fehler.html", code=e.code, titel=texte.get(e.code, "Fehler"),
                               text=getattr(e, "description", "")), e.code

    return app
