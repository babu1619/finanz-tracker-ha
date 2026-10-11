"""SQLite-Zugriff und schlanke, versionierte Migrationen (migrations/NNN_name.sql)."""
import json
import sqlite3
from pathlib import Path

from flask import g

from . import config

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def connect(path=None) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path or config.DB_PATH), detect_types=0, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 15000")
    return conn


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = connect()
    return g.db


def close_db(_exc=None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def migrate(path=None) -> int:
    """Spielt alle noch nicht angewendeten Migrationen ein. Gibt die Schema-Version zurück."""
    config.ensure_dirs()
    conn = connect(path)
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
        row = conn.execute("SELECT version FROM schema_version").fetchone()
        current = row["version"] if row else 0
        if row is None:
            conn.execute("INSERT INTO schema_version (version) VALUES (0)")
            conn.commit()
        for f in sorted(MIGRATIONS_DIR.glob("*.sql")):
            num = int(f.name.split("_", 1)[0])
            if num <= current:
                continue
            # Fremdschlüssel aus, damit Tabellen-Neuaufbauten keine Kaskaden auslösen
            conn.execute("PRAGMA foreign_keys = OFF")
            try:
                conn.executescript("BEGIN;\n" + f.read_text(encoding="utf-8")
                                   + f"\nUPDATE schema_version SET version = {num};\nCOMMIT;")
            except Exception:
                if conn.in_transaction:
                    conn.rollback()
                raise
            fehler = conn.execute("PRAGMA foreign_key_check").fetchall()
            if fehler:
                raise RuntimeError(f"Migration {f.name}: Fremdschlüssel verletzt ({len(fehler)} Zeilen)")
            conn.execute("PRAGMA foreign_keys = ON")
            current = num
        return current
    finally:
        conn.close()


# ---------- kleine Helfer ----------

def q(sql, params=()):
    return get_db().execute(sql, params).fetchall()


def q1(sql, params=()):
    return get_db().execute(sql, params).fetchone()


def exe(sql, params=()):
    cur = get_db().execute(sql, params)
    return cur.lastrowid


def commit():
    get_db().commit()


def jload(value, default):
    if value in (None, ""):
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def jdump(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def einstellung(schluessel, default=None):
    row = q1("SELECT wert FROM einstellung WHERE schluessel = ?", (schluessel,))
    return row["wert"] if row else default


def setze_einstellung(schluessel, wert):
    exe("INSERT INTO einstellung (schluessel, wert) VALUES (?, ?) "
        "ON CONFLICT(schluessel) DO UPDATE SET wert = excluded.wert", (schluessel, wert))


def log_aenderung(benutzer_id, tabelle, datensatz_id, aktion, daten=None):
    exe("INSERT INTO aenderungslog (benutzer_id, tabelle, datensatz_id, aktion, daten) VALUES (?,?,?,?,?)",
        (benutzer_id, tabelle, datensatz_id, aktion, jdump(daten) if daten is not None else None))
