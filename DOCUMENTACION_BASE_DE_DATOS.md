# Base de datos de HandWash (PostgreSQL 16)

Generado a partir de las migraciones Flyway `V1`–`V17` (fuente de verdad). Solo números y estados: **nunca se guardan imágenes ni datos personales** (lo verifica `NoPersonalDataSchemaTest`).

**22 tablas.** Orden de aplicación: `migraciones_postgresql/V1…V17`.


## `failed_attempts`  _(creada en V1)_

| Columna | Tipo y restricciones |
|---|---|
| `session_id` | VARCHAR(36) NOT NULL |
| `attempt_number` | INTEGER NOT NULL |
| `result` | VARCHAR(32) NOT NULL |
| `reason` | VARCHAR(128) NOT NULL |
| `duration_ms` | BIGINT NOT NULL |
| `payload_json` | TEXT NOT NULL |
| `created_at_epoch_ms` | BIGINT NOT NULL |
| `(restricción)` | CONSTRAINT pk_failed_attempts PRIMARY KEY (session_id, attempt_number) |
| `(restricción)` | CONSTRAINT chk_failed_attempts_number CHECK (attempt_number > 0) |
| `(restricción)` | CONSTRAINT chk_failed_attempts_duration CHECK (duration_ms >= 0) |

## `wash_encounters`  _(creada en V1)_

| Columna | Tipo y restricciones |
|---|---|
| `session_id` | VARCHAR(36) PRIMARY KEY |
| `protocol_code` | VARCHAR(64) NOT NULL |
| `status` | VARCHAR(32) NOT NULL |
| `started_at_epoch_ms` | BIGINT NOT NULL |
| `ended_at_epoch_ms` | BIGINT |
