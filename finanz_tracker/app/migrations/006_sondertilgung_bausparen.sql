-- Version 0.5.0: Sondertilgungen als Buchung, Bausparverträge im Bereich Darlehen.

-- Sondertilgung: Buchung im Darlehenskonto (von Hand angelegt) und optional die Zahlung im Girokonto o. Ä.
ALTER TABLE darlehen_ereignis ADD COLUMN buchung_id INTEGER REFERENCES buchung(id) ON DELETE SET NULL;
ALTER TABLE darlehen_ereignis ADD COLUMN zahlung_buchung_id INTEGER REFERENCES buchung(id) ON DELETE SET NULL;

CREATE TABLE bausparvertrag (
    id                      INTEGER PRIMARY KEY,
    name                    TEXT NOT NULL,
    institut                TEXT,
    vertragsnummer          TEXT,
    bausparsumme_cent       INTEGER NOT NULL,
    beginn                  TEXT NOT NULL,              -- YYYY-MM (Vertragsbeginn)
    sparrate_cent           INTEGER NOT NULL DEFAULT 0, -- monatlich
    guthabenzins            REAL NOT NULL DEFAULT 0,    -- % p. a.
    darlehenszins           REAL,                       -- % p. a. des Bauspardarlehens
    tilgungsbeitrag_promille REAL,                      -- Monatsrate Zins+Tilgung in ‰ der Bausparsumme
    mindestguthaben_prozent REAL NOT NULL DEFAULT 40,   -- Mindestsparguthaben für die Zuteilung
    zuteilung_gewuenscht    TEXT,                       -- YYYY-MM, z. B. Ende der Zinsbindung
    darlehen_konto_id       INTEGER REFERENCES darlehen(konto_id) ON DELETE SET NULL,  -- löst dieses Darlehen ab
    immobilie_id            INTEGER REFERENCES immobilie(id) ON DELETE SET NULL,
    aktiv                   INTEGER NOT NULL DEFAULT 1,
    notiz                   TEXT
);

-- Guthabenstände laut Bausparkasse (Jahreskontoauszug); die Prognose rechnet vom jüngsten Stand aus weiter
CREATE TABLE bauspar_stand (
    id          INTEGER PRIMARY KEY,
    vertrag_id  INTEGER NOT NULL REFERENCES bausparvertrag(id) ON DELETE CASCADE,
    datum       TEXT NOT NULL,
    guthaben_cent INTEGER NOT NULL,
    notiz       TEXT
);
CREATE INDEX idx_bauspar_stand ON bauspar_stand(vertrag_id, datum);
