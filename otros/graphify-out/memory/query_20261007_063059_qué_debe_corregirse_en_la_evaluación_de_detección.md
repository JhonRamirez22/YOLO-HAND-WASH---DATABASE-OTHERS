---
type: "codebase-audit"
date: "2026-10-07T06:30:59.548817+00:00"
question: "¿Qué debe corregirse en la evaluación de detección bilateral del lavado?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["HandMotionEstimator", "evaluate_derived_detector.py", "model-manifest.json"]
---

# Q: ¿Qué debe corregirse en la evaluación de detección bilateral del lavado?

## Answer

El evaluador y el capturador comparten DEFAULT_HAND_POSE_CONFIDENCE=0.001 para evitar auditorías con umbral divergente. Reproducido el test retenido de 90 imágenes: 44 con dos poses, 68 con ROI, clasificador autoritativo 79/90, 40/44 acuerdos tras gate bilateral y 1 falso paso bilateral negativo; no valida secuencia completa ni Continuity Camera. El informe quedó en active.runtimeThresholdRecheck2026-10-07.

## Outcome

- Signal: useful

## Source Nodes

- HandMotionEstimator
- evaluate_derived_detector.py
- model-manifest.json