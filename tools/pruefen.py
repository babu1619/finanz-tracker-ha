#!/usr/bin/env python3
"""Prüft das Repository vor dem Hochladen (läuft auch automatisch auf GitHub).

Aufruf:  python tools/pruefen.py            # Konfiguration prüfen und Tests ausführen
         python tools/pruefen.py --ohne-tests
"""
import py_compile
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "finanz_tracker"
errors, warnings = [], []


def err(msg):
    errors.append(msg)


def warn(msg):
    warnings.append(msg)


try:
    import yaml
except ImportError:
    sys.exit("Bitte zuerst installieren:  python -m pip install pyyaml")


def load(path):
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        err(f"{path.relative_to(ROOT)} fehlt")
    except yaml.YAMLError as e:
        err(f"{path.relative_to(ROOT)} ist kein gültiges YAML: {e}")
    return None


# ---- repository.yaml
repo = load(ROOT / "repository.yaml")
if repo is not None and not repo.get("name"):
    err("repository.yaml: 'name' fehlt")

# ---- config.yaml
cfg = load(APP / "config.yaml") or {}
for key in ("name", "version", "slug", "description", "arch"):
    if not cfg.get(key):
        err(f"config.yaml: '{key}' fehlt")
version = str(cfg.get("version", ""))
if not isinstance(cfg.get("version"), str):
    err('config.yaml: version muss in Anführungszeichen stehen, z. B. version: "0.2.1"')
if not re.fullmatch(r"\d+\.\d+\.\d+", version):
    err(f"config.yaml: Version '{version}' hat nicht die Form 1.2.3")
if cfg.get("slug") != "finanz_tracker":
    err("config.yaml: slug muss 'finanz_tracker' bleiben, sonst sieht Home Assistant eine neue App ohne Daten")
for arch in cfg.get("arch") or []:
    if arch not in ("aarch64", "amd64"):
        err(f"config.yaml: unbekannte Architektur '{arch}'")
options, schema = cfg.get("options") or {}, cfg.get("schema") or {}
fehlend = set(options) - set(schema)
if fehlend:
    err(f"config.yaml: options ohne schema: {sorted(fehlend)}")
for key, typ in schema.items():
    if key not in options and not str(typ).endswith("?"):
        err(f"config.yaml: schema '{key}' ist Pflicht (ohne ?), hat aber keinen Standardwert in options")
if "DEIN-GITHUB-NAME" in (APP / "config.yaml").read_text(encoding="utf-8"):
    warn("config.yaml enthält noch den Platzhalter DEIN-GITHUB-NAME (python tools/einrichten.py NAME)")
if cfg.get("image") and "{arch}" not in str(cfg["image"]):
    err("config.yaml: image muss den Platzhalter {arch} enthalten")
build = load(APP / "build.yaml") or {}
for arch in cfg.get("arch") or []:
    if arch not in (build.get("build_from") or {}):
        err(f"build.yaml: kein Basis-Image für '{arch}'")

# ---- Übersetzungen
for lang in ("de", "en"):
    tr = load(APP / "translations" / f"{lang}.yaml") or {}
    missing = set(schema) - set((tr.get("configuration") or {}).keys())
    if missing:
        err(f"translations/{lang}.yaml: Beschreibung fehlt für {sorted(missing)}")

# ---- Dateien
for name in ("Dockerfile", "requirements.txt", "DOCS.md", "CHANGELOG.md", "icon.png", "logo.png",
             "app/__init__.py", "app/__main__.py", "app/config.py"):
    if not (APP / name).exists():
        err(f"finanz_tracker/{name} fehlt")
dockerfile = (APP / "Dockerfile").read_text(encoding="utf-8") if (APP / "Dockerfile").exists() else ""
if dockerfile and "COPY app" not in dockerfile:
    err("Dockerfile: 'COPY app' fehlt")

# ---- Python-Code kompilierbar
for py in sorted((APP / "app").rglob("*.py")):
    try:
        py_compile.compile(str(py), doraise=True, cfile=str(ROOT / ".pruefen.pyc"))
    except py_compile.PyCompileError as e:
        err(f"{py.relative_to(ROOT)} enthält einen Fehler: {e.msg}")
(ROOT / ".pruefen.pyc").unlink(missing_ok=True)

# ---- Migrationen: lückenlos nummeriert
nummern = sorted(int(p.name.split("_", 1)[0]) for p in (APP / "app" / "migrations").glob("*.sql"))
if nummern != list(range(1, len(nummern) + 1)):
    err(f"Migrationen nicht lückenlos nummeriert: {nummern}")

# ---- Versionen stimmen überein
cfg_py = APP / "app" / "config.py"
if cfg_py.exists():
    m = re.search(r'^VERSION = "([^"]+)"', cfg_py.read_text(encoding="utf-8"), re.M)
    if not m:
        err("app/config.py: VERSION nicht gefunden")
    elif m.group(1) != version:
        err(f"Version in app/config.py ({m.group(1)}) und config.yaml ({version}) unterschiedlich")

# ---- Änderungsprotokoll
changelog = APP / "CHANGELOG.md"
if changelog.exists() and not re.search(rf"^## {re.escape(version)}\b", changelog.read_text(encoding="utf-8"), re.M):
    warn(f"CHANGELOG.md enthält keinen Abschnitt '## {version}'")

for w in warnings:
    print(f"Hinweis: {w}")
for e in errors:
    print(f"FEHLER:  {e}")
if errors:
    sys.exit(1)
print(f"Konfiguration in Ordnung: Finanz-Tracker {version}")

# ---- Automatische Tests
if "--ohne-tests" not in sys.argv:
    try:
        import flask  # noqa: F401
    except ImportError:
        sys.exit("Für die Tests bitte installieren:  python -m pip install -r finanz_tracker/requirements.txt")
    print("Starte Tests …")
    r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], cwd=APP)
    if r.returncode != 0:
        sys.exit("FEHLER:  Tests fehlgeschlagen")
    print("Tests in Ordnung.")
