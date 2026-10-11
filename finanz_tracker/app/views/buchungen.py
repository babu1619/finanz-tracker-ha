import csv
import io

from flask import Blueprint, Response, abort, g, redirect, render_template, request, url_for

from .. import auth
from ..db import q, q1, exe, commit, log_aenderung
from ..services import kategorien, ruecklagen, splits, tags, umbuchungen, zuordnung
from ..util import ist_monat, monat_plus, aktueller_monat, parse_euro_eingabe, datum_de
from . import melde, int_oder_none

bp = Blueprint("buchungen", __name__, url_prefix="/buchungen")


def _filter():
    a = request.args
    f = {
        "monat": a.get("monat", ""),
        "konto": int_oder_none(a.get("konto")),
        "kategorie": a.get("kategorie", ""),
        "person": int_oder_none(a.get("person")),
        "tag": int_oder_none(a.get("tag")),
        "suche": a.get("suche", "").strip(),
        "status": a.get("status", ""),
        "partei": a.get("partei", "").strip(),
        "von": a.get("von", "") if _ist_datum(a.get("von", "")) else "",
        "bis": a.get("bis", "") if _ist_datum(a.get("bis", "")) else "",
        "min": a.get("min", "").strip(),
        "max": a.get("max", "").strip(),
        "richtung": a.get("richtung", "") if a.get("richtung") in ("aus", "ein") else "",
        "sort": a.get("sort", "") if a.get("sort", "").lstrip("-") in SORTIERUNG else "",
    }
    if f["monat"] and f["monat"] != "alle" and not ist_monat(f["monat"]):
        f["monat"] = ""
    return f


SORTIERUNG = {
    "datum": "b.buchungsdatum {r}, b.id {r}",
    "monat": "b.abrechnungsmonat {r}, b.buchungsdatum DESC",
    "konto": "k.name COLLATE NOCASE {r}, b.buchungsdatum DESC",
    "partei": "b.gegenpartei COLLATE NOCASE {r}, b.buchungsdatum DESC",
    "kategorie": "kat.pfad IS NULL, kat.pfad COLLATE NOCASE {r}, b.buchungsdatum DESC",
    "person": "p.name IS NULL, p.name COLLATE NOCASE {r}, b.buchungsdatum DESC",
    "tags": "tagsort IS NULL, tagsort COLLATE NOCASE {r}, b.buchungsdatum DESC",
    "betrag": "b.betrag_cent {r}, b.buchungsdatum DESC",
}
FILTER_FELDER = ("konto", "kategorie", "person", "tag", "suche", "status", "partei", "von", "bis", "min", "max", "richtung")


def _ist_datum(text) -> bool:
    import re
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", text or ""))


def filter_aktiv(f) -> int:
    return sum(1 for k in FILTER_FELDER if f.get(k))


def _abfrage(f, limit=500):
    sichtbar = auth.sichtbare_konten()
    if not sichtbar:
        return [], {"n": 0, "aus": 0, "ein": 0}, sichtbar
    where = [f"b.konto_id IN ({','.join('?' * len(sichtbar))})"]
    params: list = list(sichtbar)
    if f["monat"] and f["monat"] != "alle":
        where.append("b.abrechnungsmonat = ?")
        params.append(f["monat"])
    if f["konto"]:
        where.append("b.konto_id = ?")
        params.append(f["konto"])
    if f["kategorie"] == "ohne":
        where.append("b.kategorie_id IS NULL AND b.ist_umbuchung = 0")
    elif f["kategorie"]:
        ids = kategorien.nachkommen_ids(int_oder_none(f["kategorie"]) or 0)
        marks = ",".join("?" * len(ids)) or "NULL"
        where.append(f"(b.kategorie_id IN ({marks}) OR EXISTS (SELECT 1 FROM buchung_split s "
                     f"WHERE s.buchung_id = b.id AND s.kategorie_id IN ({marks})))")
        params.extend(ids + ids)
    if f["person"]:
        where.append("(b.person_id = ? OR EXISTS (SELECT 1 FROM buchung_split s WHERE s.buchung_id = b.id AND s.person_id = ?))")
        params.extend([f["person"], f["person"]])
    if f["tag"]:
        where.append("EXISTS (SELECT 1 FROM buchung_tag bt WHERE bt.buchung_id = b.id AND bt.tag_id = ?)")
        params.append(f["tag"])
    if f["suche"]:
        where.append("(b.gegenpartei LIKE ? OR b.verwendungszweck LIKE ? OR b.notiz LIKE ? OR "
                     "printf('%.2f', abs(b.betrag_cent)/100.0) LIKE ?)")
        s = f"%{f['suche']}%"
        params.extend([s, s, s, f"%{f['suche'].replace(',', '.')}%"])
    if f["partei"]:
        where.append("b.gegenpartei LIKE ?")
        params.append(f"%{f['partei']}%")
    if f["von"]:
        where.append("b.buchungsdatum >= ?")
        params.append(f["von"])
    if f["bis"]:
        where.append("b.buchungsdatum <= ?")
        params.append(f["bis"])
    for feld, op in (("min", ">="), ("max", "<=")):
        if f[feld]:
            try:
                wert = abs(parse_euro_eingabe(f[feld]))
            except ValueError:
                continue
            where.append(f"abs(b.betrag_cent) {op} ?")
            params.append(wert)
    if f["richtung"] == "aus":
        where.append("b.betrag_cent < 0")
    elif f["richtung"] == "ein":
        where.append("b.betrag_cent > 0")
    if f["status"] == "ungeprueft":
        where.append("b.geprueft = 0 AND b.kategorie_id IS NOT NULL AND b.ist_umbuchung = 0")
    elif f["status"] == "umbuchung":
        where.append("b.ist_umbuchung = 1")
    elif f["status"] == "manuell":
        where.append("b.zuordnung_quelle = 'manuell'")
    elif f["status"] == "aufgeteilt":
        where.append("EXISTS (SELECT 1 FROM buchung_split s WHERE s.buchung_id = b.id)")
    elif f["status"] == "verteilt":
        where.append("b.verteilung_monate > 1")
    elif f["status"] == "bar":
        where.append("b.manuell_erfasst = 1")
    sql_where = " AND ".join(where)
    rows = q(f"""SELECT b.*, k.name AS konto_name, k.typ AS konto_typ, kat.pfad AS kat_pfad,
                        p.name AS person_name, r.name AS regel_name, rl.name AS ruecklage_name,
                        gk.name AS umbuchung_konto_name,
                        (SELECT MIN(t.name) FROM buchung_tag bt JOIN tag t ON t.id = bt.tag_id
                         WHERE bt.buchung_id = b.id) AS tagsort
                 FROM buchung b JOIN konto k ON k.id = b.konto_id
                 LEFT JOIN kategorie kat ON kat.id = b.kategorie_id
                 LEFT JOIN person p ON p.id = b.person_id
                 LEFT JOIN regel r ON r.id = b.regel_id
                 LEFT JOIN ruecklage rl ON rl.id = b.ruecklage_id
                 LEFT JOIN konto gk ON gk.id = b.umbuchung_konto_id
                 WHERE {sql_where} ORDER BY {_order(f["sort"])} LIMIT {int(limit)}""", params)
    summe = q1(f"""SELECT COUNT(*) AS n,
                     COALESCE(SUM(CASE WHEN b.betrag_cent < 0 AND b.ist_umbuchung = 0 THEN b.betrag_cent END),0) AS aus,
                     COALESCE(SUM(CASE WHEN b.betrag_cent > 0 AND b.ist_umbuchung = 0 THEN b.betrag_cent END),0) AS ein
                   FROM buchung b WHERE {sql_where}""", params)
    return rows, summe, sichtbar


def _order(sort: str) -> str:
    schluessel = (sort or "-datum").lstrip("-")
    richtung = "DESC" if (sort or "-datum").startswith("-") else "ASC"
    return SORTIERUNG.get(schluessel, SORTIERUNG["datum"]).format(r=richtung)


def _split_details(ids):
    erg: dict = {}
    if not ids:
        return erg
    marks = ",".join("?" * len(ids))
    for r in q(f"""SELECT s.*, k.pfad AS kat_pfad, p.name AS person_name FROM buchung_split s
                   LEFT JOIN kategorie k ON k.id = s.kategorie_id LEFT JOIN person p ON p.id = s.person_id
                   WHERE s.buchung_id IN ({marks}) ORDER BY s.id""", ids):
        erg.setdefault(r["buchung_id"], []).append(r)
    return erg


@bp.route("/")
@auth.login_required
def liste():
    f = _filter()
    if not request.args:
        f["monat"] = aktueller_monat()
    rows, summe, sichtbar = _abfrage(f)
    ids = [r["id"] for r in rows]
    konten = q(f"SELECT * FROM konto WHERE id IN ({','.join('?' * len(sichtbar)) or 'NULL'}) ORDER BY sortierung, name",
               sichtbar)
    monate = [r["abrechnungsmonat"] for r in q("SELECT DISTINCT abrechnungsmonat FROM buchung ORDER BY 1 DESC LIMIT 36")]
    return render_template("buchungen.html", rows=rows, summe=summe, f=f, konten=konten,
                           kategorien=kategorien.alle(), personen=q("SELECT * FROM person WHERE aktiv = 1 ORDER BY name"),
                           monate=monate, tags_je=tags.fuer_buchungen(ids), splits_je=_split_details(ids),
                           alle_tags=q("SELECT * FROM tag ORDER BY name"), filter_n=filter_aktiv(f),
                           tag_name=(q1("SELECT name FROM tag WHERE id = ?", (f["tag"],)) or {"name": ""})["name"] if f["tag"] else "",
                           basis={k: v for k, v in f.items() if v not in (None, "")},
                           gegenkonten=_gegenkonten_liste(),
                           aktive=_aktive_filter(f, konten))


def _gegenkonten_liste():
    sichtbar = auth.sichtbare_konten(nur_aktive=True, mit_darlehen=False)
    return q(f"SELECT id, name, typ FROM konto WHERE id IN ({','.join('?' * len(sichtbar)) or 'NULL'}) ORDER BY sortierung, name",
             sichtbar)


def _aktive_filter(f, konten) -> list[tuple[str, str]]:
    """Für die Chip-Leiste: (Schlüssel, Beschriftung) aller gesetzten Filter."""
    namen = {k["id"]: k["name"] for k in konten}
    erg = []
    if f["konto"]:
        erg.append(("konto", f"Konto: {namen.get(f['konto'], '?')}"))
    if f["kategorie"]:
        k = q1("SELECT pfad FROM kategorie WHERE id = ?", (int_oder_none(f["kategorie"]) or 0,))
        erg.append(("kategorie", "ohne Kategorie" if f["kategorie"] == "ohne" else f"Kategorie: {k['pfad'] if k else '?'}"))
    if f["person"]:
        p = q1("SELECT name FROM person WHERE id = ?", (f["person"],))
        erg.append(("person", f"Person: {p['name'] if p else '?'}"))
    if f["tag"]:
        t = q1("SELECT name FROM tag WHERE id = ?", (f["tag"],))
        erg.append(("tag", f"#{t['name'] if t else '?'}"))
    if f["partei"]:
        erg.append(("partei", f"Gegenpartei enthält „{f['partei']}“"))
    if f["suche"]:
        erg.append(("suche", f"Suche „{f['suche']}“"))
    if f["von"]:
        erg.append(("von", f"ab {datum_de(f['von'])}"))
    if f["bis"]:
        erg.append(("bis", f"bis {datum_de(f['bis'])}"))
    if f["min"]:
        erg.append(("min", f"Betrag ≥ {f['min']} €"))
    if f["max"]:
        erg.append(("max", f"Betrag ≤ {f['max']} €"))
    if f["richtung"]:
        erg.append(("richtung", "nur Ausgaben" if f["richtung"] == "aus" else "nur Einnahmen"))
    if f["status"]:
        erg.append(("status", f"Status: {f['status']}"))
    return erg


@bp.route("/sammel", methods=["POST"])
@auth.schreibrecht
def sammel():
    ids = [int(i) for i in request.form.getlist("ids") if i.isdigit()]
    sichtbar = set(auth.sichtbare_konten())
    ids = [i for i in ids if (r := q1("SELECT konto_id FROM buchung WHERE id = ?", (i,))) and r["konto_id"] in sichtbar]
    aktion = request.form.get("aktion")
    if not ids:
        melde("Keine Buchungen ausgewählt.", "warn")
    elif aktion == "kategorie":
        kat = int_oder_none(request.form.get("kategorie_id"))
        n = 0
        for i in ids:
            b = q1("SELECT * FROM buchung WHERE id = ?", (i,))
            if b["ist_umbuchung"] or splits.hat_split([i]):
                continue
            zuordnung.feedback(b, kat)
            exe("UPDATE buchung SET kategorie_id = ?, zuordnung_quelle = 'manuell', geprueft = 1, regel_id = NULL, "
                "vorschlag_kategorie_id = NULL WHERE id = ?", (kat, i))
            n += 1
        melde(f"Kategorie für {n} Buchungen gesetzt." + (" Aufgeteilte Buchungen und Umbuchungen bleiben unverändert."
                                                         if n < len(ids) else ""))
    elif aktion == "person":
        pid = int_oder_none(request.form.get("person_id"))
        for i in ids:
            exe("UPDATE buchung SET person_id = ? WHERE id = ?", (pid, i))
        melde(f"Person für {len(ids)} Buchungen gesetzt.")
    elif aktion == "monat":
        m = request.form.get("abrechnungsmonat", "")
        if ist_monat(m):
            for i in ids:
                exe("UPDATE buchung SET abrechnungsmonat = ? WHERE id = ?", (m, i))
            melde(f"Abrechnungsmonat für {len(ids)} Buchungen gesetzt.")
        else:
            melde("Bitte einen Monat wählen.", "warn")
    elif aktion == "verteilung":
        n = max(1, min(60, int_oder_none(request.form.get("verteilung_monate")) or 1))
        for i in ids:
            exe("UPDATE buchung SET verteilung_monate = ? WHERE id = ?", (n, i))
        melde(f"{len(ids)} Buchungen " + (f"auf {n} Monate verteilt." if n > 1 else "nicht mehr verteilt."))
    elif aktion == "tag":
        tid = tags.finde_oder_lege_an(request.form.get("tag_name", ""))
        if tid:
            n = tags.hinzufuegen(ids, tid)
            melde(f"Tag bei {n} Buchungen ergänzt.")
        else:
            melde("Bitte einen Tag-Namen eingeben.", "warn")
    elif aktion == "tag_weg" and int_oder_none(request.form.get("tag_id")):
        for i in ids:
            exe("DELETE FROM buchung_tag WHERE buchung_id = ? AND tag_id = ?", (i, int(request.form["tag_id"])))
        melde(f"Tag bei {len(ids)} Buchungen entfernt.")
    elif aktion == "bestaetigen":
        for i in ids:
            b = q1("SELECT * FROM buchung WHERE id = ?", (i,))
            if b["kategorie_id"] and not b["geprueft"]:
                zuordnung.feedback(b, b["kategorie_id"])
                exe("UPDATE buchung SET geprueft = 1 WHERE id = ?", (i,))
        melde(f"{len(ids)} Buchungen als geprüft bestätigt.")
    elif aktion == "als_umbuchung":
        zaehler: dict = {}
        for i in ids:
            b = q1("SELECT * FROM buchung WHERE id = ?", (i,))
            if b["ist_umbuchung"]:
                continue
            splits.speichere(b, [])
            if b["ruecklage_id"]:
                ruecklagen.entnahme_fuer_buchung(i, None)
            erg = umbuchungen.markiere(q1("SELECT * FROM buchung WHERE id = ?", (i,)),
                                       _gegenkonto(request.form.get("gegenkonto"), b))
            zaehler[erg] = zaehler.get(erg, 0) + 1
        n = sum(zaehler.values())
        details = ", ".join(f"{v} {t}" for k, t in (("angelegt", "im Barkonto gegengebucht"), ("verknuepft", "verknüpft"),
                                                     ("vorgemerkt", "Gegenbuchung folgt beim Import"))
                            if (v := zaehler.get(k)))
        melde(f"{n} Buchungen als Umbuchung markiert" + (f" ({details})." if details else "."))
    elif aktion == "umbuchung" and len(ids) == 2:
        a, b = (q1("SELECT * FROM buchung WHERE id = ?", (i,)) for i in ids)
        if a["betrag_cent"] != -b["betrag_cent"] or a["konto_id"] == b["konto_id"]:
            melde("Zwei Buchungen mit entgegengesetztem, gleichem Betrag auf verschiedenen Konten auswählen.", "warn")
        else:
            umbuchungen.verknuepfe(a["id"], b["id"])
            melde("Als Umbuchung verknüpft.")
    else:
        melde("Aktion nicht möglich.", "warn")
    log_aenderung(g.user["id"], "buchung", None, f"sammel:{aktion}", {"ids": ids})
    commit()
    return redirect(request.form.get("zurueck") or url_for("buchungen.liste"))


@bp.route("/<int:bid>/inline", methods=["POST"])
@auth.schreibrecht
def inline(bid):
    """Direkte Bearbeitung in der Tabelle (Kategorie, Person, Tags). Antwort als JSON."""
    from flask import jsonify
    b = q1("SELECT * FROM buchung WHERE id = ?", (bid,))
    if not b or not auth.konto_sichtbar(b["konto_id"]):
        abort(404)
    daten = request.get_json(silent=True) or request.form
    feld, wert = daten.get("feld"), daten.get("wert")
    if feld == "kategorie":
        if b["ist_umbuchung"] or splits.hat_split([bid]):
            return jsonify(ok=False, meldung="Umbuchung oder aufgeteilte Buchung – bitte in der Buchung bearbeiten."), 400
        kat = int_oder_none(wert)
        if kat and not q1("SELECT 1 FROM kategorie WHERE id = ?", (kat,)):
            return jsonify(ok=False, meldung="Unbekannte Kategorie."), 400
        if kat and kategorien.art_map().get(kat) == "umbuchung":
            return jsonify(ok=False, frage_gegenkonto=True, meldung="Bitte das Gegenkonto wählen."), 409
        zuordnung.feedback(b, kat)
        exe("UPDATE buchung SET kategorie_id = ?, zuordnung_quelle = 'manuell', geprueft = 1, regel_id = NULL, "
            "vorschlag_kategorie_id = NULL WHERE id = ?", (kat, bid))
        anzeige = (q1("SELECT pfad FROM kategorie WHERE id = ?", (kat,)) or {"pfad": ""})["pfad"] if kat else ""
    elif feld == "umbuchung":
        if b["ist_umbuchung"]:
            return jsonify(ok=False, meldung="Ist bereits eine Umbuchung."), 400
        splits.speichere(b, [])
        if b["ruecklage_id"]:
            ruecklagen.entnahme_fuer_buchung(bid, None)
        ziel = _gegenkonto(wert, b)
        erg = umbuchungen.markiere(q1("SELECT * FROM buchung WHERE id = ?", (bid,)), ziel)
        name = (q1("SELECT name FROM konto WHERE id = ?", (ziel,)) or {"name": ""})["name"] if ziel else "Konto außerhalb"
        anzeige = f"Umbuchung mit {name}"
        log_aenderung(g.user["id"], "buchung", bid, "inline:umbuchung", {"gegenkonto": ziel, "ergebnis": erg})
        commit()
        return jsonify(ok=True, anzeige=anzeige, umbuchung=True, ergebnis=erg, meldung=umbuchungen.MELDUNGEN[erg])
    elif feld == "person":
        pid = int_oder_none(wert)
        if pid and not q1("SELECT 1 FROM person WHERE id = ?", (pid,)):
            return jsonify(ok=False, meldung="Unbekannte Person."), 400
        exe("UPDATE buchung SET person_id = ? WHERE id = ?", (pid, bid))
        anzeige = (q1("SELECT name FROM person WHERE id = ?", (pid,)) or {"name": ""})["name"] if pid else ""
    elif feld == "tags":
        tags.setze(bid, [t for t in str(wert or "").split(",") if t.strip()])
        anzeige = ", ".join(t["name"] for t in tags.fuer_buchungen([bid]).get(bid, []))
    else:
        return jsonify(ok=False, meldung="Unbekanntes Feld."), 400
    log_aenderung(g.user["id"], "buchung", bid, f"inline:{feld}", {"wert": wert})
    commit()
    return jsonify(ok=True, anzeige=anzeige)


def _gegenkonto(wert, b):
    """Formularwert -> Konto-ID oder None (außerhalb). Nur sichtbare, eigene Konten, nicht das eigene."""
    kid = int_oder_none(wert)
    if not kid or kid == b["konto_id"] or not auth.konto_sichtbar(kid):
        return None
    k = q1("SELECT typ FROM konto WHERE id = ?", (kid,))
    return kid if k and k["typ"] != "darlehen" else None


def _ist_umbuchung_formular(form) -> bool:
    """Art „Umbuchung“ gewählt – oder die Kategorie „Umbuchung“ (auch ohne JavaScript)."""
    if form.get("art") == "umbuchung":
        return True
    if form.get("art") == "kategorie":
        return False
    kat = int_oder_none(form.get("kategorie_id"))
    return bool(kat) and kategorien.art_map().get(kat) == "umbuchung"


def _split_zeilen_aus_formular():
    zeilen = []
    betraege = request.form.getlist("split_betrag")
    kats = request.form.getlist("split_kategorie")
    personen = request.form.getlist("split_person")
    notizen = request.form.getlist("split_notiz")
    for i, roh in enumerate(betraege):
        if not roh.strip():
            continue
        zeilen.append({"betrag_cent": parse_euro_eingabe(roh), "kategorie_id": int_oder_none(kats[i] if i < len(kats) else None),
                       "person_id": int_oder_none(personen[i] if i < len(personen) else None),
                       "notiz": (notizen[i] if i < len(notizen) else "").strip()})
    return zeilen


@bp.route("/<int:bid>", methods=["GET", "POST"])
@auth.login_required
def bearbeiten(bid):
    b = q1("""SELECT b.*, k.name AS konto_name, k.typ AS konto_typ, r.name AS regel_name, kat.pfad AS kat_pfad,
                     gk.name AS umbuchung_konto_name
              FROM buchung b JOIN konto k ON k.id = b.konto_id LEFT JOIN konto gk ON gk.id = b.umbuchung_konto_id
              LEFT JOIN regel r ON r.id = b.regel_id LEFT JOIN kategorie kat ON kat.id = b.kategorie_id
              WHERE b.id = ?""", (bid,))
    if not b or not auth.konto_sichtbar(b["konto_id"]):
        abort(404)
    if request.method == "POST":
        if not auth.darf_schreiben():
            abort(403)
        aktion = request.form.get("aktion")
        if aktion == "umbuchung_loesen":
            umbuchungen.loese(bid)
            melde("Umbuchung gelöst.")
        elif aktion == "loeschen" and b["manuell_erfasst"]:
            exe("DELETE FROM ruecklage_bewegung WHERE buchung_id = ?", (bid,))
            exe("DELETE FROM buchung WHERE id = ?", (bid,))
            log_aenderung(g.user["id"], "buchung", bid, "geloescht", dict(b))
            commit()
            melde("Buchung gelöscht.")
            return redirect(request.form.get("zurueck") or url_for("buchungen.liste"))
        elif _ist_umbuchung_formular(request.form):
            splits.speichere(b, [])
            m = request.form.get("abrechnungsmonat")
            exe("UPDATE buchung SET person_id = ?, abrechnungsmonat = ?, notiz = ? WHERE id = ?",
                (int_oder_none(request.form.get("person_id")), m if ist_monat(m) else b["abrechnungsmonat"],
                 request.form.get("notiz", "").strip() or None, bid))
            if b["ruecklage_id"]:
                ruecklagen.entnahme_fuer_buchung(bid, None)
            tags.setze(bid, [t for t in request.form.get("tags", "").split(",") if t.strip()])
            erg = umbuchungen.markiere(q1("SELECT * FROM buchung WHERE id = ?", (bid,)), _gegenkonto(request.form.get("gegenkonto"), b))
            melde(umbuchungen.MELDUNGEN[erg])
        else:
            try:
                zeilen = _split_zeilen_aus_formular() if request.form.get("aufteilen") else []
                splits.speichere(b, zeilen)
            except ValueError as exc:
                melde(str(exc), "warn")
                return redirect(url_for("buchungen.bearbeiten", bid=bid, zurueck=request.form.get("zurueck", ""), split=1))
            m = request.form.get("abrechnungsmonat")
            verteilung = max(1, min(60, int_oder_none(request.form.get("verteilung_monate")) or 1))
            werte = {"person_id": int_oder_none(request.form.get("person_id")),
                     "abrechnungsmonat": m if ist_monat(m) else b["abrechnungsmonat"],
                     "notiz": request.form.get("notiz", "").strip() or None, "verteilung_monate": verteilung}
            if zeilen:
                exe("UPDATE buchung SET person_id = ?, abrechnungsmonat = ?, notiz = ?, verteilung_monate = ? WHERE id = ?",
                    (*werte.values(), bid))
            else:
                kat = int_oder_none(request.form.get("kategorie_id"))
                zuordnung.feedback(b, kat)
                exe("UPDATE buchung SET kategorie_id = ?, person_id = ?, abrechnungsmonat = ?, notiz = ?, verteilung_monate = ?, "
                    "zuordnung_quelle = 'manuell', geprueft = 1, regel_id = NULL, vorschlag_kategorie_id = NULL WHERE id = ?",
                    (kat, *werte.values(), bid))
            tags.setze(bid, [t for t in request.form.get("tags", "").split(",") if t.strip()])
            rl = int_oder_none(request.form.get("ruecklage_id"))
            if rl != b["ruecklage_id"]:
                ruecklagen.entnahme_fuer_buchung(bid, rl)
            melde("Buchung gespeichert.")
        log_aenderung(g.user["id"], "buchung", bid, "bearbeitet", dict(request.form))
        commit()
        if request.form.get("regel"):
            return redirect(url_for("regeln.neu", von_buchung=bid))
        return redirect(request.form.get("zurueck") or url_for("buchungen.liste"))
    partner = q1("SELECT b.*, k.name AS konto_name FROM buchung b JOIN konto k ON k.id = b.konto_id WHERE b.id = ?",
                 (b["umbuchung_partner_id"],)) if b["umbuchung_partner_id"] else None
    monate = [monat_plus(b["abrechnungsmonat"], i) for i in (-2, -1, 0, 1, 2)]
    vorschlag = q1("SELECT pfad FROM kategorie WHERE id = ?", (b["vorschlag_kategorie_id"],)) \
        if b["vorschlag_kategorie_id"] and not b["kategorie_id"] else None
    return render_template("buchung.html", b=b, partner=partner, kategorien=kategorien.alle(),
                           personen=q("SELECT * FROM person WHERE aktiv = 1 ORDER BY name"), monate=monate,
                           zurueck=request.args.get("zurueck", ""), split_liste=splits.lade(bid),
                           split_offen=bool(request.args.get("split")),
                           tags=tags.fuer_buchungen([bid]).get(bid, []), alle_tags=q("SELECT name FROM tag ORDER BY name"),
                           ruecklagen=q("SELECT r.id, r.name, k.name AS konto_name FROM ruecklage r JOIN konto k "
                                        "ON k.id = r.traeger_konto_id WHERE r.aktiv = 1 AND r.bezug = 'topf' ORDER BY r.name"),
                           vorschlag=vorschlag, gegenkonten=[k for k in _gegenkonten_liste() if k["id"] != b["konto_id"]],
                           umbuchung_kat=kategorien.umbuchung_kategorie_id())


@bp.route("/export.csv")
@auth.login_required
def export():
    f = _filter()
    rows, _, _ = _abfrage(f, limit=1_000_000)
    ids = [r["id"] for r in rows]
    tags_je = tags.fuer_buchungen(ids)
    splits_je = _split_details(ids)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Buchungsdatum", "Abrechnungsmonat", "Konto", "Gegenpartei", "Gegen-IBAN", "Verwendungszweck",
                "Betrag", "Kategorie", "Person", "Umbuchung", "Notiz", "Zuordnung", "Tags", "Verteilt auf Monate", "Teil"])

    def betrag(c):
        return f"{c / 100:.2f}".replace(".", ",")
    for r in rows:
        tagtext = ", ".join(t["name"] for t in tags_je.get(r["id"], []))
        basis = [r["buchungsdatum"], r["abrechnungsmonat"], r["konto_name"], r["gegenpartei"], r["gegen_iban"] or "",
                 r["verwendungszweck"]]
        if r["id"] in splits_je:
            for i, s in enumerate(splits_je[r["id"]], 1):
                w.writerow(basis + [betrag(s["betrag_cent"]), s["kat_pfad"] or "", s["person_name"] or r["person_name"] or "",
                                    "", s["notiz"] or r["notiz"] or "", "aufgeteilt", tagtext, r["verteilung_monate"],
                                    f"{i}/{len(splits_je[r['id']])}"])
        else:
            w.writerow(basis + [betrag(r["betrag_cent"]), r["kat_pfad"] or "", r["person_name"] or "",
                                "ja" if r["ist_umbuchung"] else "", r["notiz"] or "", r["zuordnung_quelle"] or "", tagtext,
                                r["verteilung_monate"], ""])
    name = "buchungen.csv"
    if f["tag"]:
        t = q1("SELECT name FROM tag WHERE id = ?", (f["tag"],))
        if t:
            name = "".join(ch if ch.isalnum() else "-" for ch in t["name"]).strip("-").lower() + ".csv"
    return Response("﻿" + buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={name}"})
