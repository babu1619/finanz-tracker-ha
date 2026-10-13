"""Kreditkartenabrechnung (z. B. Hanseatic Bank) als PDF oder Bild einlesen.

Tabellenaufbau: Buchungsdatum | Transaktionsdatum | Beschreibung (mehrzeilig) | Karte | Betrag, dazu „Alter Saldo“
und „Neuer Saldo“. Gearbeitet wird mit Wörtern samt Position – aus dem PDF-Text (pdftotext) oder, bei Bildern und
eingescannten PDFs, aus der lokalen Texterkennung. So zählen Spalten statt starrer Zeichenpositionen.

Buchungsdatum wird Buchungsdatum (passt zum Saldo der Abrechnung), das Transaktionsdatum landet als Wertstellung
und im Verwendungszweck.
"""
import html
import os
import re
import shutil
import subprocess
import tempfile
from datetime import date
from statistics import median

from . import ocr

DATUM_VOLL = re.compile(r"^(\d{2})\.(\d{2})\.(\d{4})$")
SALDO_RE = re.compile(r"\b(alter|neuer)\s+saldo\b", re.I)
WORT_RE = re.compile(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>')


def _datum(text):
    m = DATUM_VOLL.match(text.strip().rstrip(",."))
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def pdf_woerter(raw: bytes) -> list[dict]:
    """Wörter mit Position aus dem Text eines PDFs; leer, wenn das PDF nur Bilder enthält (Scan)."""
    if not shutil.which("pdftotext"):
        raise ocr.OcrFehler("Zum Lesen von PDFs fehlt das Programm pdftotext (poppler-utils).")
    with tempfile.TemporaryDirectory() as tmp:
        pfad = os.path.join(tmp, "a.pdf")
        with open(pfad, "wb") as fh:
            fh.write(raw)
        r = subprocess.run(["pdftotext", "-bbox", pfad, "-"], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise ocr.OcrFehler("Das PDF konnte nicht gelesen werden (beschädigt oder passwortgeschützt?).")
    woerter = []
    for nr, seite in enumerate(r.stdout.split("<page ")[1:]):
        versatz = nr * 5000  # Seiten untereinander legen
        for m in WORT_RE.finditer(seite):
            x0, y0, x1, y1 = (float(v) * 3 for v in m.groups()[:4])  # Punkte -> ~Pixel bei 216 dpi
            woerter.append({"x": int(x0), "y": int(y0) + versatz, "w": int(x1 - x0), "h": max(1, int(y1 - y0)),
                            "text": html.unescape(m.group(5)), "conf": 100})
    return woerter


def pdf_seiten_als_bilder(raw: bytes, max_seiten=6) -> list[bytes]:
    if not shutil.which("pdftoppm"):
        raise ocr.OcrFehler("Für eingescannte PDFs fehlt das Programm pdftoppm (poppler-utils).")
    with tempfile.TemporaryDirectory() as tmp:
        pfad = os.path.join(tmp, "a.pdf")
        with open(pfad, "wb") as fh:
            fh.write(raw)
        subprocess.run(["pdftoppm", "-r", "200", "-l", str(max_seiten), "-png", pfad, os.path.join(tmp, "s")],
                       capture_output=True, timeout=180)
        return [open(os.path.join(tmp, f), "rb").read() for f in sorted(os.listdir(tmp)) if f.endswith(".png")]


def auswerten(ws: list[dict]) -> dict:
    """Umsätze und Salden aus Wortpositionen. Ergebnis wie ocr.auswerten plus 'alter_saldo'/'neuer_saldo'."""
    rows = ocr.zeilen(ws)
    erg = {"umsaetze": [], "alter_saldo": None, "neuer_saldo": None, "text": "\n".join(r["text"] for r in rows)}
    if not rows:
        return erg
    h = median([r["h"] for r in rows]) or 10
    zeichen = median([w["w"] / max(1, len(w["text"])) for w in ws]) or 8
    i = 0
    while i < len(rows):
        r = rows[i]
        ws_r = r["woerter"]
        saldo = SALDO_RE.search(r["text"])
        if saldo and not _datum(ws_r[0]["text"]):
            b = ocr.finde_betrag(r["text"])
            if b:
                erg["alter_saldo" if saldo.group(1).lower() == "alter" else "neuer_saldo"] = b[0] * (b[1] or 1)
            i += 1
            continue
        buchung = _datum(ws_r[0]["text"])
        betrag = ocr.finde_betrag(r["text"])
        if not buchung or not betrag:
            i += 1
            continue
        j = 1
        transaktion = None
        if j < len(ws_r) and _datum(ws_r[j]["text"]):
            transaktion = _datum(ws_r[j]["text"])
            j += 1
        while j < len(ws_r) and ws_r[j]["text"] in ("-", "–", "—"):
            j += 1
        # Betrag (rechts) und Kartennummer (4 Ziffern bzw. „-“ davor) abtrennen
        rest = ws_r[j:]
        betrag_x = None
        for k in range(len(rest) - 1, -1, -1):
            if ocr.finde_betrag(rest[k]["text"]):
                betrag_x = rest[k]["x"]
                rest = rest[:k]
                break
        karte = ""
        while rest and (re.fullmatch(r"\d{4}", rest[-1]["text"]) or rest[-1]["text"] in ("-", "–", "€")):
            if rest[-1]["text"].isdigit():
                karte = rest[-1]["text"]
            rest = rest[:-1]
        if not rest:
            i += 1
            continue
        spalte = rest[0]["x"]
        erste = " ".join(w["text"] for w in rest)
        weitere = []
        k = i + 1
        while k < len(rows):
            n = rows[k]
            if n["mitte"] - rows[k - 1]["mitte"] > h * 2.4:
                break
            nw = n["woerter"]
            if _datum(nw[0]["text"]) or SALDO_RE.search(n["text"]):
                break
            if abs(nw[0]["x"] - spalte) > zeichen * 3 or (betrag_x and ocr.finde_betrag(n["text"])):
                break
            weitere.append(" ".join(w["text"] for w in nw if not betrag_x or w["x"] < betrag_x - zeichen * 2))
            k += 1
        cent, vz, _ = betrag
        gegenpartei = weitere[-1] if weitere else erste
        zweck = [erste] + weitere[:-1] if weitere else []
        if transaktion and transaktion != buchung:
            zweck.append(f"Umsatz vom {transaktion.strftime('%d.%m.%Y')}")
        erg["umsaetze"].append({
            "datum": buchung, "valuta": transaktion, "gegenpartei": gegenpartei.strip(" ,"),
            "bank_kategorie": " · ".join(z for z in zweck if z), "betrag_cent": cent * (vz or 1),
            "status": "gebucht", "vorzeichen_geraten": False, "karte": karte,
        })
        i = k
    return erg


def lies(raw: bytes, dateiname: str = "") -> dict:
    """Datei (PDF oder Bild) lesen. Erkennt selbst, ob es eine Abrechnungstabelle oder eine App-Liste ist."""
    ist_pdf = raw[:5] == b"%PDF-" or dateiname.lower().endswith(".pdf")
    if ist_pdf:
        ws = pdf_woerter(raw)
        if len(ws) >= 5:
            erg = auswerten(ws)
            erg["quelle"] = "pdf"
            return erg
        # eingescanntes PDF: Seiten als Bilder erkennen
        gesamt = {"umsaetze": [], "alter_saldo": None, "neuer_saldo": None, "text": "", "quelle": "pdf-scan"}
        for bild in pdf_seiten_als_bilder(raw):
            e = auswerten(ocr.woerter(bild))
            gesamt["umsaetze"] += e["umsaetze"]
            gesamt["text"] += e["text"] + "\n\n"
            gesamt["alter_saldo"] = gesamt["alter_saldo"] if gesamt["alter_saldo"] is not None else e["alter_saldo"]
            gesamt["neuer_saldo"] = e["neuer_saldo"] if e["neuer_saldo"] is not None else gesamt["neuer_saldo"]
        return gesamt
    ws = ocr.woerter(raw)
    tabelle = auswerten(ws)
    if tabelle["umsaetze"]:
        tabelle["quelle"] = "bild-abrechnung"
        return tabelle
    app = ocr.auswerten(ws)
    app.update({"alter_saldo": None, "neuer_saldo": None, "quelle": "bild-app"})
    return app
