-- ADMIN-issued API keys. A key is bound to one station; CONSOLE opens the operator console and
-- PRODUCER lets the YOLO PC publish detections. Only the SHA-256 of the 256-bit secret is stored.
CREATE TABLE api_keys (
    key_id VARCHAR(16) PRIMARY KEY,
