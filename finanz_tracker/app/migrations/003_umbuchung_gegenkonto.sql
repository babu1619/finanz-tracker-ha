-- Version 0.3.0: Umbuchung mit festgelegtem Gegenkonto, auch wenn die Gegenbuchung (noch) nicht importiert ist.
ALTER TABLE buchung ADD COLUMN umbuchung_konto_id INTEGER REFERENCES konto(id) ON DELETE SET NULL;
