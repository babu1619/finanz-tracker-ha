-- Version 0.3.1: Gegenbuchung im Barkonto wird bei einer Umbuchung automatisch angelegt.
ALTER TABLE buchung ADD COLUMN auto_gegenbuchung INTEGER NOT NULL DEFAULT 0;

-- Bereits vorgemerkte Umbuchungen ins/aus dem Barkonto nachträglich ergänzen
INSERT INTO buchung (konto_id, buchungsdatum, betrag_cent, gegenpartei, verwendungszweck, partner_key, abrechnungsmonat,
                     kategorie_id, person_id, dedup_hash, zuordnung_quelle, geprueft, ist_umbuchung, umbuchung_partner_id,
                     umbuchung_konto_id, auto_gegenbuchung)
SELECT b.umbuchung_konto_id, b.buchungsdatum, -b.betrag_cent,
       CASE WHEN b.betrag_cent < 0 THEN 'Abhebung ' ELSE 'Einzahlung ' END || k.name,
       'Automatisch aus Umbuchung', '', b.abrechnungsmonat, b.kategorie_id, b.person_id, 'gegen:' || b.id,
       'umbuchung', 1, 1, b.id, b.konto_id, 1
FROM buchung b JOIN konto k ON k.id = b.konto_id JOIN konto bar ON bar.id = b.umbuchung_konto_id
WHERE b.ist_umbuchung = 1 AND b.umbuchung_partner_id IS NULL AND bar.typ = 'bargeld';

UPDATE buchung SET umbuchung_partner_id = (SELECT g.id FROM buchung g WHERE g.dedup_hash = 'gegen:' || buchung.id
                                           AND g.auto_gegenbuchung = 1)
WHERE ist_umbuchung = 1 AND umbuchung_partner_id IS NULL
  AND EXISTS (SELECT 1 FROM buchung g WHERE g.dedup_hash = 'gegen:' || buchung.id AND g.auto_gegenbuchung = 1);
