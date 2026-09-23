CREATE TABLE station_enrollment_codes (
    code_hash VARCHAR(64) PRIMARY KEY,
    station_name VARCHAR(80) NOT NULL,
    created_by VARCHAR(128) NOT NULL,
