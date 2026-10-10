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
