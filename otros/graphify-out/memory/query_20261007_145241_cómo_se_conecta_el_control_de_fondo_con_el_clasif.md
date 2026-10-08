---
type: "query"
date: "2026-10-07T14:52:41.794346+00:00"
question: "¿Cómo se conecta el control de Fondo con el clasificador de pasos YOLO en el flujo de cámara?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["run_yolo26_continuity_camera.py", "classifier_challenge_allowed()", "test_run_yolo26_continuity_camera.py", "evaluate_derived_detector.py"]
---

# Q: ¿Cómo se conecta el control de Fondo con el clasificador de pasos YOLO en el flujo de cámara?

## Answer

Expanded from graph vocabulary: [background, step, classifier, detection, confidence, yolo]. The graph links run() to classifier_challenge_allowed() and its bilateral-freshness tests. Source review confirmed the runtime's best_detection already compares Fondo with the detector step, but the subsequent classifier gate treated any Fondo box as a veto. The fix centralizes confidence-relative Fondo vetoes for detector and classifier candidates and applies the same rule in both offline evaluators; equal-or-higher Fondo abstains, lower Fondo does not.

## Outcome

- Signal: useful

## Source Nodes

- run_yolo26_continuity_camera.py
- classifier_challenge_allowed()
- test_run_yolo26_continuity_camera.py
- evaluate_derived_detector.py