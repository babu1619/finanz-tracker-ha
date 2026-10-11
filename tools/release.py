#!/usr/bin/env python3
"""Neue Version veröffentlichen: Versionsnummer erhöhen, Änderung notieren, prüfen, committen, hochladen.

Aufruf (im Repository-Ordner):
    python tools/release.py patch "Tippfehler im Budget-Formular behoben"
    python tools/release.py minor "PDF-Import für die Kreditkarte"
    python tools/release.py 0.3.0 "Text"          # Version direkt angeben
    python tools/release.py patch "Text" --ohne-push
    python tools/release.py patch "Text" --ohne-tests

patch = kleine Korrektur (0.2.1 → 0.2.2), minor = neue Funktion (0.2.2 → 0.3.0).
Home Assistant zeigt das Update an, sobald die neue Version auf GitHub liegt.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "finanz_tracker" / "config.yaml"
CHANGELOG = ROOT / "finanz_tracker" / "CHANGELOG.md"
APP_CONFIG = ROOT / "finanz_tracker" / "app" / "config.py"
MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober",
          "November", "Dezember"]


def git(*args, check=True):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    if check and r.returncode != 0:
        sys.exit(f"git {' '.join(args)} fehlgeschlagen:\n{r.stderr.strip() or r.stdout.strip()}")
    return r.stdout.strip()


def main():
    from datetime import date
    p = argparse.ArgumentParser(description="Neue Version des Finanz-Trackers veröffentlichen")
    p.add_argument("stufe", help="patch, minor, major oder eine Version wie 0.3.0")
    p.add_argument("text", help="kurze Beschreibung der Änderung")
    p.add_argument("--ohne-push", action="store_true", help="nur lokal committen, nicht hochladen")
    p.add_argument("--ohne-tests", action="store_true", help="nur Konfiguration prüfen, Tests überspringen")
    a = p.parse_args()

    text = CONFIG.read_text(encoding="utf-8")
    m = re.search(r'^version:\s*"?(\d+)\.(\d+)\.(\d+)"?\s*$', text, re.M)
    if not m:
        sys.exit("Version in finanz_tracker/config.yaml nicht gefunden.")
    major, minor, patch = map(int, m.groups())
    old = f"{major}.{minor}.{patch}"
    if a.stufe == "patch":
        new = f"{major}.{minor}.{patch + 1}"
    elif a.stufe == "minor":
        new = f"{major}.{minor + 1}.0"
    elif a.stufe == "major":
        new = f"{major + 1}.0.0"
    elif re.fullmatch(r"\d+\.\d+\.\d+", a.stufe):
        new = a.stufe
        if tuple(map(int, new.split("."))) <= (major, minor, patch):
            sys.exit(f"Die neue Version {new} muss höher sein als {old}.")
    else:
        sys.exit("Stufe muss patch, minor, major oder eine Version wie 0.3.0 sein.")

    if git("rev-parse", "--is-inside-work-tree", check=False) != "true":
        sys.exit("Dieser Ordner ist kein Git-Repository.")

    # Version in der App (Anzeige im Fuß, Protokoll, Cache-Schlüssel der installierten App) mitziehen
    c = APP_CONFIG.read_text(encoding="utf-8")
    log_alt = CHANGELOG.read_text(encoding="utf-8") if CHANGELOG.exists() else None
    c2 = re.sub(r'^VERSION = "[^"]+"', f'VERSION = "{new}"', c, count=1, flags=re.M)
    if c2 == c and f'VERSION = "{new}"' not in c:
        sys.exit("VERSION in finanz_tracker/app/config.py nicht gefunden.")
    APP_CONFIG.write_text(c2, encoding="utf-8", newline="\n")

    CONFIG.write_text(text[:m.start()] + f'version: "{new}"' + text[m.end():], encoding="utf-8", newline="\n")
    heute = date.today()
    log = CHANGELOG.read_text(encoding="utf-8") if CHANGELOG.exists() else "# Änderungen\n"
    head, _, rest = log.partition("\n## ")
    entry = f"## {new} – {MONATE[heute.month - 1]} {heute.year}\n\n- {a.text}\n"
    log = head.rstrip("\n") + "\n\n" + entry + ("\n## " + rest if rest else "")
    CHANGELOG.write_text(log, encoding="utf-8", newline="\n")

    cmd = [sys.executable, str(ROOT / "tools" / "pruefen.py")] + (["--ohne-tests"] if a.ohne_tests else [])
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode != 0:
        # Versionsnummer und Änderungsprotokoll zurücksetzen, damit derselbe Aufruf später wieder passt
        CONFIG.write_text(text, encoding="utf-8", newline="\n")
        APP_CONFIG.write_text(c, encoding="utf-8", newline="\n")
        if log_alt is not None:
            CHANGELOG.write_text(log_alt, encoding="utf-8", newline="\n")
        sys.exit(f"Prüfung fehlgeschlagen – nichts committet, Version bleibt {old}. "
                 "Fehler beheben und denselben Befehl erneut aufrufen.")

    git("add", "-A")
    git("commit", "-m", f"Version {new}: {a.text}")
    git("tag", "-a", f"v{new}", "-m", f"Version {new}")
    print(f"Version {old} → {new} committet (Tag v{new}).")
    if a.ohne_push:
        print("Hochladen später mit:  git push --follow-tags")
        return
    git("push", "--follow-tags")
    print("Hochgeladen. In Home Assistant: Einstellungen → Add-ons → Add-on Store → ⋮ → Nach Updates suchen.")


if __name__ == "__main__":
    main()
