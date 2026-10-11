"""Lernendes Zuordnungsmodell (Naive Bayes, reines Python).

Lernt aus allen geprüften Buchungen: Wörter aus Gegenpartei und Verwendungszweck, Konto, Richtung und
Betragsgröße. Greift nur, wenn weder Regel noch Gedächtnis passen.
  Wahrscheinlichkeit >= 0,85  -> Kategorie wird gesetzt, bleibt aber „ungeprüft“
  0,50 bis 0,85              -> nur Vorschlag im Prüf-Modus
"""
import math
import re
from collections import Counter, defaultdict

from ..db import q

SICHER = 0.85
VORSCHLAG = 0.50
MIN_TRAINING = 20

_WORT = re.compile(r"[a-zäöüß]{3,}")
_STOPP = {"und", "der", "die", "das", "für", "von", "mit", "eur", "sepa", "lastschrift", "gutschrift",
          "kartenzahlung", "ueberweisung", "überweisung", "datum", "uhr", "ref", "end", "mandat", "kunde",
          "kundennr", "rechnung", "gmbh", "folgenr", "verfalld", "zahlung", "online"}


def merkmale(b) -> list[str]:
    text = f"{b['gegenpartei'] or ''} {b['verwendungszweck'] or ''}".lower()
    worte = [w for w in _WORT.findall(text) if w not in _STOPP]
    m = [f"w:{w}" for w in dict.fromkeys(worte)][:25]
    partei = [w for w in _WORT.findall((b["gegenpartei"] or "").lower()) if w not in _STOPP]
    m += [f"p:{w}" for w in partei[:4]]
    betrag = abs(b["betrag_cent"])
    m.append("r:ein" if b["betrag_cent"] > 0 else "r:aus")
    m.append(f"g:{min(int(math.log10(betrag + 1) * 2), 12)}")
    m.append(f"k:{b['konto_id']}")
    return m


class Modell:
    def __init__(self):
        self.klassen: Counter = Counter()
        self.zaehler: dict = defaultdict(Counter)
        self.summe: Counter = Counter()
        self.vokabular: set = set()
        self.n = 0

    def trainiere(self):
        rows = q("""SELECT b.id, b.gegenpartei, b.verwendungszweck, b.betrag_cent, b.konto_id, b.kategorie_id
                    FROM buchung b WHERE b.geprueft = 1 AND b.kategorie_id IS NOT NULL AND b.ist_umbuchung = 0
                      AND NOT EXISTS (SELECT 1 FROM buchung_split s WHERE s.buchung_id = b.id)
                    ORDER BY b.buchungsdatum DESC LIMIT 20000""")
        for r in rows:
            k = r["kategorie_id"]
            self.klassen[k] += 1
            for m in merkmale(r):
                self.zaehler[k][m] += 1
                self.summe[k] += 1
                self.vokabular.add(m)
        self.n = len(rows)
        return self

    @property
    def bereit(self) -> bool:
        return self.n >= MIN_TRAINING and len(self.klassen) >= 2

    def vorhersage(self, b):
        """-> (kategorie_id, wahrscheinlichkeit) oder (None, 0)."""
        if not self.bereit:
            return None, 0.0
        ms = [m for m in merkmale(b) if m in self.vokabular]
        if not any(m.startswith(("w:", "p:")) for m in ms):
            return None, 0.0
        v = len(self.vokabular)
        scores = {}
        for k, anzahl in self.klassen.items():
            s = math.log(anzahl / self.n)
            nenner = self.summe[k] + v
            z = self.zaehler[k]
            for m in ms:
                s += math.log((z.get(m, 0) + 1) / nenner)
            scores[k] = s
        best = max(scores, key=scores.get)
        mx = scores[best]
        total = sum(math.exp(s - mx) for s in scores.values())
        return best, 1.0 / total


def trefferquoten() -> list:
    """Anteil korrekter automatischer Zuordnungen je Quelle in den letzten 6 Monaten."""
    rows = q("""SELECT quelle, COUNT(*) AS n, SUM(korrekt) AS ok FROM zuordnung_feedback
                WHERE zeitpunkt >= datetime('now', '-6 months') GROUP BY quelle""")
    regel_n = q("SELECT COUNT(*) AS n FROM buchung WHERE zuordnung_quelle = 'regel' "
                "AND erstellt >= datetime('now', '-6 months')")[0]["n"]
    rows = [dict(r) for r in rows]
    r_regel = next((r for r in rows if r["quelle"] == "regel"), None)
    if r_regel:  # Regel-Feedback enthält nur Korrekturen
        r_regel["n"] += regel_n
        r_regel["ok"] = regel_n
    elif regel_n:
        rows.append({"quelle": "regel", "n": regel_n, "ok": regel_n})
    namen = {"regel": "Regeln", "gedaechtnis": "Frühere Buchungen", "modell": "Lernmodell", "vorschlag": "Vorschläge"}
    return [{"quelle": namen.get(r["quelle"], r["quelle"]), "n": r["n"], "quote": (r["ok"] or 0) / r["n"]}
            for r in rows if r["n"]]
