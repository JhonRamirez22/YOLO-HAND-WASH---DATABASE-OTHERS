# YOLO Hand Wash — base de datos y recursos

Este repositorio reúne la base H2 y los recursos complementarios del sistema YOLO Hand Wash. Es una parte del proyecto: **no incluye el código activo del backend Java ni del frontend React**. Esos componentes están en [YOLO-HAND-WASH---BACKEND](https://github.com/JhonRamirez22/YOLO-HAND-WASH---BACKEND) y [YOLO-HAND-WASH---FRONTEND](https://github.com/JhonRamirez22/YOLO-HAND-WASH---FRONTEND).

## Cómo se conectan las partes

```mermaid
flowchart LR
  Cam[Continuity Camera del iPhone] --> Py[Captura e inferencia YOLO en la Mac]
  Py -->|video MJPEG local :8091| UI[Dashboard React]
  Py -->|REST POST /api/v1/deteccion| Java[Backend Java / Spring Boot]
  Java -->|H2: resúmenes de intentos fallidos| DB[(Base H2 local)]
  Java -->|WebSocket /ws/{sessionId}| UI
```

- El proceso Python de `otros/scripts/run_yolo26_continuity_camera.py` captura la cámara, ejecuta YOLO y publica el video anotado localmente. Envía al backend eventos JSON con detecciones y metadatos; no transmite los fotogramas al backend.
- El backend Java controla las sesiones y la evaluación. El dashboard consume su API y recibe actualizaciones por WebSocket; el video lo consume desde el stream MJPEG.
- La base H2 guarda resúmenes limitados de intentos fallidos. No es el almacén de imágenes, videos ni inferencias normales.
- El modelo disponible detecta siete movimientos de fricción; no evalúa todas las acciones del procedimiento OMS ni certifica un lavado clínico completo.

## Contenido

| Ruta | Contenido |
| --- | --- |
| `database/handwash.mv.db` | Archivo binario H2 incluido con el repositorio. No es una base SQLite. |
| `database/schema.sql` | DDL de la tabla `failed_attempts`, sus restricciones y un índice por fecha. |
| `otros/scripts/` | Captura YOLO, ejecución local, preparación y evaluación de datasets, validaciones y pruebas Python. |
| `otros/requirements-camera.txt` y `otros/requirements-camera-macos-arm64.lock` | Dependencias del proceso de cámara e inferencia; el lock corresponde a macOS arm64. |
| `otros/datasets/`, `otros/DataSet5_YOLO/` | Configuración y subconjuntos versionados de datasets YOLO. Los datos de entrenamiento grandes no están todos versionados. |
| `otros/yolo26n*.pt` | Pesos YOLO auxiliares incluidos en esta parte del proyecto. Los pesos activos del backend se mantienen en el repositorio del backend. |
| `otros/circuito/` | Documentación y prototipos de integración con sensores, ESP32, Android e iOS; no son necesarios para el flujo actual de cámara YOLO. |
| `otros/docs/` | Operación de estación, requisitos del modelo OMS, evaluación, decisiones de arquitectura y documentación técnica. |
| `otros/archive/` | Implementaciones históricas y prototipos —incluido el gateway FastAPI legado— fuera del runtime activo. |
| `otros/scripts/graphify-out/`, `otros/GRAFO_PROYECTO.md` | Grafos y reportes de análisis estructural del proyecto. |
| `otros/README.md`, `otros/SUMMARY.md` | Documentación detallada del sistema completo y resumen operativo. Algunos comandos allí requieren el monorepo completo. |

## Esquema de persistencia

`database/schema.sql` define `failed_attempts` con:

- `session_id VARCHAR(36)` y `attempt_number INTEGER`, con clave primaria compuesta.
- `result VARCHAR(32)`, `reason VARCHAR(128)`, `duration_ms BIGINT`, `payload_json CLOB` y `created_at_epoch_ms BIGINT`.
- Restricciones: `attempt_number > 0` y `duration_ms >= 0`.
- Índice `idx_failed_attempts_created` sobre `created_at_epoch_ms`.

En el backend completo, H2 se ejecuta embebida y su ruta por defecto es `.runtime/handwash.mv.db`, configurable mediante `HANDWASH_DB_URL`. Ese archivo de runtime se ignora en Git. La carpeta `database/` pertenece a esta división del repositorio; el monorepo inicializa el esquema desde los recursos del backend. El archivo versionado `database/handwash.mv.db` no cambia por sí solo la ruta que usa el backend. Para el detalle de retención y persistencia, consulta la sección «Persistencia local de fallos» de [`otros/README.md`](otros/README.md).

## Ejecutar el sistema completo

Este repositorio dividido, por sí solo, **no arranca la aplicación**: `otros/scripts/start_handwash.sh` espera el entorno Python, los modelos y las carpetas `backend/` y `frontend/` del proyecto integrado, además de macOS con FFmpeg/AVFoundation y Continuity Camera. Para desplegar o desarrollar el flujo completo, combina los repositorios de backend, frontend y estos recursos siguiendo [`otros/README.md`](otros/README.md).

El README de `otros/` conserva comandos y decisiones del monorepo original. Los nombres de clases del FastAPI archivado se expresan en inglés; se mantienen los nombres de campos y valores del contrato histórico para no alterar su serialización.

## Referencias

- [Resumen operativo](otros/SUMMARY.md)
- [Grafo detallado del proyecto](otros/GRAFO_PROYECTO.md)
- [Operación segura de una estación](otros/docs/OPERATIONS_STATION.md)
- [Requisitos del modelo OMS](otros/docs/REQUISITOS_MODELO_OMS.md)
- [Código histórico archivado](otros/archive/README.md)
