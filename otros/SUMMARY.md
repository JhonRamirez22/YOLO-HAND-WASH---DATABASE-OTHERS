# Hand Wash YOLO — resumen operativo

## Propósito y límites

Sistema local para observar movimientos de fricción de manos con YOLO y evaluar su secuencia con Java. El iPhone funciona únicamente como Continuity Camera; la captura, inferencia, backend y dashboard se ejecutan en la Mac. No hay una app iOS requerida.

El modelo activo reconoce siete clases de fricción. Su equivalencia uno-a-uno con los gestos numerados de la OMS no está validada; tampoco detecta mojar las manos, aplicar jabón, enjuagar, secar o cerrar el grifo. El resultado es una evaluación parcial, no una certificación clínica del procedimiento completo.

Los perfiles de estación y demo rechazan la ingestión de clases OMS porque el modelo y la evidencia no están aprobados; solo el perfil de desarrollo permite ejercitar esa ruta experimental, sin aprobación clínica.

## Flujo activo

```text
iPhone Continuity Camera → captura/YOLO Python en Mac →
    ├─ MJPEG local → dashboard React/TypeScript (127.0.0.1:5173)
    └─ REST /api/v1/deteccion → backend Java/Spring (127.0.0.1:8080)
                                      └─ WebSocket → dashboard
```

Java aplica State, Strategy, Observer, Factory Method, Chain of Responsibility y Decorator. La secuencia, los tiempos y la aceptación de detecciones los controla el backend; YOLO produce observaciones, no certifica pasos por sí solo.

## Carpetas relevantes

- `backend/`: aplicación canónica Java/Spring y modelos. Java es el backend; Python solo captura/infiere YOLO y publica detecciones.
- `frontend/`: aplicación React/TypeScript y sus pruebas.
- `scripts/`: arranque, Continuity Camera, evaluación y utilidades de entrenamiento.
- `backend/models/`: pesos usados por captura e inferencia.
- `ENTRENAMIENTO/`, `datasets/`, `DataSet5_YOLO/`, `runs/`: datos y artefactos de entrenamiento; conservar.
- `circuito/`: integración futura, no requerida por el runtime actual.
- `archive/`: gateways FastAPI y otros códigos/documentación históricos fuera del arranque y del build.

## Ejecución local

Desde la raíz del repositorio:

```bash
./scripts/start_handwash.sh
```

El dashboard se sirve en `http://127.0.0.1:5173/`; Java en `http://127.0.0.1:8080/`; el video anotado usa MJPEG local en el puerto `8091`. El iPhone debe aparecer en la lista AVFoundation antes del arranque. Sigue en Terminal el código de sesión que imprime el capturador y vincúlalo desde el dashboard según el flujo indicado en `README.md`.

No entrenar modelos en esta Mac. Todo entrenamiento debe ejecutarse en otra máquina. No se graban imágenes ni videos; los frames se procesan en memoria.

## Mantenimiento seguro

No borrar `backend/models/`, datasets, `ENTRENAMIENTO/` ni resultados de entrenamiento durante una limpieza general. `.venv/`, `frontend/node_modules/`, `backend/target/` y `.runtime/` son generados, pero sirven al entorno local; `.runtime/` puede contener datos de desarrollo y los servicios en ejecución pueden depender de los otros directorios. Para comandos, variables, API y límites completos, consultar `README.md` y `AGENTS.md`.
