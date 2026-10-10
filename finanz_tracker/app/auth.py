"""Anmeldung, Rollen, Passwort-Hashing (scrypt aus der Standardbibliothek) und Kontosichtbarkeit."""
import base64
import hashlib
import hmac
import secrets
import time
from functools import wraps

from flask import abort, g, redirect, request, session, url_for

from . import config
from .db import q, q1

_FEHLVERSUCHE: dict[str, tuple[int, float]] = {}

ROLLEN = {"admin": "Admin", "mitglied": "Mitglied", "lesend": "Lesend"}


def hash_passwort(passwort: str) -> str:
    salt = secrets.token_bytes(16)
    n, r, p = 2 ** 14, 8, 1
    h = hashlib.scrypt(passwort.encode(), salt=salt, n=n, r=r, p=p, dklen=32)
    return f"scrypt${n}${r}${p}${base64.b64encode(salt).decode()}${base64.b64encode(h).decode()}"


def pruefe_passwort(passwort: str, gespeichert: str) -> bool:
    try:
        verfahren, n, r, p, salt, h = gespeichert.split("$")
        if verfahren != "scrypt":
            return False
        neu = hashlib.scrypt(passwort.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(neu, base64.b64decode(h))
    except (ValueError, TypeError):
        return False


def gesperrt_bis(name: str) -> float | None:
    eintrag = _FEHLVERSUCHE.get(name.lower())
    if eintrag and eintrag[0] >= config.LOGIN_MAX_FEHLVERSUCHE and eintrag[1] > time.time():
        return eintrag[1]
    return None


def fehlversuch(name: str):
    anzahl, _ = _FEHLVERSUCHE.get(name.lower(), (0, 0))
    _FEHLVERSUCHE[name.lower()] = (anzahl + 1, time.time() + config.LOGIN_SPERRE_MINUTEN * 60)


def erfolg(name: str):
    _FEHLVERSUCHE.pop(name.lower(), None)


def lade_benutzer():
    g.user = None
    uid = session.get("uid")
    if uid:
        u = q1("SELECT b.*, p.name AS person_name FROM benutzer b LEFT JOIN person p ON p.id = b.person_id "
               "WHERE b.id = ? AND b.aktiv = 1", (uid,))
        if u and session.get("pw") == u["passwort_hash"][-12:]:
            g.user = u
        else:
            session.clear()


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not q1("SELECT 1 FROM benutzer LIMIT 1"):
            return redirect(url_for("auth.einrichtung"))
        if g.user is None:
            return redirect(url_for("auth.login", next=request.full_path if request.method == "GET" else None))
        return view(*args, **kwargs)
    return wrapper


def schreibrecht(view):
    @wraps(view)
    @login_required
    def wrapper(*args, **kwargs):
        if g.user["rolle"] == "lesend":
            abort(403)
        return view(*args, **kwargs)
    return wrapper


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapper(*args, **kwargs):
        if g.user["rolle"] != "admin":
            abort(403)
        return view(*args, **kwargs)
    return wrapper


def darf_schreiben() -> bool:
    return g.get("user") is not None and g.user["rolle"] in ("admin", "mitglied")


def sichtbare_konten(nur_aktive=False, mit_darlehen=True) -> list[int]:
    """Admins sehen alles; sonst gemeinsame Konten und private Konten der eigenen Person."""
    u = g.user
    sql = "SELECT id FROM konto WHERE 1=1"
    params: list = []
    if nur_aktive:
        sql += " AND aktiv = 1"
    if not mit_darlehen:
        sql += " AND typ != 'darlehen'"
    if u["rolle"] != "admin":
        sql += " AND (sichtbarkeit = 'alle' OR eigentuemer_person_id = ?)"
        params.append(u["person_id"] or -1)
    return [r["id"] for r in q(sql, params)]


def konto_sichtbar(konto_id) -> bool:
    return int(konto_id) in sichtbare_konten()
