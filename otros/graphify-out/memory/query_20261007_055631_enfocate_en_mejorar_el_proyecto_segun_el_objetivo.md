---
type: "query"
date: "2026-10-07T05:56:31.290056+00:00"
question: "enfocate en mejorar el proyecto segun el objetivo del lavado de manos, no te desvies"
contributor: "graphify"
outcome: "useful"
source_nodes: ["HandMotionEstimator", "SessionManager", "SesionLavado", "StationReleaseManifestVerifier", "ClinicalDecisionPolicy", "run_yolo26_continuity_camera.py"]
---

# Q: enfocate en mejorar el proyecto segun el objetivo del lavado de manos, no te desvies

## Answer

Expanded from original query via vocab: [intention, movement, evidence, estimator, hands, step, session]. The graph points to HandMotionEstimator and the Java session/evidence pipeline, plus StationReleaseManifestVerifier and ClinicalDecisionPolicy as release controls. Source inspection confirms the producer-to-Java REST edge because this graph misses cross-language calls. Current tree and test results are authoritative; the graph contains stale iOS/archive nodes. Useful as navigation, not clinical validation.

## Outcome

- Signal: useful

## Source Nodes

- HandMotionEstimator
- SessionManager
- SesionLavado
- StationReleaseManifestVerifier
- ClinicalDecisionPolicy
- run_yolo26_continuity_camera.py