---
type: "query"
date: "2026-10-08T19:18:36.161607+00:00"
question: "Evalúa el detector y el clasificador por cada cámara disponible, sin entrenar ni guardar medios, para identificar vistas débiles."
contributor: "graphify"
outcome: "useful"
source_nodes: ["evaluate_derived_detector.py", "YOLO", "HandMotionEstimator", "run_yolo26_continuity_camera.py", "model-manifest.json"]
---

# Q: Evalúa el detector y el clasificador por cada cámara disponible, sin entrenar ni guardar medios, para identificar vistas débiles.

## Answer

Query ampliada desde vocabulario del grafo: camera, classifier, evaluation, video, pose, dataset, split, hand, step, test. Se extendió scripts/evaluate_derived_detector.py con --per-camera, muestreo balanceado por cámara/clase, métricas por cámara y manejo determinista de muestras. En 235 imágenes del test del clasificador, inferencia CPU: detector 88/235; clasificador 197/235 con 3 propuestas falsas en 85 negativos; candidato combinado 173/235 con 5 falsas; poses bilaterales 152/235. Por cámara, poses bilaterales: 100 34/45, 101 3/10 (solo negativos), 102 37/45, 103 30/45, 104 17/45, 105 31/45. El muestreo test es por video, sin video IDs compartidos entre train/val/test, pero todas las cámaras aparecen en train; no es holdout de ángulos ni validación clínica. 134 pruebas Python pasaron. No se entrenó ni se guardaron frames.

## Outcome

- Signal: useful

## Source Nodes

- evaluate_derived_detector.py
- YOLO
- HandMotionEstimator
- run_yolo26_continuity_camera.py
- model-manifest.json