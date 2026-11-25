# ADR-0012: Kein FinTS vorerst

- **Status:** zurückgestellt
- **Datum:** 2026-10-12 (Version –); nachträglich dokumentiert am 2026-11-25

## Kontext

Ein direkter Kontoabruf würde den CSV-Export ersparen. FinTS verlangt eine Produktregistrierung bei der Deutschen
Kreditwirtschaft, PIN-Eingabe und eine pushTAN-Freigabe. Die Hanseatic-Kreditkarte geht ohnehin nicht über FinTS.

## Entscheidung

FinTS ist zurückgestellt. Der Wunsch bleibt mit Status „zurückgestellt“ in der Wunschliste. Wenn umgesetzt, gilt:
PIN nicht speichern, sondern beim Abruf eingeben; TAN-Freigabe in der Oberfläche; zuerst Sparkasse und GLS, die
UmweltBank prüfen.

## Alternativen

- Sofort umsetzen ohne Registrierung: nicht zulässig.
- Drittanbieter-Aggregatoren: Daten gehen an Dritte.

## Folgen

Import bleibt bei CSV, PDF und Screenshot.
