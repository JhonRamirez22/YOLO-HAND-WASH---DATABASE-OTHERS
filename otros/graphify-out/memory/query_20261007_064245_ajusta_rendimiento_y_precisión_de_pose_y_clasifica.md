---
type: "query"
date: "2026-10-07T06:42:45.282905+00:00"
question: "Ajusta rendimiento y precisión de pose y clasificador para el lavado"
contributor: "graphify"
outcome: "useful"
source_nodes: ["HandMotionEstimator", "evaluate_derived_detector.py", "ClinicalDecisionPolicy"]
---

# Q: Ajusta rendimiento y precisión de pose y clasificador para el lavado

## Answer

Expanded from graph vocabulary: [hand, motion, evidence, intention, sequence, detector, model, clinical]. The producer/evaluator share pose image-size 320 and confidence 0.001. Held-out test90 resolution comparison: 256 gave 41 bilateral and 36/41 agreements in 10.39 s; 320 gave 44 and 40/44 in 10.61 s; 416 gave 29 and 26/29 in 13.07 s. Keep 320. Classifier thresholds 0.75 and 0.80 had identical sampled outcomes (79/90 standalone, 40/44 bilateral, one negative false step); 0.85 fell to 78/90 and 39/44, same false step, so keep 0.75. Motion magnitude pairs were too sparse and overlapped between palms and other washing; do not guess a movement gate. Full verification passed: 336 Java, 165 Python, 58 frontend; dependency scans clear. Clinical/OMS release remains blocked by missing taxonomy, full procedure model, target-camera validation and clinical approval.

## Outcome

- Signal: useful

## Source Nodes

- HandMotionEstimator
- evaluate_derived_detector.py
- ClinicalDecisionPolicy