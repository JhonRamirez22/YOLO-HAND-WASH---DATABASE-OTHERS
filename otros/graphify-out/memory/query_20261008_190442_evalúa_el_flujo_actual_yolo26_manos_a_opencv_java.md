---
type: "query"
date: "2026-10-08T19:04:42.710490+00:00"
question: "Evalúa el flujo actual YOLO26 manos a OpenCV Java y pasos OMS; corrige o mejora el sistema sin entrenar localmente"
contributor: "graphify"
outcome: "useful"
source_nodes: ["HandPresenceWarmup", "SessionManager", "OpenCvHandMotionEstimator", "TemporalStepFilter", "YOLO"]
---

# Q: Evalúa el flujo actual YOLO26 manos a OpenCV Java y pasos OMS; corrige o mejora el sistema sin entrenar localmente

## Answer

Expanded from graph vocabulary: [yolo, hand, pose, presence, java, opencv, movement, sequence, intention, state, step, model]. Source inspection confirms the 3-second bilateral warm-up, Python YOLO producer, Java OpenCV movement estimator, and temporal filtering already exist. Controlled 180-image inference at 320/640 produced 110 bilateral frames, 96/110 candidate agreement, 1 negative candidate, 0 valid single-image motion estimates, wall 18.29s. At 416/640 it produced 79 bilateral frames, 67/79 agreement, 2 negative candidates, wall 24.17s. Keep the 320 default; 416 degraded coverage and runtime. Maven 380 tests and Python 130 tests passed. Preflight passed structural roles but warned generic paso_1..paso_7 are mapped by order without training YAML/rubric. Continuity Camera unavailable. Hospital readiness remains blocked; no training or code/model changes.

## Outcome

- Signal: useful

## Source Nodes

- HandPresenceWarmup
- SessionManager
- OpenCvHandMotionEstimator
- TemporalStepFilter
- YOLO