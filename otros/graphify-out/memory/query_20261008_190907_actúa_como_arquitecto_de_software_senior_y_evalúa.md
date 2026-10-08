---
type: "query"
date: "2026-10-08T19:09:07.710169+00:00"
question: "Actúa como Arquitecto de Software Senior y evalúa aditivamente JavaCV + OpenCV + YOLO y cinco patrones para auditoría de lavado OMS."
contributor: "graphify"
outcome: "useful"
source_nodes: ["YOLO", "OpenCvHandMotionEstimator", "HandPresenceWarmup", "SessionManager", "model-manifest.json"]
---

# Q: Actúa como Arquitecto de Software Senior y evalúa aditivamente JavaCV + OpenCV + YOLO y cinco patrones para auditoría de lavado OMS.

## Answer

Query ampliada desde vocabulario del grafo: yolo, hand, pose, opencv, motion, sequence, intention, step, strategy, observer, pipeline, java. Verificado en fuentes activas: backend/pom.xml usa JavaCPP/OpenCV y ONNX Runtime, no el artefacto JavaCV; scripts/run_yolo26_continuity_camera.py ejecuta Ultralytics YOLO en Python. OpenCvHandMotionEstimator revalida movimiento bilateral en Java; el modelo manifiesta NOT_READY y no cubre todo el procedimiento OMS. Propuesta viable si los pesos se exportan a ONNX para inferencia JVM; las mejoras deben ser tracking con detector de refresco, fusión temporal/geométrica por paso, control de calidad/abstención, calibración multiángulo y recursos nativos acotados, sin prometer precisión clínica sin validación independiente.

## Outcome

- Signal: useful

## Source Nodes

- YOLO
- OpenCvHandMotionEstimator
- HandPresenceWarmup
- SessionManager
- model-manifest.json