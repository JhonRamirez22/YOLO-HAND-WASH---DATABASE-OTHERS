-- ===== V1__pilot_audit_schema.sql =====
CREATE TABLE failed_attempts (
    session_id VARCHAR(36) NOT NULL,
    attempt_number INTEGER NOT NULL,
