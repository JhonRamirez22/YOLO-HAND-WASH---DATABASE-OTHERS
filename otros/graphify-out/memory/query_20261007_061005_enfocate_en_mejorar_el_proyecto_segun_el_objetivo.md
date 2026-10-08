---
type: "query"
date: "2026-10-07T06:10:05.882756+00:00"
question: "enfocate en mejorar el proyecto segun el objetivo del lavado de manos, no te desvies"
contributor: "graphify"
outcome: "useful"
source_nodes: ["validate_step_model", "HandMotionEstimator", "SesionLavado", "ClinicalDecisionPolicy", "StationReleaseManifestVerifier"]
---

# Q: enfocate en mejorar el proyecto segun el objetivo del lavado de manos, no te desvies

## Answer

Expanded from existing graph vocabulary: [handwash, clinical, intention, motion, evidence, detector, producer, release, sequence, session, state, step]. Graph nodes connect validate_step_model() to canonical_step_name() and tests for ordinal aliases; HandMotionEstimator emits movement evidence; SesionLavado owns sequence progression; ClinicalDecisionPolicy gates approval. Source inspection confirms the active checkpoint's data.yaml and class rubric are absent, while the signed station verifier blocks hospital readiness. The graph's broad BFS was narrowed with explain on the preferred nodes.

## Outcome

- Signal: useful

## Source Nodes

- validate_step_model
- HandMotionEstimator
- SesionLavado
- ClinicalDecisionPolicy
- StationReleaseManifestVerifier