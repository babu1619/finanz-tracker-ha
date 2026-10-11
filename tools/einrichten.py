#!/usr/bin/env python3
"""Trägt einmalig deinen GitHub-Namen und den Repository-Namen in die Dateien ein.

Aufruf:  python tools/einrichten.py DEIN-GITHUB-NAME [REPOSITORY-NAME]
Beispiel: python tools/einrichten.py babu1619 finanz-tracker
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = ["repository.yaml", "README.md", "finanz_tracker/config.yaml", "finanz_tracker/DOCS.md"]

if len(sys.argv) < 2 or not re.fullmatch(r"[A-Za-z0-9-]{1,39}", sys.argv[1]):
    sys.exit(__doc__)
user = sys.argv[1]
repo = sys.argv[2] if len(sys.argv) > 2 else "finanz-tracker"
if not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", repo):
    sys.exit("Ungültiger Repository-Name.")

for name in FILES:
    path = ROOT / name
    if not path.exists():
        continue
    text = path.read_text(encoding="utf-8")
    new = (text.replace("DEIN-GITHUB-NAME/finanz-tracker", f"{user}/{repo}")
               .replace("ghcr.io/DEIN-GITHUB-NAME/", f"ghcr.io/{user.lower()}/")
               .replace("DEIN-GITHUB-NAME", user))
    if new != text:
        path.write_text(new, encoding="utf-8", newline="\n")
        print(f"angepasst: {name}")
print(f"Fertig. Repository-Adresse für Home Assistant: https://github.com/{user}/{repo}")
