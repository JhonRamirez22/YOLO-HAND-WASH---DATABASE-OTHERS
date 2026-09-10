CREATE TABLE IF NOT EXISTS failed_attempts (
    session_id VARCHAR(36) NOT NULL,
    attempt_number INTEGER NOT NULL,
    result VARCHAR(32) NOT NULL,
    reason VARCHAR(128) NOT NULL,
