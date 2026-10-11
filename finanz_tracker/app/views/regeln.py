from flask import Blueprint, abort, g, redirect, render_template, request, url_for

from .. import auth
from ..db import q, q1, exe, commit, jload, jdump, log_aenderung
from ..services import kategorien, zuordnung
from . import melde, int_oder_none

bp = Blueprint("regeln", __name__, url_prefix="/regeln")


def _beschreibe(regel, kat_pfade, personen, konten):
    bed = []
    for c in jload(regel["bedingungen"], []):
        feld = zuordnung.BEDINGUNGS_FELDER.get(c.get("feld"), c.get("feld"))
        op = zuordnung.OPERATOREN.get(c.get("op"), c.get("op"))
        wert = c.get("wert")
        if c.get("feld") == "konto":
            wert = konten.get(int_oder_none(wert), wert)
        if c.get("feld") == "richtung":
            op, wert = "ist", "Eingang" if wert == "eingang" else "Ausgang"
        bed.append(f"{feld} {op} „{wert}“")
    a = jload(regel["aktionen"], {})
    akt = []
    if a.get("als_umbuchung"):
        akt.append("als Umbuchung")
    elif a.get("kategorie_id"):
        akt.append(kat_pfade.get(int(a["kategorie_id"]), "?"))
    if a.get("person_id"):
        akt.append(personen.get(int(a["person_id"]), "?"))
    if a.get("monat_versatz"):
        akt.append(f"Monat {int(a['monat_versatz']):+d}")
    if a.get("verteilung_monate") and int(a["verteilung_monate"]) > 1:
        akt.append(f"auf {int(a['verteilung_monate'])} Monate verteilt")
    if a.get("tag_id"):
        t = q1("SELECT name FROM tag WHERE id = ?", (int(a["tag_id"]),))
        akt.append(f"Tag „{t['name'] if t else '?'}“")
    return " und ".join(bed), " · ".join(akt)


@bp.route("/")
@auth.login_required
def liste():
    kat_pfade = {k["id"]: k["pfad"] for k in kategorien.alle()}
    personen = {p["id"]: p["name"] for p in q("SELECT id, name FROM person")}
    konten = {k["id"]: k["name"] for k in q("SELECT id, name FROM konto")}
    stat = zuordnung.regel_statistik()
    rows = []
    for r in q("SELECT * FROM regel ORDER BY prioritaet, id"):
        wenn, dann = _beschreibe(r, kat_pfade, personen, konten)
        rows.append({"r": r, "wenn": wenn, "dann": dann, "stat": stat.get(r["id"], {"n": 0, "zuletzt": None})})
    from ..services import modell
    return render_template("regeln.html", rows=rows, quoten=modell.trefferquoten())


def _aus_formular():
    bed = []
    for i in range(4):
        feld = request.form.get(f"feld{i}")
        wert = request.form.get(f"wert{i}", "").strip()
        op = request.form.get(f"op{i}")
        if feld == "richtung":
            wert = request.form.get(f"richtung{i}", "ausgang")
            op = "gleich"
        if feld == "konto":
            wert = request.form.get(f"konto{i}", "")
            op = "gleich"
        if feld and wert:
            bed.append({"feld": feld, "op": op or "enthaelt", "wert": wert})
    akt = {}
    if request.form.get("als_umbuchung"):
        akt["als_umbuchung"] = True
    elif int_oder_none(request.form.get("kategorie_id")):
        akt["kategorie_id"] = int(request.form["kategorie_id"])
    if int_oder_none(request.form.get("person_id")):
        akt["person_id"] = int(request.form["person_id"])
    versatz = int_oder_none(request.form.get("monat_versatz")) or 0
    if versatz:
        akt["monat_versatz"] = versatz
    verteilung = int_oder_none(request.form.get("verteilung_monate")) or 1
    if verteilung > 1:
        akt["verteilung_monate"] = min(60, verteilung)
    tag_name = request.form.get("tag_name", "").strip()
    if tag_name:
        from ..services import tags
        akt["tag_id"] = tags.finde_oder_lege_an(tag_name)
    return bed, akt


def _form(regel=None, bed=None, akt=None, test=None, name=""):
    bed = bed if bed is not None else (jload(regel["bedingungen"], []) if regel else [])
    akt = akt if akt is not None else (jload(regel["aktionen"], {}) if regel else {})
    while len(bed) < 4:
        bed.append({"feld": "", "op": "enthaelt", "wert": ""})
    tag = q1("SELECT name FROM tag WHERE id = ?", (int(akt["tag_id"]),)) if akt.get("tag_id") else None
    return render_template("regel.html", regel=regel, bed=bed, akt=akt, test=test, tag_name=tag["name"] if tag else "",
                           alle_tags=q("SELECT name FROM tag ORDER BY name"),
                           name=name or (regel["name"] if regel else ""), kategorien=kategorien.alle(),
                           personen=q("SELECT * FROM person WHERE aktiv = 1 ORDER BY name"),
                           konten=q("SELECT * FROM konto ORDER BY sortierung, name"),
                           felder=zuordnung.BEDINGUNGS_FELDER, operatoren=zuordnung.OPERATOREN)


@bp.route("/neu", methods=["GET", "POST"])
@auth.schreibrecht
def neu():
    if request.method == "POST":
        return _speichern(None)
    bed, akt, name = [], {}, ""
    bid = int_oder_none(request.args.get("von_buchung"))
    if bid:
        b = q1("SELECT * FROM buchung WHERE id = ?", (bid,))
        if b and auth.konto_sichtbar(b["konto_id"]):
            if b["gegenpartei"]:
                bed.append({"feld": "gegenpartei", "op": "enthaelt", "wert": b["gegenpartei"][:60]})
            elif b["verwendungszweck"]:
                bed.append({"feld": "verwendungszweck", "op": "enthaelt", "wert": b["verwendungszweck"][:60]})
            if b["kategorie_id"]:
                akt["kategorie_id"] = b["kategorie_id"]
            if b["person_id"]:
                akt["person_id"] = b["person_id"]
            name = (b["gegenpartei"] or b["verwendungszweck"])[:40]
    return _form(bed=bed, akt=akt, name=name)


@bp.route("/<int:rid>", methods=["GET", "POST"])
@auth.schreibrecht
def bearbeiten(rid):
    r = q1("SELECT * FROM regel WHERE id = ?", (rid,))
    if not r:
        abort(404)
    if request.method == "POST":
        if request.form.get("aktion") == "loeschen":
            exe("UPDATE buchung SET regel_id = NULL WHERE regel_id = ?", (rid,))
            exe("DELETE FROM regel WHERE id = ?", (rid,))
            log_aenderung(g.user["id"], "regel", rid, "geloescht")
            commit()
            melde("Regel gelöscht.")
            return redirect(url_for("regeln.liste"))
        return _speichern(r)
    return _form(regel=r)


def _speichern(regel):
    bed, akt = _aus_formular()
    name = request.form.get("name", "").strip() or "Regel"
    if request.form.get("aktion") == "testen":
        test = zuordnung.teste_regel(bed, akt, auth.sichtbare_konten())
        return _form(regel=regel, bed=bed, akt=akt, test=test, name=name)
    if not bed:
        melde("Mindestens eine Bedingung angeben.", "warn")
        return _form(regel=regel, bed=bed, akt=akt, name=name)
    if not akt:
        melde("Mindestens eine Aktion angeben (Kategorie, Person, Monat oder Umbuchung).", "warn")
        return _form(regel=regel, bed=bed, akt=akt, name=name)
    if regel:
        exe("UPDATE regel SET name = ?, bedingungen = ?, aktionen = ?, aktiv = ? WHERE id = ?",
            (name, jdump(bed), jdump(akt), 1 if request.form.get("aktiv") else 0, regel["id"]))
        rid = regel["id"]
    else:
        rid = exe("INSERT INTO regel (name, prioritaet, bedingungen, aktionen) VALUES (?,?,?,?)",
                  (name, zuordnung.naechste_prioritaet(), jdump(bed), jdump(akt)))
    log_aenderung(g.user["id"], "regel", rid, "gespeichert", {"bedingungen": bed, "aktionen": akt})
    if request.form.get("anwenden"):
        stat = zuordnung.ordne_zu(None, ueberschreiben=True)
        melde(f"Regel gespeichert und angewendet: {stat['regel']} Buchungen per Regel zugeordnet.")
    else:
        melde("Regel gespeichert. Sie gilt für alle neuen Importe.")
    commit()
    return redirect(url_for("regeln.liste"))


@bp.route("/<int:rid>/verschieben", methods=["POST"])
@auth.schreibrecht
def verschieben(rid):
    regeln = list(q("SELECT id FROM regel ORDER BY prioritaet, id"))
    ids = [r["id"] for r in regeln]
    if rid not in ids:
        abort(404)
    i = ids.index(rid)
    j = i - 1 if request.form.get("richtung") == "hoch" else i + 1
    if 0 <= j < len(ids):
        ids[i], ids[j] = ids[j], ids[i]
    for pos, x in enumerate(ids):
        exe("UPDATE regel SET prioritaet = ? WHERE id = ?", ((pos + 1) * 10, x))
    commit()
    return redirect(url_for("regeln.liste"))


@bp.route("/anwenden", methods=["POST"])
@auth.schreibrecht
def anwenden():
    stat = zuordnung.ordne_zu(None, ueberschreiben=True)
    commit()
    melde(f"Regeln angewendet: {stat['regel']} per Regel, {stat['gedaechtnis']} aus früheren Buchungen, "
          f"{stat['offen']} bleiben offen. Manuell zugeordnete Buchungen wurden nicht verändert.")
    return redirect(url_for("regeln.liste"))
