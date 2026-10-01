-- Station provisioning: the ADMIN creates the station up front and the Mac redeems a one-time
-- activation token. Additive and nullable, so the previous release keeps working on this schema.
ALTER TABLE handwash_stations ADD COLUMN activation_hash VARCHAR(64);
