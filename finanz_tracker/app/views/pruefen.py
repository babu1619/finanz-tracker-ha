"""Prüf-Modus: offene Buchungen einzeln zuordnen, mit Vorschlag und optionaler Regel."""
from flask import Blueprint, abort, g, redirect, render_template, request, session, url_for

from .. import auth
from ..db import q, q1, exe, commit, jdump, log_aenderung
from ..services import kategorien, umbuchungen, zuordnung
from ..util import ist_monat, monat_plus
from . import melde, int_oder_none

bp = Blueprint("pruefen", __name__, url_prefix="/pruefen")


def _offene():
    sichtbar = auth.sichtbare_konten()
    if not sichtbar:
        return []
    marks = ",".join("?" * len(sichtbar))
    return q(f"""SELECT b.id FROM buchung b JOIN konto k ON k.id = b.konto_id
                 WHERE b.konto_id IN ({marks}) AND b.ist_umbuchung = 0
                   AND (b.kategorie_id IS NULL OR b.geprueft = 0)
                 ORDER BY (b.kategorie_id IS NOT NULL), b.buchungsdatum DESC, b.id DESC""", sichtbar)


@bp.route("/")
@auth.schreibrecht
def index():
    offene = [r["id"] for r in _offene()]
    uebersprungen = set(session.get("uebersprungen", []))
    rest = [i for i in offene if i not in uebersprungen] or offene
    vorschlaege = umbuchungen.offene_vorschlaege(auth.sichtbare_konten())
    if not rest:
        return render_template("pruefen.html", b=None, gesamt=0, vorschlaege=vorschlaege)
    b = q1("""SELECT b.*, k.name AS konto_name, kat.pfad AS kat_pfad FROM buchung b JOIN konto k ON k.id = b.konto_id
              LEFT JOIN kategorie kat ON kat.id = b.kategorie_id WHERE b.id = ?""", (rest[0],))
    vorschlag = None
    if b["kategorie_id"]:
        vorschlag = {"kategorie_id": b["kategorie_id"], "person_id": b["person_id"], "quelle": b["zuordnung_quelle"]}
    else:
        gv = zuordnung.gedaechtnis_vorschlag(b)
        if gv:
            vorschlag = {"kategorie_id": gv["kategorie_id"], "person_id": gv["person_id"], "quelle": "gedaechtnis",
                         "anzahl": gv["anzahl"]}
    aehnliche = q("""SELECT b.buchungsdatum, b.betrag_cent, kat.pfad AS kat_pfad, p.name AS person_name
                     FROM buchung b LEFT JOIN kategorie kat ON kat.id = b.kategorie_id
                     LEFT JOIN person p ON p.id = b.person_id
                     WHERE b.partner_key = ? AND b.partner_key != '' AND b.id != ? AND b.kategorie_id IS NOT NULL
                     ORDER BY b.buchungsdatum DESC LIMIT 6""", (b["partner_key"], b["id"]))
    alle_kat = kategorien.alle()
    vorschlag_pfad = next((k["pfad"] for k in alle_kat if vorschlag and k["id"] == vorschlag["kategorie_id"]), None)
    return render_template(
        "pruefen.html", b=b, gesamt=len(offene), position=offene.index(b["id"]) + 1, vorschlag=vorschlag,
        vorschlag_pfad=vorschlag_pfad, aehnliche=aehnliche, kategorien=alle_kat,
        personen=q("SELECT * FROM person WHERE aktiv = 1 ORDER BY name"),
        monate=[monat_plus(b["abrechnungsmonat"], i) for i in (-1, 0, 1)], vorschlaege=vorschlaege)


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
    kat = int_oder_none(request.form.get("kategorie_id"))
    if not kat:
        melde("Bitte eine Kategorie wählen.", "warn")
        return redirect(url_for("pruefen.index"))
    person = int_oder_none(request.form.get("person_id"))
    monat = request.form.get("abrechnungsmonat")
    exe("UPDATE buchung SET kategorie_id = ?, person_id = ?, abrechnungsmonat = ?, zuordnung_quelle = 'manuell', "
        "geprueft = 1, regel_id = NULL WHERE id = ?",
        (kat, person, monat if ist_monat(monat) else b["abrechnungsmonat"], bid))
    log_aenderung(g.user["id"], "buchung", bid, "geprueft", {"kategorie_id": kat, "person_id": person})
    if request.form.get("regel") and request.form.get("regel_text", "").strip():
        feld = request.form.get("regel_feld", "gegenpartei")
        text = request.form["regel_text"].strip()
        aktionen = {"kategorie_id": kat}
        if person:
            aktionen["person_id"] = person
        rid = exe("INSERT INTO regel (name, prioritaet, bedingungen, aktionen) VALUES (?,?,?,?)",
                  (f"{text} → automatisch", zuordnung.naechste_prioritaet(),
                   jdump([{"feld": feld, "op": "enthaelt", "wert": text}]), jdump(aktionen)))
        offen = [r["id"] for r in _offene()]
        stat = zuordnung.ordne_zu(offen)
        melde(f"Regel angelegt; {stat['regel']} weitere offene Buchungen damit zugeordnet.")
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
