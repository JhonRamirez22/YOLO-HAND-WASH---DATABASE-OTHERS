---
type: "query"
date: "2026-10-08T16:42:36.770147+00:00"
question: "Actúa como arquitecto senior: evalúa la viabilidad de JavaCV + YOLO/OpenCV para auditar pasos OMS, propón complementos aditivos de precisión y explica cómo se acoplan a Singleton, Factory Method, Strategy, Chain of Responsibility y Observer."
contributor: "graphify"
outcome: "useful"
source_nodes: ["ObserverPipelineConfig", "ReglaValidacionStrategyFactory", "CadenaIntencionLavado", "Receptor", "SessionManager", "Notificador"]
---

# Q: Actúa como arquitecto senior: evalúa la viabilidad de JavaCV + YOLO/OpenCV para auditar pasos OMS, propón complementos aditivos de precisión y explica cómo se acoplan a Singleton, Factory Method, Strategy, Chain of Responsibility y Observer.

## Answer

Expanded from graph vocabulary: [java, camera, yolo, strategy, factory, observer, chain, motion, roi, pipeline, step, model]. El diseño es viable, con riesgos de memoria nativa que exigen cerrar Frames/Mat/grabbers y no retener el buffer reutilizado; los cinco patrones organizan el sistema pero no mejoran precisión por sí mismos. Complementos: tracking KCF/CSRT o Lucas-Kanade entre inferencias YOLO, control de calidad/visibilidad bilateral, clasificador temporal ligero sobre keypoints y flujo óptico con abstención, fusión calibrada por paso y evaluación independiente por persona/video/cámara/ángulo/iluminación. HSV sirve como señal auxiliar, no como prueba clínica de jabón. Encaje: tracking/ROI/features se añaden a la Chain; cada paso combina señales en su Strategy; Factory construye captura/tracker por fuente; Singleton administra modelo con seguridad de concurrencia; Observer publica async con colas acotadas. Verificado contra fuentes: README y pom describen en este repo Python+YOLO y Java/Spring, ONNX Runtime pero sin JavaCV; no es la arquitectura hipotética JavaCV. Manifiesto bloquea uso hospitalario: faltan rúbrica/data.yaml del checkpoint, validación independiente, semántica OMS completa y aprobación clínica. Fuentes Graphify: ObserverPipelineConfig, ReglaValidacionStrategyFactory, CadenaIntencionLavado, Receptor, SessionManager, Notificador; fuentes externas oficiales JavaCV/OpenCV.

## Outcome

- Signal: useful

## Source Nodes

- ObserverPipelineConfig
- ReglaValidacionStrategyFactory
- CadenaIntencionLavado
- Receptor
- SessionManager
- Notificador