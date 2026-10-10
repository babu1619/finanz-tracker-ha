"""Start: python -m app  (Migrationen laufen beim Start automatisch)."""
import json
import logging

from . import config, create_app

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def notfall_passwort():
    """Home-Assistant-Option 'admin_passwort_reset': setzt das Passwort des ersten Admins zurück."""
    opt_datei = config.DATA_DIR / "options.json"
    if not opt_datei.exists():
        return
    try:
        neu = (json.loads(opt_datei.read_text()) or {}).get("admin_passwort_reset") or ""
    except (OSError, ValueError):
        return
    if not neu:
        return
    if len(neu) < 8:
        logging.warning("admin_passwort_reset ignoriert: mindestens 8 Zeichen nötig")
        return
    from .auth import hash_passwort
    from .db import connect
    conn = connect()
    try:
        admin = conn.execute("SELECT id, name FROM benutzer WHERE rolle = 'admin' ORDER BY id LIMIT 1").fetchone()
        if admin:
            conn.execute("UPDATE benutzer SET passwort_hash = ?, aktiv = 1 WHERE id = ?", (hash_passwort(neu), admin["id"]))
            conn.commit()
            logging.warning("Passwort von Admin '%s' wurde zurückgesetzt. Bitte die Option "
                            "'admin_passwort_reset' jetzt wieder leeren!", admin["name"])
    finally:
        conn.close()


def main():
    app = create_app()
    notfall_passwort()
    logging.info("Finanz-Tracker %s startet auf Port %s, Daten in %s", config.VERSION, config.PORT, config.DATA_DIR)
    try:
        from waitress import serve
    except ImportError:  # Entwicklung ohne waitress
        logging.warning("waitress nicht installiert – nutze den Flask-Entwicklungsserver")
        app.run(host="0.0.0.0", port=config.PORT)
        return
    serve(app, host="0.0.0.0", port=config.PORT, threads=4)


if __name__ == "__main__":
    main()
