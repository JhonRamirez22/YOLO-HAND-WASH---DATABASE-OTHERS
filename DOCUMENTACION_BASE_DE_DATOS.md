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
