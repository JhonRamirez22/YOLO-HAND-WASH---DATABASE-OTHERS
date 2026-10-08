---
type: "query"
date: "2026-10-08T02:43:11.660827+00:00"
question: "propon agregar un parametro que haga que primero se deban detectar las manos, y cuando ya esten manos presentes despues de 3 segundos de detectar las manos, empiece el lavado por los pasos correspondientes, esto que quede super bien funcional para el uso clinico en hospitales"
contributor: "graphify"
outcome: "useful"
source_nodes: ["HandPresenceWarmup", "SessionManagerPresenceWarmupTest", "SessionManager", "run_yolo26_continuity_camera.py", "LiveCameraFeed", "StationProfileSafetyGuard"]
---

# Q: propon agregar un parametro que haga que primero se deban detectar las manos, y cuando ya esten manos presentes despues de 3 segundos de detectar las manos, empiece el lavado por los pasos correspondientes, esto que quede super bien funcional para el uso clinico en hospitales

## Answer

Query expanded from graph vocabulary: hand, hands, presence, timer, start, detection, intention, sequence, session, state. Verified directly in source: the requested bilateral 3000 ms gate already exists. Python --hand-presence-warmup-ms defaults to 3000 and gates ordinary step inference; Java handwash.intention.hand-presence-warmup-ms independently measures authenticated PRESENCE pulses using monotonic receive time, with a 500 ms max gap. The station runner and StationProfileSafetyGuard pin 3000 ms. Dashboard reports 0/2, stabilization progress, and after readiness says to start with palms. Tests confirm two-hand presence alone does not start a session; step 1/intention is still required, and every step needs fresh bilateral evidence. Recommendation: do not add a duplicate or auto-start on hand presence. Keep 3 seconds as a stabilization gate, not a clinical criterion; current release is not validated for hospital/clinical use.

## Outcome

- Signal: useful

## Source Nodes

- HandPresenceWarmup
- SessionManagerPresenceWarmupTest
- SessionManager
- run_yolo26_continuity_camera.py
- LiveCameraFeed
- StationProfileSafetyGuard