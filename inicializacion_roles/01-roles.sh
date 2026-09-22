#!/bin/bash
# Runs once, when the data volume is created. Same split as the AWS bootstrap:
# handwash_migrator owns the schema (Flyway); handwash_runtime only reads and writes rows.
set -euo pipefail
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v runtime_pw="$HANDWASH_RUNTIME_PASSWORD" -v migrator_pw="$HANDWASH_MIGRATOR_PASSWORD" <<'SQL'
CREATE ROLE handwash_runtime LOGIN PASSWORD :'runtime_pw';
CREATE ROLE handwash_migrator LOGIN PASSWORD :'migrator_pw';
