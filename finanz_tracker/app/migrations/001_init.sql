-- Finanz-Tracker v1: Grundschema
-- Beträge immer in Cent (INTEGER), Daten als ISO-Text (YYYY-MM-DD), Abrechnungsmonat als YYYY-MM.

CREATE TABLE person (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    farbe       TEXT,
    aktiv       INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE benutzer (
    id              INTEGER PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE COLLATE NOCASE,
    passwort_hash   TEXT NOT NULL,
    rolle           TEXT NOT NULL DEFAULT 'mitglied' CHECK (rolle IN ('admin','mitglied','lesend')),
    person_id       INTEGER REFERENCES person(id) ON DELETE SET NULL,
    aktiv           INTEGER NOT NULL DEFAULT 1,
    erstellt        TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE konto (
    id                      INTEGER PRIMARY KEY,
    name                    TEXT NOT NULL,
    typ                     TEXT NOT NULL DEFAULT 'giro'
                            CHECK (typ IN ('giro','tagesgeld','kreditkarte','bargeld','depot','darlehen','sonstiges')),
    iban                    TEXT,
    institut                TEXT,
    eigentuemer_person_id   INTEGER REFERENCES person(id) ON DELETE SET NULL,
    sichtbarkeit            TEXT NOT NULL DEFAULT 'alle' CHECK (sichtbarkeit IN ('alle','privat')),
    startsaldo_cent         INTEGER NOT NULL DEFAULT 0,
    import_erinnerung_tage  INTEGER NOT NULL DEFAULT 7,
    aktiv                   INTEGER NOT NULL DEFAULT 1,
    sortierung              INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE importprofil (
    id              INTEGER PRIMARY KEY,
    name            TEXT NOT NULL,
    format          TEXT NOT NULL DEFAULT 'csv' CHECK (format IN ('csv','pdf','tilgungsplan','manuell')),
    zielart         TEXT NOT NULL DEFAULT 'kontobewegung' CHECK (zielart IN ('kontobewegung','darlehen')),
    einstellungen   TEXT NOT NULL DEFAULT '{}',   -- JSON: encoding, delimiter, date_format, decimal
    spalten         TEXT NOT NULL DEFAULT '[]',   -- JSON: [{index, header, feld}]
    betrag_modus    TEXT NOT NULL DEFAULT 'vorzeichen' CHECK (betrag_modus IN ('vorzeichen','soll_haben','kennzeichen')),
    beispiel        TEXT NOT NULL DEFAULT '[]',   -- JSON: einige Rohzeilen zum späteren Bearbeiten
    erstellt        TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    geaendert       TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE konto_importprofil (
    id                  INTEGER PRIMARY KEY,
    konto_id            INTEGER NOT NULL REFERENCES konto(id) ON DELETE CASCADE,
    importprofil_id     INTEGER NOT NULL REFERENCES importprofil(id) ON DELETE CASCADE,
    rolle               TEXT NOT NULL DEFAULT 'buchungen' CHECK (rolle IN ('buchungen','abgleich')),
    erkennungswert      TEXT,
    aktiv               INTEGER NOT NULL DEFAULT 1
);
CREATE UNIQUE INDEX ux_konto_profil_buchungen ON konto_importprofil(konto_id) WHERE rolle = 'buchungen';

CREATE TABLE kategorie (
    id          INTEGER PRIMARY KEY,
    parent_id   INTEGER REFERENCES kategorie(id) ON DELETE RESTRICT,
    name        TEXT NOT NULL,
    pfad        TEXT NOT NULL,
    ebene       INTEGER NOT NULL DEFAULT 0,
    art         TEXT CHECK (art IN ('einnahme','ausgabe','umbuchung')),  -- NULL = vom Elternteil erben
    farbe       TEXT,
    sortierung  INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX ix_kategorie_pfad ON kategorie(pfad);

CREATE TABLE importlauf (
    id                      INTEGER PRIMARY KEY,
    konto_id                INTEGER NOT NULL REFERENCES konto(id) ON DELETE CASCADE,
    importprofil_id         INTEGER REFERENCES importprofil(id) ON DELETE SET NULL,
    dateiname               TEXT,
    datei_hash              TEXT,
    zeitpunkt               TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    benutzer_id             INTEGER REFERENCES benutzer(id) ON DELETE SET NULL,
    anzahl_neu              INTEGER NOT NULL DEFAULT 0,
    anzahl_doppelt          INTEGER NOT NULL DEFAULT 0,
    anzahl_fehler           INTEGER NOT NULL DEFAULT 0,
    saldo_datei_cent        INTEGER,
    saldo_differenz_cent    INTEGER,
    rueckgaengig            INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE regel (
    id              INTEGER PRIMARY KEY,
    name            TEXT NOT NULL,
    prioritaet      INTEGER NOT NULL DEFAULT 100,
    aktiv           INTEGER NOT NULL DEFAULT 1,
    bedingungen     TEXT NOT NULL DEFAULT '[]',   -- JSON: [{feld, op, wert}]
    aktionen        TEXT NOT NULL DEFAULT '{}',   -- JSON: {kategorie_id, person_id, monat_versatz, als_umbuchung}
    erstellt        TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE buchung (
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
    kategorie_id            INTEGER REFERENCES kategorie(id) ON DELETE SET NULL,
    person_id               INTEGER REFERENCES person(id) ON DELETE SET NULL,
    notiz                   TEXT,
    saldo_cent              INTEGER,
    rohdaten                TEXT,
    dedup_hash              TEXT NOT NULL,
    importlauf_id           INTEGER REFERENCES importlauf(id) ON DELETE SET NULL,
    zuordnung_quelle        TEXT CHECK (zuordnung_quelle IN ('regel','gedaechtnis','manuell','umbuchung')),
    regel_id                INTEGER REFERENCES regel(id) ON DELETE SET NULL,
    geprueft                INTEGER NOT NULL DEFAULT 0,
    ist_umbuchung           INTEGER NOT NULL DEFAULT 0,
    umbuchung_partner_id    INTEGER REFERENCES buchung(id) ON DELETE SET NULL,
    erstellt                TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE (konto_id, dedup_hash)
);
CREATE INDEX ix_buchung_monat ON buchung(abrechnungsmonat);
CREATE INDEX ix_buchung_datum ON buchung(buchungsdatum);
CREATE INDEX ix_buchung_kategorie ON buchung(kategorie_id);
CREATE INDEX ix_buchung_partner ON buchung(partner_key);
CREATE INDEX ix_buchung_import ON buchung(importlauf_id);

CREATE TABLE umbuchung_vorschlag (
    id              INTEGER PRIMARY KEY,
    buchung_a_id    INTEGER NOT NULL REFERENCES buchung(id) ON DELETE CASCADE,
    buchung_b_id    INTEGER NOT NULL REFERENCES buchung(id) ON DELETE CASCADE,
    score           REAL NOT NULL,
    status          TEXT NOT NULL DEFAULT 'offen' CHECK (status IN ('offen','abgelehnt')),
    erstellt        TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE (buchung_a_id, buchung_b_id)
);

CREATE TABLE aenderungslog (
    id              INTEGER PRIMARY KEY,
    benutzer_id     INTEGER REFERENCES benutzer(id) ON DELETE SET NULL,
    zeitpunkt       TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    tabelle         TEXT NOT NULL,
    datensatz_id    INTEGER,
    aktion          TEXT NOT NULL,
    daten           TEXT
);

CREATE TABLE einstellung (
    schluessel  TEXT PRIMARY KEY,
    wert        TEXT
);
