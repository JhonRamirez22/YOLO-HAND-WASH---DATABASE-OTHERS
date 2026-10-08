---
type: "query"
date: "2026-10-08T17:03:40.673840+00:00"
question: "Audita la evaluación offline del detector para distinguir poses bilaterales de evidencia de movimiento y aceptación Java."
contributor: "graphify"
outcome: "useful"
source_nodes: ["evaluate_derived_detector.py", "HandMotionEstimator", "motion_evidence_matches_frame()"]
---

# Q: Audita la evaluación offline del detector para distinguir poses bilaterales de evidencia de movimiento y aceptación Java.

## Answer

Expanded from original query via graph vocab: [yolo hand motion pipeline presence roi sequence strategy evidence temporal model session]. The evaluator previously labeled agreement after a two-hand pose check as if it followed Java's evidence gate. Each still image creates a new HandMotionEstimator, so it cannot measure inter-frame motion. Updated scripts/evaluate_derived_detector.py to call this a two-hand-pose proxy, count motion-valid single-frame samples, and state that Java motion/intent/temporal/sequence acceptance is not evaluated. Fresh CPU replay: 90 images, 53 bilateral poses, 48/53 proxy matches, one negative-class proposal on the proxy, 0/90 motion-valid measurements; classifier 79/90, 2 negative-class proposals, ~24.2 ms on 53 eligible images. Diagnostic only; no training or media writes.

## Outcome

- Signal: useful

## Source Nodes

- evaluate_derived_detector.py
- HandMotionEstimator
- motion_evidence_matches_frame()