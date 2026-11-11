from flask import Blueprint, render_template, request, url_for

from .. import auth
from ..db import q
from ..services import budgets, depot, importer, krypto, ruecklagen, statistik, umbuchungen, vermoegen as vm, vertraege
from ..db import commit
from ..util import monat_plus
from . import monat_param, int_oder_none

bp = Blueprint("dashboard", __name__)

# Kategorienfarben für Ring, Liste und Sankey (gleiche Kategorie = gleiche Farbe)
FARBEN_AUSGABEN = ["#3B6FB6", "#C98A12", "#B5475A", "#7A5BA8", "#2F9C9C", "#A0662E", "#D16BA5", "#6A8F3A",
                   "#44546A", "#8A9A2B", "#5E6B66", "#E07A3F"]
FARBEN_EINNAHMEN = ["#0F6B5C", "#2F9C9C", "#6A8F3A", "#3B8F6E", "#8A9A2B", "#44546A"]
FARBE_WEITERE, FARBE_OHNE, FARBE_GESPART, FARBE_RESERVE = "#AEB8B4", "#E0A93B", "#0A4D42", "#C98A12"
ZEITRAEUME_NV = {"6": "6 M", "12": "1 J", "36": "3 J", "60": "5 J", "alle": "Alles"}


def _farbtabelle(kat: list) -> dict:
    farben = {}
    for i, k in enumerate(x for x in kat if x["id"]):
        farben[k["id"]] = FARBEN_AUSGABEN[i % len(FARBEN_AUSGABEN)]
    return farben


def _faerben(cf: dict, farben: dict) -> dict:
    frei = [f for f in FARBEN_AUSGABEN if f not in farben.values()] or FARBEN_AUSGABEN
    j = 0
    for i, x in enumerate(cf["quellen"]):
        x["farbe"] = FARBE_RESERVE if x["id"] == "reserve" else FARBE_WEITERE if x["id"] == "sonstige" else \
            FARBEN_EINNAHMEN[i % len(FARBEN_EINNAHMEN)]
    for x in cf["ziele"]:
        if x["id"] == "gespart":
            x["farbe"] = FARBE_GESPART
        elif x["id"] == "sonstige":
            x["farbe"] = FARBE_WEITERE
        elif x["id"] is None:
            x["farbe"] = FARBE_OHNE
        elif x["id"] in farben:
            x["farbe"] = farben[x["id"]]
        else:
            x["farbe"] = frei[j % len(frei)]
            j += 1
    return cf


def _bereich_link(cf: dict, person_id) -> dict:
    """Basis-URL für Klicks im Sankey: Buchungen des Zeitraums."""
    if cf["von"] == cf["bis"]:
        cf["url"] = url_for("buchungen.liste", monat=cf["von"], person=person_id)
    else:
        bis = vm._monatsende(cf["bis"])
        cf["url"] = url_for("buchungen.liste", monat="alle", von=cf["von"] + "-01", bis=bis, person=person_id)
    return cf


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
            if k["typ"] == "depot":
                saldo = depot.wert(k["id"])
            elif k["typ"] == "krypto":
                saldo = krypto.wert(k["id"])
            else:
                saldo = importer.kontostand(k["id"])
            from ..services import darlehen as dl
            if k["typ"] == "darlehen" and not dl.hat_importierte_buchungen(k["id"]):
                d = dl.lade(k["id"])
                if d:  # ohne importierte Buchungen: Restschuld laut Plan
                    saldo = -dl.kennzahlen(d)["restschuld"]
            letzter = importer.letzter_import(k["id"])
            tage = importer.tage_seit(letzter["zeitpunkt"]) if letzter else None
            konto_rows.append({"k": k, "saldo": saldo, "letzter": letzter, "tage": tage,
                               "faellig": k["typ"] not in ("bargeld", "depot", "darlehen", "krypto") and
                               (tage is None or tage > k["import_erinnerung_tage"])})
            if k["typ"] != "darlehen" and (k["typ"] != "krypto" or krypto.im_vermoegen(k["id"])):
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
    # 0.8.0: Nettovermögen, Cashflow, Vermögensaufstellung
    farben = _farbtabelle(kat)
    for k in kat:
        k["farbe"] = farben.get(k["id"], FARBE_OHNE)
    hist = vm.verlauf_je_konto(sichtbar)
    nv = vm.nettovermoegen(hist)
    bil = vm.bilanz(hist)
    cashflow = {
        "monat": _bereich_link(_faerben(vm.cashflow(konten, monat, monat, person_id), farben), person_id),
        "jahr": _bereich_link(_faerben(vm.cashflow(konten, monat[:4] + "-01", monat, person_id), farben), person_id),
        "zwoelf": _bereich_link(_faerben(vm.cashflow(konten, monat_plus(monat, -11), monat, person_id), farben),
                                person_id),
    }
    dash = {
        "nv": {"labels": nv["monate"], "netto": nv["netto"], "aktiva": nv["aktiva"], "passiva": nv["passiva"]},
        "cashflow": cashflow,
        "ausgaben": {"labels": [monat], "reihen": [{"id": k["id"], "name": k["name"], "werte": [k["betrag"]]} for k in kat],
                     "farben": [k["farbe"] for k in kat], "einheit": "€",
                     "url": url_for("buchungen.liste", monat=monat, art="ausgabe", person=person_id)},
        "verlauf": {"labels": [v["monat"] for v in verlauf], "einheit": "€",
                    "reihen": [{"name": "Einnahmen", "werte": [v["einnahmen"] for v in verlauf]},
                               {"name": "Ausgaben", "werte": [v["ausgaben"] for v in verlauf]}]},
    }
    return render_template(
        "dashboard.html", monat=monat, vor=monat_plus(monat, -1), nach=monat_plus(monat, 1),
        werte=werte, vormonat=vormonat, kat=kat, max_kat=max_kat, verlauf=verlauf, max_verlauf=max_verlauf,
        konten=konto_rows, vermoegen=vermoegen, ohne_kat=ohne_kat, ungeprueft=ungeprueft,
        umbuchungs_vorschlaege=len(umbuchungen.offene_vorschlaege(sichtbar)), saldo_warnungen=saldo_warnungen,
        personen=personen, person_id=person_id, bue=bue, budget_top=budget_top, spar=spar, ziele=ziele,
        vt_hinweise=vt_hinweise, darlehen_hinweise=darlehen_hinweise(sichtbar),
        nv=nv, bilanz=bil, dash=dash, zeitraeume_nv=ZEITRAEUME_NV)
