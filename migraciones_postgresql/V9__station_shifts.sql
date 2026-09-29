-- A shift is the span during which a station keeps evaluating without an operator present.
CREATE TABLE station_shifts (
    shift_id VARCHAR(36) PRIMARY KEY,
    station_id VARCHAR(36) NOT NULL REFERENCES handwash_stations(station_id),
    protocol_code VARCHAR(64) NOT NULL,
    started_by VARCHAR(128) NOT NULL,
    started_at_epoch_ms BIGINT NOT NULL,
    ends_at_epoch_ms BIGINT NOT NULL,
    ended_at_epoch_ms BIGINT,
    end_reason VARCHAR(24) CHECK (end_reason IN ('EXPIRED', 'STOPPED', 'STATION_REVOKED')),
    -- Equals station_id while the shift is open and NULL once closed. UNIQUE ignores NULLs, so a
    -- station can have at most one open shift; a partial index would not run on H2.
