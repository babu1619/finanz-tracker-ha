"""Formatierung, Normalisierung und kleine Rechenhelfer."""
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
          "August", "September", "Oktober", "November", "Dezember"]
MONATE_KURZ = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]


def euro(cent, vorzeichen=False, nachkomma=True) -> str:
    if cent is None:
        return "–"
    neg = cent < 0
    c = abs(int(cent))
    if nachkomma:
        ganz, rest = divmod(c, 100)
        text = f"{ganz:,}".replace(",", ".") + f",{rest:02d}"
    else:
        ganz = (c + 50) // 100
        text = f"{ganz:,}".replace(",", ".")
    if neg:
        text = "−" + text
    elif vorzeichen and cent > 0:
        text = "+" + text
    return text + " €"


def parse_euro_eingabe(text) -> int:
    """Eingabe aus Formularen wie '1.234,56', '-12,5' oder '1234.56' in Cent."""
    s = (text or "").strip().replace("€", "").replace(" ", "").replace("−", "-")
    if not s:
        return 0
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        d = Decimal(s)
    except InvalidOperation as exc:
        raise ValueError(f"Kein gültiger Betrag: {text}") from exc
    return int((d * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def datum_de(iso) -> str:
    if not iso:
        return ""
    try:
        d = date.fromisoformat(str(iso)[:10])
    except ValueError:
        return str(iso)
    return d.strftime("%d.%m.%Y")


def monat_name(monat: str) -> str:
    try:
        j, m = monat.split("-")
        return f"{MONATE[int(m) - 1]} {j}"
    except (ValueError, IndexError, AttributeError):
        return monat or ""


def monat_kurz(monat: str) -> str:
    try:
        j, m = monat.split("-")
        return f"{MONATE_KURZ[int(m) - 1]} {j[2:]}"
    except (ValueError, IndexError, AttributeError):
        return monat or ""


def monat_von(d) -> str:
    if isinstance(d, str):
        d = date.fromisoformat(d[:10])
    return f"{d.year:04d}-{d.month:02d}"


def monat_plus(monat: str, n: int) -> str:
    j, m = (int(x) for x in monat.split("-"))
    idx = j * 12 + (m - 1) + n
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


def aktueller_monat() -> str:
    return monat_von(date.today())


def ist_monat(text) -> bool:
    return bool(text) and re.fullmatch(r"\d{4}-\d{2}", text) is not None


_STOPP = {"gmbh", "ag", "kg", "se", "co", "ohg", "ev", "e.v", "sagt", "danke", "dankt", "lastschrift",
          "kartenzahlung", "pos", "ec", "einkauf", "filiale", "fil", "de", "eur", "online", "www", "com"}


def partner_key(gegenpartei: str, gegen_iban: str | None = None) -> str:
    """Stabiler Schlüssel für 'gleicher Zahlungsempfänger' (Gedächtnis-Zuordnung)."""
    text = (gegenpartei or "").lower()
    text = re.sub(r"[0-9]+", " ", text)
    text = re.sub(r"[^a-zäöüß ]+", " ", text)
    worte = [w for w in text.split() if len(w) > 1 and w not in _STOPP]
    if worte:
        return " ".join(worte[:3])
    if gegen_iban:
        return "iban:" + re.sub(r"\s+", "", gegen_iban).upper()
    return ""


def norm_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def norm_iban(iban) -> str | None:
    if not iban:
        return None
    s = re.sub(r"\s+", "", str(iban)).upper()
    return s or None


def jetzt() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
