-- Version 0.6.0: Verträge als eigene Datensätze (Laufzeit, Kündigungsfrist, Rhythmus), Buchungen zu Verträgen und
-- Darlehen zuordnen, gespeicherte Auswertungs-Ansichten.

ALTER TABLE vertrag RENAME TO vertrag_alt;

CREATE TABLE vertrag (
    id                      INTEGER PRIMARY KEY,
    name                    TEXT NOT NULL,
    art                     TEXT NOT NULL DEFAULT 'vertrag' CHECK (art IN ('abo','fix','vertrag','ignoriert')),
    anbieter                TEXT,
    vertragsnummer          TEXT,
    partner_key             TEXT,                       -- Gegenpartei für die automatische Zuordnung
    kategorie_id            INTEGER REFERENCES kategorie(id) ON DELETE SET NULL,
    konto_id                INTEGER REFERENCES konto(id) ON DELETE SET NULL,
    betrag_cent             INTEGER,                    -- erwarteter Betrag je Zahlung (positiv)
    rhythmus_monate         INTEGER NOT NULL DEFAULT 1, -- 1, 2, 3, 4, 6, 12, 24 … ; 0 = unregelmäßig
    beginn                  TEXT,                       -- Vertragsbeginn (YYYY-MM-DD)
    laufzeit_ende           TEXT,                       -- Ende der (ersten) Laufzeit
    verlaengerung_monate    INTEGER,                    -- automatische Verlängerung; NULL/0 = endet
    kuendigungsfrist        INTEGER,                    -- Anzahl …
    kuendigungsfrist_einheit TEXT NOT NULL DEFAULT 'monate' CHECK (kuendigungsfrist_einheit IN ('tage','wochen','monate')),
    gekuendigt_zum          TEXT,
    notiz                   TEXT,
    aktiv                   INTEGER NOT NULL DEFAULT 1,
    erstellt                TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX idx_vertrag_partner ON vertrag(partner_key);

-- Bisherige Markierungen (Abo/Fix/ausgeblendet je Gegenpartei) übernehmen
INSERT INTO vertrag (name, art, partner_key, notiz, kategorie_id, betrag_cent)
SELECT COALESCE(a.name, (SELECT b.gegenpartei FROM buchung b WHERE b.partner_key = a.partner_key
                         ORDER BY b.buchungsdatum DESC LIMIT 1), a.partner_key),
       a.art, a.partner_key, a.notiz,
       (SELECT b.kategorie_id FROM buchung b WHERE b.partner_key = a.partner_key AND b.kategorie_id IS NOT NULL
        ORDER BY b.buchungsdatum DESC LIMIT 1),
       (SELECT -b.betrag_cent FROM buchung b WHERE b.partner_key = a.partner_key AND b.betrag_cent < 0
        ORDER BY b.buchungsdatum DESC LIMIT 1)
FROM vertrag_alt a;
DROP TABLE vertrag_alt;

ALTER TABLE buchung ADD COLUMN vertrag_id INTEGER REFERENCES vertrag(id) ON DELETE SET NULL;
ALTER TABLE buchung ADD COLUMN darlehen_konto_id INTEGER REFERENCES konto(id) ON DELETE SET NULL;
CREATE INDEX idx_buchung_vertrag ON buchung(vertrag_id);
CREATE INDEX idx_buchung_darlehen ON buchung(darlehen_konto_id);

UPDATE buchung SET vertrag_id = (SELECT v.id FROM vertrag v WHERE v.partner_key = buchung.partner_key
                                 AND v.art != 'ignoriert' ORDER BY v.id LIMIT 1)
WHERE betrag_cent < 0 AND ist_umbuchung = 0 AND partner_key != ''
  AND EXISTS (SELECT 1 FROM vertrag v WHERE v.partner_key = buchung.partner_key AND v.art != 'ignoriert');

-- Rhythmus der übernommenen Verträge aus dem Abstand der letzten Zahlungen schätzen (sonst monatlich)
UPDATE vertrag SET rhythmus_monate = (
    SELECT CASE WHEN d BETWEEN 300 AND 430 THEN 12 WHEN d BETWEEN 150 AND 215 THEN 6
                WHEN d BETWEEN 75 AND 110 THEN 3 ELSE 1 END
    FROM (SELECT julianday(MAX(b.buchungsdatum)) - julianday((SELECT b2.buchungsdatum FROM buchung b2
                 WHERE b2.vertrag_id = vertrag.id ORDER BY b2.buchungsdatum DESC LIMIT 1 OFFSET 1)) AS d
          FROM buchung b WHERE b.vertrag_id = vertrag.id))
WHERE EXISTS (SELECT 1 FROM buchung b WHERE b.vertrag_id = vertrag.id);
UPDATE vertrag SET rhythmus_monate = 1 WHERE rhythmus_monate IS NULL;

CREATE TABLE auswertung_ansicht (
    id          INTEGER PRIMARY KEY,
    benutzer_id INTEGER REFERENCES benutzer(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    sortierung  INTEGER NOT NULL DEFAULT 0,
    diagramme   TEXT NOT NULL DEFAULT '[]',     -- JSON-Liste der Diagramm-Einstellungen
    erstellt    TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
