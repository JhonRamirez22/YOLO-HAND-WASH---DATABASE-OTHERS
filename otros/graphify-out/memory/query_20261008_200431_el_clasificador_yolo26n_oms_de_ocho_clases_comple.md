---
type: "architecture"
date: "2026-10-08T20:04:31.682604+00:00"
question: "¿El clasificador YOLO26n OMS de ocho clases complementa al activo y cómo verifica Java el prerrequisito de dos manos por tres segundos?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["derived_classifier_decision", "HandPresenceWarmupTest", "SessionManagerPresenceWarmupTest", "OpenCvHandMotionEstimator", "run_yolo26_continuity_camera.py"]
---

# Q: ¿El clasificador YOLO26n OMS de ocho clases complementa al activo y cómo verifica Java el prerrequisito de dos manos por tres segundos?

## Answer

Comparé por inferencia (sin entrenar ni escribir medios) el activo de 9 clases a imgsz 320 y el challenger de 8 clases a imgsz 224, CPU, batch 1, en la misma muestra determinista de 180 imágenes: activo 158/180 top-1 mapeado (87,8 %), 155 decisiones con confianza >=0,75, 144 correctas (92,9 %) y 2 pasos falsos aceptados en negativos; challenger 138/180 (76,7 %), 102 aceptadas, 89 correctas (87,3 %) y 1 paso falso. Challenger omite la clase no_lavado; cierre de grifo es negativo, no Paso7. No integrarlo. El validador runtime lo rechaza por taxonomía incompatible. El parámetro hand-presence-warmup-ms vale 3000; Maven focalizado aprobó 11 pruebas de HandPresenceWarmup, SessionManagerPresenceWarmup y OpenCvHandMotionEstimator. Las imágenes fijas no prueban secuencia, ángulos nuevos ni precisión clínica; el manifiesto sigue NOT_READY y hospitalUseAllowed=false.

## Outcome

- Signal: useful

## Source Nodes

- derived_classifier_decision
- HandPresenceWarmupTest
- SessionManagerPresenceWarmupTest
- OpenCvHandMotionEstimator
- run_yolo26_continuity_camera.py
