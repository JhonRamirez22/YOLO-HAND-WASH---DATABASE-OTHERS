---
type: "query"
date: "2026-10-08T04:00:01.420385+00:00"
question: "¿Dónde se detecta la presencia bilateral de manos, cómo se mide su frescura/continuidad y cómo se habilita el inicio de una sesión o la evaluación de pasos? Busca configuraciones de timeout o warmup."
contributor: "graphify"
outcome: "useful"
source_nodes: ["HandPresenceWarmup", "SessionManager", "SessionManagerPresenceWarmupTest.java", "HandPresenceWarmupTest", "run_yolo26_continuity_camera.py", "LiveCameraFeed.tsx", "application.yml", "application-station.yml"]
---

# Q: ¿Dónde se detecta la presencia bilateral de manos, cómo se mide su frescura/continuidad y cómo se habilita el inicio de una sesión o la evaluación de pasos? Busca configuraciones de timeout o warmup.

## Answer

El gate de 3000 ms ya existe en Python y Java. Requiere dos manos recientes con continuidad (hueco máximo 500 ms), reinicia antes del inicio ante pérdida de manos o hueco largo, y Java valida de nuevo por reloj monotónico antes de admitir pasos. Al completar warmup solo habilita inferencia: la sesión empieza después de confirmar Palmas/intención; cada paso conserva evidencia bilateral fresca y validación temporal. El perfil station fija 3000 ms. No equivale a autorización clínica: OMS sigue deshabilitado/no autorizado hasta evaluación y release firmados.

## Outcome

- Signal: useful

## Source Nodes

- HandPresenceWarmup
- SessionManager
- SessionManagerPresenceWarmupTest.java
- HandPresenceWarmupTest
- run_yolo26_continuity_camera.py
- LiveCameraFeed.tsx
- application.yml
- application-station.yml