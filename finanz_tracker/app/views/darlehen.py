"""Eigener Bereich für Immobilien-Darlehen – getrennt vom Haupt-Dashboard."""
from datetime import date

from flask import Blueprint, abort, g, redirect, render_template, request, url_for

from .. import auth
from ..db import q, q1, exe, commit, log_aenderung
from ..services import darlehen as dl, importer
from ..util import aktueller_monat, ist_monat, monat_plus, parse_euro_eingabe
from . import melde, int_oder_none

bp = Blueprint("darlehen", __name__, url_prefix="/darlehen")


def _konten():
    return [r["id"] for r in q(f"SELECT id FROM konto WHERE typ = 'darlehen' AND id IN "
                               f"({','.join('?' * len(s)) or 'NULL'})", s)] if (s := auth.sichtbare_konten()) else []


@bp.route("/")
@auth.login_required
def index():
    konten = _konten()
    darlehen = dl.alle(konten)
    karten = [dl.kennzahlen(d) for d in darlehen]
    ohne = q(f"""SELECT k.* FROM konto k WHERE k.typ = 'darlehen' AND k.id IN ({','.join('?' * len(konten)) or 'NULL'})
                 AND NOT EXISTS (SELECT 1 FROM darlehen d WHERE d.konto_id = k.id)""", konten)
    gesamt = {"rest": sum(k["restschuld"] for k in karten if k["d"]["aktiv"]),
              "ursprung": sum(k["d"]["ursprung_cent"] for k in karten if k["d"]["aktiv"]),
              "zins_jahr": sum(k["jahr"]["zins"] for k in karten), "tilgung_jahr": sum(k["jahr"]["tilgung"] + k["jahr"]["sonder"] for k in karten),
              "rate": sum(k["d"]["rate_cent"] for k in karten if k["restschuld"] > 0)}
    immobilien = q("SELECT * FROM immobilie ORDER BY name")
    for_imm = []
    for i in immobilien:
        rest = sum(k["restschuld"] for k in karten if k["d"]["immobilie_id"] == i["id"])
        wert = i["wert_cent"] or i["kaufpreis_cent"]
        for_imm.append({"i": i, "rest": rest, "wert": wert, "eigen": (wert - rest) if wert else None,
                        "beleihung": (rest / wert) if wert else None})
    # Restschuld-Verlauf aller Darlehen (jährlich, Planwerte)
    verlauf = []
    if karten:
        start = int(min(k["d"]["erste_rate"] for k in karten)[:4])
        ende = int(max((k["ende"] or k["d"]["erste_rate"]) for k in karten)[:4])
        for j in range(start, min(ende, start + 40) + 1):
            m = f"{j}-12"
            verlauf.append({"jahr": j, "rest": sum(dl.restschuld(k["plan"], m, k["d"]) for k in karten)})
    vergleich = None
    betrag = request.args.get("vergleich_betrag")
    if betrag and len(darlehen) > 1:
        try:
            cent = abs(parse_euro_eingabe(betrag))
            vergleich = dl.vergleich([d for d in darlehen if d["aktiv"]], cent, aktueller_monat()) if cent else None
        except ValueError:
            melde("Ungültiger Betrag.", "warn")
    return render_template("darlehen.html", karten=karten, ohne=ohne, gesamt=gesamt, immobilien=for_imm,
                           verlauf=verlauf, max_verlauf=max([v["rest"] for v in verlauf] + [1]), heute_jahr=date.today().year,
                           vergleich=vergleich, vergleich_betrag=betrag or "")


@bp.route("/<int:kid>")
@auth.login_required
def detail(kid):
    if kid not in _konten():
        abort(404)
    d = dl.lade(kid)
    if not d:
        return redirect(url_for("darlehen.konditionen", kid=kid))
    k = dl.kennzahlen(d)
    sim = None
    a = request.args
    if a.get("sim_betrag"):
        try:
            cent = abs(parse_euro_eingabe(a["sim_betrag"]))
            monat = a.get("sim_monat") if ist_monat(a.get("sim_monat", "")) else aktueller_monat()
            sim = dl.simuliere(d, cent, monat, jaehrlich=bool(a.get("sim_jaehrlich")))
        except ValueError:
            melde("Ungültiger Betrag.", "warn")
    konto_saldo = importer.kontostand(kid)
    hat_buchungen = q1("SELECT 1 FROM buchung WHERE konto_id = ? LIMIT 1", (kid,)) is not None
    jahre = {}
    for z in k["plan"]:
        j = jahre.setdefault(z["monat"][:4], {"zins": 0, "tilgung": 0, "sonder": 0, "rest": 0})
        j["zins"] += z["zins"]
        j["tilgung"] += z["tilgung"]
        j["sonder"] += z["sonder"]
        j["rest"] = z["rest"]
    return render_template("darlehen_detail.html", k=k, d=d, sim=sim, jahre=jahre, konto_saldo=konto_saldo,
                           hat_buchungen=hat_buchungen, monat=aktueller_monat(), a=a)


@bp.route("/<int:kid>/konditionen", methods=["GET", "POST"])
@auth.schreibrecht
def konditionen(kid):
    k = q1("SELECT * FROM konto WHERE id = ? AND typ = 'darlehen'", (kid,))
    if not k or kid not in _konten():
        abort(404)
    d = dl.lade(kid)
    if request.method == "POST":
        f = request.form
        try:
            ursprung = abs(parse_euro_eingabe(f.get("ursprung", "")))
            rate = abs(parse_euro_eingabe(f.get("rate", "")))
            zins = float((f.get("sollzins") or "").replace(",", "."))
            sonder = float((f.get("sondertilgung_prozent") or "0").replace(",", ".")) or None
        except ValueError:
            melde("Bitte Zahlen prüfen (Beträge wie 250.000,00; Zins wie 1,45).", "warn")
            return redirect(url_for("darlehen.konditionen", kid=kid))
        erste = f.get("erste_rate", "")
        if not (ursprung and rate and ist_monat(erste) and 0 <= zins < 20):
            melde("Darlehensbetrag, Rate, Sollzins und erste Rate sind Pflicht.", "warn")
            return redirect(url_for("darlehen.konditionen", kid=kid))
        zb = f.get("zinsbindung_bis") if ist_monat(f.get("zinsbindung_bis", "")) else None
        werte = (int_oder_none(f.get("immobilie_id")), ursprung, zins, rate, erste, zb, sonder,
                 int_oder_none(f.get("zahlkonto_id")), int_oder_none(f.get("erinnerung_monate")) or 24)
        if d:
            exe("UPDATE darlehen SET immobilie_id=?, ursprung_cent=?, sollzins=?, rate_cent=?, erste_rate=?, zinsbindung_bis=?, "
                "sondertilgung_prozent=?, zahlkonto_id=?, erinnerung_monate=? WHERE konto_id = ?", (*werte, kid))
        else:
            exe("INSERT INTO darlehen (immobilie_id, ursprung_cent, sollzins, rate_cent, erste_rate, zinsbindung_bis, "
                "sondertilgung_prozent, zahlkonto_id, erinnerung_monate, konto_id) VALUES (?,?,?,?,?,?,?,?,?,?)", (*werte, kid))
        log_aenderung(g.user["id"], "darlehen", kid, "konditionen", dict(f))
        commit()
        melde("Konditionen gespeichert.")
        return redirect(url_for("darlehen.detail", kid=kid))
    sichtbar = auth.sichtbare_konten()
    return render_template("darlehen_konditionen.html", k=k, d=d, immobilien=q("SELECT * FROM immobilie ORDER BY name"),
                           zahlkonten=q(f"SELECT * FROM konto WHERE typ != 'darlehen' AND id IN ({','.join('?' * len(sichtbar)) or 'NULL'}) "
                                        f"ORDER BY name", sichtbar))


@bp.route("/<int:kid>/ereignis", methods=["POST"])
@auth.schreibrecht
def ereignis(kid):
    if kid not in _konten() or not dl.lade(kid):
        abort(404)
    f = request.form
    if f.get("aktion") == "loeschen":
        exe("DELETE FROM darlehen_ereignis WHERE id = ? AND konto_id = ?", (int_oder_none(f.get("eid")), kid))
        melde("Eintrag entfernt.")
    else:
        try:
            betrag = abs(parse_euro_eingabe(f.get("betrag", "")))
            datum = date.fromisoformat(f.get("datum", "")).isoformat()
        except ValueError:
            melde("Datum und Betrag prüfen.", "warn")
            return redirect(url_for("darlehen.detail", kid=kid))
        art = "abgleich" if f.get("art") == "abgleich" else "sondertilgung"
        if betrag or art == "abgleich":
            exe("INSERT INTO darlehen_ereignis (konto_id, datum, art, betrag_cent, notiz) VALUES (?,?,?,?,?)",
                (kid, datum, art, betrag, f.get("notiz", "").strip() or None))
            melde("Sondertilgung eingetragen." if art == "sondertilgung" else "Restschuld laut Bank eingetragen – der Plan rechnet ab diesem Monat damit weiter.")
    log_aenderung(g.user["id"], "darlehen", kid, "ereignis", dict(f))
    commit()
    return redirect(url_for("darlehen.detail", kid=kid))


@bp.route("/immobilie", methods=["POST"])
@auth.schreibrecht
def immobilie():
    f = request.form
    iid = int_oder_none(f.get("id"))
    if f.get("aktion") == "loeschen" and iid:
        exe("DELETE FROM immobilie WHERE id = ?", (iid,))
        commit()
        melde("Immobilie entfernt.")
        return redirect(url_for("darlehen.index"))
    name = f.get("name", "").strip()
    if not name:
        melde("Name fehlt.", "warn")
        return redirect(url_for("darlehen.index"))
    try:
        werte = (name, abs(parse_euro_eingabe(f.get("kaufpreis", ""))) or None, f.get("kaufdatum") or None,
                 abs(parse_euro_eingabe(f.get("wert", ""))) or None, f.get("wert_datum") or None)
    except ValueError as exc:
        melde(str(exc), "warn")
        return redirect(url_for("darlehen.index"))
    if iid:
        exe("UPDATE immobilie SET name=?, kaufpreis_cent=?, kaufdatum=?, wert_cent=?, wert_datum=? WHERE id = ?", (*werte, iid))
    else:
        exe("INSERT INTO immobilie (name, kaufpreis_cent, kaufdatum, wert_cent, wert_datum) VALUES (?,?,?,?,?)", werte)
    commit()
    melde("Immobilie gespeichert.")
    return redirect(url_for("darlehen.index"))


def hinweise(sichtbar) -> list[dict]:
    """Für das Haupt-Dashboard: nur Hinweise (Zinsbindung läuft aus), keine Beträge in den Summen."""
    konten = [r["id"] for r in q(f"SELECT id FROM konto WHERE typ = 'darlehen' AND aktiv = 1 AND id IN "
                                 f"({','.join('?' * len(sichtbar)) or 'NULL'})", sichtbar)] if sichtbar else []
    erg = []
    for d in dl.alle(konten):
        k = dl.kennzahlen(d)
        if k["zinsbindung_warnung"]:
            erg.append({"kid": d["konto_id"], "text": f"Zinsbindung {d['name']} endet {d['zinsbindung_bis']}"
                        f" – Anschlussfinanzierung planen"})
    return erg
