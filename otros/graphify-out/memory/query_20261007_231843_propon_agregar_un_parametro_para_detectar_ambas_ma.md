---
type: "query"
date: "2026-10-07T23:18:43.335424+00:00"
question: "Propon agregar un parametro para detectar ambas manos durante 3 segundos antes de habilitar el lavado por pasos"
contributor: "graphify"
outcome: "useful"
source_nodes: ["HandPresenceWarmup", "CadenaIntencionLavado", "SeguimientoIntencion", "LiveCameraFeed"]
---

# Q: Propon agregar un parametro para detectar ambas manos durante 3 segundos antes de habilitar el lavado por pasos

## Answer

La implementación ya existe en scripts/run_yolo26_continuity_camera.py como hand-presence-warmup-ms=3000; el supervisor la fija y rechaza overrides. El gate exige dos poses bilaterales frescas durante 3000 ms, reinicia ante pérdida o antigüedad, y habilita inferencia de pasos; el dashboard muestra el progreso. Las manos solas no inician la sesión: Java aún exige evidencia bilateral reciente, movimiento, Palmas y confirmaciones. Java no mide independientemente esos 3000 ms; para ello harían falta eventos de presencia v2 secuenciados y un temporizador monotónico de servidor. El manifiesto sigue NOT_READY para uso hospitalario. Query expanded from graph vocabulary: [hands, bilateral, presence, intention, start, sequence, session, evidence].

## Outcome

- Signal: useful

## Source Nodes

- HandPresenceWarmup
- CadenaIntencionLavado
- SeguimientoIntencion
- LiveCameraFeed