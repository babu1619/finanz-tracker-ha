-- Version 0.9.0: gelöschte Buchungen (damit sie beim nächsten Import nicht wieder entstehen) und Finanzplanung.

CREATE TABLE buchung_geloescht (
    id              INTEGER PRIMARY KEY,
    konto_id        INTEGER NOT NULL REFERENCES konto(id) ON DELETE CASCADE,
    dedup_hash      TEXT NOT NULL,
    buchungsdatum   TEXT,
    betrag_cent     INTEGER,
    gegenpartei     TEXT,
    benutzer_id     INTEGER REFERENCES benutzer(id) ON DELETE SET NULL,
    geloescht_am    TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (konto_id, dedup_hash)
);

-- Geplante Ausgaben (Autokauf, Sanierung …) und erwartete Sondereinnahmen
CREATE TABLE plan_posten (
    id              INTEGER PRIMARY KEY,
    art             TEXT NOT NULL CHECK (art IN ('ausgabe','einnahme')),
    name            TEXT NOT NULL,
    betrag_cent     INTEGER NOT NULL CHECK (betrag_cent >= 0),
    monat           TEXT NOT NULL,              -- YYYY-MM
    kategorie_id    INTEGER REFERENCES kategorie(id) ON DELETE SET NULL,
    notiz           TEXT,
    erledigt        INTEGER NOT NULL DEFAULT 0,
    erstellt        TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX ix_plan_posten_monat ON plan_posten(monat);
