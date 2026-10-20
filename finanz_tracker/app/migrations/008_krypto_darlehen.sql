-- Version 0.7.0: Kontotyp „krypto“ mit Bestand und Kursverlauf, Sondertilgung in €, Anschlussfinanzierung.

-- Kontotyp erweitern: SQLite kann CHECK-Bedingungen nicht ändern, daher Tabelle neu aufbauen
-- (Fremdschlüssel sind während der Migration abgeschaltet; Verweise auf „konto“ bleiben gültig).
CREATE TABLE konto_neu (
    id                      INTEGER PRIMARY KEY,
    name                    TEXT NOT NULL,
    typ                     TEXT NOT NULL DEFAULT 'giro'
                            CHECK (typ IN ('giro','tagesgeld','kreditkarte','bargeld','depot','darlehen','krypto','sonstiges')),
    iban                    TEXT,
    institut                TEXT,
    eigentuemer_person_id   INTEGER REFERENCES person(id) ON DELETE SET NULL,
    sichtbarkeit            TEXT NOT NULL DEFAULT 'alle' CHECK (sichtbarkeit IN ('alle','privat')),
    startsaldo_cent         INTEGER NOT NULL DEFAULT 0,
    import_erinnerung_tage  INTEGER NOT NULL DEFAULT 7,
    aktiv                   INTEGER NOT NULL DEFAULT 1,
    sortierung              INTEGER NOT NULL DEFAULT 0
);
INSERT INTO konto_neu (id, name, typ, iban, institut, eigentuemer_person_id, sichtbarkeit, startsaldo_cent,
                       import_erinnerung_tage, aktiv, sortierung)
SELECT id, name, typ, iban, institut, eigentuemer_person_id, sichtbarkeit, startsaldo_cent,
       import_erinnerung_tage, aktiv, sortierung FROM konto;
DROP TABLE konto;
ALTER TABLE konto_neu RENAME TO konto;

CREATE TABLE krypto (
    konto_id        INTEGER PRIMARY KEY REFERENCES konto(id) ON DELETE CASCADE,
    coin            TEXT NOT NULL CHECK (coin IN ('bitcoin','ethereum')),
    menge           REAL NOT NULL DEFAULT 0,
    einstand_cent   INTEGER,                 -- optional: insgesamt bezahlt
    im_vermoegen    INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE krypto_kurs (
    coin        TEXT NOT NULL,
    datum       TEXT NOT NULL,               -- YYYY-MM-DD
    preis_cent  INTEGER NOT NULL,            -- Preis je Coin in Euro-Cent
    PRIMARY KEY (coin, datum)
);

ALTER TABLE darlehen ADD COLUMN sondertilgung_max_cent INTEGER;
ALTER TABLE darlehen ADD COLUMN anschluss_sollzins REAL;
ALTER TABLE darlehen ADD COLUMN anschluss_rate_cent INTEGER;
