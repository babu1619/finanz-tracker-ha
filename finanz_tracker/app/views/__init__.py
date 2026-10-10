"""Hilfen für alle Views."""
from flask import flash, request

from ..util import ist_monat, aktueller_monat


def melde(text, art="ok"):
    flash(text, art)


def monat_param(name="monat"):
    m = request.args.get(name) or request.form.get(name)
    return m if ist_monat(m) else aktueller_monat()


def int_oder_none(wert):
    try:
        return int(wert) if wert not in (None, "", "None") else None
    except (TypeError, ValueError):
        return None
