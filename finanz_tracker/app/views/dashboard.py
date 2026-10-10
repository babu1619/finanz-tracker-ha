from flask import Blueprint, render_template, request

from .. import auth
from ..db import q
from ..services import importer, statistik, umbuchungen
from ..util import monat_plus
from . import monat_param, int_oder_none

bp = Blueprint("dashboard", __name__)


@bp.route("/")
@auth.login_required
def index():
    monat = monat_param()
    person_id = int_oder_none(request.args.get("person"))
    sichtbar = auth.sichtbare_konten()
    konten = statistik.basis_konten(sichtbar)
    werte = statistik.monatswerte(konten, monat, person_id)
    vormonat = statistik.monatswerte(konten, monat_plus(monat, -1), person_id)
    kat = statistik.ausgaben_nach_kategorie(konten, monat, person_id)
    vor_kat = {k["id"]: k["betrag"] for k in statistik.ausgaben_nach_kategorie(konten, monat_plus(monat, -1), person_id)}
    for k in kat:
        k["vormonat"] = vor_kat.get(k["id"])
    verlauf = statistik.verlauf(konten, monat, 12, person_id)
    max_verlauf = max([max(v["einnahmen"], v["ausgaben"]) for v in verlauf] + [1])

    konto_rows = []
    vermoegen = 0
    if sichtbar:
        marks = ",".join("?" * len(sichtbar))
        for k in q(f"SELECT * FROM konto WHERE id IN ({marks}) AND aktiv = 1 ORDER BY typ = 'darlehen', sortierung, name",
                   sichtbar):
            saldo = importer.kontostand(k["id"])
            letzter = importer.letzter_import(k["id"])
            tage = importer.tage_seit(letzter["zeitpunkt"]) if letzter else None
            konto_rows.append({"k": k, "saldo": saldo, "letzter": letzter, "tage": tage,
                               "faellig": k["typ"] not in ("bargeld", "depot", "darlehen") and
                               (tage is None or tage > k["import_erinnerung_tage"])})
            if k["typ"] != "darlehen":
                vermoegen += saldo
    marks = ",".join("?" * len(konten)) or "NULL"
    ohne_kat = q(f"SELECT COUNT(*) AS n FROM buchung WHERE konto_id IN ({marks}) AND kategorie_id IS NULL "
                 f"AND ist_umbuchung = 0", konten)[0]["n"] if konten else 0
    ungeprueft = q(f"SELECT COUNT(*) AS n FROM buchung WHERE konto_id IN ({marks}) AND kategorie_id IS NOT NULL "
                   f"AND geprueft = 0 AND ist_umbuchung = 0", konten)[0]["n"] if konten else 0
    saldo_warnungen = [r for r in konto_rows if r["letzter"] and r["letzter"]["saldo_differenz_cent"]]
    personen = q("SELECT * FROM person WHERE aktiv = 1 ORDER BY name")
    max_kat = max([k["betrag"] for k in kat] + [1])
    return render_template(
        "dashboard.html", monat=monat, vor=monat_plus(monat, -1), nach=monat_plus(monat, 1),
        werte=werte, vormonat=vormonat, kat=kat, max_kat=max_kat, verlauf=verlauf, max_verlauf=max_verlauf,
        konten=konto_rows, vermoegen=vermoegen, ohne_kat=ohne_kat, ungeprueft=ungeprueft,
        umbuchungs_vorschlaege=len(umbuchungen.offene_vorschlaege(sichtbar)), saldo_warnungen=saldo_warnungen,
        personen=personen, person_id=person_id)
