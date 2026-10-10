"""Importablauf: Datei lesen, Duplikate erkennen, Vorschau, übernehmen, Saldo abgleichen, rückgängig machen."""
import hashlib
import json
import secrets
from datetime import date

from .. import config
from ..db import q, q1, exe, jload, jdump
from ..util import partner_key, monat_von, norm_text, norm_iban
from . import csvimport, zuordnung, umbuchungen


def profil_dict(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "format": row["format"],
        "einstellungen": jload(row["einstellungen"], {}),
        "spalten": jload(row["spalten"], []),
        "betrag_modus": row["betrag_modus"],
        "beispiel": jload(row["beispiel"], []),
    }


def profil_fuer_konto(konto_id):
    r = q1("SELECT p.* FROM konto_importprofil kp JOIN importprofil p ON p.id = kp.importprofil_id "
           "WHERE kp.konto_id = ? AND kp.rolle = 'buchungen' AND kp.aktiv = 1", (konto_id,))
    return profil_dict(r) if r else None


def erkenne_konto(raw: bytes):
    """Konto über IBAN im Dateikopf oder hinterlegten Erkennungswert finden."""
    ibans = csvimport.finde_ibans(raw)
    if not ibans:
        return None
    for k in q("SELECT id, iban FROM konto WHERE aktiv = 1 AND iban IS NOT NULL"):
        if norm_iban(k["iban"]) in ibans:
            return k["id"]
    for kp in q("SELECT konto_id, erkennungswert FROM konto_importprofil WHERE erkennungswert IS NOT NULL"):
        w = norm_iban(kp["erkennungswert"])
        if w and any(i.endswith(w) or w in i for i in ibans):
            return kp["konto_id"]
    return None


def _dedup_hash(konto_id, d) -> str:
    teile = [str(konto_id), d["buchungsdatum"].isoformat(), str(d["betrag_cent"]), d.get("gegen_iban") or "",
             norm_text(d["verwendungszweck"])[:140], norm_text(d["gegenpartei"])[:80]]
    return "|".join(teile)


def vorbereiten(konto_id, raw: bytes, dateiname: str) -> dict:
    """Liest die Datei, markiert Duplikate. Speichert die Datei temporär für den zweiten Schritt."""
    profil = profil_fuer_konto(konto_id)
    if not profil:
        raise csvimport.ProfilFehler("Diesem Konto ist noch kein Importprofil zugewiesen.")
    if profil["format"] != "csv":
        raise csvimport.ProfilFehler(f"Das Profil „{profil['name']}“ ist kein CSV-Profil; "
                                     "dieser Importweg ist in v1 noch nicht verfügbar.")
    erg = csvimport.lese_datei(raw, profil)
    vorhanden = {r["dedup_hash"] for r in q("SELECT dedup_hash FROM buchung WHERE konto_id = ?", (konto_id,))}
    zaehler: dict[str, int] = {}
    zeilen = []
    for d in erg["datensaetze"]:
        basis = _dedup_hash(konto_id, d)
        n = zaehler.get(basis, 0)
        zaehler[basis] = n + 1
        h = hashlib.sha256(f"{basis}#{n}".encode()).hexdigest()
        d["dedup_hash"] = h
        d["status"] = "doppelt" if h in vorhanden else "neu"
        zeilen.append(d)
    token = secrets.token_hex(12)
    (config.TMP_DIR / f"{token}.bin").write_bytes(raw)
    (config.TMP_DIR / f"{token}.json").write_text(json.dumps({"konto_id": konto_id, "dateiname": dateiname}))
    return {
        "token": token,
        "profil": profil,
        "zeilen": zeilen,
        "fehler": erg["fehler"],
        "hinweise": erg["hinweise"],
        "neu": sum(1 for z in zeilen if z["status"] == "neu"),
        "doppelt": sum(1 for z in zeilen if z["status"] == "doppelt"),
    }


def lade_vorbereitung(token: str):
    if not token.isalnum():
        return None
    meta = config.TMP_DIR / f"{token}.json"
    raw = config.TMP_DIR / f"{token}.bin"
    if not meta.exists() or not raw.exists():
        return None
    return json.loads(meta.read_text()), raw.read_bytes()


def entferne_vorbereitung(token: str):
    for endung in ("json", "bin"):
        p = config.TMP_DIR / f"{token}.{endung}"
        if p.exists():
            p.unlink()


def kontostand(konto_id, bis: str | None = None) -> int:
    k = q1("SELECT startsaldo_cent FROM konto WHERE id = ?", (konto_id,))
    if bis:
        s = q1("SELECT COALESCE(SUM(betrag_cent),0) AS s FROM buchung WHERE konto_id = ? AND buchungsdatum <= ?",
               (konto_id, bis))
    else:
        s = q1("SELECT COALESCE(SUM(betrag_cent),0) AS s FROM buchung WHERE konto_id = ?", (konto_id,))
    return (k["startsaldo_cent"] if k else 0) + s["s"]


def uebernehmen(token: str, benutzer_id) -> int:
    geladen = lade_vorbereitung(token)
    if not geladen:
        raise csvimport.ProfilFehler("Die Vorschau ist abgelaufen. Bitte die Datei erneut hochladen.")
    meta, raw = geladen
    konto_id = meta["konto_id"]
    vorb = vorbereiten(konto_id, raw, meta["dateiname"])
    entferne_vorbereitung(vorb["token"])
    neue = [z for z in vorb["zeilen"] if z["status"] == "neu"]
    konto_leer = q1("SELECT COUNT(*) AS n FROM buchung WHERE konto_id = ?", (konto_id,))["n"] == 0

    lauf_id = exe("INSERT INTO importlauf (konto_id, importprofil_id, dateiname, datei_hash, benutzer_id, "
                  "anzahl_neu, anzahl_doppelt, anzahl_fehler) VALUES (?,?,?,?,?,?,?,?)",
                  (konto_id, vorb["profil"]["id"], meta["dateiname"], hashlib.sha256(raw).hexdigest(), benutzer_id,
                   len(neue), vorb["doppelt"], len(vorb["fehler"])))
    ids = []
    for z in neue:
        ids.append(exe(
            "INSERT INTO buchung (konto_id, buchungsdatum, valuta, betrag_cent, gegenpartei, gegen_iban, "
            "verwendungszweck, partner_key, abrechnungsmonat, saldo_cent, rohdaten, dedup_hash, importlauf_id) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (konto_id, z["buchungsdatum"].isoformat(), z["valuta"].isoformat() if z["valuta"] else None,
             z["betrag_cent"], z["gegenpartei"], z["gegen_iban"], z["verwendungszweck"],
             partner_key(z["gegenpartei"], z["gegen_iban"]), monat_von(z["buchungsdatum"]), z["saldo_cent"],
             jdump(z["roh"]), z["dedup_hash"], lauf_id)))

    # Startsaldo beim allerersten Import aus der Saldo-Spalte ableiten
    ende = endsaldo(vorb["zeilen"])
    if konto_leer and ende:
        k = q1("SELECT startsaldo_cent FROM konto WHERE id = ?", (konto_id,))
        if k["startsaldo_cent"] == 0:
            summe = sum(z["betrag_cent"] for z in neue if z["buchungsdatum"] <= ende["datum"])
            exe("UPDATE konto SET startsaldo_cent = ? WHERE id = ?", (ende["saldo"] - summe, konto_id))

    abgleich = saldo_abgleich(konto_id, vorb["zeilen"])
    if abgleich:
        exe("UPDATE importlauf SET saldo_datei_cent = ?, saldo_differenz_cent = ? WHERE id = ?",
            (abgleich["datei"], abgleich["differenz"], lauf_id))

    zuordnung.ordne_zu(ids)
    umbuchungen.erkenne(ids)
    return lauf_id


def endsaldo(zeilen):
    """Saldo nach der jüngsten Buchung der Datei. Berücksichtigt auf- und absteigend sortierte Exporte."""
    mit_saldo = [z for z in zeilen if z.get("saldo_cent") is not None]
    if not mit_saldo:
        return None
    absteigend = mit_saldo[0]["buchungsdatum"] >= mit_saldo[-1]["buchungsdatum"]
    if mit_saldo[0]["buchungsdatum"] == mit_saldo[-1]["buchungsdatum"]:
        absteigend = True
    z = mit_saldo[0] if absteigend else mit_saldo[-1]
    return {"saldo": z["saldo_cent"], "datum": z["buchungsdatum"]}


def saldo_abgleich(konto_id, zeilen):
    """Vergleicht den Endsaldo der Datei mit dem errechneten Kontostand an diesem Tag."""
    ende = endsaldo(zeilen)
    if not ende:
        return None
    errechnet = kontostand(konto_id, ende["datum"].isoformat())
    return {"datei": ende["saldo"], "errechnet": errechnet, "differenz": errechnet - ende["saldo"], "datum": ende["datum"]}


def rueckgaengig(lauf_id) -> int:
    ids = [r["id"] for r in q("SELECT id FROM buchung WHERE importlauf_id = ?", (lauf_id,))]
    for i in ids:
        partner = q1("SELECT umbuchung_partner_id FROM buchung WHERE id = ?", (i,))
        if partner and partner["umbuchung_partner_id"]:
            umbuchungen.loese(i)
    exe("DELETE FROM buchung WHERE importlauf_id = ?", (lauf_id,))
    exe("UPDATE importlauf SET rueckgaengig = 1 WHERE id = ?", (lauf_id,))
    return len(ids)


def letzter_import(konto_id):
    return q1("SELECT * FROM importlauf WHERE konto_id = ? AND rueckgaengig = 0 ORDER BY zeitpunkt DESC LIMIT 1",
              (konto_id,))


def tage_seit(zeitpunkt: str | None) -> int | None:
    if not zeitpunkt:
        return None
    return (date.today() - date.fromisoformat(zeitpunkt[:10])).days
