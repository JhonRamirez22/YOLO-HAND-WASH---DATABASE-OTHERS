-- A shift is the span during which a station keeps evaluating without an operator present.
CREATE TABLE station_shifts (
    shift_id VARCHAR(36) PRIMARY KEY,
    station_id VARCHAR(36) NOT NULL REFERENCES handwash_stations(station_id),
