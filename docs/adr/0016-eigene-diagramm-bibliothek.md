# ADR-0016: Eigene SVG-Diagramm-Bibliothek

- **Status:** angenommen
- **Datum:** 2026-10-15 (Version 0.6.0); nachträglich dokumentiert am 2026-11-25

## Kontext

Für die eigenen Auswertungen und später das Dashboard wurden viele Diagrammarten gebraucht. Die App soll ohne
Internet laufen; in der Entwicklungsumgebung waren npm-Downloads gesperrt.

## Entscheidung

`static/diagramme.js` zeichnet alle Diagramme selbst als SVG:
- Säulen, gestapelt, Balken, Linie, Fläche
- Ring, Torte, Tabelle, Kennzahl, Wärmekarte
- seit 0.8.0 Sankey und Mini-Verläufe

Dazu Tooltip, Klickziele und Legende. Schnittstelle: `window.Diagramme.zeichne(box, daten, typ, optionen)`.

## Alternativen

- Chart.js, ECharts oder D3 über CDN: Internet nötig, fremde Abhängigkeit.
- Bibliothek mitliefern: Download in der Umgebung nicht möglich, Lizenz und Größe prüfen.

## Folgen

- Volle Kontrolle über Aussehen und Dunkelmodus (Farben über CSS-Klassen).
- Neue Diagrammarten müssen selbst gebaut werden.
