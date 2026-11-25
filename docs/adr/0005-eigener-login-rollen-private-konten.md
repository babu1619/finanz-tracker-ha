# ADR-0005: Eigener Login, Rollen, Personen und private Konten

- **Status:** angenommen
- **Datum:** 2026-10-10 (Version 0.1.0); nachträglich dokumentiert am 2026-11-25

## Kontext

Mehrere Familienmitglieder nutzen die App, Kinder ohne eigenen Zugang. Manche Konten sollen privat bleiben.

## Entscheidung

- Eigene Benutzer mit scrypt-Passwort, Sperre nach 5 Fehlversuchen für 15 Minuten, Sitzung 30 Tage.
- Rollen: `admin` (alles), `mitglied` (lesen und schreiben), `lesend`.
- Personen sind getrennt von Benutzern; Buchungen, Budgets und Rücklagen werden Personen zugeordnet.
- Konten sind `alle` (gemeinsam) oder `privat` mit Eigentümer-Person. Nicht-Admins sehen private Konten anderer
  nicht, auch nicht in Summen. Alle Abfragen laufen über `auth.sichtbare_konten()`.
- CSRF-Token bei jedem POST.

## Alternativen

- Anmeldung über Home Assistant: alle bräuchten Home-Assistant-Konten (ADR-0001).
- Ein gemeinsames Passwort: keine Zuordnung, keine privaten Konten.

## Folgen

- Admins sehen alles; das ist gewollt (Familienverwaltung).
- Neue Seiten müssen die Sichtbarkeit selbst beachten; Kennzahlen nutzen `statistik.basis_konten()`.
- Notfall-Zugang über die Add-on-Option `admin_passwort_reset`.
