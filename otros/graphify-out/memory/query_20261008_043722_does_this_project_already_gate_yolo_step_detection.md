---
type: "query"
date: "2026-10-08T04:37:22.270041+00:00"
question: "Does this project already gate YOLO step detection on three seconds of bilateral hand presence, and what else starts the wash?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["HandPresenceWarmup", "SessionManager", "CadenaIntencionLavado", "LiveCameraFeed"]
---

# Q: Does this project already gate YOLO step detection on three seconds of bilateral hand presence, and what else starts the wash?

## Answer

Expanded from graph vocabulary: [intencion, hand, pose, motion, minimum, movement, temporal, step, confidence, evidence, taxonomy, clinical]. The 3000 ms bilateral fresh-pose gate exists in Python HandPresenceWarmup and Java SessionManager. Java blocks strict-v2 step events until its independent monotonic dwell passes; the gate only enables detection and does not start the wash. CadenaIntencionLavado additionally requires recent bilateral spatial evidence, measurable movement, confident Palmas, and sustained observations. The UI shows the warmup countdown. Source files were checked directly. This is not clinical validation: active paso_1...paso_7 taxonomy and movement threshold remain unverified; release manifest says NOT_READY and clinicalDecisionAllowed=false.

## Outcome

- Signal: useful

## Source Nodes

- HandPresenceWarmup
- SessionManager
- CadenaIntencionLavado
- LiveCameraFeed