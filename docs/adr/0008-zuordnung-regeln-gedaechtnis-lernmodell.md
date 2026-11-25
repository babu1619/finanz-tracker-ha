# ADR-0008: Automatische Zuordnung: Regeln, Gedächtnis, Lernmodell

- **Status:** angenommen
- **Datum:** 2026-10-11 (Version 0.1.0 / 0.2.0 / 0.5.0); nachträglich dokumentiert am 2026-11-25

## Kontext

Ohne Automatik muss jede Buchung von Hand kategorisiert werden. Die Automatik darf aber keine bewusst gesetzten
Zuordnungen kaputtmachen und muss nachvollziehbar bleiben.

## Entscheidung

- Drei Stufen, die erste passende gewinnt:
  1. Regeln mit Priorität, Bedingungen und Aktionen.
  2. Gedächtnis: häufigste bestätigte Kategorie derselben Gegenpartei; geprüft, wenn mindestens zwei Buchungen
     übereinstimmen.
  3. Lernmodell: Naive Bayes in reinem Python; ab 85 % gesetzt, aber ungeprüft, ab 50 % nur Vorschlag.
- Manuell zugeordnete Buchungen und Umbuchungen ändern Gedächtnis und Lernmodell nie.
- Regeln überschreiben manuelle Zuordnungen nur auf ausdrücklichen Wunsch beim Speichern (seit 0.5.0).
- Aufgeteilte Buchungen, verknüpfte Umbuchungen und automatische Gegenbuchungen sind immer geschützt.
- Die Trefferquote je Quelle wird gemessen (`zuordnung_feedback`).

## Alternativen

- Nur Regeln: zu viel Pflege.
- Externes Modell oder scikit-learn: schwere Abhängigkeit auf dem Green, Daten verlassen evtl. das Haus.

## Folgen

- Neue Buchungen landen sortiert im Prüf-Modus; Bestätigen trainiert Gedächtnis und Modell.
- Das Modell wird bei Bedarf in der Anfrage trainiert; bei sehr vielen Buchungen kann das spürbar werden.
