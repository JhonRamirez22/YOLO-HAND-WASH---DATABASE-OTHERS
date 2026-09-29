-- A shift is the span during which a station keeps evaluating without an operator present.
CREATE TABLE station_shifts (
    shift_id VARCHAR(36) PRIMARY KEY,
    station_id VARCHAR(36) NOT NULL REFERENCES handwash_stations(station_id),
    protocol_code VARCHAR(64) NOT NULL,
    started_by VARCHAR(128) NOT NULL,
    started_at_epoch_ms BIGINT NOT NULL,
    ends_at_epoch_ms BIGINT NOT NULL,
