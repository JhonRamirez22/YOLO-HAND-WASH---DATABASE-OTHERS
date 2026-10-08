---
type: "query"
date: "2026-10-08T17:23:12.650568+00:00"
question: "Continúa la mejora del flujo manos→pasos: verifica si la recuperación actual puede mejorar la detección bilateral y si Java usa OpenCV en el camino activo"
contributor: "graphify"
outcome: "useful"
source_nodes: ["HandPresenceWarmup", "SessionManager", "run_yolo26_continuity_camera.py", "HandMotionEstimator", "InferenceService"]
---

# Q: Continúa la mejora del flujo manos→pasos: verifica si la recuperación actual puede mejorar la detección bilateral y si Java usa OpenCV en el camino activo

## Answer

Expanded from graph vocab: [camera, detector, evidence, hand, inference, java, motion, presence, sequence, step, warmup, yolo]. Source check: Python YOLO26 pose detector emits bilateral presence; Java HandPresenceWarmup independently requires 3 s, and Java receives only scalar movement in MovementEvidenceRequest. backend/pom.xml has ONNX Runtime but no JavaCV/OpenCV; don't claim Java OpenCV is integrated. Six offline failures: 640 full-frame recovered 0/6 to two hands; 960 recovered 0/6; crop recovery had no ROI on these cases; two overlapping 640 tiles recovered 1/6 but cost 115–158 ms per image after warm-up. Do not add tile fallback without a broader, angle-labeled evaluation and latency budget. No frames saved and no training performed. Manifest still blocks clinical use due to missing exact data.yaml/rubric and non-independent validation.

## Outcome

- Signal: useful

## Source Nodes

- HandPresenceWarmup
- SessionManager
- run_yolo26_continuity_camera.py
- HandMotionEstimator
- InferenceService