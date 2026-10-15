from flask import Blueprint, render_template, request

from .. import auth
from ..db import q
from ..services import budgets, depot, importer, ruecklagen, statistik, umbuchungen, vertraege
from ..db import commit
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
    kat = statistik.ausgaben_baum(konten, monat, person_id)
    vor_kat = {}
    for k in statistik.ausgaben_baum(konten, monat_plus(monat, -1), person_id):
        vor_kat[("o", k["id"])] = k["betrag"]
        for c in k["kinder"]:
            vor_kat[("d" if c["direkt"] else "u", c["id"])] = c["betrag"]
    for k in kat:
        k["vormonat"] = vor_kat.get(("o", k["id"]))
        for c in k["kinder"]:
            c["vormonat"] = vor_kat.get(("d" if c["direkt"] else "u", c["id"]))
    verlauf = statistik.verlauf(konten, monat, 12, person_id)
    max_verlauf = max([max(v["einnahmen"], v["ausgaben"]) for v in verlauf] + [1])

    konto_rows = []
    vermoegen = 0
    if sichtbar:
        marks = ",".join("?" * len(sichtbar))
        for k in q(f"SELECT * FROM konto WHERE id IN ({marks}) AND aktiv = 1 ORDER BY typ = 'darlehen', sortierung, name",
                   sichtbar):
            saldo = depot.wert(k["id"]) if k["typ"] == "depot" else importer.kontostand(k["id"])
            from ..services import darlehen as dl
            if k["typ"] == "darlehen" and not dl.hat_importierte_buchungen(k["id"]):
                d = dl.lade(k["id"])
                if d:  # ohne importierte Buchungen: Restschuld laut Plan
                    saldo = -dl.kennzahlen(d)["restschuld"]
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
    # Budgets: die kritischsten zuerst
    bue = budgets.uebersicht(konten, monat)
    budget_top = sorted([z for z in bue["zeilen"] if not z["unterbudget"]], key=lambda z: -z["quote"])[:6]
    # Sparen
    from .sparen import sparkennzahlen
    from .darlehen import hinweise as darlehen_hinweise
    spar = sparkennzahlen(konten, sichtbar, monat)
    ziele = [e for e in ruecklagen.uebersicht(konten)["liste"] if e["r"]["ziel_cent"] and e["r"]["aktiv"]][:4]
    commit()
    vt_hinweise = [v for v in vertraege.liste(konten) if v["aenderung"] or v["ausgeblieben"]]
    max_kat = max([k["betrag"] for k in kat] + [1])
    return render_template(
        "dashboard.html", monat=monat, vor=monat_plus(monat, -1), nach=monat_plus(monat, 1),
        werte=werte, vormonat=vormonat, kat=kat, max_kat=max_kat, verlauf=verlauf, max_verlauf=max_verlauf,
        konten=konto_rows, vermoegen=vermoegen, ohne_kat=ohne_kat, ungeprueft=ungeprueft,
        umbuchungs_vorschlaege=len(umbuchungen.offene_vorschlaege(sichtbar)), saldo_warnungen=saldo_warnungen,
        personen=personen, person_id=person_id, bue=bue, budget_top=budget_top, spar=spar, ziele=ziele,
        vt_hinweise=vt_hinweise, darlehen_hinweise=darlehen_hinweise(sichtbar))
