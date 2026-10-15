"""Abos, Fixkosten und Verträge: eigene Datensätze mit Laufzeit und Kündigungsfrist, dazu erkannte Vorschläge."""
from datetime import date

from flask import Blueprint, abort, g, redirect, render_template, request, url_for

from .. import auth
from ..db import q, q1, exe, commit, log_aenderung
from ..services import kategorien, statistik, vertraege as vt
from ..util import parse_euro_eingabe
from . import melde, int_oder_none

bp = Blueprint("vertraege", __name__, url_prefix="/vertraege")


def _konten():
    return statistik.basis_konten(auth.sichtbare_konten())


@bp.route("/")
@auth.login_required
def index():
    konten = _konten()
    alle = vt.liste(konten, mit_inaktiven=True)
    aktiv = [v for v in alle if v["v"]["aktiv"]]
    summe = sum(v["monatlich"] or 0 for v in aktiv)
    return render_template(
        "vertraege.html", aktiv=aktiv, inaktiv=[v for v in alle if not v["v"]["aktiv"]],
        erkannt=vt.erkenne(konten), summe_monat=summe,
        summe_je_art={a: sum(v["monatlich"] or 0 for v in aktiv if v["art"] == a) for a in vt.ARTEN},
        hinweise=[v for v in aktiv if v["aenderung"] or v["ausgeblieben"]],
        kuendigungen=vt.faellige_kuendigungen(), arten=vt.ARTEN,
        ausgeblendet=q("SELECT * FROM vertrag WHERE art = 'ignoriert' ORDER BY name"))


@bp.route("/markieren", methods=["POST"])
@auth.schreibrecht
def markieren():
    """Erkannte regelmäßige Zahlung als Abo/Fixkosten/Vertrag übernehmen oder dauerhaft ausblenden."""
    f = request.form
    key = f.get("partner_key", "")
    art = f.get("art")
    if not key:
        return redirect(url_for("vertraege.index"))
    if art in vt.ARTEN:
        b = q1("""SELECT * FROM buchung WHERE partner_key = ? AND betrag_cent < 0 AND vertrag_id IS NULL
                  ORDER BY buchungsdatum DESC LIMIT 1""", (key,))
        if not b:
            abort(404)
        vid = vt.aus_buchung_anlegen(b, art, int_oder_none(f.get("monate")) or 1, f.get("name"))
        log_aenderung(g.user["id"], "vertrag", vid, "angelegt", dict(f))
        commit()
        melde(f"Als {vt.ARTEN[art]} übernommen. Laufzeit und Kündigungsfrist kannst du hier ergänzen.")
        return redirect(url_for("vertraege.bearbeiten", vid=vid))
    if art == "ignoriert":
        exe("INSERT INTO vertrag (name, art, partner_key) VALUES (?, 'ignoriert', ?)", (f.get("name") or key, key))
        melde("Ausgeblendet – diese Gegenpartei wird nicht mehr vorgeschlagen.")
    elif art == "einblenden":
        exe("DELETE FROM vertrag WHERE partner_key = ? AND art = 'ignoriert'", (key,))
        melde("Wird wieder vorgeschlagen.")
    commit()
    return redirect(url_for("vertraege.index"))


def _form_werte(f):
    def datum(name):
        try:
            return date.fromisoformat(f.get(name, "")).isoformat()
        except ValueError:
            return None
    betrag = abs(parse_euro_eingabe(f.get("betrag", ""))) or None
    rhythmus = int_oder_none(f.get("rhythmus_monate"))
    if f.get("rhythmus_monate") == "eigen":
        rhythmus = int_oder_none(f.get("rhythmus_eigen"))
    return {
        "name": f.get("name", "").strip(), "art": f.get("art") if f.get("art") in vt.ARTEN else "vertrag",
        "anbieter": f.get("anbieter", "").strip() or None, "vertragsnummer": f.get("vertragsnummer", "").strip() or None,
        "partner_key": f.get("partner_key", "").strip() or None,
        "kategorie_id": int_oder_none(f.get("kategorie_id")), "konto_id": int_oder_none(f.get("konto_id")),
        "betrag_cent": betrag, "rhythmus_monate": max(0, min(120, rhythmus if rhythmus is not None else 1)),
        "beginn": datum("beginn"), "laufzeit_ende": datum("laufzeit_ende"),
        "verlaengerung_monate": int_oder_none(f.get("verlaengerung_monate")),
        "kuendigungsfrist": int_oder_none(f.get("kuendigungsfrist")),
        "kuendigungsfrist_einheit": f.get("kuendigungsfrist_einheit") if f.get("kuendigungsfrist_einheit") in vt.EINHEITEN else "monate",
        "gekuendigt_zum": datum("gekuendigt_zum"), "notiz": f.get("notiz", "").strip() or None,
        "aktiv": 1 if f.get("aktiv") else 0,
    }


@bp.route("/neu", methods=["GET", "POST"])
@bp.route("/<int:vid>", methods=["GET", "POST"])
@auth.login_required
def bearbeiten(vid=None):
    v = q1("SELECT * FROM vertrag WHERE id = ?", (vid,)) if vid else None
    if vid and not v:
        abort(404)
    if request.method == "POST":
        if not auth.darf_schreiben():
            abort(403)
        f = request.form
        if f.get("aktion") == "loeschen" and v:
            exe("UPDATE buchung SET vertrag_id = NULL WHERE vertrag_id = ?", (vid,))
            exe("DELETE FROM vertrag WHERE id = ?", (vid,))
            log_aenderung(g.user["id"], "vertrag", vid, "geloescht")
            commit()
            melde("Vertrag gelöscht; die Buchungen bleiben erhalten.")
            return redirect(url_for("vertraege.index"))
        if f.get("aktion") == "gekuendigt" and v:
            k = vt.kuendigung(v)
            zum = k["ende"].isoformat() if k else date.today().isoformat()
            exe("UPDATE vertrag SET gekuendigt_zum = ? WHERE id = ?", (zum, vid))
            commit()
            melde("Als gekündigt vermerkt – der Hinweis erscheint nicht mehr.")
            return redirect(request.form.get("zurueck") or url_for("vertraege.bearbeiten", vid=vid))
        if f.get("aktion") == "loesen" and v:
            exe("UPDATE buchung SET vertrag_id = NULL WHERE id = ? AND vertrag_id = ?", (int_oder_none(f.get("bid")), vid))
            commit()
            melde("Zuordnung entfernt.")
            return redirect(url_for("vertraege.bearbeiten", vid=vid))
        try:
            w = _form_werte(f)
        except ValueError:
            melde("Betrag prüfen.", "warn")
            return redirect(request.full_path)
        if not w["name"]:
            melde("Bitte einen Namen angeben.", "warn")
            return redirect(request.full_path)
        if not v:
            w["aktiv"] = 1
        spalten = list(w)
        if v:
            exe(f"UPDATE vertrag SET {', '.join(s + ' = ?' for s in spalten)} WHERE id = ?", [w[s] for s in spalten] + [vid])
        else:
            vid = exe(f"INSERT INTO vertrag ({', '.join(spalten)}) VALUES ({', '.join('?' * len(spalten))})",
                      [w[s] for s in spalten])
        n = vt.zuordnen() if w["partner_key"] else 0
        log_aenderung(g.user["id"], "vertrag", vid, "gespeichert", dict(f))
        commit()
        melde("Vertrag gespeichert." + (f" {n} Buchungen automatisch zugeordnet." if n else ""))
        return redirect(url_for("vertraege.bearbeiten", vid=vid))
    konten = _konten()
    info = next((x for x in vt.liste(konten, mit_inaktiven=True) if x["id"] == vid), None) if v else None
    zahlungen = q(f"""SELECT b.*, k.name AS konto_name FROM buchung b JOIN konto k ON k.id = b.konto_id
                      WHERE b.vertrag_id = ? AND b.konto_id IN ({','.join('?' * len(konten)) or 'NULL'})
                      ORDER BY b.buchungsdatum DESC LIMIT 60""", [vid] + list(konten)) if v else []
    sichtbar = auth.sichtbare_konten(nur_aktive=True, mit_darlehen=False)
    return render_template("vertrag.html", v=v, info=info, zahlungen=zahlungen, arten=vt.ARTEN,
                           rhythmen=vt.RHYTHMUS_NAMEN, einheiten=vt.EINHEITEN, kategorien=kategorien.alle(),
                           konten=q(f"SELECT id, name FROM konto WHERE id IN ({','.join('?' * len(sichtbar)) or 'NULL'}) "
                                    f"ORDER BY sortierung, name", sichtbar),
                           partner=q("""SELECT partner_key, MAX(gegenpartei) AS name, COUNT(*) AS n FROM buchung
                                        WHERE partner_key != '' AND betrag_cent < 0 GROUP BY partner_key
                                        ORDER BY n DESC LIMIT 400"""))
