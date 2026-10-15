"""Daten für frei konfigurierbare Diagramme (Seite „Eigene Auswertungen“).

Eine Diagramm-Einstellung (JSON) beschreibt, *was* gezeigt wird; das Aussehen (Linie, Balken, Torte …) entscheidet
der Browser. Grundlage sind wie überall die Posten (Aufteilungen je Kategorie, verteilte Zahlungen anteilig,
Umbuchungen und Darlehen ausgenommen).

Einstellungen:
  messgroesse  ausgaben | einnahmen | saldo | anzahl
  gruppe       gesamt | einaus | kategorie | unterkategorie | tag | person | konto | gegenpartei | vertrag | vertragsart
  auswahl      Liste von IDs (Kategorien inkl. Unterkategorien, Tags, Personen, Konten, Verträge) – leer = alle
  eltern       Kategorie-ID, deren direkte Unterkategorien gezeigt werden (gruppe = unterkategorie)
  zeit         monat | quartal | jahr | summe (summe = keine Zeitachse)
  zeitraum     3 | 6 | 12 | 24 | 36 | 60 | jahr | vorjahr | eigen   (+ von / bis als YYYY-MM)
  vergleich    keiner | vorjahr   (zusätzliche Reihe(n) mit demselben Zeitraum ein Jahr früher)
  kumuliert    true/false (laufende Summe über die Zeit)
  top          höchstens so viele Reihen, der Rest als „Sonstige“ (0 = alle)
"""
from datetime import date

from ..db import q
from ..util import aktueller_monat, ist_monat, monat_kurz, monat_plus
from . import kategorien, statistik

GRUPPEN = {"gesamt": "Gesamt", "einaus": "Einnahmen und Ausgaben", "kategorie": "Kategorien",
           "unterkategorie": "Unterkategorien einer Kategorie", "tag": "Tags", "person": "Personen", "konto": "Konten",
           "gegenpartei": "Gegenparteien", "vertrag": "Verträge / Abos", "vertragsart": "Abo · Fixkosten · Vertrag · sonstige"}
MESSGROESSEN = {"ausgaben": "Ausgaben", "einnahmen": "Einnahmen", "saldo": "Saldo (Einnahmen − Ausgaben)",
                "anzahl": "Anzahl Buchungen"}
ZEITEN = {"monat": "je Monat", "quartal": "je Quartal", "jahr": "je Jahr", "summe": "Summe über den Zeitraum"}
ZEITRAEUME = {"3": "letzte 3 Monate", "6": "letzte 6 Monate", "12": "letzte 12 Monate", "24": "letzte 24 Monate",
              "36": "letzte 36 Monate", "60": "letzte 5 Jahre", "jahr": "dieses Jahr", "vorjahr": "letztes Jahr",
              "eigen": "eigener Zeitraum"}
TYPEN = {"balken": "Säulen", "gestapelt": "Säulen gestapelt", "horizontal": "Balken waagerecht", "linie": "Linie",
         "flaeche": "Fläche", "donut": "Ring", "torte": "Torte", "tabelle": "Tabelle", "kennzahl": "Kennzahl",
         "heatmap": "Wärmekarte"}
VERTRAGSARTEN = {"abo": "Abos", "fix": "Fixkosten", "vertrag": "Verträge", None: "nicht wiederkehrend"}


def zeitraum(konfig, heute: date | None = None) -> tuple[str, str]:
    jetzt = aktueller_monat() if heute is None else f"{heute.year:04d}-{heute.month:02d}"
    z = str(konfig.get("zeitraum") or "12")
    if z == "jahr":
        return f"{jetzt[:4]}-01", jetzt
    if z == "vorjahr":
        j = int(jetzt[:4]) - 1
        return f"{j}-01", f"{j}-12"
    if z == "eigen" and ist_monat(konfig.get("von", "")) and ist_monat(konfig.get("bis", "")):
        von, bis = konfig["von"], konfig["bis"]
        return (von, bis) if von <= bis else (bis, von)
    n = int(z) if z.isdigit() else 12
    return monat_plus(jetzt, -(max(1, min(120, n)) - 1)), jetzt


def _schluessel_zeit(monat: str, zeit: str) -> str:
    if zeit == "quartal":
        return f"{monat[:4]}-Q{(int(monat[5:7]) - 1) // 3 + 1}"
    if zeit == "jahr":
        return monat[:4]
    if zeit == "summe":
        return "summe"
    return monat


def _beschriftung(s: str, zeit: str) -> str:
    if zeit == "quartal":
        return f"Q{s[-1]} {s[2:4]}"
    if zeit == "monat":
        return monat_kurz(s)
    if zeit == "summe":
        return "Summe"
    return s


def _achse(von: str, bis: str, zeit: str) -> list[str]:
    erg, m = [], von
    while m <= bis:
        s = _schluessel_zeit(m, zeit)
        if s not in erg:
            erg.append(s)
        m = monat_plus(m, 1)
    return erg


def _rohdaten(konten, von, bis, konfig):
    """Posten im Zeitraum mit Art (einnahme/ausgabe) und Wert gemäß Messgröße."""
    arten = kategorien.art_map()
    mess = konfig.get("messgroesse") or "ausgaben"
    erg = []
    for r in statistik.posten(konten, von, bis):
        art = statistik.art_von(arten, r["kategorie_id"], r["betrag"])
        if art == "umbuchung":
            continue
        if mess == "ausgaben":
            if art != "ausgabe":
                continue
            wert = -r["betrag"]
        elif mess == "einnahmen":
            if art != "einnahme":
                continue
            wert = r["betrag"]
        elif mess == "anzahl":
            wert = 1
        elif konfig.get("gruppe") == "einaus":
            wert = r["betrag"] if art == "einnahme" else -r["betrag"]  # beide Seiten positiv darstellen
        else:
            wert = r["betrag"]
        erg.append({**dict(r), "art": art, "wert": wert})
    return erg


def _gruppierer(konfig, posten):
    """Funktion posten -> Liste von (schlüssel, name) – mehrere bei Tags."""
    gruppe = konfig.get("gruppe") or "gesamt"
    auswahl = {int(x) for x in (konfig.get("auswahl") or []) if str(x).lstrip("-").isdigit()}
    alle = kategorien.alle()
    nach_id = {k["id"]: k for k in alle}
    ids = [p["buchung_id"] for p in posten]

    def stueckweise(sql, extra=()):
        erg = {}
        for i in range(0, len(ids), 800):
            teil = ids[i:i + 800]
            for r in q(sql.format(",".join("?" * len(teil))), list(extra) + teil):
                erg.setdefault(r["bid"], []).append(r)
        return erg

    if gruppe == "gesamt":
        return lambda p: [("gesamt", MESSGROESSEN.get(konfig.get("messgroesse") or "ausgaben", "Gesamt"))]
    if gruppe == "einaus":
        return lambda p: [(p["art"], "Einnahmen" if p["art"] == "einnahme" else "Ausgaben")]
    if gruppe in ("kategorie", "unterkategorie"):
        eltern = int(konfig["eltern"]) if str(konfig.get("eltern") or "").isdigit() else None
        gewaehlt = {}
        for kid in auswahl:
            for n in kategorien.nachkommen_ids(kid):
                gewaehlt.setdefault(n, kid)  # jede Unterkategorie zählt zu der gewählten Kategorie

        def kat(p):
            cur = nach_id.get(p["kategorie_id"])
            if gruppe == "kategorie" and auswahl:
                g = gewaehlt.get(p["kategorie_id"])
                return [(g, nach_id[g]["pfad"])] if g else []
            kette = []
            while cur:
                kette.append(cur)
                cur = nach_id.get(cur["parent_id"]) if cur["parent_id"] else None
            kette.reverse()
            if gruppe == "kategorie":
                return [(kette[0]["id"], kette[0]["name"])] if kette else [("ohne", "Ohne Kategorie")]
            ids_kette = [k["id"] for k in kette]
            if eltern not in ids_kette:
                return []
            i = ids_kette.index(eltern)
            if i + 1 < len(kette):
                return [(kette[i + 1]["id"], kette[i + 1]["name"])]
            return [(eltern, f"{kette[i]['name']} (direkt)")]
        return kat
    if gruppe == "tag":
        tags = stueckweise("SELECT bt.buchung_id AS bid, t.id, t.name FROM buchung_tag bt JOIN tag t ON t.id = bt.tag_id "
                           "WHERE bt.buchung_id IN ({})")
        return lambda p: [(t["id"], t["name"]) for t in tags.get(p["buchung_id"], [])
                          if not auswahl or t["id"] in auswahl] or ([] if auswahl else [("ohne", "ohne Tag")])
    if gruppe == "person":
        namen = {r["id"]: r["name"] for r in q("SELECT id, name FROM person")}
        return lambda p: ([(p["person_id"] or "ohne", namen.get(p["person_id"], "Gemeinsam / ohne Person"))]
                          if not auswahl or p["person_id"] in auswahl else [])
    if gruppe == "konto":
        namen = {r["id"]: r["name"] for r in q("SELECT id, name FROM konto")}
        return lambda p: [(p["konto_id"], namen.get(p["konto_id"], "?"))] if not auswahl or p["konto_id"] in auswahl else []
    if gruppe == "gegenpartei":
        info = stueckweise("SELECT id AS bid, partner_key, gegenpartei FROM buchung WHERE id IN ({})")
        return lambda p: [((info[p["buchung_id"]][0]["partner_key"] or "–"),
                           (info[p["buchung_id"]][0]["gegenpartei"] or "–"))] if p["buchung_id"] in info else []
    if gruppe in ("vertrag", "vertragsart"):
        info = stueckweise("SELECT b.id AS bid, v.id, v.name, v.art FROM buchung b LEFT JOIN vertrag v ON v.id = b.vertrag_id "
                           "WHERE b.id IN ({})")
        if gruppe == "vertragsart":
            return lambda p: [(info[p["buchung_id"]][0]["art"] or "keiner",
                               VERTRAGSARTEN.get(info[p["buchung_id"]][0]["art"], "nicht wiederkehrend"))]

        def vt(p):
            r = dict(info.get(p["buchung_id"], [{}])[0])
            if not r.get("id") or (auswahl and r["id"] not in auswahl):
                return []
            return [(r["id"], r["name"])]
        return vt
    return lambda p: [("gesamt", "Gesamt")]


def berechne(konten: list[int], konfig: dict, heute: date | None = None) -> dict:
    zeit = konfig.get("zeit") or "monat"
    von, bis = zeitraum(konfig, heute)
    achse = _achse(von, bis, zeit)
    reihen = _reihen(konten, konfig, von, bis, zeit, achse)
    erg = {"labels": [_beschriftung(s, zeit) for s in achse], "schluessel": achse, "von": von, "bis": bis,
           "reihen": reihen, "einheit": "" if konfig.get("messgroesse") == "anzahl" else "€",
           "zeit": zeit, "gruppe": konfig.get("gruppe") or "gesamt"}
    if konfig.get("vergleich") == "vorjahr":
        v_von, v_bis = monat_plus(von, -12), monat_plus(bis, -12)
        v_achse = _achse(v_von, v_bis, zeit)
        for r in _reihen(konten, konfig, v_von, v_bis, zeit, v_achse):
            r["name"] = f"{r['name']} (Vorjahr)"
            r["vorjahr"] = True
            erg["reihen"].append(r)
        # Vorjahresreihen sinnvoll neben die zugehörige Reihe sortieren
        erg["reihen"].sort(key=lambda r: (r["name"].replace(" (Vorjahr)", ""), r.get("vorjahr", False)))
    if konfig.get("kumuliert") and zeit != "summe":
        erg["summe"] = sum(r["werte"][-1] for r in erg["reihen"] if not r.get("vorjahr") and r["werte"])
    else:
        erg["summe"] = sum(sum(r["werte"]) for r in erg["reihen"] if not r.get("vorjahr"))
    return erg


def _reihen(konten, konfig, von, bis, zeit, achse) -> list[dict]:
    posten = _rohdaten(konten, von, bis, konfig)
    gruppiere = _gruppierer(konfig, posten)
    summen: dict = {}
    namen: dict = {}
    for p in posten:
        z = _schluessel_zeit(p["monat"], zeit)
        for key, name in gruppiere(p):
            namen[key] = name
            reihe = summen.setdefault(key, {})
            reihe[z] = reihe.get(z, 0) + p["wert"]
    reihen = [{"id": key, "name": namen[key], "werte": [summen[key].get(s, 0) for s in achse]} for key in summen]
    reihen.sort(key=lambda r: -abs(sum(r["werte"])))
    top = int(konfig.get("top") or 0)
    if top and len(reihen) > top:
        rest = reihen[top:]
        reihen = reihen[:top] + [{"id": "sonstige", "name": f"Sonstige ({len(rest)})",
                                  "werte": [sum(r["werte"][i] for r in rest) for i in range(len(achse))]}]
    if konfig.get("kumuliert") and zeit != "summe":
        for r in reihen:
            lauf, neu = 0, []
            for w in r["werte"]:
                lauf += w
                neu.append(lauf)
            r["werte"] = neu
    for r in reihen:
        r["id"] = str(r["id"])
    return reihen


def standard_diagramme() -> list[dict]:
    """Startansicht für neue Benutzer."""
    return [
        {"titel": "Einnahmen und Ausgaben", "typ": "balken", "messgroesse": "saldo", "gruppe": "einaus",
         "zeit": "monat", "zeitraum": "12", "breite": "voll"},
        {"titel": "Ausgaben nach Kategorie", "typ": "donut", "messgroesse": "ausgaben", "gruppe": "kategorie",
         "zeit": "summe", "zeitraum": "12", "top": 8, "breite": "halb"},
        {"titel": "Ausgaben im Vergleich zum Vorjahr (kumuliert)", "typ": "linie", "messgroesse": "ausgaben",
         "gruppe": "gesamt", "zeit": "monat", "zeitraum": "jahr", "vergleich": "vorjahr", "kumuliert": True,
         "breite": "halb"},
        {"titel": "Kategorien je Monat", "typ": "gestapelt", "messgroesse": "ausgaben", "gruppe": "kategorie",
         "zeit": "monat", "zeitraum": "12", "top": 6, "breite": "voll"},
        {"titel": "Größte Empfänger", "typ": "horizontal", "messgroesse": "ausgaben", "gruppe": "gegenpartei",
         "zeit": "summe", "zeitraum": "12", "top": 10, "breite": "halb"},
        {"titel": "Tags", "typ": "tabelle", "messgroesse": "ausgaben", "gruppe": "tag", "zeit": "quartal",
         "zeitraum": "12", "breite": "halb"},
    ]
