-- Exact wall-clock start/end of each V2 attempt, its audit outcome and photo status.
ALTER TABLE friction_attempt_validation ADD COLUMN started_at_epoch_ms BIGINT;
ALTER TABLE friction_attempt_validation ADD COLUMN finished_at_epoch_ms BIGINT;
ALTER TABLE friction_attempt_validation ADD COLUMN duration_ms BIGINT CHECK (duration_ms >= 0);
ALTER TABLE friction_attempt_validation ADD COLUMN slow BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE friction_attempt_validation ADD COLUMN outcome VARCHAR(16)
    CHECK (outcome IN ('CORRECTO', 'REPORTADO', 'REINICIADO', 'INTERRUMPIDO'));
ALTER TABLE friction_attempt_validation ADD COLUMN evidence_status VARCHAR(24)
