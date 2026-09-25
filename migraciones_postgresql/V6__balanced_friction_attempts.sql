CREATE TABLE friction_attempt_validation (
    session_id VARCHAR(36) NOT NULL,
    attempt_number INTEGER NOT NULL CHECK (attempt_number > 0),
    policy_version VARCHAR(48) NOT NULL,
