---
type: "query"
date: "2026-10-08T18:59:34.693468+00:00"
question: "Actúa como arquitecto y evalúa aditivamente JavaCV + OpenCV + YOLO y los cinco patrones para auditar lavado de manos OMS; propone complementos de precisión sin reemplazar la arquitectura"
contributor: "graphify"
outcome: "useful"
source_nodes: ["OpenCvHandMotionEstimator", "HandPresenceWarmup", "TemporalStepFilter", "YOLO", "SessionManager"]
---

# Q: Actúa como arquitecto y evalúa aditivamente JavaCV + OpenCV + YOLO y los cinco patrones para auditar lavado de manos OMS; propone complementos de precisión sin reemplazar la arquitectura

## Answer

Expanded from original query via graph vocab: [java, javacv, opencv, yolo, roi, hand, pose, temporal, classifier, strategy, chain, singleton]. Graph result was checked against current files. Target stack is viable, but not the live architecture: pom.xml pins JavaCPP/OpenCV and ONNX Runtime; camera YOLO is Python; Java OpenCV recalculates bilateral pose movement. Existing code already has 3s bilateral warm-up and temporal confirmation. Recommend only additive frame-quality/abstention gate, sparse LK tracking with drift-triggered YOLO re-detection, step-specific temporal evidence, calibrated fusion/negative classes, and HSV foam as non-authoritative cue. Native JavaCPP/OpenCV objects need deterministic close and RSS monitoring. Model manifest says WHO procedure and hospital use are not ready; no pattern or algorithm alone establishes clinical validity.

## Outcome

- Signal: useful

## Source Nodes

- OpenCvHandMotionEstimator
- HandPresenceWarmup
- TemporalStepFilter
- YOLO
- SessionManager