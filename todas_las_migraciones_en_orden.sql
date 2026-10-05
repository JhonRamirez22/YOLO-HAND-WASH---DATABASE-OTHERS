-- ===== V1__pilot_audit_schema.sql =====
CREATE TABLE failed_attempts (
    session_id VARCHAR(36) NOT NULL,
    attempt_number INTEGER NOT NULL,
    result VARCHAR(32) NOT NULL,
    reason VARCHAR(128) NOT NULL,
    duration_ms BIGINT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at_epoch_ms BIGINT NOT NULL,
    CONSTRAINT pk_failed_attempts PRIMARY KEY (session_id, attempt_number),
    CONSTRAINT chk_failed_attempts_number CHECK (attempt_number > 0),
    CONSTRAINT chk_failed_attempts_duration CHECK (duration_ms >= 0)
