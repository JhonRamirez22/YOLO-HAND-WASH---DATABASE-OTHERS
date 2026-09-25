CREATE TABLE protocol_profiles (
    version INTEGER PRIMARY KEY CHECK (version > 0),
    step_1_ms BIGINT NOT NULL CHECK (step_1_ms BETWEEN 3000 AND 15000),
    step_2_ms BIGINT NOT NULL CHECK (step_2_ms BETWEEN 3000 AND 15000),
    step_3_ms BIGINT NOT NULL CHECK (step_3_ms BETWEEN 3000 AND 15000),
    step_4_ms BIGINT NOT NULL CHECK (step_4_ms BETWEEN 3000 AND 15000),
    step_5_ms BIGINT NOT NULL CHECK (step_5_ms BETWEEN 3000 AND 15000),
    step_6_ms BIGINT NOT NULL CHECK (step_6_ms BETWEEN 3000 AND 15000),
    slow_threshold_ms BIGINT NOT NULL CHECK (slow_threshold_ms BETWEEN 40000 AND 120000),
    created_by VARCHAR(128) NOT NULL,
    created_at_epoch_ms BIGINT NOT NULL CHECK (created_at_epoch_ms >= 0)
);
