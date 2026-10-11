"""HTTPS: eigene Zertifizierungsstelle (CA) + Serverzertifikat oder Zertifikat von Home Assistant (/ssl).

Eigene CA: Einmal auf Handy/PC installieren, danach vertraut der Browser dem Tool dauerhaft – auch wenn das
Serverzertifikat erneuert wird oder neue Hostnamen/IPs hinzukommen. Das ist die Voraussetzung dafür, dass
Chrome auf Android die Seite als App (PWA) installieren kann.
"""
import datetime as dt
import ipaddress
import json
import logging
import os
import socket
import ssl
import urllib.request
from pathlib import Path

from . import config

log = logging.getLogger(__name__)

TLS_DIR = config.DATA_DIR / "tls"
CA_KEY, CA_CRT = TLS_DIR / "ca.key", TLS_DIR / "ca.crt"
SRV_KEY, SRV_CRT = TLS_DIR / "server.key", TLS_DIR / "server.crt"
STANDARD_HOSTS = ["homeassistant.local", "homeassistant", "localhost", "127.0.0.1", "::1"]
SERVER_TAGE = 825
ERNEUERN_TAGE = 60


def optionen() -> dict:
    """Add-on-Optionen (/data/options.json) mit Standardwerten."""
    o = {"https": True, "zertifikat": "eigenes", "zusatz_hostnamen": "", "certfile": "fullchain.pem",
         "keyfile": "privkey.pem"}
    pfad = config.DATA_DIR / "options.json"
    if pfad.exists():
        try:
            o.update({k: v for k, v in (json.loads(pfad.read_text()) or {}).items() if v is not None})
        except (OSError, ValueError):
            pass
    if os.environ.get("HTTPS") in ("0", "1"):  # für lokale Entwicklung
        o["https"] = os.environ["HTTPS"] == "1"
    return o


def _supervisor_ips() -> list[str]:
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        return []
    try:
        req = urllib.request.Request("http://supervisor/network/info", headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=4) as r:
            daten = json.loads(r.read().decode()).get("data", {})
    except Exception as exc:  # noqa: BLE001 – Netzwerkinfo ist nur ein Bonus
        log.info("Netzwerkinfo vom Supervisor nicht verfügbar: %s", exc)
        return []
    ips = []
    for iface in daten.get("interfaces", []):
        for fam in ("ipv4", "ipv6"):
            for adr in (iface.get(fam) or {}).get("address", []) or []:
                ip = adr.split("/")[0]
                try:
                    if not ipaddress.ip_address(ip).is_link_local:
                        ips.append(ip)
                except ValueError:
                    pass
    host = None
    try:
        req = urllib.request.Request("http://supervisor/host/info", headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=4) as r:
            host = json.loads(r.read().decode()).get("data", {}).get("hostname")
    except Exception:  # noqa: BLE001
        pass
    if host:
        ips += [host, f"{host}.local"]
    return ips


def gewuenschte_namen(opt: dict | None = None) -> list[str]:
    opt = opt or optionen()
    namen = list(STANDARD_HOSTS)
    namen += _supervisor_ips()
    namen += [h.strip() for h in str(opt.get("zusatz_hostnamen") or "").replace(";", ",").split(",") if h.strip()]
    try:
        namen.append(socket.gethostname())
    except OSError:
        pass
    erg = []
    for n in namen:
        n = n.strip().lower()
        if n and n not in erg:
            erg.append(n)
    return erg


def _ist_ip(n: str) -> bool:
    try:
        ipaddress.ip_address(n)
        return True
    except ValueError:
        return False


def _schreibe(pfad: Path, daten: bytes, geheim=False):
    pfad.write_bytes(daten)
    if geheim:
        try:
            pfad.chmod(0o600)
        except OSError:
            pass


def erzeuge_ca():
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID
    TLS_DIR.mkdir(parents=True, exist_ok=True)
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Finanz-Tracker Heim-CA"),
                      x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Finanz-Tracker")])
    jetzt = dt.datetime.now(dt.timezone.utc)
    ski = x509.SubjectKeyIdentifier.from_public_key(key.public_key())
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(jetzt - dt.timedelta(days=1)).not_valid_after(jetzt + dt.timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=True, key_cert_sign=True, crl_sign=True, content_commitment=False,
                                         key_encipherment=False, data_encipherment=False, key_agreement=False,
                                         encipher_only=False, decipher_only=False), critical=True)
            .add_extension(ski, critical=False)
            .sign(key, hashes.SHA256()))
    _schreibe(CA_KEY, key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                        serialization.NoEncryption()), geheim=True)
    _schreibe(CA_CRT, cert.public_bytes(serialization.Encoding.PEM))
    log.info("Neue Heim-CA erzeugt (gültig 10 Jahre).")


def erzeuge_server(namen: list[str]):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
    ca_key = serialization.load_pem_private_key(CA_KEY.read_bytes(), None)
    ca = x509.load_pem_x509_certificate(CA_CRT.read_bytes())
    key = ec.generate_private_key(ec.SECP256R1())
    san = [x509.IPAddress(ipaddress.ip_address(n)) if _ist_ip(n) else x509.DNSName(n) for n in namen]
    jetzt = dt.datetime.now(dt.timezone.utc)
    cert = (x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, namen[0])]))
            .issuer_name(ca.subject).public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(jetzt - dt.timedelta(days=1)).not_valid_after(jetzt + dt.timedelta(days=SERVER_TAGE))
            .add_extension(x509.SubjectAlternativeName(san), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=True, key_cert_sign=False, crl_sign=False, content_commitment=False,
                                         key_encipherment=False, data_encipherment=False, key_agreement=False,
                                         encipher_only=False, decipher_only=False), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
            .sign(ca_key, hashes.SHA256()))
    _schreibe(SRV_KEY, key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                         serialization.NoEncryption()), geheim=True)
    _schreibe(SRV_CRT, cert.public_bytes(serialization.Encoding.PEM) + CA_CRT.read_bytes())
    log.info("Serverzertifikat erzeugt für: %s", ", ".join(namen))


def _server_ok(namen: list[str]) -> bool:
    from cryptography import x509
    if not SRV_CRT.exists() or not SRV_KEY.exists():
        return False
    try:
        cert = x509.load_pem_x509_certificate(SRV_CRT.read_bytes())
        ca = x509.load_pem_x509_certificate(CA_CRT.read_bytes())
    except ValueError:
        return False
    if cert.issuer != ca.subject:
        return False
    rest = cert.not_valid_after_utc - dt.datetime.now(dt.timezone.utc)
    if rest < dt.timedelta(days=ERNEUERN_TAGE):
        return False
    san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    vorhanden = {str(v).lower() for v in san.get_values_for_type(x509.DNSName)}
    vorhanden |= {str(v) for v in san.get_values_for_type(x509.IPAddress)}
    return all((str(ipaddress.ip_address(n)) if _ist_ip(n) else n) in vorhanden for n in namen)


def bereite_vor() -> dict | None:
    """Stellt Zertifikat und Schlüssel bereit. Rückgabe: {"cert", "key", "quelle"} oder None (HTTP)."""
    opt = optionen()
    if not opt.get("https", True):
        log.info("HTTPS ist in den Add-on-Optionen ausgeschaltet.")
        return None
    if opt.get("zertifikat") == "homeassistant":
        cert = Path("/ssl") / str(opt.get("certfile") or "fullchain.pem")
        key = Path("/ssl") / str(opt.get("keyfile") or "privkey.pem")
        if cert.exists() and key.exists():
            return {"cert": cert, "key": key, "quelle": "homeassistant"}
        log.error("Zertifikat von Home Assistant nicht gefunden (%s / %s) – nutze eigenes Zertifikat.", cert, key)
    if not (CA_KEY.exists() and CA_CRT.exists()):
        erzeuge_ca()
    namen = gewuenschte_namen(opt)
    if not _server_ok(namen):
        erzeuge_server(namen)
    return {"cert": SRV_CRT, "key": SRV_KEY, "quelle": "eigenes"}


def ssl_kontext(tls: dict) -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(str(tls["cert"]), str(tls["key"]))
    ctx.set_alpn_protocols(["http/1.1"])
    return ctx


def ca_info() -> dict | None:
    """Für die Zertifikat-Seite: Fingerabdruck, Gültigkeit, Namen."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    if not CA_CRT.exists():
        return None
    ca = x509.load_pem_x509_certificate(CA_CRT.read_bytes())
    info = {"fingerprint": ca.fingerprint(hashes.SHA256()).hex(":").upper(), "bis": ca.not_valid_after_utc.date(),
            "name": ca.subject.rfc4514_string(), "server_namen": [], "server_bis": None}
    if SRV_CRT.exists():
        srv = x509.load_pem_x509_certificate(SRV_CRT.read_bytes())
        san = srv.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        info["server_namen"] = [str(v) for v in san.get_values_for_type(x509.DNSName)] + \
                               [str(v) for v in san.get_values_for_type(x509.IPAddress)]
        info["server_bis"] = srv.not_valid_after_utc.date()
    return info


def ca_der() -> bytes:
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization
    return x509.load_pem_x509_certificate(CA_CRT.read_bytes()).public_bytes(serialization.Encoding.DER)
