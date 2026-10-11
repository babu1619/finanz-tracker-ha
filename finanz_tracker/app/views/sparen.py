"""Sparen: Sparquote, Rücklagen-Töpfe und Sparziele."""
from flask import Blueprint, abort, g, redirect, render_template, request, url_for

from .. import auth
from ..db import q, q1, exe, commit, einstellung, log_aenderung
from ..services import darlehen, kategorien, ruecklagen, statistik
from ..util import aktueller_monat, ist_monat, parse_euro_eingabe
from . import melde, int_oder_none

bp = Blueprint("sparen", __name__, url_prefix="/sparen")


def sparkennzahlen(konten_basis, konten_alle, monat):
    """Sparquote im Monat, gespart seit Jahresbeginn, Vermögensaufbau inkl. Tilgung."""
    jahr_start = monat[:4] + "-01"
    verlauf = statistik.verlauf(konten_basis, monat, int(monat[5:]))
    ein = sum(v["einnahmen"] for v in verlauf)
    gespart = sum(v["saldo"] for v in verlauf)
    tilgung = darlehen.tilgung_im_zeitraum(konten_alle, jahr_start, monat)
    ziel = int(einstellung("sparquote_ziel", "25") or 25)
    return {"gespart_jahr": gespart, "quote_jahr": gespart / ein if ein > 0 else None, "tilgung_jahr": tilgung,
            "aufbau_jahr": gespart + tilgung, "ziel_quote": ziel / 100, "monate": verlauf}


@bp.route("/")
@auth.login_required
def index():
    monat = aktueller_monat()
    sichtbar = auth.sichtbare_konten()
    basis = statistik.basis_konten(sichtbar)
    ue = ruecklagen.uebersicht(basis)
    commit()  # automatische Zuführungen speichern
    return render_template("sparen.html", ue=ue, k=sparkennzahlen(basis, sichtbar, monat), monat=monat,
                           konten=q(f"SELECT * FROM konto WHERE id IN ({','.join('?' * len(basis)) or 'NULL'}) AND aktiv = 1 "
                                    f"ORDER BY typ != 'tagesgeld', sortierung, name", basis),
                           kategorien=kategorien.alle(), personen=q("SELECT * FROM person WHERE aktiv = 1 ORDER BY name"))


def _werte():
    f = request.form
    name = f.get("name", "").strip()
    if not name:
        raise ValueError("Name fehlt.")
    konto = int_oder_none(f.get("traeger_konto_id"))
    if not konto or not auth.konto_sichtbar(konto):
        raise ValueError("Bitte ein Trägerkonto wählen.")
    ziel = abs(parse_euro_eingabe(f.get("ziel", ""))) or None
    zufuehrung = abs(parse_euro_eingabe(f.get("zufuehrung", "")))
    zieldatum = f.get("zieldatum", "") if ist_monat(f.get("zieldatum", "")) else None
    start = f.get("start_monat", "") if ist_monat(f.get("start_monat", "")) else aktueller_monat()
    return (name, konto, "konto" if f.get("bezug") == "konto" else "topf", ziel, zufuehrung, zieldatum,
            int_oder_none(f.get("kategorie_id")), int_oder_none(f.get("person_id")), start)


@bp.route("/neu", methods=["POST"])
@auth.schreibrecht
def neu():
    try:
        w = _werte()
    except ValueError as exc:
        melde(str(exc), "warn")
        return redirect(url_for("sparen.index"))
    rid = exe("INSERT INTO ruecklage (name, traeger_konto_id, bezug, ziel_cent, zufuehrung_cent, zieldatum, kategorie_id, "
              "person_id, start_monat) VALUES (?,?,?,?,?,?,?,?,?)", w)
    start = abs(parse_euro_eingabe(request.form.get("startbetrag", "")))
    if start and w[2] == "topf":
        ruecklagen.korrektur(rid, start, "Startbetrag", "zufuehrung")
    log_aenderung(g.user["id"], "ruecklage", rid, "angelegt", dict(request.form))
    commit()
    melde(f"„{w[0]}“ angelegt.")
    return redirect(url_for("sparen.index"))


@bp.route("/<int:rid>", methods=["GET", "POST"])
@auth.login_required
def detail(rid):
    r = q1("SELECT r.*, k.name AS konto_name FROM ruecklage r JOIN konto k ON k.id = r.traeger_konto_id WHERE r.id = ?", (rid,))
    if not r or not auth.konto_sichtbar(r["traeger_konto_id"]):
        abort(404)
    if request.method == "POST":
        if not auth.darf_schreiben():
            abort(403)
        aktion = request.form.get("aktion")
        if aktion == "bewegung":
            try:
                betrag = parse_euro_eingabe(request.form.get("betrag", ""))
            except ValueError as exc:
                melde(str(exc), "warn")
                return redirect(url_for("sparen.detail", rid=rid))
            art = request.form.get("art", "zufuehrung")
            if art == "entnahme":
                betrag = -abs(betrag)
            elif art == "zufuehrung":
                betrag = abs(betrag)
            else:
                art = "korrektur"
            if betrag:
                ruecklagen.korrektur(rid, betrag, request.form.get("notiz", "").strip(), art)
                melde("Bewegung gebucht.")
        elif aktion == "loeschen":
            exe("UPDATE buchung SET ruecklage_id = NULL WHERE ruecklage_id = ?", (rid,))
            exe("DELETE FROM ruecklage WHERE id = ?", (rid,))
            log_aenderung(g.user["id"], "ruecklage", rid, "geloescht")
            commit()
            melde("Gelöscht.")
            return redirect(url_for("sparen.index"))
        elif aktion == "bewegung_loeschen":
            exe("DELETE FROM ruecklage_bewegung WHERE id = ? AND ruecklage_id = ? AND buchung_id IS NULL",
                (int_oder_none(request.form.get("bid")), rid))
            melde("Bewegung entfernt.")
        else:
            try:
                w = _werte()
            except ValueError as exc:
                melde(str(exc), "warn")
                return redirect(url_for("sparen.detail", rid=rid))
            exe("UPDATE ruecklage SET name=?, traeger_konto_id=?, bezug=?, ziel_cent=?, zufuehrung_cent=?, zieldatum=?, "
                "kategorie_id=?, person_id=?, start_monat=?, aktiv=? WHERE id = ?",
                (*w, 0 if request.form.get("aktiv") == "0" else 1, rid))
            melde("Gespeichert.")
        log_aenderung(g.user["id"], "ruecklage", rid, aktion or "gespeichert", dict(request.form))
        commit()
        return redirect(url_for("sparen.detail", rid=rid))
    basis = statistik.basis_konten(auth.sichtbare_konten())
    entnahmen = q("""SELECT b.*, k.name AS konto_name FROM buchung b JOIN konto k ON k.id = b.konto_id
                     WHERE b.ruecklage_id = ? ORDER BY b.buchungsdatum DESC LIMIT 50""", (rid,))
    return render_template("ruecklage.html", e=ruecklagen.auswertung(r), r=r, bewegungen=ruecklagen.bewegungen(rid),
                           entnahmen=entnahmen,
                           konten=q(f"SELECT * FROM konto WHERE id IN ({','.join('?' * len(basis)) or 'NULL'}) ORDER BY name", basis),
                           kategorien=kategorien.alle(), personen=q("SELECT * FROM person WHERE aktiv = 1 ORDER BY name"))


@bp.route("/sparquote", methods=["POST"])
@auth.admin_required
def sparquote():
    from ..db import setze_einstellung
    wert = int_oder_none(request.form.get("ziel"))
    if wert is not None and 0 <= wert <= 90:
        setze_einstellung("sparquote_ziel", str(wert))
        commit()
        melde(f"Sparquoten-Ziel auf {wert} % gesetzt.")
    return redirect(url_for("sparen.index"))
