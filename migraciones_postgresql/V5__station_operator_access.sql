CREATE TABLE station_operator_access_codes (
    code_id VARCHAR(36) PRIMARY KEY,
    code_hash VARCHAR(64) NOT NULL UNIQUE,
    station_id VARCHAR(36) NOT NULL REFERENCES handwash_stations(station_id),
    target_email VARCHAR(254) NOT NULL,
    created_by VARCHAR(128) NOT NULL,
    created_at_epoch_ms BIGINT NOT NULL,
    consumed_at_epoch_ms BIGINT,
