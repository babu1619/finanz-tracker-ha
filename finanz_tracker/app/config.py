"""Grundeinstellungen. Im Home-Assistant-Add-on liegt alles Persistente unter /data."""
import os
import secrets
from pathlib import Path

VERSION = "0.5.0"

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
DB_PATH = DATA_DIR / "finanz.db"
TMP_DIR = DATA_DIR / "tmp"
PORT = int(os.environ.get("PORT", "8080"))
HTTPS = False  # wird beim Start gesetzt (siehe __main__ / tls.py)

# Login-Schutz
LOGIN_MAX_FEHLVERSUCHE = 5
LOGIN_SPERRE_MINUTEN = 15
SITZUNG_TAGE = 30

# Umbuchungserkennung
UMBUCHUNG_FENSTER_TAGE = 3
UMBUCHUNG_FENSTER_KREDITKARTE_TAGE = 10
UMBUCHUNG_AUTO_SCHWELLE = 0.8


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)


def secret_key() -> str:
    """Zufälliger Schlüssel für Sitzungs-Cookies, einmalig erzeugt und in /data gespeichert."""
    ensure_dirs()
    path = DATA_DIR / "secret_key"
    if not path.exists():
        path.write_text(secrets.token_hex(32))
        try:
            path.chmod(0o600)
        except OSError:
            pass
    return path.read_text().strip()
