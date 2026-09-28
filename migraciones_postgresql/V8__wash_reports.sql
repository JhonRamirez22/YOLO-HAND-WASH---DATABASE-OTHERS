-- Exact wall-clock start/end of each V2 attempt, its audit outcome and photo status.
ALTER TABLE friction_attempt_validation ADD COLUMN started_at_epoch_ms BIGINT;
ALTER TABLE friction_attempt_validation ADD COLUMN finished_at_epoch_ms BIGINT;
ALTER TABLE friction_attempt_validation ADD COLUMN duration_ms BIGINT CHECK (duration_ms >= 0);
