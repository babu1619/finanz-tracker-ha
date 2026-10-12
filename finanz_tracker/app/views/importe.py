import json

from flask import Blueprint, abort, g, redirect, render_template, request, url_for

from .. import auth, config
from ..db import q, q1, exe, commit, jdump, jload, log_aenderung
from ..services import csvimport, importer
from ..util import datum_de
from . import melde, int_oder_none

bp = Blueprint("importe", __name__, url_prefix="/import")


def _konten_mit_profil():
    sichtbar = auth.sichtbare_konten(nur_aktive=True)
    if not sichtbar:
        return []
    marks = ",".join("?" * len(sichtbar))
    return q(f"""SELECT k.*, ip.name AS profil_name, ip.format AS profil_format FROM konto k
                 LEFT JOIN konto_importprofil kp ON kp.konto_id = k.id AND kp.rolle = 'buchungen'
                 LEFT JOIN importprofil ip ON ip.id = kp.importprofil_id
                 WHERE k.id IN ({marks}) ORDER BY k.sortierung, k.name""", sichtbar)


@bp.route("/", methods=["GET", "POST"])
@auth.schreibrecht
def index():
    konten = _konten_mit_profil()
    if request.method == "POST":
        datei = request.files.get("datei")
        if not datei or not datei.filename:
            melde("Bitte eine Datei auswählen.", "warn")
            return redirect(url_for("importe.index"))
        raw = datei.read()
        konto_id = int_oder_none(request.form.get("konto_id"))
        if not konto_id:
            konto_id = importer.erkenne_konto(raw)
            if not konto_id:
                melde("Konto konnte nicht automatisch erkannt werden. Bitte das Konto auswählen.", "warn")
                return redirect(url_for("importe.index"))
        if not auth.konto_sichtbar(konto_id):
            abort(403)
        try:
            vorb = importer.vorbereiten(konto_id, raw, datei.filename)
        except csvimport.ProfilFehler as exc:
            melde(str(exc), "warn")
            return redirect(url_for("importe.index"))
        konto = q1("SELECT * FROM konto WHERE id = ?", (konto_id,))
        return render_template("import_vorschau.html", vorb=vorb, konto=konto, dateiname=datei.filename)
    laeufe = q(f"""SELECT l.*, k.name AS konto_name, b.name AS benutzer_name FROM importlauf l
                   JOIN konto k ON k.id = l.konto_id LEFT JOIN benutzer b ON b.id = l.benutzer_id
                   WHERE l.konto_id IN ({','.join('?' * len(konten)) or 'NULL'})
                   ORDER BY l.zeitpunkt DESC LIMIT 20""", [k["id"] for k in konten])
    profile = q("""SELECT p.*, (SELECT group_concat(k.name, ', ') FROM konto_importprofil kp JOIN konto k ON k.id = kp.konto_id
                                WHERE kp.importprofil_id = p.id) AS konten FROM importprofil p ORDER BY p.name""")
    return render_template("import.html", konten=konten, laeufe=laeufe, profile=profile)


@bp.route("/uebernehmen/<token>", methods=["POST"])
@auth.schreibrecht
def uebernehmen(token):
    geladen = importer.lade_vorbereitung(token)
    if not geladen:
        melde("Die Vorschau ist abgelaufen. Bitte die Datei erneut hochladen.", "warn")
        return redirect(url_for("importe.index"))
    if not auth.konto_sichtbar(geladen[0]["konto_id"]):
        abort(403)
    try:
        lauf_id = importer.uebernehmen(token, g.user["id"])
    except csvimport.ProfilFehler as exc:
        melde(str(exc), "warn")
        return redirect(url_for("importe.index"))
    log_aenderung(g.user["id"], "importlauf", lauf_id, "import")
    commit()
    return redirect(url_for("importe.lauf", lid=lauf_id))


@bp.route("/abbrechen/<token>", methods=["POST"])
@auth.schreibrecht
def abbrechen(token):
    importer.entferne_vorbereitung(token)
    return redirect(url_for("importe.index"))


@bp.route("/lauf/<int:lid>")
@auth.login_required
def lauf(lid):
    l = q1("SELECT l.*, k.name AS konto_name FROM importlauf l JOIN konto k ON k.id = l.konto_id WHERE l.id = ?", (lid,))
    if not l or not auth.konto_sichtbar(l["konto_id"]):
        abort(404)
    stat = q1("""SELECT COUNT(*) AS n,
                 SUM(CASE WHEN zuordnung_quelle = 'regel' THEN 1 ELSE 0 END) AS regel,
                 SUM(CASE WHEN zuordnung_quelle = 'gedaechtnis' THEN 1 ELSE 0 END) AS gedaechtnis,
                 SUM(CASE WHEN ist_umbuchung = 1 THEN 1 ELSE 0 END) AS umbuchung,
                 SUM(CASE WHEN kategorie_id IS NULL AND ist_umbuchung = 0 THEN 1 ELSE 0 END) AS offen,
                 SUM(CASE WHEN geprueft = 0 AND kategorie_id IS NOT NULL THEN 1 ELSE 0 END) AS ungeprueft
                 FROM buchung WHERE importlauf_id = ?""", (lid,))
    return render_template("import_lauf.html", l=l, stat=stat, kontostand=importer.kontostand(l["konto_id"]))


@bp.route("/lauf/<int:lid>/rueckgaengig", methods=["POST"])
@auth.schreibrecht
def rueckgaengig(lid):
    l = q1("SELECT * FROM importlauf WHERE id = ?", (lid,))
    if not l or not auth.konto_sichtbar(l["konto_id"]):
        abort(404)
    n = importer.rueckgaengig(lid)
    log_aenderung(g.user["id"], "importlauf", lid, "rueckgaengig", {"buchungen": n})
    commit()
    melde(f"Import rückgängig gemacht: {n} Buchungen entfernt.")
    return redirect(url_for("importe.index"))


# ---------- Importprofile ----------

@bp.route("/profil/neu", methods=["GET", "POST"])
@auth.admin_required
def profil_neu():
    if request.method == "POST":
        datei = request.files.get("datei")
        if not datei or not datei.filename:
            melde("Bitte eine Beispieldatei der Bank auswählen.", "warn")
            return redirect(url_for("importe.profil_neu"))
        raw = datei.read()
        a = csvimport.analysiere(raw)
        if not a["headers"]:
            melde("In der Datei wurden keine Spalten erkannt. Ist es eine CSV-Datei?", "warn")
            return redirect(url_for("importe.profil_neu"))
        name = request.form.get("name", "").strip() or datei.filename.rsplit(".", 1)[0]
        spalten = [{"index": i, "header": h, "feld": f} for i, (h, f) in enumerate(zip(a["headers"], a["felder"]))]
        pid = exe("INSERT INTO importprofil (name, format, einstellungen, spalten, betrag_modus, beispiel) "
                  "VALUES (?, 'csv', ?, ?, ?, ?)",
                  (name, jdump(a["einstellungen"]), jdump(spalten), a["betrag_modus"],
                   jdump({"vorspann": a["vorspann"][:6], "headers": a["headers"], "zeilen": a["beispiel"][:6]})))
        tmp = config.TMP_DIR / f"profil_{pid}.bin"
        tmp.write_bytes(raw)
        commit()
        melde("Datei erkannt. Bitte Einstellungen und Spaltenzuordnung prüfen und speichern.")
        return redirect(url_for("importe.profil", pid=pid))
    return render_template("profil_neu.html")


@bp.route("/profil/<int:pid>", methods=["GET", "POST"])
@auth.admin_required
def profil(pid):
    p = q1("SELECT * FROM importprofil WHERE id = ?", (pid,))
    if not p:
        abort(404)
    pd = importer.profil_dict(p)
    if request.method == "POST":
        if request.form.get("aktion") == "loeschen":
            if q1("SELECT 1 FROM konto_importprofil WHERE importprofil_id = ?", (pid,)):
                melde("Profil ist noch Konten zugeordnet.", "warn")
                return redirect(url_for("importe.profil", pid=pid))
            exe("DELETE FROM importprofil WHERE id = ?", (pid,))
            commit()
            melde("Profil gelöscht.")
            return redirect(url_for("importe.index"))
        einst = {
            "encoding": request.form.get("encoding", "utf-8"),
            "delimiter": {"semikolon": ";", "komma": ",", "tab": "\t", "pipe": "|"}.get(request.form.get("delimiter"), ";"),
            "date_format": request.form.get("date_format", "TT.MM.JJJJ"),
            "decimal": "," if request.form.get("decimal", ",") == "," else ".",
        }
        headers = pd["beispiel"].get("headers", []) if isinstance(pd["beispiel"], dict) else []
        tmp = config.TMP_DIR / f"profil_{pid}.bin"
        alt_einst = pd["einstellungen"]
        if tmp.exists() and (einst["encoding"] != alt_einst.get("encoding") or einst["delimiter"] != alt_einst.get("delimiter")):
            a = csvimport.analysiere(tmp.read_bytes(), einst["encoding"], einst["delimiter"])
            alt = {s["header"]: s["feld"] for s in pd["spalten"]}
            exe("UPDATE importprofil SET beispiel = ? WHERE id = ?",
                (jdump({"vorspann": a["vorspann"][:6], "headers": a["headers"], "zeilen": a["beispiel"][:6]}), pid))
            spalten = [{"index": i, "header": h, "feld": alt.get(h, f)} for i, (h, f) in enumerate(zip(a["headers"], a["felder"]))]
            exe("UPDATE importprofil SET einstellungen = ?, spalten = ? WHERE id = ?", (jdump(einst), jdump(spalten), pid))
            commit()
            melde("Zeichensatz bzw. Trennzeichen geändert – Spalten neu eingelesen. Bitte Zuordnung prüfen.")
            return redirect(url_for("importe.profil", pid=pid))
        spalten = []
        for i, h in enumerate(headers):
            feld = request.form.get(f"feld{i}", "ignore")
            spalten.append({"index": i, "header": h, "feld": feld if feld in csvimport.FELDER else "ignore"})
        modus = request.form.get("betrag_modus", "vorzeichen")
        fehler = csvimport.pruefe_zuordnung(spalten, modus)
        exe("UPDATE importprofil SET name = ?, einstellungen = ?, spalten = ?, betrag_modus = ?, "
            "geaendert = datetime('now','localtime') WHERE id = ?",
            (request.form.get("name", p["name"]).strip() or p["name"], jdump(einst), jdump(spalten), modus, pid))
        # Kontenzuordnung
        for k in q("SELECT id FROM konto"):
            gewaehlt = request.form.get(f"konto{k['id']}")
            vorhanden = q1("SELECT * FROM konto_importprofil WHERE konto_id = ? AND rolle = 'buchungen'", (k["id"],))
            if gewaehlt and (not vorhanden or vorhanden["importprofil_id"] != pid):
                exe("DELETE FROM konto_importprofil WHERE konto_id = ? AND rolle = 'buchungen'", (k["id"],))
                exe("INSERT INTO konto_importprofil (konto_id, importprofil_id, rolle) VALUES (?,?, 'buchungen')",
                    (k["id"], pid))
            elif not gewaehlt and vorhanden and vorhanden["importprofil_id"] == pid:
                exe("DELETE FROM konto_importprofil WHERE id = ?", (vorhanden["id"],))
        log_aenderung(g.user["id"], "importprofil", pid, "gespeichert")
        commit()
        if fehler:
            for f in fehler:
                melde(f, "warn")
        else:
            melde("Profil gespeichert.")
        return redirect(url_for("importe.profil", pid=pid))

    # Vorschau mit gespeicherter Zuordnung
    vorschau, vorschau_fehler, hinweise = [], [], []
    tmp = config.TMP_DIR / f"profil_{pid}.bin"
    if tmp.exists():
        try:
            erg = csvimport.lese_datei(tmp.read_bytes(), pd)
            vorschau = erg["datensaetze"][:6]
            vorschau_fehler = erg["fehler"][:5]
            hinweise = erg["hinweise"]
        except csvimport.ProfilFehler as exc:
            hinweise = [str(exc)]
    zuordnung_konten = {r["konto_id"] for r in q("SELECT konto_id FROM konto_importprofil WHERE importprofil_id = ?", (pid,))}
    return render_template(
        "profil.html", p=p, pd=pd, felder=csvimport.FELDER, datumsformate=csvimport.DATUMSFORMATE,
        encodings=list(csvimport.ENCODINGS), pruefung=csvimport.pruefe_zuordnung(pd["spalten"], pd["betrag_modus"]),
        vorschau=vorschau, vorschau_fehler=vorschau_fehler, hinweise=hinweise, hat_datei=tmp.exists(),
        konten=q("SELECT * FROM konto ORDER BY sortierung, name"), zuordnung_konten=zuordnung_konten,
        delim_key={";": "semikolon", ",": "komma", "\t": "tab", "|": "pipe"}.get(pd["einstellungen"].get("delimiter"), "semikolon"))


@bp.route("/profil/<int:pid>/datei", methods=["POST"])
@auth.admin_required
def profil_datei(pid):
    """Neue Beispieldatei hochladen (z. B. nach Formatänderung der Bank) – Überschriften werden neu eingelesen."""
    p = q1("SELECT * FROM importprofil WHERE id = ?", (pid,))
    datei = request.files.get("datei")
    if not p or not datei or not datei.filename:
        abort(400)
    raw = datei.read()
    a = csvimport.analysiere(raw)
    alt = {s["header"]: s["feld"] for s in jload(p["spalten"], [])}
    spalten = [{"index": i, "header": h, "feld": alt.get(h, f)} for i, (h, f) in enumerate(zip(a["headers"], a["felder"]))]
    exe("UPDATE importprofil SET einstellungen = ?, spalten = ?, beispiel = ? WHERE id = ?",
        (jdump(a["einstellungen"]), jdump(spalten),
         jdump({"vorspann": a["vorspann"][:6], "headers": a["headers"], "zeilen": a["beispiel"][:6]}), pid))
    (config.TMP_DIR / f"profil_{pid}.bin").write_bytes(raw)
    commit()
    melde("Neue Beispieldatei eingelesen. Bekannte Spalten wurden übernommen, bitte den Rest prüfen.")
    return redirect(url_for("importe.profil", pid=pid))


# ---------------------------------------------------------------------------------------------------------------
# Screenshot-Import (Kreditkarte o. Ä. ohne CSV): Texterkennung lokal, Prüftabelle, dann übernehmen

def _screenshot_konten():
    sichtbar = auth.sichtbare_konten(nur_aktive=True, mit_darlehen=False)
    return q(f"SELECT * FROM konto WHERE id IN ({','.join('?' * len(sichtbar)) or 'NULL'}) "
             f"ORDER BY typ != 'kreditkarte', sortierung, name", sichtbar)


@bp.route("/screenshot", methods=["GET", "POST"])
@auth.schreibrecht
def screenshot():
    from ..services import ocr
    konten = _screenshot_konten()
    if request.method == "GET":
        return render_template("import_screenshot.html", konten=konten, ocr_da=ocr.verfuegbar(),
                               konto_id=int_oder_none(request.args.get("konto")))
    konto_id = int_oder_none(request.form.get("konto_id"))
    if konto_id not in {k["id"] for k in konten}:
        melde("Bitte ein Konto wählen.", "warn")
        return redirect(url_for("importe.screenshot"))
    bilder = [f for f in request.files.getlist("bilder") if f and f.filename]
    if not bilder:
        melde("Bitte mindestens einen Screenshot auswählen oder einfügen.", "warn")
        return redirect(url_for("importe.screenshot", konto=konto_id))
    alle, fehler, rohtexte = [], [], []
    for nr, f in enumerate(bilder[:10], 1):
        try:
            erg = ocr.erkenne(f.read())
        except ocr.OcrFehler as exc:
            fehler.append(f"Bild {nr}: {exc}")
            continue
        rohtexte.append(erg["text"])
        if not erg["umsaetze"]:
            fehler.append(f"Bild {nr}: keine Umsätze erkannt.")
        alle.append(erg["umsaetze"])
    zeilen = screenshot_zeilen(konto_id, alle)
    konto = q1("SELECT * FROM konto WHERE id = ?", (konto_id,))
    return render_template("import_screenshot_pruefen.html", konto=konto, zeilen=zeilen, fehler=fehler,
                           rohtext="\n\n".join(rohtexte), anzahl_bilder=len(bilder))


def _ocr_schluessel(u) -> tuple:
    from ..util import norm_text
    return (u["datum"].isoformat() if u["datum"] else "", u["betrag_cent"], norm_text(u["gegenpartei"])[:40])


def screenshot_zeilen(konto_id, listen: list[list[dict]]) -> list[dict]:
    """Ergebnisse mehrerer Screenshots zusammenführen und mit vorhandenen Buchungen abgleichen.

    Überlappende Screenshots (beim Scrollen) zeigen dieselben Umsätze mehrfach: Je Schlüssel zählt die höchste
    Anzahl in einem einzelnen Bild. Gleiche Umsätze im selben Bild (z. B. zweimal Parken am selben Tag) bleiben.
    """
    import hashlib
    gesamt: dict = {}
    reihenfolge = []
    for liste in listen:
        je_bild: dict = {}
        for u in liste:
            s = _ocr_schluessel(u)
            je_bild.setdefault(s, []).append(u)
        for s, us in je_bild.items():
            if s not in gesamt:
                reihenfolge.append(s)
                gesamt[s] = us
            elif len(us) > len(gesamt[s]):
                gesamt[s] = us
    vorhanden = {r["dedup_hash"] for r in q("SELECT dedup_hash FROM buchung WHERE konto_id = ?", (konto_id,))}
    zeilen = []
    for s in reihenfolge:
        for n, u in enumerate(gesamt[s]):
            h = "ocr:" + hashlib.sha256(f"{konto_id}|{'|'.join(map(str, s))}#{n}".encode()).hexdigest()[:40]
            aehnlich = None
            if u["datum"]:
                aehnlich = q1("""SELECT id, gegenpartei, buchungsdatum FROM buchung WHERE konto_id = ? AND betrag_cent = ?
                                 AND abs(julianday(buchungsdatum) - julianday(?)) <= 2 LIMIT 1""",
                              (konto_id, u["betrag_cent"], u["datum"].isoformat()))
            status = "doppelt" if h in vorhanden else ("aehnlich" if aehnlich else "neu")
            zeilen.append({**u, "hash": h, "pruefstatus": status, "aehnlich": aehnlich,
                           "vorauswahl": status == "neu" and u["status"] != "vorgemerkt" and bool(u["datum"])})
    zeilen.sort(key=lambda z: z["datum"].isoformat() if z["datum"] else "", reverse=True)
    return zeilen


@bp.route("/screenshot/uebernehmen", methods=["POST"])
@auth.schreibrecht
def screenshot_uebernehmen():
    from datetime import date as _date
    from ..services import umbuchungen, zuordnung
    from ..util import monat_von, parse_euro_eingabe, partner_key
    f = request.form
    konto_id = int_oder_none(f.get("konto_id"))
    if konto_id not in {k["id"] for k in _screenshot_konten()}:
        abort(403)
    vorhanden = {r["dedup_hash"] for r in q("SELECT dedup_hash FROM buchung WHERE konto_id = ?", (konto_id,))}
    gewaehlt = f.getlist("nr")
    daten, fehler = [], 0
    for nr in gewaehlt:
        h = f.get(f"hash_{nr}", "")
        if not h.startswith("ocr:") or h in vorhanden:
            continue
        try:
            d = _date.fromisoformat(f.get(f"datum_{nr}", ""))
            betrag = parse_euro_eingabe(f.get(f"betrag_{nr}", ""))
        except ValueError:
            fehler += 1
            continue
        partei = f.get(f"partei_{nr}", "").strip()
        if not betrag or not partei:
            fehler += 1
            continue
        bank_kat = f.get(f"bankkat_{nr}", "").strip()
        daten.append((d, betrag, partei, bank_kat, h))
        vorhanden.add(h)
    if not daten:
        melde("Keine Zeile übernommen." + (f" {fehler} Zeilen hatten ungültige Werte." if fehler else ""), "warn")
        return redirect(url_for("importe.screenshot", konto=konto_id))
    lauf_id = exe("INSERT INTO importlauf (konto_id, dateiname, benutzer_id, anzahl_neu, anzahl_doppelt, anzahl_fehler) "
                  "VALUES (?,?,?,?,?,?)",
                  (konto_id, f"Screenshot ({f.get('anzahl_bilder') or 1} Bild/er)", g.user["id"], len(daten),
                   len(gewaehlt) - len(daten) - fehler, fehler))
    ids = []
    for d, betrag, partei, bank_kat, h in daten:
        ids.append(exe("""INSERT INTO buchung (konto_id, buchungsdatum, betrag_cent, gegenpartei, verwendungszweck, partner_key,
                          abrechnungsmonat, dedup_hash, importlauf_id, rohdaten) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                       (konto_id, d.isoformat(), betrag, partei, bank_kat or "", partner_key(partei), monat_von(d), h,
                        lauf_id, jdump({"quelle": "screenshot", "bank_kategorie": bank_kat}))))
    zuordnung.ordne_zu(ids)
    umbuchungen.erkenne(ids)
    log_aenderung(g.user["id"], "importlauf", lauf_id, "screenshot", {"buchungen": len(ids)})
    commit()
    melde(f"{len(ids)} Umsätze übernommen." + (f" {fehler} Zeilen mit ungültigen Werten übersprungen." if fehler else ""))
    return redirect(url_for("importe.lauf", lid=lauf_id))
