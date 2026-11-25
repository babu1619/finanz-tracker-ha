# Offene Punkte

Stand 25.11.2026, Version 0.9.0.

## Zurückgestellte Wünsche

| Wunsch | Grund | Voraussetzung |
| --- | --- | --- |
| Direkter Kontoabruf per FinTS (Sparkasse, GLS, UmweltBank prüfen) | Braucht eine kostenlose Produktregistrierung bei der Deutschen Kreditwirtschaft, PIN-Eingabe beim Abruf und pushTAN-Freigabe in der Oberfläche ([ADR-0012](adr/0012-kein-fints-vorerst.md)) | Registrierung beantragt, Entscheidung für eine FinTS-Bibliothek mit passender Lizenz |
| CSV-Import der Darlehenskonten (offen seit 0.2.0, steht nicht in der Wunschliste) | Keine Beispieldatei der Bank vorhanden; bis dahin gelten Plan und von Hand erfasste Ereignisse | Beispiel-Export der Bank |

Die Hanseatic-Kreditkarte geht nicht per FinTS und bleibt beim PDF- bzw. Screenshot-Import.

## Bekannte Vereinfachungen

- **Nettovermögen im Verlauf:**
  - Krypto mit heutiger Menge; Käufe und Verkäufe sind nicht erfasst.
  - Depot mit der jeweils letzten Rendite-Eintragung.
  - Bausparen vor dem jüngsten Stand mit diesem Stand.
- **Bausparen:** keine Bewertungszahl; Zuteilung allein über das Mindestguthaben und den Wunschtermin.
- **Planung:** ohne Zinsen, Kursentwicklung und Inflation. Die Kontoauswahl ist je Benutzer, die Posten sind
  gemeinsam.
- **Krypto:** nur Bitcoin und Ethereum (CHECK in `krypto.coin`). Ein weiterer Coin braucht eine Migration mit
  Neuaufbau der Tabelle.
- **Login-Sperre:** liegt im Arbeitsspeicher und endet mit einem Neustart.
- **Löschen importierter Buchungen:** Danach stimmt der Saldoabgleich nicht mehr; das ist gewollt und wird angezeigt.
- **Sicherungskopien vor einer Wiederherstellung** (`/data/vor-wiederherstellung-*.db`) werden nie automatisch
  gelöscht.

## Weitere offene Punkte

1. **Keine Versions-Tags:** `tools/release.py` setzt Tags `vX.Y.Z`. Die bisherigen Versionen wurden ohne Tags
   gepusht.
2. **Commit-Historie:** Der erste Commit (`b4275dc`, „init“) ist einem fremden GitHub-Konto zugeordnet, weil eine
   Platzhalter-E-Mail verwendet wurde. Einige frühe Commits enthalten eine private E-Mail-Adresse. Eine Bereinigung
   der Historie (Neuschreiben und Force-Push) ist möglich, aber nicht entschieden.

Keine GitHub-Workflows zu haben, ist kein offener Punkt, sondern entschieden ([ADR-0026](adr/0026-keine-github-workflows.md)).

## Ideen für später

Aus Gesprächen, nicht in der Wunschliste:
- **Kopplung mit der Archiv-App** (Paperless-ngx + Begleitdienst):
  - Kategorien des Finanz-Trackers als `kat:`-Tags übernehmen.
  - Beleg und Buchung gegenseitig verlinken.
  - Kreditkartenabrechnungen an den PDF-Import weiterreichen.

  Der Finanz-Tracker speichert selbst keine Belege ([ADR-0017](adr/0017-keine-belege-im-finanz-tracker.md)).
- **Gemeinsamer Login** mit der Archiv-App.
