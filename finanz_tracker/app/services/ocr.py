"""Umsätze aus Screenshots (z. B. Kreditkarten-App) lokal per Tesseract erkennen.

Alles läuft auf dem Gerät: Das Bild geht nur an das lokal installierte Programm `tesseract`, nichts verlässt den
Home Assistant. Ergebnis ist eine Liste von Vorschlägen, die vor dem Speichern in einer Tabelle geprüft werden.

Erkennung (auf die Hanseatic-App abgestimmt, aber allgemein gehalten):
  * Wörter werden nach ihrer Höhe im Bild zu Zeilen gruppiert; Symbole links neben der Textspalte (Logos) fallen weg.
  * Jeder Betrag ("-2,00 €") verankert einen Umsatz. Darüber liegende Zeilen ohne große Lücke bilden Name und
    Kategorie der Bank, darunter folgt das Datum mit Status ("gebucht" / "vorgemerkt").
  * Fehlt das Datum am Umsatz, gilt die letzte Datums-Überschrift ("Heute", "Gestern", "12. Oktober 2026").
"""
import os
import re
import shutil
import subprocess
import tempfile
from datetime import date, timedelta
from statistics import median

MONATE = {"jan": 1, "feb": 2, "mär": 3, "mar": 3, "maer": 3, "apr": 4, "mai": 5, "may": 5, "jun": 6, "jul": 7,
          "aug": 8, "sep": 9, "okt": 10, "oct": 10, "nov": 11, "dez": 12, "dec": 12}

# Betrag: optionales Vorzeichen (OCR liest das Minus gern als Gedankenstrich oder Anführungszeichen),
# deutsche Schreibweise mit Komma und zwei Nachkommastellen, optional €/EUR.
BETRAG_RE = re.compile(r"(?<![\d,.])([-+−–—~“”\"'‘’]?)\s?(\d{1,3}(?:[.\s]\d{3})*|\d+),(\d{2})(?!\d)\s*(?:€|EUR|E\b)?")
DATUM_RE = re.compile(r"(?<!\d)(\d{1,2})\.?\s?(\d{1,2})\.\s?(\d{4}|\d{2})?(?!\d)")
DATUM_TEXT_RE = re.compile(r"(?<!\d)(\d{1,2})\.?\s+([A-Za-zÄÖÜäöü]{3,})\.?\s*(\d{4})?", re.I)
STATUS = {"gebucht": "gebucht", "vorgemerkt": "vorgemerkt", "ausstehend": "vorgemerkt", "reserviert": "vorgemerkt",
          "in bearbeitung": "vorgemerkt"}
GUTSCHRIFT_WORTE = ("gutschrift", "erstattung", "einzahlung", "rückzahlung", "ruckzahlung", "lastschrift einzug")


class OcrFehler(Exception):
    pass


def verfuegbar() -> bool:
    return shutil.which("tesseract") is not None


def sprachen() -> list[str]:
    try:
        out = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True, timeout=20).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return [z.strip() for z in out.splitlines()[1:] if z.strip()]


def _sprache() -> str:
    vorhanden = sprachen()
    if "deu" in vorhanden:
        return "deu+eng" if "eng" in vorhanden else "deu"
    return "eng" if "eng" in vorhanden else (vorhanden[0] if vorhanden else "eng")


def _vorbereiten(pfad: str) -> str:
    """Graustufen, bei dunklem Hintergrund invertieren, kleine Bilder hochskalieren (bessere Erkennung)."""
    try:
        from PIL import Image, ImageOps, ImageStat
    except ImportError:
        return pfad
    with Image.open(pfad) as bild:
        bild = ImageOps.exif_transpose(bild).convert("L")
        if ImageStat.Stat(bild).mean[0] < 110:  # Dunkelmodus
            bild = ImageOps.invert(bild)
        if bild.width < 1400:
            f = 1400 / bild.width
            bild = bild.resize((1400, int(bild.height * f)), Image.LANCZOS)
        ziel = pfad + ".png"
        bild.save(ziel)
    return ziel


def woerter(bild: bytes) -> list[dict]:
    """Wörter mit Position aus Tesseract (TSV)."""
    if not verfuegbar():
        raise OcrFehler("Die Texterkennung (tesseract) ist auf diesem System nicht installiert.")
    with tempfile.TemporaryDirectory() as tmp:
        pfad = os.path.join(tmp, "bild")
        with open(pfad, "wb") as fh:
            fh.write(bild)
        try:
            pfad = _vorbereiten(pfad)
        except Exception as exc:  # kein lesbares Bild
            raise OcrFehler("Die Datei konnte nicht als Bild gelesen werden (PNG oder JPG verwenden).") from exc
        try:
            r = subprocess.run(["tesseract", pfad, "stdout", "-l", _sprache(), "--psm", "11", "tsv"],
                               capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired as exc:
            raise OcrFehler("Die Texterkennung hat zu lange gedauert.") from exc
    if r.returncode != 0:
        raise OcrFehler("Die Texterkennung ist fehlgeschlagen: " + (r.stderr.strip().splitlines() or ["?"])[-1])
    erg = []
    for zeile in r.stdout.splitlines()[1:]:
        teile = zeile.split("\t")
        if len(teile) < 12 or teile[0] != "5" or not teile[11].strip():
            continue
        try:
            conf = float(teile[10])
        except ValueError:
            conf = -1
        erg.append({"x": int(teile[6]), "y": int(teile[7]), "w": int(teile[8]), "h": int(teile[9]),
                    "text": teile[11].strip(), "conf": conf})
    return erg


def zeilen(ws: list[dict]) -> list[dict]:
    """Wörter zu Bildzeilen gruppieren (gleiche Höhe, von links nach rechts)."""
    if not ws:
        return []
    h = median([w["h"] for w in ws]) or 10
    rows: list[dict] = []
    for w in sorted(ws, key=lambda w: w["y"] + w["h"] / 2):
        mitte = w["y"] + w["h"] / 2
        if rows and abs(rows[-1]["mitte"] - mitte) <= h * 0.6:
            r = rows[-1]
            r["woerter"].append(w)
            r["mitte"] = sum(x["y"] + x["h"] / 2 for x in r["woerter"]) / len(r["woerter"])
        else:
            rows.append({"mitte": mitte, "woerter": [w]})
    for r in rows:
        r["woerter"].sort(key=lambda w: w["x"])
        r["text"] = " ".join(w["text"] for w in r["woerter"])
        r["h"] = max(w["h"] for w in r["woerter"])
    return rows


def _jahr(tag, monat, jahr, heute):
    if jahr is None:
        j = heute.year
        try:
            if date(j, monat, tag) > heute + timedelta(days=2):
                j -= 1
        except ValueError:
            return None
        return j
    return 2000 + jahr if jahr < 100 else jahr


def finde_datum(text: str, heute: date | None = None):
    heute = heute or date.today()
    t = text.lower()
    if re.search(r"\bheute\b", t):
        return heute
    if re.search(r"\bgestern\b", t):
        return heute - timedelta(days=1)
    m = DATUM_RE.search(text)
    if m:
        tag, monat = int(m.group(1)), int(m.group(2))
        jahr = int(m.group(3)) if m.group(3) else None
        # "0710.2026" (Punkt nicht erkannt) -> 07.10.2026
        j = _jahr(tag, monat, jahr, heute)
        try:
            return date(j, monat, tag) if j else None
        except ValueError:
            pass
    m = DATUM_TEXT_RE.search(text)
    if m:
        monat = MONATE.get(m.group(2).lower()[:3].replace("ä", "a") if m.group(2).lower()[:3] != "mär" else "mär")
        if monat:
            tag = int(m.group(1))
            j = _jahr(tag, monat, int(m.group(3)) if m.group(3) else None, heute)
            try:
                return date(j, monat, tag) if j else None
            except ValueError:
                return None
    return None


def finde_betrag(text: str):
    """(cent, explizites_vorzeichen, match) oder None. Vorzeichen: -1, +1 oder 0 (keins erkannt)."""
    treffer = None
    for m in BETRAG_RE.finditer(text):
        treffer = m  # der rechteste Betrag ist der Umsatz (links stehen evtl. Datumsteile)
    if not treffer:
        return None
    ganz = re.sub(r"[.\s]", "", treffer.group(2))
    cent = int(ganz) * 100 + int(treffer.group(3))
    z = treffer.group(1)
    vz = 1 if z == "+" else (-1 if z else 0)
    return cent, vz, treffer


def _bereinige(text: str) -> str:
    text = re.sub(r"[›>»<«|_]+", " ", text)
    return re.sub(r"\s+", " ", text).strip(" –·•,").lstrip("-").strip()


def _status(text: str):
    t = text.lower()
    for wort, s in STATUS.items():
        if wort in t:
            return s
    return None


def _ohne_status(text: str) -> str:
    for wort in STATUS:
        text = re.sub(re.escape(wort), "", text, flags=re.I)
    return text


def _verbinde(teile: list[str]) -> list[str]:
    """Silbentrennung und abgebrochene Zeilen zusammenführen: 'Hengsten-' + 'berg' -> 'Hengstenberg'."""
    erg: list[str] = []
    for t in teile:
        if erg and erg[-1].endswith("-") and t[:1].islower():
            erg[-1] = erg[-1][:-1] + t
        elif erg and (erg[-1].endswith("&") or erg[-1].endswith("-")):
            erg[-1] = erg[-1] + " " + t
        else:
            erg.append(t)
    return erg


def erkenne(bild: bytes, heute: date | None = None, standard_vorzeichen=-1) -> dict:
    ws = woerter(bild)
    return auswerten(ws, heute, standard_vorzeichen)


def auswerten(ws: list[dict], heute: date | None = None, standard_vorzeichen=-1) -> dict:
    heute = heute or date.today()
    rows = zeilen(ws)
    if not rows:
        return {"umsaetze": [], "text": ""}
    for r in rows:
        r["betrag"] = finde_betrag(r["text"])
        r["datum"] = finde_datum(r["text"], heute)
    # Textspalte bestimmen: Logos/Symbole links davon ignorieren
    # bevorzugt die Datumszeilen (dort steht selten ein Logo), sonst die Betragszeilen
    xs = [r["woerter"][0]["x"] for r in rows if r["datum"] and not r["betrag"]] or \
         [r["woerter"][0]["x"] for r in rows if r["betrag"]]
    links = median(xs) - 15 if xs else 0
    breite = max(w["x"] + w["w"] for w in ws)
    if links > breite * 0.5:  # nur Beträge rechts erkannt – keine Spaltenlogik
        links = 0
    h = median([r["h"] for r in rows]) or 10

    def text_ohne_logo(r):
        return " ".join(w["text"] for w in r["woerter"] if w["x"] + w["w"] >= links)

    anker = [i for i, r in enumerate(rows) if r["betrag"]]
    umsaetze = []
    ende_vorher = -1
    ueberschrift = None
    for n, i in enumerate(anker):
        naechster = anker[n + 1] if n + 1 < len(anker) else len(rows)
        # Datums-Überschriften zwischen den Umsätzen merken
        for j in range(ende_vorher + 1, i):
            if rows[j]["datum"] and not rows[j]["betrag"] and len(_bereinige(rows[j]["text"])) <= 24:
                ueberschrift = rows[j]["datum"]
        # Datum/Status: gleiche Zeile oder darunter bis vor den nächsten Umsatz (nahe dran)
        datum = rows[i]["datum"] if rows[i]["datum"] and rows[i]["betrag"][2].start() > 0 else None
        status = _status(rows[i]["text"])
        ende = i
        for j in range(i + 1, naechster):
            if rows[j]["mitte"] - rows[ende]["mitte"] > h * 3.2:
                break
            if rows[j]["datum"] or _status(rows[j]["text"]):
                datum = datum or rows[j]["datum"]
                status = status or _status(rows[j]["text"])
                ende = j
            else:
                break
        # Name/Kategorie: zusammenhängende Zeilen über dem Betrag
        start = i
        while start - 1 > ende_vorher and rows[start]["mitte"] - rows[start - 1]["mitte"] <= h * 2.4 \
                and not rows[start - 1]["betrag"] and not (rows[start - 1]["datum"] and start - 1 != i):
            start -= 1
        teile = []
        for j in range(start, i + 1):
            t = text_ohne_logo(rows[j])
            if j == i:
                m = finde_betrag(t)
                t = t[:m[2].start()] if m else t
            t = _bereinige(_ohne_status(DATUM_RE.sub("", t)))
            if t:
                teile.append(t)
        teile = _verbinde(teile)
        cent, vz, _ = rows[i]["betrag"]
        name = teile[0] if teile else ""
        rest = teile[1:]
        if not vz:
            vz = 1 if any(w in " ".join(teile).lower() for w in GUTSCHRIFT_WORTE) else standard_vorzeichen
        umsaetze.append({
            "datum": datum or ueberschrift,
            "gegenpartei": name,
            "bank_kategorie": " · ".join(rest),
            "betrag_cent": cent * vz,
            "status": status or "",
            "vorzeichen_geraten": rows[i]["betrag"][1] == 0,
        })
        ende_vorher = ende
    return {"umsaetze": umsaetze, "text": "\n".join(r["text"] for r in rows)}
