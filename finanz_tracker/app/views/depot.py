"""Depot-Seite: Ein-/Auszahlungen, Gebühren und Erträge von Hand erfassen, Rendite eintragen, Wert ablesen."""
import secrets
from datetime import date

from flask import Blueprint, abort, g, redirect, render_template, request, url_for

from .. import auth
from ..db import q, q1, exe, commit, log_aenderung
from ..services import depot, kategorien, umbuchungen, zuordnung
from ..util import euro, monat_von, partner_key, parse_euro_eingabe
from . import melde, int_oder_none

bp = Blueprint("depot", __name__, url_prefix="/depot")

ARTEN = {
    "einzahlung": ("Einzahlung", +1),
    "auszahlung": ("Auszahlung", -1),
    "gebuehr": ("Gebühr / Kosten", -1),
    "ertrag": ("Ertrag (Dividende, Zinsen)", +1),
}


def _konto(kid):
    k = q1("SELECT * FROM konto WHERE id = ? AND typ = 'depot'", (kid,))
    if not k or not auth.konto_sichtbar(kid):
        abort(404)
    return k


def _gegenkonten(kid):
    sichtbar = auth.sichtbare_konten(nur_aktive=True, mit_darlehen=False)
    return q(f"SELECT id, name, typ FROM konto WHERE id IN ({','.join('?' * len(sichtbar)) or 'NULL'}) AND id != ? "
             f"ORDER BY sortierung, name", list(sichtbar) + [kid])


@bp.route("/<int:kid>")
@auth.login_required
def detail(kid):
    k = _konto(kid)
    kz = depot.kennzahlen(kid)
    bewegungen = q("""SELECT b.*, kat.pfad AS kat_pfad, gk.name AS gegen_name FROM buchung b
                      LEFT JOIN kategorie kat ON kat.id = b.kategorie_id
                      LEFT JOIN buchung p ON p.id = b.umbuchung_partner_id
                      LEFT JOIN konto gk ON gk.id = COALESCE(p.konto_id, b.umbuchung_konto_id)
                      WHERE b.konto_id = ? ORDER BY b.buchungsdatum DESC, b.id DESC LIMIT 60""", (kid,))
    return render_template("depot.html", k=k, kz=kz, bewertungen=depot.bewertungen(kid), bewegungen=bewegungen,
                           arten=ARTEN, gegenkonten=_gegenkonten(kid), kategorien=kategorien.alle(),
                           heute=date.today().isoformat())


@bp.route("/<int:kid>/rendite", methods=["POST"])
@auth.schreibrecht
def rendite(kid):
    _konto(kid)
    f = request.form
    if f.get("loeschen"):
        exe("DELETE FROM depot_bewertung WHERE id = ? AND konto_id = ?", (int_oder_none(f["loeschen"]), kid))
        commit()
        melde("Eintrag entfernt.")
        return redirect(url_for("depot.detail", kid=kid))
    einheit = "betrag" if f.get("einheit") == "betrag" else "prozent"
    try:
        wert = parse_euro_eingabe(f.get("wert", ""))  # 12,5 -> 1250 (Hundertstel-Prozent bzw. Cent)
        datum = date.fromisoformat(f.get("datum") or date.today().isoformat())
    except ValueError:
        melde("Wert oder Datum ungültig.", "warn")
        return redirect(url_for("depot.detail", kid=kid))
    bid = exe("INSERT INTO depot_bewertung (konto_id, datum, einheit, wert, notiz) VALUES (?,?,?,?,?)",
              (kid, datum.isoformat(), einheit, wert, f.get("notiz", "").strip() or None))
    log_aenderung(g.user["id"], "depot_bewertung", bid, "erfasst", dict(f))
    commit()
    melde("Rendite eingetragen.")
    return redirect(url_for("depot.detail", kid=kid))


@bp.route("/<int:kid>/eintrag", methods=["POST"])
@auth.schreibrecht
def eintrag(kid):
    k = _konto(kid)
    f = request.form
    art = f.get("art")
    if art not in ARTEN:
        abort(400)
    try:
        betrag = abs(parse_euro_eingabe(f.get("betrag", "")))
        datum = date.fromisoformat(f.get("datum") or date.today().isoformat())
    except ValueError:
        melde("Betrag oder Datum ungültig.", "warn")
        return redirect(url_for("depot.detail", kid=kid))
    if not betrag:
        melde("Bitte einen Betrag eingeben.", "warn")
        return redirect(url_for("depot.detail", kid=kid))
    name, vz = ARTEN[art]
    betrag *= vz
    gegen = f.get("gegenkonto", "")
    gegen_id = int_oder_none(gegen)
    if gegen_id and gegen_id not in {r["id"] for r in _gegenkonten(kid)}:
        gegen_id = None
    partei = f.get("gegenpartei", "").strip() or name
    kat = int_oder_none(f.get("kategorie_id")) if art in ("gebuehr", "ertrag") else None
    bid = exe("""INSERT INTO buchung (konto_id, buchungsdatum, betrag_cent, gegenpartei, verwendungszweck, partner_key,
                 abrechnungsmonat, kategorie_id, notiz, dedup_hash, zuordnung_quelle, geprueft, manuell_erfasst)
                 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1)""",
              (kid, datum.isoformat(), betrag, partei, f"Depot: {name}", partner_key(partei), monat_von(datum), kat,
               f.get("notiz", "").strip() or None, "manuell:" + secrets.token_hex(8),
               "manuell" if kat else None, 1 if kat else 0))
    meldung = f"{name} über {euro(abs(betrag))} erfasst."
    if art in ("einzahlung", "auszahlung"):
        b = q1("SELECT * FROM buchung WHERE id = ?", (bid,))
        ergebnis = umbuchungen.markiere(b, gegen_id)
        if ergebnis == "verknuepft":
            meldung += " Mit der vorhandenen Buchung im Gegenkonto verknüpft."
        elif ergebnis == "angelegt":
            meldung += " Die Gegenbuchung wurde automatisch angelegt."
    elif not kat:
        zuordnung.ordne_zu([bid])
    log_aenderung(g.user["id"], "buchung", bid, "erfasst", dict(f))
    commit()
    melde(meldung)
    return redirect(url_for("depot.detail", kid=kid))
