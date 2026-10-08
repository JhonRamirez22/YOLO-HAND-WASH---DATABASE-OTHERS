---
type: "query"
date: "2026-10-07T04:56:07.837898+00:00"
question: "¿Qué conecta al productor Python de cámara con el backend Java?"
contributor: "graphify"
outcome: "corrected"
correction: "La falta de camino en Graphify es una limitación de relaciones AST entre Python y Java, no evidencia de desconexión: el productor usa REST /api/v1/deteccion y Java valida/procesa la solicitud."
source_nodes: ["SessionManager", "Receptor", "DetectionController", "ProducerProtocolRegistry"]
---

# Q: ¿Qué conecta al productor Python de cámara con el backend Java?

## Answer

Consulta expandida desde vocabulario del grafo: [backend, java, spring, station, clinical, yolo, camera, session, sequence, intention, model, evidence]. El grafo AST no contiene camino dirigido ni no dirigido de run_yolo26_continuity_camera.py a Receptor; no significa que falte conexión en ejecución. El código verifica Python POST /api/v1/deteccion (scripts/run_yolo26_continuity_camera.py:796), DetectionController recibe @PostMapping("/deteccion") bajo /api/v1 (backend/src/main/java/com/handwash/controller/DetectionController.java:25), y SessionManager valida ProducerProtocolRegistry antes de Receptor. Falta representar esta relación HTTP entre procesos en el grafo.

## Outcome

- Signal: corrected
- Correction: La falta de camino en Graphify es una limitación de relaciones AST entre Python y Java, no evidencia de desconexión: el productor usa REST /api/v1/deteccion y Java valida/procesa la solicitud.

## Source Nodes

- SessionManager
- Receptor
- DetectionController
- ProducerProtocolRegistry