-- A station whose Mac already holds a device credential counts as linked, so a key-login from another
-- device cannot silently replace it. Stations enrolled the old way were never marked.
UPDATE handwash_stations
