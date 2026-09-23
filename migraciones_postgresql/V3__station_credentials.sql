CREATE TABLE station_enrollment_codes (
    code_hash VARCHAR(64) PRIMARY KEY,
    station_name VARCHAR(80) NOT NULL,
    created_by VARCHAR(128) NOT NULL,
    created_at_epoch_ms BIGINT NOT NULL,
    expires_at_epoch_ms BIGINT NOT NULL,
    consumed_at_epoch_ms BIGINT,
    CONSTRAINT chk_station_enrollment_expiry CHECK (expires_at_epoch_ms > created_at_epoch_ms)
);

CREATE INDEX idx_station_enrollment_expiry
    ON station_enrollment_codes (expires_at_epoch_ms);
