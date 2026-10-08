---
type: "query"
date: "2026-10-08T04:54:31.357942+00:00"
question: "propon agregar un parametro que haga que primero se deban detectar las manos, y cuando ya esten manos presentes despues de 3 segundos de detectar las manos, empiece el lavado por los pasos correspondientes, esto que quede super bien funcional para el uso clinico en hospitales"
contributor: "graphify"
outcome: "useful"
source_nodes: ["HandPresenceWarmup", "SessionManager", "DetectionApiIntegrationTest", "run_yolo26_continuity_camera.py", "LiveCameraFeed.tsx", "StationProfileSafetyGuard"]
---

# Q: propon agregar un parametro que haga que primero se deban detectar las manos, y cuando ya esten manos presentes despues de 3 segundos de detectar las manos, empiece el lavado por los pasos correspondientes, esto que quede super bien funcional para el uso clinico en hospitales

## Answer

El parámetro ya existe: --hand-presence-warmup-ms (3000 por defecto). La cámara requiere dos poses válidas continuas; el productor exige observaciones frescas con hueco máximo de 500 ms, reinicia el calentamiento si falta una mano antes del inicio y bloquea inferencias de pasos hasta estar listo. Java repite la compuerta con reloj monotónico y el perfil station fija 3000 ms, rechazando overrides. La disponibilidad de pasos no inicia el lavado automáticamente: Java espera además intención de Palmas confirmada, y exige evidencia bilateral fresca para cada fase. Pruebas enfocadas pasaron: Maven 47/47; Python 165/165. Esto demuestra lógica offline, no precisión clínica. El modelo/semántica de siete pasos y la autorización clínica siguen sin validación independiente.

## Outcome

- Signal: useful

## Source Nodes

- HandPresenceWarmup
- SessionManager
- DetectionApiIntegrationTest
- run_yolo26_continuity_camera.py
- LiveCameraFeed.tsx
- StationProfileSafetyGuard