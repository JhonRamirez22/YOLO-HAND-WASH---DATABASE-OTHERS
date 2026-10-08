---
type: "query"
date: "2026-10-08T15:50:41.156369+00:00"
question: "propon agregar un parametro que primero detecte manos y, tras 3 segundos, habilite el lavado por pasos para uso clinico"
contributor: "graphify"
outcome: "useful"
source_nodes: ["HandPresenceWarmup", "SessionManager", "run_yolo26_continuity_camera.py", "LiveCameraFeed.tsx", "StationProfileSafetyGuard"]
---

# Q: propon agregar un parametro que primero detecte manos y, tras 3 segundos, habilite el lavado por pasos para uso clinico

## Answer

Expanded from original query via graph vocabulary [hand, presence, warmup, gate, session, sequence, step, detection, observer]. Verified directly in source: the parameter already exists as --hand-presence-warmup-ms (3000 ms default); Python gates ordinary step inference on two fresh hand poses, and Java independently measures 3000 ms of bilateral presence with monotonic server time and max 500 ms pulse gaps before forwarding a step. Station supervisor fixes 3000 ms and rejects attempts to set 0. This only enables inference; presence alone must not start or approve a wash: Java's intent and ordered-step rules remain. Dashboard exposes elapsed/required time and instructs to start with palms. The active model manifest remains NOT_READY, hospitalUseAllowed=false, and OMS unsupported, so this gate is not clinical clearance. Focused tests passed: 47 Maven, 6 Python, 5 frontend.

## Outcome

- Signal: useful

## Source Nodes

- HandPresenceWarmup
- SessionManager
- run_yolo26_continuity_camera.py
- LiveCameraFeed.tsx
- StationProfileSafetyGuard