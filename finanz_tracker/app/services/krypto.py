"""Krypto-Bestände (Bitcoin, Ethereum): Kurse abrufen, Wert und Verlauf berechnen.

Kurse kommen von der öffentlichen CoinGecko-API (ohne Schlüssel, nur Lesezugriff auf Marktdaten – es werden keine
eigenen Daten übertragen). Abgerufen wird jede Nacht um 4 Uhr und auf Knopfdruck. Gespeichert wird ein Kurs je Tag.
"""
import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone

from ..db import q, q1, exe, commit, einstellung, setze_einstellung

COINS = {"bitcoin": {"name": "Bitcoin", "kurz": "BTC", "farbe": "#C98A12"},
         "ethereum": {"name": "Ethereum", "kurz": "ETH", "farbe": "#3B6FB6"}}
API = "https://api.coingecko.com/api/v3"
ABRUF_STUNDE = 4
log = logging.getLogger(__name__)


def jetzt() -> datetime:
    """Ortszeit (Home Assistant setzt TZ für Add-ons; sonst Europe/Berlin)."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(os.environ.get("TZ") or "Europe/Berlin")).replace(tzinfo=None)
    except Exception:  # noqa: BLE001 – ohne Zeitzonendaten: Systemzeit
        return datetime.now()


def _hole(url: str, timeout=25):
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "finanz-tracker-ha"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 – feste https-Adresse
        return json.loads(r.read().decode("utf-8"))


def _speichere(coin: str, tag: str, preis_eur: float):
    exe("INSERT INTO krypto_kurs (coin, datum, preis_cent) VALUES (?,?,?) "
        "ON CONFLICT(coin, datum) DO UPDATE SET preis_cent = excluded.preis_cent", (coin, tag, round(preis_eur * 100)))


def abrufen(holer=None) -> dict:
    """Aktuelle Kurse und fehlenden Verlauf (bis 365 Tage) holen. holer: Funktion url -> JSON (für Tests)."""
    holer = holer or _hole
    zeit = jetzt()
    ergebnis = {"ok": True, "meldung": "", "neu": 0}
    try:
        for coin in COINS:
            letzter = q1("SELECT MAX(datum) AS d FROM krypto_kurs WHERE coin = ?", (coin,))["d"]
            tage = 365 if not letzter else min(365, max(2, (zeit.date() - date.fromisoformat(letzter)).days + 2))
            daten = holer(f"{API}/coins/{coin}/market_chart?vs_currency=eur&days={tage}&interval=daily")
            je_tag = {}
            for ms, preis in daten.get("prices", []):
                je_tag[datetime.fromtimestamp(ms / 1000, timezone.utc).date().isoformat()] = preis
            for tag, preis in je_tag.items():
                _speichere(coin, tag, preis)
            ergebnis["neu"] += len(je_tag)
        aktuell = holer(f"{API}/simple/price?ids={','.join(COINS)}&vs_currencies=eur")
        for coin in COINS:
            if coin in aktuell and "eur" in aktuell[coin]:
                _speichere(coin, zeit.date().isoformat(), aktuell[coin]["eur"])
        ergebnis["meldung"] = "Kurse aktualisiert"
    except (urllib.error.URLError, OSError, ValueError, KeyError, TypeError) as exc:
        ergebnis = {"ok": False, "meldung": f"Abruf fehlgeschlagen: {exc}", "neu": 0}
        log.warning("Krypto-Kurse: %s", exc)
    setze_einstellung("krypto_letzter_versuch", zeit.isoformat(timespec="minutes"))
    setze_einstellung("krypto_status", ergebnis["meldung"])
    if ergebnis["ok"]:
        setze_einstellung("krypto_letzter_abruf", zeit.isoformat(timespec="minutes"))
    commit()
    return ergebnis


def status() -> dict:
    return {"letzter_abruf": einstellung("krypto_letzter_abruf"), "letzter_versuch": einstellung("krypto_letzter_versuch"),
            "meldung": einstellung("krypto_status")}


def faellig(zeit: datetime | None = None) -> bool:
    """Nachts ab 4 Uhr einmal täglich; nach Fehlschlag höchstens alle 30 Minuten neu versuchen.
    Ohne jede Kursangabe sofort (damit neue Bestände gleich einen Wert haben)."""
    zeit = zeit or jetzt()
    if not q1("SELECT 1 FROM krypto WHERE menge > 0 LIMIT 1"):
        return False
    versuch = einstellung("krypto_letzter_versuch")
    if versuch and zeit - datetime.fromisoformat(versuch) < timedelta(minutes=30):
        return False
    if not q1("SELECT 1 FROM krypto_kurs LIMIT 1"):
        return True
    abruf = einstellung("krypto_letzter_abruf")
    heute_4 = zeit.replace(hour=ABRUF_STUNDE, minute=0, second=0, microsecond=0)
    if zeit < heute_4:
        return False
    return not abruf or datetime.fromisoformat(abruf) < heute_4


def starte_planer(app):
    """Hintergrund-Thread: prüft jede Minute, ob der nächtliche Abruf fällig ist."""
    def lauf():
        while True:
            try:
                with app.app_context():
                    if faellig():
                        abrufen()
            except Exception:  # noqa: BLE001 – der Planer darf nie abstürzen
                log.exception("Krypto-Planer")
            time.sleep(60)
    t = threading.Thread(target=lauf, name="krypto-planer", daemon=True)
    t.start()
    return t


# ---------------------------------------------------------------------------------------------------------------
# Bestände und Werte

def kurs(coin: str):
    return q1("SELECT * FROM krypto_kurs WHERE coin = ? ORDER BY datum DESC LIMIT 1", (coin,))


def kurs_am(coin: str, tag: str):
    return q1("SELECT * FROM krypto_kurs WHERE coin = ? AND datum <= ? ORDER BY datum DESC LIMIT 1", (coin, tag))


def bestaende(konten: list[int]) -> list[dict]:
    if not konten:
        return []
    marks = ",".join("?" * len(konten))
    erg = []
    for r in q(f"""SELECT k.id, k.name, k.aktiv, x.coin, x.menge, x.einstand_cent, x.im_vermoegen FROM konto k
                   JOIN krypto x ON x.konto_id = k.id WHERE k.id IN ({marks}) ORDER BY k.aktiv DESC, k.sortierung, k.name""",
                 list(konten)):
        akt = kurs(r["coin"])
        wert = round(r["menge"] * akt["preis_cent"]) if akt else None
        vortag = kurs_am(r["coin"], (date.fromisoformat(akt["datum"]) - timedelta(days=1)).isoformat()) if akt else None
        erg.append({**dict(r), "kurs": akt["preis_cent"] if akt else None, "kurs_datum": akt["datum"] if akt else None,
                    "wert": wert,
                    "gewinn": (wert - r["einstand_cent"]) if wert is not None and r["einstand_cent"] else None,
                    "aenderung_tag": ((akt["preis_cent"] / vortag["preis_cent"] - 1) * 100)
                    if akt and vortag and vortag["preis_cent"] and vortag["datum"] != akt["datum"] else None,
                    "coin_name": COINS[r["coin"]]["name"], "kurz": COINS[r["coin"]]["kurz"]})
    return erg


def wert(konto_id: int) -> int:
    """Wert eines Krypto-Kontos in Cent (für Kontenliste und Dashboard)."""
    r = q1("SELECT * FROM krypto WHERE konto_id = ?", (konto_id,))
    if not r:
        return 0
    akt = kurs(r["coin"])
    return round(r["menge"] * akt["preis_cent"]) if akt else 0


def im_vermoegen(konto_id: int) -> bool:
    r = q1("SELECT im_vermoegen FROM krypto WHERE konto_id = ?", (konto_id,))
    return bool(r and r["im_vermoegen"])


def verlauf(coin: str, tage: int | None, menge: float | None = None) -> dict:
    """Kursverlauf (oder Wert eines Bestands) für das Diagramm im Format der Diagramm-Bibliothek."""
    sql = "SELECT datum, preis_cent FROM krypto_kurs WHERE coin = ?"
    params: list = [coin]
    if tage:
        sql += " AND datum >= ?"
        params.append((jetzt().date() - timedelta(days=tage)).isoformat())
    rows = q(sql + " ORDER BY datum", params)
    werte = [round(r["preis_cent"] * (menge if menge is not None else 1)) for r in rows]
    return {"labels": [f"{r['datum'][8:10]}.{r['datum'][5:7]}.{r['datum'][2:4]}" for r in rows],
            "reihen": [{"id": coin, "name": COINS[coin]["name"] + (" (Bestand)" if menge is not None else " (Kurs)"),
                        "werte": werte}], "einheit": "€",
            "aenderung": ((werte[-1] / werte[0] - 1) * 100) if len(werte) > 1 and werte[0] else None}
