CREATE TABLE failed_attempts (
    session_id VARCHAR(36) NOT NULL,
    attempt_number INTEGER NOT NULL,
    result VARCHAR(32) NOT NULL,
    reason VARCHAR(128) NOT NULL,
    duration_ms BIGINT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at_epoch_ms BIGINT NOT NULL,
