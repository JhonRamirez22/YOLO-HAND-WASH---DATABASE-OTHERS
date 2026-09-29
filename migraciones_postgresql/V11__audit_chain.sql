-- Tamper-evident audit log: every new event stores the HMAC of itself and of the previous event.
-- Events written before this migration keep NULL hashes and are outside the chain.
ALTER TABLE wash_audit_events ADD COLUMN prev_hash CHAR(64);
ALTER TABLE wash_audit_events ADD COLUMN event_hash CHAR(64);
