---
type: "query"
date: "2026-10-08T16:00:02.322984+00:00"
question: "propon agregar un parametro que haga que primero se deban detectar las manos, y cuando ya esten manos presentes despues de 3 segundos de detectar las manos, empiece el lavado por los pasos correspondientes, esto que quede super bien funcional para el uso clinico en hospitales"
contributor: "graphify"
outcome: "useful"
source_nodes: ["HandPresenceWarmup", "SessionManager", "SeguimientoIntencion", "run_yolo26_continuity_camera.py"]
---

# Q: propon agregar un parametro que haga que primero se deban detectar las manos, y cuando ya esten manos presentes despues de 3 segundos de detectar las manos, empiece el lavado por los pasos correspondientes, esto que quede super bien funcional para el uso clinico en hospitales

## Answer

Expanded from graph vocabulary: hand presence warmup session step intention bilateral evidence. The parameter already exists: Python --hand-presence-warmup-ms defaults to 3000; Java independently enforces 3000 ms from monotonic server receipt, requiring two fresh hands with max 500 ms gaps. Station runner pins 3000 and station guard rejects overrides. This opens ordinary step inference; it does not start/credit washing. Java separately requires a sustained palms gesture, confidence, valid bilateral motion and distinct observations. Existing backend/Python tests passed. Clinical readiness remains NOT_READY: step taxonomy and model validation are not established; no new parameter or code change needed.

## Outcome

- Signal: useful

## Source Nodes

- HandPresenceWarmup
- SessionManager
- SeguimientoIntencion
- run_yolo26_continuity_camera.py