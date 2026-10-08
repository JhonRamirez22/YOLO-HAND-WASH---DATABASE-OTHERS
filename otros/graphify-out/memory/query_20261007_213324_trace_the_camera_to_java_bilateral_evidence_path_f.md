---
type: "query"
date: "2026-10-07T21:33:24.645210+00:00"
question: "Trace the camera-to-Java bilateral evidence path for step credit and identify trust-boundary errors."
contributor: "graphify"
outcome: "useful"
source_nodes: ["HandMotionEstimator", "motion_evidence_matches_frame()", "Receptor", "SessionManager"]
---

# Q: Trace the camera-to-Java bilateral evidence path for step credit and identify trust-boundary errors.

## Answer

Expanded from graph vocabulary: [evidence, bilateral, movement, measurement, sequence, intent, duration, capture, detector, session, spatial, pose]. Graph traversal located HandMotionEstimator and motion_evidence_matches_frame() in scripts/run_yolo26_continuity_camera.py plus Receptor and SessionManager in Java. Direct source verification reproduced a Python edge case: bool is a subclass of int, so sequence=true matched frameSequence=1 and was sent as a JSON boolean to Java's Long DTO. Local type guards and regression tests now reject it before HTTP; no model or threshold behavior changed.

## Outcome

- Signal: useful

## Source Nodes

- HandMotionEstimator
- motion_evidence_matches_frame()
- Receptor
- SessionManager