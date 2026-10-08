---
type: "architecture"
date: "2026-10-08T19:59:53.435577+00:00"
question: "Evalúa viabilidad JavaCV + OpenCV + YOLO y los cinco patrones; propone complementos aditivos para mejorar precisión del lavado OMS."
contributor: "graphify"
outcome: "useful"
source_nodes: ["OpenCvHandMotionEstimator", "ReglaValidacionStrategyFactory", "ClinicalDecisionPolicy", "ObserverPipelineConfig", "YOLO"]
---

# Q: Evalúa viabilidad JavaCV + OpenCV + YOLO y los cinco patrones; propone complementos aditivos para mejorar precisión del lavado OMS.

## Answer

Viable como arquitectura, pero patrones no garantizan precisión. Estado del repo: no depende de JavaCV; usa JavaCPP/OpenCV y ONNX Runtime en Java para movimiento, mientras YOLO/Ultralytics corre en Python. El manifest sigue NOT_READY/hospitalUseAllowed=false; el modelo activo tiene taxonomía genérica y falta su YAML/rúbrica. Prioridad: fijar rúbrica WHO y evidencia por paso; control de calidad de encuadre/oclusión; tracking estable de dos manos; flujo óptico local con compensación de movimiento de cámara; clasificador temporal complementario calibrado con videos anotados; fusión con abstención; validación separada por persona/video/ángulo. No contar HSV/espuma ni optical flow como prueba clínica única. Mapear tracking y QC como eslabones Chain; técnicas/fusión dentro de Strategies por paso; abrir sources por Factory; Singleton solo para modelo con acceso serializado y cierre nativo determinista; Observer publica snapshots compactos asincrónicos. Native Mat/Indexer debe cerrarse explícitamente; GC no sustituye cierre. El proyecto actual ya estima movimiento OpenCV y tiene compuertas temporales; no duplicarlas. No se modifica arquitectura ni se entrena.

## Outcome

- Signal: useful

## Source Nodes

- OpenCvHandMotionEstimator
- ReglaValidacionStrategyFactory
- ClinicalDecisionPolicy
- ObserverPipelineConfig
- YOLO