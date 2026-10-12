-- Version 0.4.0: Depot ohne Kontoauszug – Rendite/Bewertung von Hand, Gegenbuchungen automatisch.
CREATE TABLE depot_bewertung (
    id          INTEGER PRIMARY KEY,
    konto_id    INTEGER NOT NULL REFERENCES konto(id) ON DELETE CASCADE,
    datum       TEXT NOT NULL,
    einheit     TEXT NOT NULL CHECK (einheit IN ('prozent', 'betrag')),
    wert        INTEGER NOT NULL,          -- Prozent in Hundertstel (12,5 % = 1250) oder Cent
    notiz       TEXT,
    erstellt    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_depot_bewertung_konto ON depot_bewertung(konto_id, datum);

-- Bereits vorgemerkte Umbuchungen ins/aus dem Depot nachträglich mit Gegenbuchung versehen (wie 004 fürs Barkonto)
INSERT INTO buchung (konto_id, buchungsdatum, betrag_cent, gegenpartei, verwendungszweck, partner_key, abrechnungsmonat,
                     kategorie_id, person_id, dedup_hash, zuordnung_quelle, geprueft, ist_umbuchung, umbuchung_partner_id,
                     umbuchung_konto_id, auto_gegenbuchung)
SELECT b.umbuchung_konto_id, b.buchungsdatum, -b.betrag_cent,
       CASE WHEN b.betrag_cent < 0 THEN 'Einzahlung von ' ELSE 'Auszahlung an ' END || k.name,
       'Automatisch aus Umbuchung', '', b.abrechnungsmonat, b.kategorie_id, b.person_id, 'gegen:' || b.id,
       'umbuchung', 1, 1, b.id, b.konto_id, 1
FROM buchung b JOIN konto k ON k.id = b.konto_id JOIN konto dep ON dep.id = b.umbuchung_konto_id
WHERE b.ist_umbuchung = 1 AND b.umbuchung_partner_id IS NULL AND dep.typ = 'depot'
  AND NOT EXISTS (SELECT 1 FROM buchung x WHERE x.dedup_hash = 'gegen:' || b.id);

UPDATE buchung SET umbuchung_partner_id = (SELECT g.id FROM buchung g WHERE g.dedup_hash = 'gegen:' || buchung.id
                                           AND g.auto_gegenbuchung = 1)
WHERE ist_umbuchung = 1 AND umbuchung_partner_id IS NULL
  AND EXISTS (SELECT 1 FROM buchung g WHERE g.dedup_hash = 'gegen:' || buchung.id AND g.auto_gegenbuchung = 1);
