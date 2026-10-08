---
type: "query"
date: "2026-10-08T17:47:52.035539+00:00"
question: "Actúa como un Arquitecto de Software Senior y Experto en Visión por Computadora en Java.\n\nEstoy diseñando un sistema de auditoría en tiempo real para validar el lavado de manos según el protocolo de la OMS. Ya tengo una arquitectura base definida y aprobada. El objetivo es evaluarla y proponer adiciones técnicas, sin reemplazar los componentes ni patrones actuales.\n\nBase: JavaCV para captura/OpenCV/YOLO; YOLO localiza manos y ROI; OpenCV usa HSV para espuma y Optical Flow para movimiento; patrones Singleton, Factory Method, Strategy, Chain of Responsibility y Observer.\n\nTareas: validar viabilidad/riesgos de rendimiento y memoria nativa; proponer técnicas y capas para mejorar precisión de pasos finos; explicar cómo se integran en los cinco patrones."
contributor: "graphify"
outcome: "useful"
source_nodes: ["YOLO", "ProducerProtocolRegistry", "HandMotionEstimator", "HandPresenceWarmup", "EvidenciaMovimiento"]
---

# Q: Actúa como un Arquitecto de Software Senior y Experto en Visión por Computadora en Java.

Estoy diseñando un sistema de auditoría en tiempo real para validar el lavado de manos según el protocolo de la OMS. Ya tengo una arquitectura base definida y aprobada. El objetivo es evaluarla y proponer adiciones técnicas, sin reemplazar los componentes ni patrones actuales.

Base: JavaCV para captura/OpenCV/YOLO; YOLO localiza manos y ROI; OpenCV usa HSV para espuma y Optical Flow para movimiento; patrones Singleton, Factory Method, Strategy, Chain of Responsibility y Observer.

Tareas: validar viabilidad/riesgos de rendimiento y memoria nativa; proponer técnicas y capas para mejorar precisión de pasos finos; explicar cómo se integran en los cinco patrones.

## Answer

Expansion de Graphify: backend camera detector evidence javacv motion opencv pipeline pose producer sequence yolo. Viabilidad: JavaCV+OpenCV con un runtime de modelo es viable, pero JavaCV es wrapper de OpenCV/FFmpeg, no un loader directo de YOLO .pt; usar export ONNX/runtime y comprobar paridad de preprocesamiento/NMS. Riesgos: ciclo de vida de memoria nativa, FrameGrabber reutiliza el buffer del frame anterior, colas de video crecientes y tracking que deriva en oclusión; cerrar recursos, clonar solo frames retenidos, reutilizar buffers y usar cola acotada de último frame.

Adiciones: (1) estimador de pose/keypoints en ROI para geometría de dedos y contacto bilateral; (2) tracking Lucas-Kanade/Kalman entre detecciones con reacquisición YOLO y abstención al bajar calidad; (3) temporalidad con dwell, histéresis, evidencia fresca y secuencia ordenada; (4) HSV/espuma como evidencia auxiliar normalizada, nunca prueba única; (5) chequeos de blur/iluminación/encuadre y evaluación agrupada por persona, video, cámara, ángulo e iluminación, midiendo errores por paso y falsos aprobados. El flujo óptico detecta movimiento, no qué gesto OMS ocurrió; HSV detecta color, no jabón químicamente. Los cinco patrones organizan estas adiciones, pero no generan precisión por sí mismos.

Comprobación del repositorio: README actual muestra YOLO/cámara en Python y Java recibe etiquetas/metadatos; backend/pom.xml no incluye JavaCV/OpenCV (sí ONNX Runtime opcional). Ya existe warmup bilateral de 3 s y confirmación temporal. El manifiesto declara NOT_READY y el modelo activo no cubre mojado, jabón, enjuague, secado y cierre del grifo; no se puede presentar como validación clínica. Fuentes: README.md, backend/pom.xml, model-manifest.json, scripts/run_yolo26_continuity_camera.py.

## Outcome

- Signal: useful

## Source Nodes

- YOLO
- ProducerProtocolRegistry
- HandMotionEstimator
- HandPresenceWarmup
- EvidenciaMovimiento