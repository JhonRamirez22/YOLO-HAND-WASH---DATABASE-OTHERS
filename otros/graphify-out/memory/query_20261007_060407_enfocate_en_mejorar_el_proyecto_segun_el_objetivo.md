---
type: "query"
date: "2026-10-07T06:04:07.938243+00:00"
question: "enfocate en mejorar el proyecto segun el objetivo del lavado de manos, no te desvies"
contributor: "graphify"
outcome: "useful"
source_nodes: ["HandMotionEstimator", "run_yolo26_continuity_camera.py", "SesionLavado", "ClinicalDecisionPolicy", "StationReleaseManifestVerifier"]
---

# Q: enfocate en mejorar el proyecto segun el objetivo del lavado de manos, no te desvies

## Answer

Expanded from graph vocabulary: [intention, movement, evidence, estimator, hands, step, session, clinical]. The graph points to HandMotionEstimator for Python motion evidence and SesionLavado for Java session progression; ClinicalDecisionPolicy and StationReleaseManifestVerifier gate clinical release. The graph omits the Python-to-Java call edge, which must be verified in source.

## Outcome

- Signal: useful

## Source Nodes

- HandMotionEstimator
- run_yolo26_continuity_camera.py
- SesionLavado
- ClinicalDecisionPolicy
- StationReleaseManifestVerifier