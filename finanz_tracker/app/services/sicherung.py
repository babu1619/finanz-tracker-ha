"""Verschlüsselte Sicherung und Wiederherstellung der Datenbank.

Format .ftbak: b"FTBAK1" + 16 Byte Salz + Fernet-Token (AES-128-CBC + HMAC-SHA256).
Der Schlüssel wird mit scrypt aus dem Passwort abgeleitet. Ohne Passwort ist die Datei nicht lesbar.
"""
import base64
import hashlib
import os
import sqlite3
import tempfile

from .. import config

MAGIC = b"FTBAK1"


class SicherungsFehler(ValueError):
    pass


def _schluessel(passwort: str, salz: bytes) -> bytes:
    roh = hashlib.scrypt(passwort.encode("utf-8"), salt=salz, n=2 ** 15, r=8, p=1, maxmem=64 * 1024 * 1024, dklen=32)
    return base64.urlsafe_b64encode(roh)


def _db_bytes() -> bytes:
    """Konsistente Kopie der laufenden Datenbank (SQLite-Backup-API)."""
    fd, pfad = tempfile.mkstemp(dir=config.TMP_DIR, suffix=".db")
    os.close(fd)
    try:
        quelle = sqlite3.connect(str(config.DB_PATH))
        ziel = sqlite3.connect(pfad)
        with ziel:
            quelle.backup(ziel)
        ziel.close()
        quelle.close()
        with open(pfad, "rb") as f:
            return f.read()
    finally:
        os.unlink(pfad)


def erstelle(passwort: str) -> bytes:
    from cryptography.fernet import Fernet
    if len(passwort or "") < 8:
        raise SicherungsFehler("Das Sicherungspasswort braucht mindestens 8 Zeichen.")
    salz = os.urandom(16)
    return MAGIC + salz + Fernet(_schluessel(passwort, salz)).encrypt(_db_bytes())


def entschluessele(daten: bytes, passwort: str) -> bytes:
    from cryptography.fernet import Fernet, InvalidToken
    if not daten.startswith(MAGIC) or len(daten) < len(MAGIC) + 17:
        raise SicherungsFehler("Keine Sicherungsdatei des Finanz-Trackers (.ftbak).")
    salz = daten[len(MAGIC):len(MAGIC) + 16]
    try:
        return Fernet(_schluessel(passwort, salz)).decrypt(daten[len(MAGIC) + 16:])
    except InvalidToken as exc:
        raise SicherungsFehler("Passwort falsch oder Datei beschädigt.") from exc


def stelle_wieder_her(daten: bytes, passwort: str) -> int:
    """Ersetzt die laufende Datenbank durch die Sicherung. Gibt die Schema-Version der Sicherung zurück."""
    roh = entschluessele(daten, passwort)
    fd, pfad = tempfile.mkstemp(dir=config.TMP_DIR, suffix=".db")
    with os.fdopen(fd, "wb") as f:
        f.write(roh)
    try:
        quelle = sqlite3.connect(pfad)
        try:
            if quelle.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise SicherungsFehler("Die Datenbank in der Sicherung ist beschädigt.")
            version = quelle.execute("SELECT version FROM schema_version").fetchone()[0]
            if not quelle.execute("SELECT 1 FROM benutzer WHERE rolle = 'admin' AND aktiv = 1").fetchone():
                raise SicherungsFehler("Die Sicherung enthält keinen aktiven Admin.")
        except sqlite3.DatabaseError as exc:
            raise SicherungsFehler("Die Sicherung enthält keine gültige Datenbank.") from exc
        ziel = sqlite3.connect(str(config.DB_PATH), timeout=30)
        with ziel:
            quelle.backup(ziel)
        ziel.close()
        quelle.close()
    finally:
        os.unlink(pfad)
    from ..db import migrate
    migrate()
    return version
