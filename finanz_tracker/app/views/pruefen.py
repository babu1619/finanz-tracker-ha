"""Prüf-Modus: offene Buchungen einzeln oder als Tabelle zuordnen, mit Vorschlag, Tags, Umbuchung und Regel."""
from flask import Blueprint, abort, g, redirect, render_template, request, session, url_for

from .. import auth
from ..db import q, q1, exe, commit, jdump, log_aenderung
from ..services import kategorien, tags, umbuchungen, zuordnung
from ..util import ist_monat, monat_plus
from . import melde, int_oder_none

bp = Blueprint("pruefen", __name__, url_prefix="/pruefen")

TABELLE_MAX = 150


def _offene():
    sichtbar = auth.sichtbare_konten()
    if not sichtbar:
        return []
    marks = ",".join("?" * len(sichtbar))
    return q(f"""SELECT b.id FROM buchung b JOIN konto k ON k.id = b.konto_id
                 WHERE b.konto_id IN ({marks}) AND b.ist_umbuchung = 0
                   AND (b.kategorie_id IS NULL OR b.geprueft = 0)
                 ORDER BY (b.kategorie_id IS NOT NULL), b.buchungsdatum DESC, b.id DESC""", sichtbar)


def _gegenkonten():
    """Eigene Konten, auf die umgebucht werden kann (ohne Darlehen)."""
    sichtbar = auth.sichtbare_konten(nur_aktive=True, mit_darlehen=False)
    return q(f"SELECT id, name, typ FROM konto WHERE id IN ({','.join('?' * len(sichtbar)) or 'NULL'}) "
             f"ORDER BY sortierung, name", sichtbar)


def _vorschlag(b):
    """Kategorie-Vorschlag: bestehende Zuordnung, Gedächtnis oder Lernmodell."""
    if b["kategorie_id"]:
        return {"kategorie_id": b["kategorie_id"], "person_id": b["person_id"], "quelle": b["zuordnung_quelle"],
                "konfidenz": b["konfidenz"]}
    gv = zuordnung.gedaechtnis_vorschlag(b)
    if gv:
        return {"kategorie_id": gv["kategorie_id"], "person_id": gv["person_id"], "quelle": "gedaechtnis",
                "anzahl": gv["anzahl"]}
    if b["vorschlag_kategorie_id"]:
        return {"kategorie_id": b["vorschlag_kategorie_id"], "person_id": b["person_id"], "quelle": "modell",
                "konfidenz": b["konfidenz"]}
    return None


def _tagnamen(text: str) -> list[str]:
    return [t.strip() for t in (text or "").split(",") if t.strip()]


def _speichere_eine(b, kat, person, monat, tagtext, art, gegenkonto) -> str:
    """Speichert die Zuordnung einer Buchung. Rückgabe: Kurzbeschreibung für die Meldung."""
    tags.setze(b["id"], _tagnamen(tagtext))
    if art == "umbuchung":
        if gegenkonto == b["konto_id"]:
            gegenkonto = None
        erg = umbuchungen.markiere(b, gegenkonto)
        if person is not None:
            exe("UPDATE buchung SET person_id = ? WHERE id = ?", (person, b["id"]))
        log_aenderung(g.user["id"], "buchung", b["id"], "umbuchung", {"gegenkonto": gegenkonto, "ergebnis": erg})
        return erg
    zuordnung.feedback(b, kat)
    exe("UPDATE buchung SET kategorie_id = ?, person_id = ?, abrechnungsmonat = ?, zuordnung_quelle = 'manuell', "
        "geprueft = 1, regel_id = NULL, vorschlag_kategorie_id = NULL WHERE id = ?",
        (kat, person, monat if ist_monat(monat) else b["abrechnungsmonat"], b["id"]))
    log_aenderung(g.user["id"], "buchung", b["id"], "geprueft", {"kategorie_id": kat, "person_id": person})
    return "kategorie"


@bp.route("/")
@auth.schreibrecht
def index():
    if request.args.get("ansicht") == "tabelle":
        session["pruef_ansicht"] = "tabelle"
    elif request.args.get("ansicht") == "einzeln":
        session["pruef_ansicht"] = "einzeln"
    if session.get("pruef_ansicht") == "tabelle":
        return tabelle()
    offene = [r["id"] for r in _offene()]
    uebersprungen = set(session.get("uebersprungen", []))
    rest = [i for i in offene if i not in uebersprungen] or offene
    vorschlaege = umbuchungen.offene_vorschlaege(auth.sichtbare_konten())
    if not rest:
        return render_template("pruefen.html", b=None, gesamt=0, vorschlaege=vorschlaege)
    b = q1("""SELECT b.*, k.name AS konto_name, kat.pfad AS kat_pfad FROM buchung b JOIN konto k ON k.id = b.konto_id
              LEFT JOIN kategorie kat ON kat.id = b.kategorie_id WHERE b.id = ?""", (rest[0],))
    vorschlag = _vorschlag(b)
    aehnliche = q("""SELECT b.buchungsdatum, b.betrag_cent, kat.pfad AS kat_pfad, p.name AS person_name
                     FROM buchung b LEFT JOIN kategorie kat ON kat.id = b.kategorie_id
                     LEFT JOIN person p ON p.id = b.person_id
                     WHERE b.partner_key = ? AND b.partner_key != '' AND b.id != ? AND b.kategorie_id IS NOT NULL
                     ORDER BY b.buchungsdatum DESC LIMIT 6""", (b["partner_key"], b["id"]))
    alle_kat = kategorien.alle()
    vorschlag_pfad = next((k["pfad"] for k in alle_kat if vorschlag and k["id"] == vorschlag["kategorie_id"]), None)
    # Tags aus früheren Buchungen derselben Gegenpartei vorschlagen
    tag_vorschlag = [r["name"] for r in q("""SELECT t.name, COUNT(*) AS n FROM buchung_tag bt JOIN tag t ON t.id = bt.tag_id
                                             JOIN buchung x ON x.id = bt.buchung_id
                                             WHERE x.partner_key = ? AND x.partner_key != '' AND x.id != ?
                                             GROUP BY t.id ORDER BY n DESC LIMIT 3""", (b["partner_key"], b["id"]))]
    vorhandene_tags = [t["name"] for t in tags.fuer_buchungen([b["id"]]).get(b["id"], [])]
    # Gegenkonto vorschlagen: IBAN der Gegenpartei passt zu eigenem Konto oder offener Umbuchungsvorschlag
    gegen_vorschlag = None
    if b["gegen_iban"]:
        k = q1("SELECT id FROM konto WHERE replace(upper(iban), ' ', '') = ? AND id != ?",
               (b["gegen_iban"].replace(" ", "").upper(), b["konto_id"]))
        gegen_vorschlag = k["id"] if k else None
    if not gegen_vorschlag:
        v = q1("""SELECT CASE WHEN v.buchung_a_id = ? THEN bb.konto_id ELSE ba.konto_id END AS kid
                  FROM umbuchung_vorschlag v JOIN buchung ba ON ba.id = v.buchung_a_id JOIN buchung bb ON bb.id = v.buchung_b_id
                  WHERE (v.buchung_a_id = ? OR v.buchung_b_id = ?) AND v.status = 'offen' ORDER BY v.score DESC LIMIT 1""",
               (b["id"], b["id"], b["id"]))
        gegen_vorschlag = v["kid"] if v else None
    return render_template(
        "pruefen.html", b=b, gesamt=len(offene), position=offene.index(b["id"]) + 1, vorschlag=vorschlag,
        vorschlag_pfad=vorschlag_pfad, aehnliche=aehnliche, kategorien=alle_kat,
        personen=q("SELECT * FROM person WHERE aktiv = 1 ORDER BY name"),
        monate=[monat_plus(b["abrechnungsmonat"], i) for i in (-1, 0, 1)], vorschlaege=vorschlaege,
        gegenkonten=[k for k in _gegenkonten() if k["id"] != b["konto_id"]],
        alle_tags=q("SELECT name FROM tag ORDER BY name"),
        tag_text=", ".join(vorhandene_tags), gegen_vorschlag=gegen_vorschlag, tag_vorschlag=[t for t in tag_vorschlag if t not in vorhandene_tags])


def tabelle():
    offene = [r["id"] for r in _offene()]
    ids = offene[:TABELLE_MAX]
    rows = []
    if ids:
        marks = ",".join("?" * len(ids))
        daten = {r["id"]: r for r in q(f"""SELECT b.*, k.name AS konto_name FROM buchung b JOIN konto k ON k.id = b.konto_id
                                           WHERE b.id IN ({marks})""", ids)}
        tags_je = tags.fuer_buchungen(ids)
        for i in ids:
            b = daten[i]
            rows.append({"b": b, "vorschlag": _vorschlag(b),
                         "tags": ", ".join(t["name"] for t in tags_je.get(i, []))})
    return render_template("pruefen_tabelle.html", rows=rows, gesamt=len(offene), max=TABELLE_MAX,
                           kategorien=kategorien.alle(), personen=q("SELECT * FROM person WHERE aktiv = 1 ORDER BY name"),
                           gegenkonten=_gegenkonten(), alle_tags=q("SELECT name FROM tag ORDER BY name"),
                           vorschlaege=umbuchungen.offene_vorschlaege(auth.sichtbare_konten()))


@bp.route("/tabelle", methods=["POST"])
@auth.schreibrecht
def tabelle_speichern():
    ids = [int(i) for i in request.form.getlist("ids") if i.isdigit()]
    sichtbar = set(auth.sichtbare_konten())
    n = {"kategorie": 0, "verknuepft": 0, "angelegt": 0, "vorgemerkt": 0, "extern": 0, "ohne": 0}
    for bid in ids:
        b = q1("SELECT * FROM buchung WHERE id = ?", (bid,))
        if not b or b["konto_id"] not in sichtbar or b["ist_umbuchung"]:
            continue
        f = request.form
        gegen = f.get(f"gegen_{bid}", "")
        art = "umbuchung" if gegen else "kategorie"
        kat = int_oder_none(f.get(f"kat_{bid}"))
        if art == "kategorie" and not kat:
            n["ohne"] += 1
            continue
        erg = _speichere_eine(b, kat, int_oder_none(f.get(f"person_{bid}")), b["abrechnungsmonat"],
                              f.get(f"tags_{bid}", ""), art, int_oder_none(gegen) if gegen != "extern" else None)
        n[erg] = n.get(erg, 0) + 1
    commit()
    teile = []
    if n["kategorie"]:
        teile.append(f"{n['kategorie']} zugeordnet")
    umb = n["verknuepft"] + n["angelegt"] + n["vorgemerkt"] + n["extern"]
    if umb:
        zusatz = []
        if n["verknuepft"]:
            zusatz.append(f"{n['verknuepft']} mit Gegenbuchung verknüpft")
        if n["angelegt"]:
            zusatz.append(f"{n['angelegt']} automatisch gegengebucht")
        teile.append(f"{umb} als Umbuchung" + (f" ({', '.join(zusatz)})" if zusatz else ""))
    if n["ohne"]:
        teile.append(f"{n['ohne']} ohne Kategorie übersprungen")
    melde(("Gespeichert: " + ", ".join(teile) + ".") if teile else "Keine Buchung ausgewählt.", "ok" if teile else "warn")
    return redirect(url_for("pruefen.index"))


@bp.route("/<int:bid>", methods=["POST"])
@auth.schreibrecht
def speichern(bid):
    b = q1("SELECT * FROM buchung WHERE id = ?", (bid,))
    if not b or not auth.konto_sichtbar(b["konto_id"]):
        abort(404)
    if request.form.get("aktion") == "ueberspringen":
        s = session.get("uebersprungen", [])
        s.append(bid)
        session["uebersprungen"] = s[-200:]
        return redirect(url_for("pruefen.index"))
    art = "umbuchung" if request.form.get("art") == "umbuchung" else "kategorie"
    kat = int_oder_none(request.form.get("kategorie_id"))
    if art == "kategorie" and not kat:
        melde("Bitte eine Kategorie wählen.", "warn")
        return redirect(url_for("pruefen.index"))
    person = int_oder_none(request.form.get("person_id"))
    gegen = request.form.get("gegenkonto", "")
    erg = _speichere_eine(b, kat, person, request.form.get("abrechnungsmonat"), request.form.get("tags", ""), art,
                          int_oder_none(gegen) if gegen and gegen != "extern" else None)
    if erg == "verknuepft":
        melde("Als Umbuchung mit der Gegenbuchung verknüpft.")
    elif erg == "angelegt":
        melde("Als Umbuchung gespeichert; die Gegenbuchung im Bar- bzw. Depotkonto wurde automatisch angelegt.")
    elif erg == "vorgemerkt":
        melde("Als Umbuchung markiert. Die Gegenbuchung wird beim nächsten Import des Gegenkontos automatisch verknüpft.")
    elif erg == "extern":
        melde("Als Umbuchung an ein Konto außerhalb des Tools markiert.")
    if art == "kategorie" and request.form.get("regel") and request.form.get("regel_text", "").strip():
        feld = request.form.get("regel_feld", "gegenpartei")
        text = request.form["regel_text"].strip()
        aktionen = {"kategorie_id": kat}
        if person:
            aktionen["person_id"] = person
        if request.form.get("regel_tags") and _tagnamen(request.form.get("tags", "")):
            aktionen["tag_id"] = tags.finde_oder_lege_an(_tagnamen(request.form["tags"])[0])
        rid = exe("INSERT INTO regel (name, prioritaet, bedingungen, aktionen) VALUES (?,?,?,?)",
                  (f"{text} → automatisch", zuordnung.naechste_prioritaet(),
                   jdump([{"feld": feld, "op": "enthaelt", "wert": text}]), jdump(aktionen)))
        offen = [r["id"] for r in _offene()]
        stat = zuordnung.ordne_zu(offen)
        melde(f"Regel angelegt; {stat['regel']} weitere offene Buchungen damit zugeordnet.")
        log_aenderung(g.user["id"], "regel", rid, "angelegt")
    elif art == "umbuchung" and request.form.get("regel") and request.form.get("regel_text", "").strip():
        text = request.form["regel_text"].strip()
        rid = exe("INSERT INTO regel (name, prioritaet, bedingungen, aktionen) VALUES (?,?,?,?)",
                  (f"{text} → Umbuchung", zuordnung.naechste_prioritaet(),
                   jdump([{"feld": request.form.get("regel_feld", "gegenpartei"), "op": "enthaelt", "wert": text}]),
                   jdump({"als_umbuchung": True})))
        melde("Regel „als Umbuchung“ angelegt.")
        log_aenderung(g.user["id"], "regel", rid, "angelegt")
    commit()
    return redirect(url_for("pruefen.index"))


@bp.route("/umbuchung/<int:vid>", methods=["POST"])
@auth.schreibrecht
def umbuchung(vid):
    v = q1("SELECT * FROM umbuchung_vorschlag WHERE id = ?", (vid,))
    if not v:
        abort(404)
    if request.form.get("aktion") == "bestaetigen":
        umbuchungen.verknuepfe(v["buchung_a_id"], v["buchung_b_id"])
        melde("Umbuchung verknüpft.")
    else:
        exe("UPDATE umbuchung_vorschlag SET status = 'abgelehnt' WHERE id = ?", (vid,))
        melde("Vorschlag verworfen.")
    commit()
    return redirect(request.form.get("zurueck") or url_for("pruefen.index"))


@bp.route("/neustart", methods=["POST"])
@auth.schreibrecht
def neustart():
    session.pop("uebersprungen", None)
    return redirect(url_for("pruefen.index"))
