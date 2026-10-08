---
type: "query"
date: "2026-10-08T15:39:38.764540+00:00"
question: "¿Cómo se aplica la compuerta bilateral de tres segundos entre el productor YOLO y Java antes de aceptar pasos?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["HandPresenceWarmup", "SessionManager", "DeteccionEvento", "Receptor"]
---

# Q: ¿Cómo se aplica la compuerta bilateral de tres segundos entre el productor YOLO y Java antes de aceptar pasos?

## Answer

Expandido desde vocabulario Graphify: [hand, presence, warmup, intention, sequence, evidence, step, session, gate, transition, strategy, java]. El grafo conecta HandPresenceWarmup con SessionManager, DeteccionEvento y Receptor. La inspección directa confirma que Python emite pulsos PRESENCE con conteo y secuencia de frame; Java valida epoch y watermarks, mide 3000 ms con reloj monotónico y no envía esos pulsos a Observer. Las detecciones de paso con secuencia anterior al último watermark se rechazan antes del pipeline. La presencia por sí sola no inicia el lavado. No es validación clínica del modelo.

## Outcome

- Signal: useful

## Source Nodes

- HandPresenceWarmup
- SessionManager
- DeteccionEvento
- Receptor