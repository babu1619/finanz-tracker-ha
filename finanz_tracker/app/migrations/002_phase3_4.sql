-- Version 0.2.0: Splits, Verteilung, Tags, Budgets, Rücklagen/Sparziele, Darlehen, Verträge, Lernmodell.
-- Läuft mit foreign_keys = OFF (siehe db.migrate), daher ist der Neuaufbau von 'buchung' gefahrlos.

CREATE TABLE ruecklage (
    id                  INTEGER PRIMARY KEY,
    name                TEXT NOT NULL,
    traeger_konto_id    INTEGER NOT NULL REFERENCES konto(id) ON DELETE CASCADE,
    bezug               TEXT NOT NULL DEFAULT 'topf' CHECK (bezug IN ('topf','konto')),
    ziel_cent           INTEGER,
    zufuehrung_cent     INTEGER NOT NULL DEFAULT 0,
    zieldatum           TEXT,                       -- YYYY-MM; gesetzt = Sparziel
    kategorie_id        INTEGER REFERENCES kategorie(id) ON DELETE SET NULL,
    person_id           INTEGER REFERENCES person(id) ON DELETE SET NULL,
    start_monat         TEXT NOT NULL,              -- ab hier laufen die monatlichen Zuführungen
    aktiv               INTEGER NOT NULL DEFAULT 1,
    sortierung          INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE ruecklage_bewegung (
    id              INTEGER PRIMARY KEY,
    ruecklage_id    INTEGER NOT NULL REFERENCES ruecklage(id) ON DELETE CASCADE,
    datum           TEXT NOT NULL,
    monat           TEXT NOT NULL,
    betrag_cent     INTEGER NOT NULL,              -- + Zuführung, − Entnahme
    art             TEXT NOT NULL CHECK (art IN ('zufuehrung','entnahme','korrektur')),
    buchung_id      INTEGER REFERENCES buchung(id) ON DELETE SET NULL,
    notiz           TEXT
);
CREATE INDEX ix_rbew_ruecklage ON ruecklage_bewegung(ruecklage_id);

-- buchung neu aufbauen: neue Spalten und Zuordnungsquelle 'modell'
CREATE TABLE buchung_neu (
    id                      INTEGER PRIMARY KEY,
    konto_id                INTEGER NOT NULL REFERENCES konto(id) ON DELETE CASCADE,
    buchungsdatum           TEXT NOT NULL,
    valuta                  TEXT,
    betrag_cent             INTEGER NOT NULL,
    gegenpartei             TEXT NOT NULL DEFAULT '',
    gegen_iban              TEXT,
    verwendungszweck        TEXT NOT NULL DEFAULT '',
    partner_key             TEXT NOT NULL DEFAULT '',
    abrechnungsmonat        TEXT NOT NULL,
    verteilung_monate       INTEGER NOT NULL DEFAULT 1 CHECK (verteilung_monate BETWEEN 1 AND 60),
    kategorie_id            INTEGER REFERENCES kategorie(id) ON DELETE SET NULL,
    person_id               INTEGER REFERENCES person(id) ON DELETE SET NULL,
    notiz                   TEXT,
    saldo_cent              INTEGER,
    rohdaten                TEXT,
    dedup_hash              TEXT NOT NULL,
    importlauf_id           INTEGER REFERENCES importlauf(id) ON DELETE SET NULL,
    zuordnung_quelle        TEXT CHECK (zuordnung_quelle IN ('regel','gedaechtnis','modell','manuell','umbuchung')),
    regel_id                INTEGER REFERENCES regel(id) ON DELETE SET NULL,
    konfidenz               REAL,
    vorschlag_kategorie_id  INTEGER REFERENCES kategorie(id) ON DELETE SET NULL,
    geprueft                INTEGER NOT NULL DEFAULT 0,
    ist_umbuchung           INTEGER NOT NULL DEFAULT 0,
    umbuchung_partner_id    INTEGER REFERENCES buchung(id) ON DELETE SET NULL,
    ruecklage_id            INTEGER REFERENCES ruecklage(id) ON DELETE SET NULL,
    manuell_erfasst         INTEGER NOT NULL DEFAULT 0,
    erstellt                TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE (konto_id, dedup_hash)
);
INSERT INTO buchung_neu (id, konto_id, buchungsdatum, valuta, betrag_cent, gegenpartei, gegen_iban, verwendungszweck,
    partner_key, abrechnungsmonat, kategorie_id, person_id, notiz, saldo_cent, rohdaten, dedup_hash, importlauf_id,
    zuordnung_quelle, regel_id, geprueft, ist_umbuchung, umbuchung_partner_id, erstellt)
SELECT id, konto_id, buchungsdatum, valuta, betrag_cent, gegenpartei, gegen_iban, verwendungszweck,
    partner_key, abrechnungsmonat, kategorie_id, person_id, notiz, saldo_cent, rohdaten, dedup_hash, importlauf_id,
    zuordnung_quelle, regel_id, geprueft, ist_umbuchung, umbuchung_partner_id, erstellt FROM buchung;
DROP TABLE buchung;
ALTER TABLE buchung_neu RENAME TO buchung;
CREATE INDEX ix_buchung_monat ON buchung(abrechnungsmonat);
CREATE INDEX ix_buchung_datum ON buchung(buchungsdatum);
CREATE INDEX ix_buchung_kategorie ON buchung(kategorie_id);
CREATE INDEX ix_buchung_partner ON buchung(partner_key);
CREATE INDEX ix_buchung_import ON buchung(importlauf_id);
CREATE INDEX ix_buchung_konto ON buchung(konto_id);

CREATE TABLE buchung_split (
    id              INTEGER PRIMARY KEY,
    buchung_id      INTEGER NOT NULL REFERENCES buchung(id) ON DELETE CASCADE,
    betrag_cent     INTEGER NOT NULL,
    kategorie_id    INTEGER REFERENCES kategorie(id) ON DELETE SET NULL,
    person_id       INTEGER REFERENCES person(id) ON DELETE SET NULL,
    notiz           TEXT
);
CREATE INDEX ix_split_buchung ON buchung_split(buchung_id);

CREATE TABLE tag (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE COLLATE NOCASE,
    farbe       TEXT,
    start       TEXT,           -- YYYY-MM-DD, optional (z. B. Reise)
    ende        TEXT,
    budget_cent INTEGER,
    notiz       TEXT
);

CREATE TABLE buchung_tag (
    buchung_id  INTEGER NOT NULL REFERENCES buchung(id) ON DELETE CASCADE,
    tag_id      INTEGER NOT NULL REFERENCES tag(id) ON DELETE CASCADE,
    PRIMARY KEY (buchung_id, tag_id)
);

CREATE TABLE budget (
    id              INTEGER PRIMARY KEY,
    kategorie_id    INTEGER NOT NULL REFERENCES kategorie(id) ON DELETE CASCADE,
    person_id       INTEGER REFERENCES person(id) ON DELETE SET NULL,
    betrag_cent     INTEGER NOT NULL,
    rhythmus        TEXT NOT NULL DEFAULT 'monat' CHECK (rhythmus IN ('monat','jahr')),
    gueltig_ab      TEXT NOT NULL,      -- YYYY-MM
    uebertrag       INTEGER NOT NULL DEFAULT 0,
    warnschwelle    INTEGER NOT NULL DEFAULT 90,
    aktiv           INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX ix_budget_kat ON budget(kategorie_id);

CREATE TABLE immobilie (
    id              INTEGER PRIMARY KEY,
    name            TEXT NOT NULL,
    kaufpreis_cent  INTEGER,
    kaufdatum       TEXT,
    wert_cent       INTEGER,
    wert_datum      TEXT
);

CREATE TABLE darlehen (
    konto_id                INTEGER PRIMARY KEY REFERENCES konto(id) ON DELETE CASCADE,
    immobilie_id            INTEGER REFERENCES immobilie(id) ON DELETE SET NULL,
    ursprung_cent           INTEGER NOT NULL,
    sollzins                REAL NOT NULL,          -- Prozent p. a., z. B. 1.45
    rate_cent               INTEGER NOT NULL,       -- Monatsrate
    erste_rate              TEXT NOT NULL,          -- YYYY-MM
    zinsbindung_bis         TEXT,                   -- YYYY-MM
    sondertilgung_prozent   REAL,                   -- Rahmen pro Jahr in % der Darlehenssumme
    zahlkonto_id            INTEGER REFERENCES konto(id) ON DELETE SET NULL,
    erinnerung_monate       INTEGER NOT NULL DEFAULT 24
);

CREATE TABLE darlehen_ereignis (
    id          INTEGER PRIMARY KEY,
    konto_id    INTEGER NOT NULL REFERENCES darlehen(konto_id) ON DELETE CASCADE,
    datum       TEXT NOT NULL,
    art         TEXT NOT NULL CHECK (art IN ('sondertilgung','abgleich')),
    betrag_cent INTEGER NOT NULL,   -- Sondertilgung: Betrag; Abgleich: Restschuld laut Bank
    notiz       TEXT
);

CREATE TABLE vertrag (
    partner_key     TEXT PRIMARY KEY,
    name            TEXT,
    art             TEXT NOT NULL CHECK (art IN ('fix','abo','ignoriert')),
    notiz           TEXT
);

CREATE TABLE zuordnung_feedback (
    id          INTEGER PRIMARY KEY,
    buchung_id  INTEGER REFERENCES buchung(id) ON DELETE SET NULL,
    quelle      TEXT NOT NULL,
    konfidenz   REAL,
    korrekt     INTEGER NOT NULL,
    zeitpunkt   TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- Posten = Buchung ohne Aufteilung oder einzelne Aufteilung einer Buchung
CREATE VIEW posten AS
SELECT b.id AS buchung_id, NULL AS split_id, b.konto_id, b.buchungsdatum, b.abrechnungsmonat, b.verteilung_monate,
       b.betrag_cent, b.kategorie_id, b.person_id, b.ist_umbuchung, b.ruecklage_id
FROM buchung b
WHERE NOT EXISTS (SELECT 1 FROM buchung_split s WHERE s.buchung_id = b.id)
UNION ALL
SELECT b.id, s.id, b.konto_id, b.buchungsdatum, b.abrechnungsmonat, b.verteilung_monate,
       s.betrag_cent, s.kategorie_id, COALESCE(s.person_id, b.person_id), b.ist_umbuchung, b.ruecklage_id
FROM buchung_split s JOIN buchung b ON b.id = s.buchung_id;

-- Posten je Monat: Jahreszahlungen etc. auf N Monate verteilt (Rest im ersten Monat)
CREATE VIEW posten_monat AS
WITH RECURSIVE n(i) AS (SELECT 0 UNION ALL SELECT i + 1 FROM n WHERE i < 59)
SELECT p.*,
       strftime('%Y-%m', date(p.abrechnungsmonat || '-01', '+' || n.i || ' months')) AS monat,
       CASE WHEN n.i = 0
            THEN p.betrag_cent - (p.betrag_cent / p.verteilung_monate) * (p.verteilung_monate - 1)
            ELSE p.betrag_cent / p.verteilung_monate END AS betrag_monat
FROM posten p JOIN n ON n.i < p.verteilung_monate;

INSERT OR IGNORE INTO einstellung (schluessel, wert) VALUES ('sparquote_ziel', '25');
