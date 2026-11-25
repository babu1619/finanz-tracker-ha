# ADR-0014: HTTPS mit eigener Heim-CA, Zugriff von außen nur per VPN

- **Status:** angenommen
- **Datum:** 2026-10-11 (Version 0.2.0); nachträglich dokumentiert am 2026-11-25

## Kontext

Chrome auf Android installiert eine Seite nur bei vertrauenswürdigem HTTPS als App. Im Heimnetz gibt es keine
öffentliche Domain, und der Port soll nicht ins Internet.

## Entscheidung

- Das Add-on erzeugt eine eigene Zertifizierungsstelle (10 Jahre) und ein Serverzertifikat für die Adressen des
  Green und zusätzliche Namen (`zusatz_hostnamen`). Die CA wird einmal je Gerät installiert.
- Alternativ nutzt es ein Zertifikat aus `/ssl` (z. B. Let's Encrypt).
- Unverschlüsseltes HTTP auf demselben Port wird per 301 auf HTTPS umgeleitet.
- Schlägt die HTTPS-Einrichtung fehl, startet die App per HTTP, um erreichbar zu bleiben.
- Port 8099 wird nicht im Router freigegeben; Zugriff von unterwegs nur über VPN.

## Alternativen

- Selbstsigniertes Serverzertifikat ohne CA: bei jeder Erneuerung neue Warnung, keine PWA-Installation.
- Öffentliche Domain mit Let's Encrypt: braucht Domain und Freigabe; bleibt als Option.

## Folgen

- Einmaliger Aufwand je Gerät (CA installieren); Seite „App & Zertifikat“ mit Anleitung.
- Beim Zugriff über VPN müssen dessen Namen bzw. IPs im Zertifikat stehen.
