---
type: "query"
date: "2026-10-08T18:55:46.591534+00:00"
question: "Trace the active hand-pose to ordered-step path and assess what currently prevents hospital readiness."
contributor: "graphify"
outcome: "useful"
source_nodes: ["SessionManager", "run_yolo26_continuity_camera.py", "HandPresenceWarmup", "OpenCvHandMotionEstimator", "model-manifest.json"]
---

# Q: Trace the active hand-pose to ordered-step path and assess what currently prevents hospital readiness.

## Answer

Expanded from graph vocabulary: [yolo, opencv, presence, intention, evidence, pose, hand, detector, temporal, step, classifier, movement, pipeline]. Source verification: Python YOLO localizer gates partial-step inference on two fresh hands; Java independently requires 3000 ms bilateral presence, validates v2 epoch/sequences, recalculates same-frame movement with OpenCV, then routes candidates through State/Strategy/Observer. Current model preflight passes role compatibility but warns paso_1...paso_7 is mapped by order because its exact training data.yaml/rubric is missing. Offline inference on 180 sampled held-out classifier frames: detector+classifier pre-gate agreement 127/180 with 5 negative-class false proposals; classifier alone 156/180 with 2 false proposals; on frames with two detected poses, 96/110 agreement and 1 negative candidate. This split reuses camera IDs and is not independent validation; no Java temporal acceptance or Continuity Camera behavior was tested. Java tests 380, camera tests 130, frontend 65/build/lint passed. Continuity Camera unavailable. No training performed. Hospital gate remains NOT_READY and must not be relaxed.

## Outcome

- Signal: useful

## Source Nodes

- SessionManager
- run_yolo26_continuity_camera.py
- HandPresenceWarmup
- OpenCvHandMotionEstimator
- model-manifest.json