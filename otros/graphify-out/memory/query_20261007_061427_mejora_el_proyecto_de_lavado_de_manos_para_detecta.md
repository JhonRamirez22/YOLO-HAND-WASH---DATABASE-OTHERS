---
type: "query"
date: "2026-10-07T06:14:27.582035+00:00"
question: "mejora el proyecto de lavado de manos para detectar la secuencia y avanzar hacia producción hospitalaria usando el grafo existente"
contributor: "graphify"
outcome: "useful"
source_nodes: ["HandMotionEstimator", "SesionLavado", "SessionManager", "validate_step_model", "ClinicalDecisionPolicy", "StationReleaseManifestVerifier"]
---

# Q: mejora el proyecto de lavado de manos para detectar la secuencia y avanzar hacia producción hospitalaria usando el grafo existente

## Answer

Expanded from graph vocabulary: [handwash, intention, motion, evidence, step, sequence, state, threshold, gesture, detector, session, movement]. The graph identifies HandMotionEstimator, SesionLavado, SessionManager, validate_step_model(), ClinicalDecisionPolicy, and StationReleaseManifestVerifier as the relevant detection, sequence, and release nodes. Source verification shows motion magnitude remains diagnostic and paso_1…paso_7 are mapped by order without the active training rubric; the hospital gate remains NOT_READY. The grouped dataset test split is not independent for the active checkpoint (111/121 images overlap its training split) and has no proven video-level separation.

## Outcome

- Signal: useful

## Source Nodes

- HandMotionEstimator
- SesionLavado
- SessionManager
- validate_step_model
- ClinicalDecisionPolicy
- StationReleaseManifestVerifier