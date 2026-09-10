CREATE TABLE IF NOT EXISTS failed_attempts (
    session_id VARCHAR(36) NOT NULL,
    attempt_number INTEGER NOT NULL,
    result VARCHAR(32) NOT NULL,
    reason VARCHAR(128) NOT NULL,
    duration_ms BIGINT NOT NULL,
    payload_json CLOB NOT NULL,
    created_at_epoch_ms BIGINT NOT NULL,
    CONSTRAINT pk_failed_attempts PRIMARY KEY (session_id, attempt_number),
    CONSTRAINT chk_failed_attempts_number CHECK (attempt_number > 0),
    CONSTRAINT chk_failed_attempts_duration CHECK (duration_ms >= 0)
);

CREATE INDEX IF NOT EXISTS idx_failed_attempts_created
    ON failed_attempts (created_at_epoch_ms);

CREATE TABLE IF NOT EXISTS wash_encounters (
    session_id VARCHAR(36) PRIMARY KEY,
    protocol_code VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL,
    started_at_epoch_ms BIGINT NOT NULL,
    ended_at_epoch_ms BIGINT,
    model_version VARCHAR(128) NOT NULL,
    model_sha256 VARCHAR(64) NOT NULL,
    dataset_version VARCHAR(128) NOT NULL,
