"""Schnellerfassung für Bargeld (und andere Konten ohne Import), optimiert fürs Handy."""
import secrets
from datetime import date

from flask import Blueprint, g, redirect, render_template, request, url_for

from .. import auth
from ..db import q, exe, commit, log_aenderung
from ..services import kategorien, tags, umbuchungen, zuordnung
from ..util import monat_von, partner_key, parse_euro_eingabe
from . import melde, int_oder_none

bp = Blueprint("erfassen", __name__, url_prefix="/erfassen")


def _konten():
    sichtbar = auth.sichtbare_konten(nur_aktive=True, mit_darlehen=False)
    return q(f"SELECT * FROM konto WHERE id IN ({','.join('?' * len(sichtbar)) or 'NULL'}) "
             f"ORDER BY typ != 'bargeld', sortierung, name", sichtbar)


@bp.route("/", methods=["GET", "POST"])
@auth.schreibrecht
def index():
    konten = _konten()
    if request.method == "POST":
        f = request.form
        kid = int_oder_none(f.get("konto_id"))
        if kid not in {k["id"] for k in konten}:
            melde("Bitte ein Konto wählen.", "warn")
            return redirect(url_for("erfassen.index"))
        try:
            betrag = abs(parse_euro_eingabe(f.get("betrag", "")))
            datum = date.fromisoformat(f.get("datum") or date.today().isoformat())
        except ValueError:
            melde("Betrag oder Datum ungültig.", "warn")
            return redirect(url_for("erfassen.index"))
        if not betrag:
            melde("Bitte einen Betrag eingeben.", "warn")
            return redirect(url_for("erfassen.index"))
        if f.get("richtung") != "ein":
            betrag = -betrag
        partei = f.get("gegenpartei", "").strip()
        kat = int_oder_none(f.get("kategorie_id"))
        bid = exe("""INSERT INTO buchung (konto_id, buchungsdatum, betrag_cent, gegenpartei, verwendungszweck, partner_key,
                     abrechnungsmonat, kategorie_id, person_id, notiz, dedup_hash, zuordnung_quelle, geprueft, manuell_erfasst)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
                  (kid, datum.isoformat(), betrag, partei, "Bar erfasst", partner_key(partei),
                   monat_von(datum), kat, int_oder_none(f.get("person_id")), f.get("notiz", "").strip() or None, "manuell:" + secrets.token_hex(8),
                   "manuell" if kat else None, 1 if kat else 0))
        if f.get("tag"):
            tags.setze(bid, [f["tag"]])
        if not kat:
            zuordnung.ordne_zu([bid])
        umbuchungen.erkenne([bid])  # z. B. Abhebung am Automaten ↔ Bargeld-Einnahme
        log_aenderung(g.user["id"], "buchung", bid, "erfasst", dict(f))
        commit()
        melde(f"Erfasst: {partei or 'Buchung'} {abs(betrag) / 100:.2f} €".replace(".", ","))
        return redirect(url_for("erfassen.index", konto=kid))
    letzte = q(f"""SELECT b.*, k.name AS konto_name, kat.pfad AS kat_pfad FROM buchung b JOIN konto k ON k.id = b.konto_id
                   LEFT JOIN kategorie kat ON kat.id = b.kategorie_id
                   WHERE b.manuell_erfasst = 1 AND b.konto_id IN ({','.join('?' * len(konten)) or 'NULL'})
                   ORDER BY b.id DESC LIMIT 8""", [k["id"] for k in konten])
    haeufig = q("""SELECT b.gegenpartei, b.kategorie_id, COUNT(*) AS n FROM buchung b
                   WHERE b.manuell_erfasst = 1 AND b.gegenpartei != '' GROUP BY b.gegenpartei, b.kategorie_id
                   ORDER BY n DESC LIMIT 12""")
    return render_template("erfassen.html", konten=konten, kategorien=kategorien.alle(),
                           personen=q("SELECT * FROM person WHERE aktiv = 1 ORDER BY name"), letzte=letzte, haeufig=haeufig,
                           konto_id=int_oder_none(request.args.get("konto")), heute=date.today().isoformat(),
                           person_id=g.user["person_id"])
