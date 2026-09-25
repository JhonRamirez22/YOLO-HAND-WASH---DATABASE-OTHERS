CREATE TABLE protocol_profiles (
    version INTEGER PRIMARY KEY CHECK (version > 0),
    step_1_ms BIGINT NOT NULL CHECK (step_1_ms BETWEEN 3000 AND 15000),
    step_2_ms BIGINT NOT NULL CHECK (step_2_ms BETWEEN 3000 AND 15000),
