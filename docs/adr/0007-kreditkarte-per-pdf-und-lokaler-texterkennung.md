# ADR-0007: Kreditkarte per PDF und Screenshot mit lokaler Texterkennung

- **Status:** angenommen
- **Datum:** 2026-10-12 (Version 0.4.0 / 0.5.0); nachträglich dokumentiert am 2026-11-25

## Kontext

Die Hanseatic Bank liefert für die Kreditkarte weder CSV noch FinTS und sperrt seit 2026 Fremdanbieter-Anbindungen.
Es gibt nur die PDF-Abrechnung und die Banking-App. Finanzdaten sollen das Haus nicht verlassen.

## Entscheidung

- PDF-Abrechnungen werden mit `pdftotext` samt Wortpositionen gelesen; gescannte PDFs und Screenshots der App
  laufen durch Tesseract (Deutsch). Beides ist im Docker-Image installiert und läuft lokal.
- Die Erkennung arbeitet mit Wortpositionen statt fester Zeichenspalten.
- Vor dem Speichern prüft der Nutzer eine Tabelle; Duplikate (`ocr:`-Schlüssel) und ähnliche Buchungen werden
  markiert, vorgemerkte Umsätze sind nicht vorausgewählt.

## Alternativen

- Cloud-OCR oder ein Sprachmodell: Daten verlassen das Haus.
- Nur Abtippen: zu viel Handarbeit.

## Folgen

- Das Image ist größer (Tesseract, poppler).
- Die Erkennung ist auf die Hanseatic-Abrechnung und -App abgestimmt; andere Layouts brauchen Anpassungen in
  `services/abrechnung.py` bzw. `services/ocr.py`.
