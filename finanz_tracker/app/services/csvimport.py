"""CSV lesen: Format erkennen, Spalten vorschlagen, Zeilen anhand eines Importprofils in Buchungen übersetzen.

Ein Profil speichert:
  einstellungen = {encoding, delimiter, date_format, decimal}
  spalten       = [{index, header, feld}]   feld ∈ FELDER
  betrag_modus  = vorzeichen | soll_haben | kennzeichen
Die Zuordnung merkt sich die Spaltenüberschriften; so fällt auf, wenn die Bank ihr Format ändert.
"""
import csv
import io
import re
from collections import Counter
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from ..util import norm_iban

FELDER = {
    "datum": "Buchungsdatum",
    "valuta": "Valuta",
    "partei": "Gegenpartei",
    "zweck": "Verwendungszweck",
    "iban": "Gegen-IBAN",
    "betrag": "Betrag",
    "soll": "Soll (Ausgang)",
    "haben": "Haben (Eingang)",
    "kennzeichen": "Kennzeichen S/H",
    "saldo": "Saldo",
    "ignore": "ignorieren",
}
MEHRFACH_ERLAUBT = {"zweck", "partei", "ignore"}

DATUMSFORMATE = {
    "TT.MM.JJJJ": "%d.%m.%Y",
    "TT.MM.JJ": "%d.%m.%y",
    "JJJJ-MM-TT": "%Y-%m-%d",
    "TT/MM/JJJJ": "%d/%m/%Y",
    "MM/TT/JJJJ": "%m/%d/%Y",
}
ENCODINGS = {"utf-8": "utf-8-sig", "windows-1252": "cp1252", "iso-8859-1": "latin-1"}
TRENNZEICHEN = {";": "Semikolon ;", ",": "Komma ,", "\t": "Tabulator", "|": "Senkrechter Strich |"}

_VORSCHLAEGE = [
    (r"valuta|wertstellung", "valuta"),
    (r"buchungstag|buchungsdatum|^datum|^date|belegdatum", "datum"),
    (r"saldo|kontostand", "saldo"),
    (r"^s/h$|soll/haben|^kennzeichen", "kennzeichen"),
    (r"^soll|^ausgang|^lastschrift", "soll"),
    (r"^haben|^eingang|^gutschrift", "haben"),
    (r"iban|kontonummer|konto-nr", "iban"),
    (r"empf|auftraggeber|zahlungspflichtig|beg(ü|ue)nstigt|^name|zahlungsbeteiligt|partner|gläubiger|glaeubiger", "partei"),
    (r"verwendungszweck|buchungstext|beschreibung|^text|vorgang|purpose|umsatzart|details", "zweck"),
    (r"betrag|umsatz|amount", "betrag"),
]


class ProfilFehler(Exception):
    """Die Datei passt nicht (mehr) zum Profil."""


# ---------- Rohdaten ----------

def decode(raw: bytes, encoding: str | None = None) -> tuple[str, str]:
    if encoding:
        return raw.decode(ENCODINGS.get(encoding, encoding), errors="replace"), encoding
    try:
        return raw.decode("utf-8-sig"), "utf-8"
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace"), "windows-1252"


def erkenne_trennzeichen(text: str) -> str:
    zeilen = [z for z in text.splitlines()[:40] if z.strip()]
    best, best_score = ";", -1
    for d in TRENNZEICHEN:
        anz = [z.count(d) for z in zeilen]
        haeufig = Counter(a for a in anz if a > 0).most_common(1)
        if not haeufig:
            continue
        wert, menge = haeufig[0]
        score = menge * 10 + wert
        if score > best_score:
            best, best_score = d, score
    return best


def zeilen(text: str, delimiter: str) -> list[list[str]]:
    return [[c.strip() for c in r] for r in csv.reader(io.StringIO(text), delimiter=delimiter)]


def _ist_zahl_oder_datum(c: str) -> bool:
    return bool(re.fullmatch(r"[-+]?[\d.,\s/:]+[-+]?|[\d.]+\s?(EUR|€)?", c.strip()))


def erkenne_kopfzeile(rows: list[list[str]]) -> int:
    breiten = Counter(len(r) for r in rows if len(r) > 1)
    if not breiten:
        return 0
    n = breiten.most_common(1)[0][0]
    for i, r in enumerate(rows):
        if len(r) == n:
            texte = sum(1 for c in r if c and not _ist_zahl_oder_datum(c))
            if texte >= max(2, int(n * 0.6)):
                return i
    for i, r in enumerate(rows):
        if len(r) == n:
            return i
    return 0


def parse_datum(text: str, fmt_name: str) -> date:
    fmt = DATUMSFORMATE.get(fmt_name, fmt_name)
    return datetime.strptime(text.strip(), fmt).date()


def erkenne_datumsformat(werte: list[str]) -> str:
    werte = [w for w in werte if w.strip()][:30]
    for name in DATUMSFORMATE:
        try:
            for w in werte:
                parse_datum(w, name)
            if werte:
                return name
        except ValueError:
            continue
    return "TT.MM.JJJJ"


def parse_betrag(text: str, decimal: str = ",") -> int | None:
    s = (text or "").strip()
    for x in ("\xa0", " ", "EUR", "€", "−"):
        s = s.replace(x, "-" if x == "−" else "")
    if not s:
        return None
    neg = False
    if s.endswith("-"):
        neg, s = True, s[:-1]
    elif s.endswith("+"):
        s = s[:-1]
    if s.startswith("-"):
        neg, s = not neg if neg else True, s[1:]
    elif s.startswith("+"):
        s = s[1:]
    if decimal == ",":
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")
    try:
        d = Decimal(s)
    except InvalidOperation as exc:
        raise ValueError(f"Betrag nicht lesbar: „{text}“") from exc
    cent = int((d * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return -cent if neg else cent


def erkenne_dezimal(werte: list[str]) -> str:
    for w in werte:
        w = w.strip()
        if re.search(r"\d,\d{1,2}[-+]?$", w):
            return ","
        if re.search(r"\d\.\d{1,2}[-+]?$", w):
            return "."
    return ","


def schlage_spalten_vor(headers: list[str]) -> list[str]:
    vergeben: set[str] = set()
    ergebnis = []
    for h in headers:
        hn = h.strip().lower()
        feld = "ignore"
        for muster, f in _VORSCHLAEGE:
            if re.search(muster, hn) and (f in MEHRFACH_ERLAUBT or f not in vergeben):
                feld = f
                break
        if feld == "valuta" and "datum" not in vergeben and not any(
                re.search(r"buchungstag|buchungsdatum", x.lower()) for x in headers):
            feld = "datum"
        vergeben.add(feld)
        ergebnis.append(feld)
    if "betrag" not in ergebnis and "soll" in ergebnis and "haben" in ergebnis:
        pass
    return ergebnis


def analysiere(raw: bytes, encoding: str | None = None, delimiter: str | None = None) -> dict:
    """Erster Blick auf eine Beispieldatei: Einstellungen und Spaltenvorschlag."""
    text, encoding = decode(raw, encoding)
    delim = delimiter or erkenne_trennzeichen(text)
    rows = zeilen(text, delim)
    hz = erkenne_kopfzeile(rows)
    headers = rows[hz] if rows else []
    daten = [r for r in rows[hz + 1:] if len(r) == len(headers) and any(r)]
    felder = schlage_spalten_vor(headers)

    def spalte(feld):
        return [r[i] for r in daten for i, f in enumerate(felder) if f == feld and i < len(r)]

    datumsformat = erkenne_datumsformat(spalte("datum"))
    dezimal = erkenne_dezimal(spalte("betrag") + spalte("soll") + spalte("haben") + spalte("saldo"))
    modus = "vorzeichen"
    if "betrag" not in felder and "soll" in felder and "haben" in felder:
        modus = "soll_haben"
    elif "kennzeichen" in felder:
        modus = "kennzeichen"
    return {
        "einstellungen": {"encoding": encoding, "delimiter": delim, "date_format": datumsformat, "decimal": dezimal},
        "kopfzeile": hz,
        "vorspann": rows[:hz],
        "headers": headers,
        "felder": felder,
        "beispiel": daten[:8],
        "betrag_modus": modus,
        "anzahl_zeilen": len(daten),
    }


# ---------- Profil anwenden ----------

def pruefe_zuordnung(spalten: list[dict], betrag_modus: str) -> list[str]:
    felder = [s["feld"] for s in spalten]
    fehler = []
    if "datum" not in felder:
        fehler.append("Pflichtfeld Buchungsdatum fehlt.")
    if betrag_modus == "vorzeichen" and "betrag" not in felder:
        fehler.append("Pflichtfeld Betrag fehlt.")
    if betrag_modus == "soll_haben" and not ("soll" in felder and "haben" in felder):
        fehler.append("Für Soll/Haben müssen beide Spalten zugeordnet sein.")
    if betrag_modus == "kennzeichen" and not ("betrag" in felder and "kennzeichen" in felder):
        fehler.append("Für Betrag mit Kennzeichen müssen Betrag und Kennzeichen zugeordnet sein.")
    if "partei" not in felder and "zweck" not in felder:
        fehler.append("Mindestens Gegenpartei oder Verwendungszweck muss zugeordnet sein.")
    for f, n in Counter(felder).items():
        if n > 1 and f not in MEHRFACH_ERLAUBT:
            fehler.append(f"„{FELDER.get(f, f)}“ ist mehreren Spalten zugeordnet.")
    return fehler


def _finde_kopfzeile(rows, spalten):
    benoetigt = [s for s in spalten if s["feld"] != "ignore"]
    # 1. exakt an gespeicherter Position
    for i, r in enumerate(rows[:80]):
        if benoetigt and all(s["index"] < len(r) and r[s["index"]] == s["header"].strip() for s in benoetigt):
            return i, {s["index"]: s["feld"] for s in benoetigt}
    # 2. Überschriften an anderer Position (Bank hat Spalten umsortiert oder ergänzt)
    for i, r in enumerate(rows[:80]):
        namen = [c for c in r]
        if benoetigt and all(s["header"].strip() in namen for s in benoetigt):
            zuordnung = {}
            for s in benoetigt:
                zuordnung[namen.index(s["header"].strip())] = s["feld"]
            return i, zuordnung
    return None, None


def lese_datei(raw: bytes, profil: dict) -> dict:
    """Wendet ein Profil an. Ergebnis: {datensaetze, fehler, hinweise, kopfzeile}."""
    einst = profil["einstellungen"]
    spalten = profil["spalten"]
    modus = profil.get("betrag_modus", "vorzeichen")
    text, _ = decode(raw, einst.get("encoding"))
    rows = zeilen(text, einst.get("delimiter", ";"))
    hz, zuordnung = _finde_kopfzeile(rows, spalten)
    if hz is None:
        erwartet = ", ".join(f"„{s['header']}“" for s in spalten if s["feld"] != "ignore")
        raise ProfilFehler(f"Die Spaltenüberschriften des Profils wurden nicht gefunden (erwartet: {erwartet}). "
                           "Hat die Bank das Exportformat geändert? Dann die Spaltenzuordnung im Profil anpassen.")
    hinweise = []
    bekannte = {s["header"].strip() for s in spalten}
    neu = [h for h in rows[hz] if h and h not in bekannte]
    if neu:
        hinweise.append("Neue, nicht zugeordnete Spalten in der Datei: " + ", ".join(f"„{h}“" for h in neu))
    breite = max(zuordnung) + 1
    datensaetze, fehler = [], []
    for nr, r in enumerate(rows[hz + 1:], start=hz + 2):
        if not any(r):
            continue
        if len(r) < breite:
            # typische Fußzeilen ("Kontostand am ...") überspringen
            continue
        try:
            datensaetze.append(_zeile(r, zuordnung, einst, modus, nr))
        except ValueError as exc:
            fehler.append({"zeile": nr, "fehler": str(exc), "roh": r})
    return {"datensaetze": datensaetze, "fehler": fehler, "hinweise": hinweise, "kopfzeile": hz + 1}


def _zeile(r, zuordnung, einst, modus, nr):
    werte: dict[str, list[str]] = {}
    for idx, feld in zuordnung.items():
        werte.setdefault(feld, []).append(r[idx] if idx < len(r) else "")

    def eins(feld):
        v = werte.get(feld, [""])
        return v[0].strip() if v else ""

    dez = einst.get("decimal", ",")
    datum_text = eins("datum")
    if not datum_text:
        raise ValueError("Buchungsdatum fehlt")
    try:
        datum = parse_datum(datum_text, einst.get("date_format", "TT.MM.JJJJ"))
    except ValueError as exc:
        raise ValueError(f"Datum „{datum_text}“ passt nicht zum Format {einst.get('date_format')}") from exc
    valuta = None
    if eins("valuta"):
        try:
            valuta = parse_datum(eins("valuta"), einst.get("date_format", "TT.MM.JJJJ"))
        except ValueError:
            valuta = None

    if modus == "soll_haben":
        soll = parse_betrag(eins("soll"), dez) or 0
        haben = parse_betrag(eins("haben"), dez) or 0
        betrag = abs(haben) - abs(soll)
        if not eins("soll") and not eins("haben"):
            raise ValueError("Weder Soll noch Haben gefüllt")
    else:
        b = parse_betrag(eins("betrag"), dez)
        if b is None:
            raise ValueError("Betrag fehlt")
        betrag = b
        if modus == "kennzeichen":
            kz = eins("kennzeichen").strip().lower()
            if kz in ("s", "soll", "-", "d", "debit", "lastschrift"):
                betrag = -abs(b)
            elif kz in ("h", "haben", "+", "c", "credit", "gutschrift"):
                betrag = abs(b)
            else:
                raise ValueError(f"Kennzeichen „{eins('kennzeichen')}“ unbekannt (erwartet S oder H)")

    saldo = None
    if eins("saldo"):
        try:
            saldo = parse_betrag(eins("saldo"), dez)
        except ValueError:
            saldo = None
    partei = " ".join(x.strip() for x in werte.get("partei", []) if x.strip())
    zweck = " · ".join(x.strip() for x in werte.get("zweck", []) if x.strip())
    return {
        "zeile": nr,
        "buchungsdatum": datum,
        "valuta": valuta,
        "betrag_cent": betrag,
        "gegenpartei": partei,
        "verwendungszweck": zweck,
        "gegen_iban": norm_iban(eins("iban")),
        "saldo_cent": saldo,
        "roh": r,
    }


def finde_ibans(raw: bytes) -> set[str]:
    """IBANs im Vorspann/Inhalt der Datei (für die Konto-Erkennung)."""
    text, _ = decode(raw)
    kopf = "\n".join(text.splitlines()[:15])
    return {re.sub(r"\s", "", m).upper() for m in re.findall(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}(?:\s?[A-Z0-9]{1,4})?\b", kopf)}
