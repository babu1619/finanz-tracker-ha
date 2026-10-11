from datetime import date

from flask import Blueprint, abort, g, redirect, render_template, request, url_for

from .. import auth
from ..db import q, q1, exe, commit, log_aenderung
from ..services import tags as tags_mod
from ..util import parse_euro_eingabe
from . import melde, int_oder_none

bp = Blueprint("tags", __name__, url_prefix="/tags")


def _datum(text):
    try:
        return date.fromisoformat(text).isoformat() if text else None
    except ValueError:
        return None


@bp.route("/")
@auth.login_required
def index():
    return render_template("tags.html", tags=tags_mod.alle(auth.sichtbare_konten()))


@bp.route("/neu", methods=["POST"])
@auth.schreibrecht
def neu():
    name = request.form.get("name", "").strip()
    if not name:
        melde("Name fehlt.", "warn")
        return redirect(url_for("tags.index"))
    if q1("SELECT 1 FROM tag WHERE name = ? COLLATE NOCASE", (name,)):
        melde("Diesen Tag gibt es schon.", "warn")
        return redirect(url_for("tags.index"))
    try:
        budget = abs(parse_euro_eingabe(request.form.get("budget", ""))) or None
    except ValueError:
        budget = None
    tid = exe("INSERT INTO tag (name, start, ende, budget_cent, notiz) VALUES (?,?,?,?,?)",
              (name[:60], _datum(request.form.get("start")), _datum(request.form.get("ende")), budget,
               request.form.get("notiz", "").strip() or None))
    commit()
    melde(f"Tag „{name}“ angelegt.")
    return redirect(url_for("tags.detail", tid=tid))


@bp.route("/<int:tid>", methods=["GET", "POST"])
@auth.login_required
def detail(tid):
    t = q1("SELECT * FROM tag WHERE id = ?", (tid,))
    if not t:
        abort(404)
    if request.method == "POST":
        if not auth.darf_schreiben():
            abort(403)
        aktion = request.form.get("aktion")
        if aktion == "markieren":
            ids = [int(i) for i in request.form.getlist("ids") if i.isdigit()]
            sichtbar = set(auth.sichtbare_konten())
            ids = [i for i in ids if (r := q1("SELECT konto_id FROM buchung WHERE id = ?", (i,))) and r["konto_id"] in sichtbar]
            n = tags_mod.hinzufuegen(ids, tid)
            melde(f"{n} Buchungen markiert.")
        elif aktion == "loeschen":
            exe("DELETE FROM tag WHERE id = ?", (tid,))
            log_aenderung(g.user["id"], "tag", tid, "geloescht", {"name": t["name"]})
            commit()
            melde(f"Tag „{t['name']}“ gelöscht (die Buchungen bleiben).")
            return redirect(url_for("tags.index"))
        else:
            name = request.form.get("name", "").strip() or t["name"]
            try:
                budget = abs(parse_euro_eingabe(request.form.get("budget", ""))) or None
            except ValueError:
                budget = t["budget_cent"]
            exe("UPDATE tag SET name = ?, start = ?, ende = ?, budget_cent = ?, notiz = ? WHERE id = ?",
                (name[:60], _datum(request.form.get("start")), _datum(request.form.get("ende")), budget,
                 request.form.get("notiz", "").strip() or None, tid))
            melde("Tag gespeichert.")
        commit()
        return redirect(url_for("tags.detail", tid=tid))
    sichtbar = auth.sichtbare_konten()
    marks = ",".join("?" * len(sichtbar)) or "NULL"
    summen = q1(f"""SELECT COUNT(*) AS n, COALESCE(-SUM(CASE WHEN b.betrag_cent < 0 THEN b.betrag_cent END), 0) AS aus,
                       COALESCE(SUM(CASE WHEN b.betrag_cent > 0 THEN b.betrag_cent END), 0) AS ein
                    FROM buchung b JOIN buchung_tag bt ON bt.buchung_id = b.id
                    WHERE bt.tag_id = ? AND b.ist_umbuchung = 0 AND b.konto_id IN ({marks})""", [tid] + sichtbar)
    nach_kat = q(f"""SELECT COALESCE(k.pfad, 'Ohne Kategorie') AS pfad, -SUM(p.betrag_cent) AS summe
                     FROM posten p JOIN buchung_tag bt ON bt.buchung_id = p.buchung_id
                     LEFT JOIN kategorie k ON k.id = p.kategorie_id
                     WHERE bt.tag_id = ? AND p.ist_umbuchung = 0 AND p.konto_id IN ({marks}) AND p.betrag_cent < 0
                     GROUP BY p.kategorie_id ORDER BY summe DESC""", [tid] + sichtbar)
    return render_template("tag.html", t=t, summen=summen, nach_kat=nach_kat,
                           kandidaten=tags_mod.kandidaten(t, sichtbar) if auth.darf_schreiben() else [])
