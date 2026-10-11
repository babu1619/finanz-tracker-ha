"""HTTPS-Server auf Basis des Werkzeug-Servers (mehrere Threads, TLS 1.2+).

Besonderheit: Auf demselben Port wird unverschlüsseltes HTTP erkannt und per 301 auf https:// umgeleitet –
alte Lesezeichen (http://…:8099) funktionieren dadurch weiter. Der TLS-Handshake läuft im Thread der
Verbindung, nicht im Haupt-Thread, damit ein langsamer Client den Server nicht blockiert.
"""
import logging
import socket
import ssl

from werkzeug.serving import ThreadedWSGIServer, WSGIRequestHandler

log = logging.getLogger("finanz.server")
TIMEOUT = 30


class Handler(WSGIRequestHandler):
    def log_request(self, code="-", size="-"):
        try:
            c = int(code)
        except (TypeError, ValueError):
            c = 0
        if c >= 500:
            super().log_request(code, size)

    def log_error(self, format, *args):  # noqa: A002 – Signatur der Basisklasse
        log.debug(format, *args)


class HttpsServer(ThreadedWSGIServer):
    daemon_threads = True

    def __init__(self, host, port, app, ctx: ssl.SSLContext):
        super().__init__(host, port, app, handler=Handler)
        self.ssl_context = ctx  # nach dem Binden setzen: Socket selbst bleibt unverschlüsselt (siehe unten)
        self.tls = ctx

    def process_request_thread(self, request, client_address):
        try:
            request.settimeout(TIMEOUT)
            erstes = request.recv(1, socket.MSG_PEEK)
            if not erstes:
                self.shutdown_request(request)
                return
            if erstes != b"\x16":  # kein TLS-Handshake -> HTTP-Anfrage umleiten
                self._umleiten(request)
                return
            gesichert = self.tls.wrap_socket(request, server_side=True)
            gesichert.settimeout(TIMEOUT * 4)
        except (OSError, ssl.SSLError) as exc:
            log.debug("Verbindung von %s abgebrochen: %s", client_address, exc)
            self.shutdown_request(request)
            return
        super().process_request_thread(gesichert, client_address)

    def _umleiten(self, sock):
        try:
            daten = b""
            while b"\r\n\r\n" not in daten and len(daten) < 8192:
                teil = sock.recv(2048)
                if not teil:
                    break
                daten += teil
            zeilen = daten.decode("latin-1").split("\r\n")
            pfad = zeilen[0].split(" ")[1] if zeilen and len(zeilen[0].split(" ")) >= 2 else "/"
            if not pfad.startswith("/"):
                pfad = "/"
            host = next((z.split(":", 1)[1].strip() for z in zeilen[1:] if z.lower().startswith("host:")), "")
            if not host or any(c in host for c in " \r\n/\\"):
                host = "homeassistant.local"
            ziel = f"https://{host}{pfad}"
            antwort = (f"HTTP/1.1 301 Moved Permanently\r\nLocation: {ziel}\r\nContent-Length: 0\r\n"
                       f"Connection: close\r\n\r\n").encode("latin-1", "replace")
            sock.sendall(antwort)
        except OSError:
            pass
        finally:
            self.shutdown_request(sock)


def starte_https(app, host: str, port: int, ctx: ssl.SSLContext):
    server = HttpsServer(host, port, app, ctx)
    try:
        server.serve_forever()
    finally:
        server.server_close()
