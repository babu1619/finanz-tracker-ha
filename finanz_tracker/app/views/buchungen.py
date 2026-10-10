import csv
import io

from flask import Blueprint, Response, abort, g, redirect, render_template, request, url_for

from .. import auth
from ..db import q, q1, exe, commit, log_aenderung
from ..services import kategorien, umbuchungen
from ..util import ist_monat, monat_plus, aktueller_monat
from . import melde, int_oder_none

bp = Blueprint("buchungen", __name__, url_prefix="/buchungen")


def _filter():
    a = request.args
    f = {
        "monat": a.get("monat", ""),
        "konto": int_oder_none(a.get("konto")),
        "kategorie": a.get("kategorie", ""),
        "person": int_oder_none(a.get("person")),
        "suche": a.get("suche", "").strip(),
        "status": a.get("status", ""),
    }
    if f["monat"] and f["monat"] != "alle" and not ist_monat(f["monat"]):
        f["monat"] = ""
    return f


def _abfrage(f, limit=500):
    sichtbar = auth.sichtbare_konten()
    if not sichtbar:
        return [], 0, 0
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
        where.append(f"b.kategorie_id IN ({','.join('?' * len(ids)) or 'NULL'})")
        params.extend(ids)
    if f["person"]:
        where.append("b.person_id = ?")
        params.append(f["person"])
    if f["suche"]:
        where.append("(b.gegenpartei LIKE ? OR b.verwendungszweck LIKE ? OR b.notiz LIKE ? OR "
                     "printf('%.2f', abs(b.betrag_cent)/100.0) LIKE ?)")
        s = f"%{f['suche']}%"
        params.extend([s, s, s, f"%{f['suche'].replace(',', '.')}%"])
    if f["status"] == "ungeprueft":
        where.append("b.geprueft = 0 AND b.kategorie_id IS NOT NULL AND b.ist_umbuchung = 0")
    elif f["status"] == "umbuchung":
        where.append("b.ist_umbuchung = 1")
    elif f["status"] == "manuell":
        where.append("b.zuordnung_quelle = 'manuell'")
    sql_where = " AND ".join(where)
    rows = q(f"""SELECT b.*, k.name AS konto_name, k.typ AS konto_typ, kat.pfad AS kat_pfad,
                        p.name AS person_name, r.name AS regel_name
                 FROM buchung b JOIN konto k ON k.id = b.konto_id
                 LEFT JOIN kategorie kat ON kat.id = b.kategorie_id
                 LEFT JOIN person p ON p.id = b.person_id
                 LEFT JOIN regel r ON r.id = b.regel_id
                 WHERE {sql_where} ORDER BY b.buchungsdatum DESC, b.id DESC LIMIT {int(limit)}""", params)
    summe = q1(f"""SELECT COUNT(*) AS n,
                     COALESCE(SUM(CASE WHEN b.betrag_cent < 0 AND b.ist_umbuchung = 0 THEN b.betrag_cent END),0) AS aus,
                     COALESCE(SUM(CASE WHEN b.betrag_cent > 0 AND b.ist_umbuchung = 0 THEN b.betrag_cent END),0) AS ein
                   FROM buchung b WHERE {sql_where}""", params)
    return rows, summe, sichtbar


@bp.route("/")
@auth.login_required
def liste():
    f = _filter()
    if not request.args:
        f["monat"] = aktueller_monat()
    rows, summe, sichtbar = _abfrage(f)
    konten = q(f"SELECT * FROM konto WHERE id IN ({','.join('?' * len(sichtbar)) or 'NULL'}) ORDER BY sortierung, name",
               sichtbar)
    monate = [r["abrechnungsmonat"] for r in q("SELECT DISTINCT abrechnungsmonat FROM buchung ORDER BY 1 DESC LIMIT 36")]
    return render_template("buchungen.html", rows=rows, summe=summe, f=f, konten=konten,
                           kategorien=kategorien.alle(), personen=q("SELECT * FROM person WHERE aktiv = 1 ORDER BY name"),
                           monate=monate)


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
        for i in ids:
            exe("UPDATE buchung SET kategorie_id = ?, zuordnung_quelle = 'manuell', geprueft = 1, regel_id = NULL "
                "WHERE id = ? AND ist_umbuchung = 0", (kat, i))
        melde(f"Kategorie für {len(ids)} Buchungen gesetzt.")
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
    elif aktion == "bestaetigen":
        for i in ids:
            exe("UPDATE buchung SET geprueft = 1 WHERE id = ? AND kategorie_id IS NOT NULL", (i,))
        melde(f"{len(ids)} Buchungen als geprüft bestätigt.")
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


@bp.route("/<int:bid>", methods=["GET", "POST"])
@auth.login_required
def bearbeiten(bid):
    b = q1("""SELECT b.*, k.name AS konto_name, r.name AS regel_name, kat.pfad AS kat_pfad
              FROM buchung b JOIN konto k ON k.id = b.konto_id
              LEFT JOIN regel r ON r.id = b.regel_id LEFT JOIN kategorie kat ON kat.id = b.kategorie_id
              WHERE b.id = ?""", (bid,))
    if not b or not auth.konto_sichtbar(b["konto_id"]):
        abort(404)
    if request.method == "POST":
        if not auth.darf_schreiben():
            abort(403)
        if request.form.get("aktion") == "umbuchung_loesen":
            umbuchungen.loese(bid)
            melde("Umbuchung gelöst.")
        else:
            kat = int_oder_none(request.form.get("kategorie_id"))
            m = request.form.get("abrechnungsmonat")
            exe("UPDATE buchung SET kategorie_id = ?, person_id = ?, abrechnungsmonat = ?, notiz = ?, "
                "zuordnung_quelle = 'manuell', geprueft = 1, regel_id = NULL WHERE id = ?",
                (kat, int_oder_none(request.form.get("person_id")), m if ist_monat(m) else b["abrechnungsmonat"],
                 request.form.get("notiz", "").strip() or None, bid))
            melde("Buchung gespeichert.")
        log_aenderung(g.user["id"], "buchung", bid, "bearbeitet", dict(request.form))
        commit()
        if request.form.get("regel"):
            return redirect(url_for("regeln.neu", von_buchung=bid))
        return redirect(request.form.get("zurueck") or url_for("buchungen.liste"))
    partner = q1("SELECT b.*, k.name AS konto_name FROM buchung b JOIN konto k ON k.id = b.konto_id WHERE b.id = ?",
                 (b["umbuchung_partner_id"],)) if b["umbuchung_partner_id"] else None
    monate = [monat_plus(b["abrechnungsmonat"], i) for i in (-2, -1, 0, 1, 2)]
    return render_template("buchung.html", b=b, partner=partner, kategorien=kategorien.alle(),
                           personen=q("SELECT * FROM person WHERE aktiv = 1 ORDER BY name"), monate=monate,
                           zurueck=request.args.get("zurueck", ""))


@bp.route("/export.csv")
@auth.login_required
def export():
    f = _filter()
    rows, _, _ = _abfrage(f, limit=1_000_000)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Buchungsdatum", "Abrechnungsmonat", "Konto", "Gegenpartei", "Gegen-IBAN", "Verwendungszweck",
                "Betrag", "Kategorie", "Person", "Umbuchung", "Notiz", "Zuordnung"])
    for r in rows:
        w.writerow([r["buchungsdatum"], r["abrechnungsmonat"], r["konto_name"], r["gegenpartei"], r["gegen_iban"] or "",
                    r["verwendungszweck"], f"{r['betrag_cent'] / 100:.2f}".replace(".", ","), r["kat_pfad"] or "",
                    r["person_name"] or "", "ja" if r["ist_umbuchung"] else "", r["notiz"] or "",
                    r["zuordnung_quelle"] or ""])
    return Response("﻿" + buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=buchungen.csv"})
