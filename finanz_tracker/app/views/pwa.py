"""Installierbare Web-App (PWA): Manifest, Service Worker, Offline-Seite, Zertifikat zum Installieren."""
from flask import Blueprint, Response, abort, current_app, jsonify, render_template, request, send_from_directory, url_for

from .. import auth, config, tls

bp = Blueprint("pwa", __name__)


@bp.route("/manifest.webmanifest")
def manifest():
    icon = lambda n, z="any": {"src": url_for("static", filename=f"icons/{n}"), "sizes": n.split("-")[-1].split(".")[0] + "x" + n.split("-")[-1].split(".")[0],  # noqa: E731
                               "type": "image/png", "purpose": z}
    daten = {
        "id": "/",
        "name": "Finanz-Tracker",
        "short_name": "Finanzen",
        "description": "Haushaltsbuch der Familie",
        "lang": "de",
        "start_url": "/?quelle=app",
        "scope": "/",
        "display": "standalone",
        "orientation": "any",
        "background_color": "#F4F5F2",
        "theme_color": "#18211E",
        "icons": [icon("icon-192.png"), icon("icon-512.png"), icon("maskable-192.png", "maskable"),
                  icon("maskable-512.png", "maskable")],
        "shortcuts": [
            {"name": "Bar erfassen", "short_name": "Bar", "url": "/erfassen/",
             "icons": [{"src": url_for("static", filename="icons/icon-192.png"), "sizes": "192x192"}]},
            {"name": "Prüfen", "url": "/pruefen/",
             "icons": [{"src": url_for("static", filename="icons/icon-192.png"), "sizes": "192x192"}]},
            {"name": "Buchungen", "url": "/buchungen/",
             "icons": [{"src": url_for("static", filename="icons/icon-192.png"), "sizes": "192x192"}]},
        ],
    }
    r = jsonify(daten)
    r.mimetype = "application/manifest+json"
    r.headers["Cache-Control"] = "no-cache"
    return r


@bp.route("/sw.js")
def service_worker():
    js = render_template("sw.js", version=config.VERSION)
    return Response(js, mimetype="text/javascript",
                    headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"})


@bp.route("/offline")
def offline():
    return render_template("offline.html")


@bp.route("/zertifikat")
@auth.login_required
def zertifikat():
    import ipaddress
    info = tls.ca_info()
    lan_ip = None
    for n in (info or {}).get("server_namen", []):
        try:
            ip = ipaddress.ip_address(n)
        except ValueError:
            continue
        if ip.version == 4 and ip.is_private and not ip.is_loopback:
            lan_ip = n
            break
    return render_template("zertifikat.html", info=info, opt=tls.optionen(), sicher=request.is_secure,
                           host=request.host, lan_ip=lan_ip)


@bp.route("/zertifikat/finanz-tracker-ca.crt")
def ca_download():
    """Öffentliches CA-Zertifikat (kein Geheimnis). DER-Format: Android und Windows installieren es per Antippen."""
    if not tls.CA_CRT.exists():
        abort(404)
    form = request.args.get("format", "der")
    if form == "pem":
        return Response(tls.CA_CRT.read_bytes(), mimetype="application/x-pem-file",
                        headers={"Content-Disposition": "attachment; filename=finanz-tracker-ca.pem"})
    return Response(tls.ca_der(), mimetype="application/x-x509-ca-cert",
                    headers={"Content-Disposition": "attachment; filename=finanz-tracker-ca.crt"})


@bp.route("/favicon.ico")
def favicon():
    return send_from_directory(current_app.static_folder + "/icons", "icon-192.png", mimetype="image/png")
