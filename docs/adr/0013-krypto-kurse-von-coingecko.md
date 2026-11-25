# ADR-0013: Krypto-Kurse von CoinGecko, nächtlicher Abruf

- **Status:** angenommen
- **Datum:** 2026-10-20 (Version 0.7.0 / 0.9.0); nachträglich dokumentiert am 2026-11-25

## Kontext

Die Familie hält Bitcoin und Ethereum und will Bestand und Verlauf sehen. Kurse brauchen eine Quelle im Internet; die
App soll sonst nichts nach außen schicken.

## Entscheidung

- Kurse in Euro von der öffentlichen CoinGecko-API ohne Schlüssel. Übertragen wird nur, welche Coins abgefragt
  werden.
- Ein Kurs je Tag in `krypto_kurs`. Abruf jede Nacht ab 4 Uhr durch einen Hintergrund-Thread und auf Knopfdruck;
  nach Fehlschlag frühestens 30 Minuten später.
- Nur Bitcoin und Ethereum. Je Bestand wählbar, ob er zum Vermögen zählt.
- Seit 0.9.0 Verlauf des Gesamtwerts aller Bestände; fehlende Tageskurse werden vom Vortag übernommen.

## Alternativen

- Kurse von Hand: veraltet schnell.
- Börsen-API mit Konto: Schlüssel und Konto nötig.

## Folgen

- Einzige Internetverbindung der App; ohne Netz bleiben die letzten Kurse stehen.
- Ein weiterer Coin braucht eine Migration (CHECK auf `krypto.coin`).
