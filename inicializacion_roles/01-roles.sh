#!/bin/bash
# Runs once, when the data volume is created. Same split as the AWS bootstrap:
# handwash_migrator owns the schema (Flyway); handwash_runtime only reads and writes rows.
set -euo pipefail
