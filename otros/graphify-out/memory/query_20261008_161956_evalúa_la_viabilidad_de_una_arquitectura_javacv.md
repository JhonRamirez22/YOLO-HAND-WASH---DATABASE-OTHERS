---
type: "query"
date: "2026-10-08T16:19:56.229434+00:00"
question: "Evalúa la viabilidad de una arquitectura JavaCV + OpenCV + YOLO con Singleton, Factory Method, Strategy, Chain of Responsibility y Observer, y propone complementos aditivos de precisión para auditoría de lavado de manos OMS."
contributor: "graphify"
outcome: "useful"
source_nodes: ["YOLO", "ObserverPipelineConfig", "FiltroIntencion", "CadenaIntencionLavado"]
---

# Q: Evalúa la viabilidad de una arquitectura JavaCV + OpenCV + YOLO con Singleton, Factory Method, Strategy, Chain of Responsibility y Observer, y propone complementos aditivos de precisión para auditoría de lavado de manos OMS.

## Answer

La arquitectura es técnicamente viable, pero los patrones no garantizan precisión. Controlar recursos nativos con AutoCloseable/PointerScope, reutilizar buffers, limitar colas y validar exportación/modelo/rendimiento del ONNX en la versión exacta de OpenCV. Añadir tracking de keypoints entre detecciones YOLO, compensación de movimiento de cámara, QA de frame, evidencia temporal con histéresis y opción abstain, y clasificador temporal secundario evaluado por sujeto/ángulo/iluminación. En el repo actual, YOLO/captura están en Python y Java/Spring evalúa secuencia; JavaCV no figura en backend/pom.xml, así que sería una arquitectura propuesta distinta del flujo implementado. Ningún resultado actual valida procedimiento OMS completo o uso clínico.

## Outcome

- Signal: useful

## Source Nodes

- YOLO
- ObserverPipelineConfig
- FiltroIntencion
- CadenaIntencionLavado