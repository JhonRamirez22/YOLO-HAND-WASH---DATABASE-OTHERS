---
type: "query"
date: "2026-10-08T18:35:23.844604+00:00"
question: "Actúa como un Arquitecto de Software Senior y Experto en Visión por Computadora en Java. \n\nEstoy diseñando un sistema de auditoría en tiempo real para validar el lavado de manos según el protocolo de la OMS. Ya tengo una arquitectura base definida y aprobada. Tu objetivo NO es reemplazarla, rediseñarla ni cambiar los componentes actuales; tu tarea es EVALUAR su viabilidad y PROPONER ADICIONES O COMPLEMENTOS técnicos que enriquezcan la solución para resolver el problema de precisión.\n\n### Arquitectura Base Actual (NO REEMPLAZAR):\n1. Stack Tecnológico: Backend en Java utilizando la biblioteca JavaCV (wrapper de OpenCV y YOLO).\n2. Rol de YOLO: Localización inicial de las manos (detección de la Región de Interés - ROI).\n3. Rol de OpenCV: Preprocesamiento de frames, segmentación por color (HSV para espuma) y flujo óptico (Optical Flow) para medir la fricción/movimiento en la ROI.\n4. Patrones de Diseño Implementados (Regla de negocio obligatoria de 5 patrones):\n   - Singleton: Para la carga única en memoria del modelo YOLO.\n   - Factory Method: Para inicializar componentes de captura y procesamiento según el stream de video.\n   - Strategy: Para intercambiar la lógica de validación específica de cada paso de la OMS.\n   - Chain of Responsibility (Pipeline): Para el flujo secuencial del frame (Preprocesamiento -> YOLO -> ROI OpenCV -> Estrategia).\n   - Observer: Para notificar el estado y progreso de los pasos en tiempo real (vía WebSockets/DB).\n\n### Tareas solicitadas:\n1. Confirmación de Viabilidad Base: Valida brevemente que la combinación actual de JavaCV + los 5 patrones es viable, identificando si existe algún riesgo menor de rendimiento (como el Garbage Collector con memoria nativa C++) que debamos prever en la implementación.\n2. Extensiones y Adiciones de Precisión (Qué agregar): Proponme componentes, técnicas, librerías complementarias o capas lógicas adicionales que se integren de forma natural dentro de esta estructura para asegurar que el sistema no falle al distinguir los pasos finos de la OMS. (Por ejemplo: algoritmos específicos de tracking de OpenCV para no saturar a YOLO, clasificadores secundarios ligeros dentro de las \"Strategies\", o control de estados temporales).\n3. Ajuste de Patrones: Explica brevemente cómo las adiciones propuestas se acoplan o enriquecen los 5 patrones ya existentes sin romperlos (por ejemplo, cómo una nueva técnica de análisis se sumaría como un eslabón extra en la Chain of Responsibility o una nueva clase en la Strategy).\n\nMantén un enfoque estrictamente aditivo: construye sobre lo que ya tengo construido."
contributor: "graphify"
outcome: "useful"
source_nodes: ["run_yolo26_continuity_camera.py", "Receptor", "SessionManager", "ObserverPipelineConfig", "Notificador"]
---

# Q: Actúa como un Arquitecto de Software Senior y Experto en Visión por Computadora en Java. 

Estoy diseñando un sistema de auditoría en tiempo real para validar el lavado de manos según el protocolo de la OMS. Ya tengo una arquitectura base definida y aprobada. Tu objetivo NO es reemplazarla, rediseñarla ni cambiar los componentes actuales; tu tarea es EVALUAR su viabilidad y PROPONER ADICIONES O COMPLEMENTOS técnicos que enriquezcan la solución para resolver el problema de precisión.

### Arquitectura Base Actual (NO REEMPLAZAR):
1. Stack Tecnológico: Backend en Java utilizando la biblioteca JavaCV (wrapper de OpenCV y YOLO).
2. Rol de YOLO: Localización inicial de las manos (detección de la Región de Interés - ROI).
3. Rol de OpenCV: Preprocesamiento de frames, segmentación por color (HSV para espuma) y flujo óptico (Optical Flow) para medir la fricción/movimiento en la ROI.
4. Patrones de Diseño Implementados (Regla de negocio obligatoria de 5 patrones):
   - Singleton: Para la carga única en memoria del modelo YOLO.
   - Factory Method: Para inicializar componentes de captura y procesamiento según el stream de video.
   - Strategy: Para intercambiar la lógica de validación específica de cada paso de la OMS.
   - Chain of Responsibility (Pipeline): Para el flujo secuencial del frame (Preprocesamiento -> YOLO -> ROI OpenCV -> Estrategia).
   - Observer: Para notificar el estado y progreso de los pasos en tiempo real (vía WebSockets/DB).

### Tareas solicitadas:
1. Confirmación de Viabilidad Base: Valida brevemente que la combinación actual de JavaCV + los 5 patrones es viable, identificando si existe algún riesgo menor de rendimiento (como el Garbage Collector con memoria nativa C++) que debamos prever en la implementación.
2. Extensiones y Adiciones de Precisión (Qué agregar): Proponme componentes, técnicas, librerías complementarias o capas lógicas adicionales que se integren de forma natural dentro de esta estructura para asegurar que el sistema no falle al distinguir los pasos finos de la OMS. (Por ejemplo: algoritmos específicos de tracking de OpenCV para no saturar a YOLO, clasificadores secundarios ligeros dentro de las "Strategies", o control de estados temporales).
3. Ajuste de Patrones: Explica brevemente cómo las adiciones propuestas se acoplan o enriquecen los 5 patrones ya existentes sin romperlos (por ejemplo, cómo una nueva técnica de análisis se sumaría como un eslabón extra en la Chain of Responsibility o una nueva clase en la Strategy).

Mantén un enfoque estrictamente aditivo: construye sobre lo que ya tengo construido.

## Answer

Expanded from original query via graph vocabulary: [javacv, opencv, yolo, pose, motion, classifier, intention, strategy, observer, chain, session, oms]. Graph points to active producer, Receptor, SessionManager and Observer pipeline; verified current sources rather than archive nodes.

Assessment: JavaCV/OpenCV/YOLO is viable in principle, but JavaCV is bindings, not a YOLO runtime; inference needs a compatible exported model and tested preprocessing/postprocessing. This repository currently runs YOLO in scripts/run_yolo26_continuity_camera.py and Java/OpenCV recalculates motion from numeric landmarks; it is not a JavaCV camera+YOLO backend. Keep that implementation distinction explicit. Native buffers (Mat/Frame/indexers/capture) require deterministic release; bound queues and avoid concurrent access to one mutable inference net.

Additions: (1) frame/pose quality gate and abstention for stale, occluded, cropped or low-quality bilateral hands; (2) sparse Lucas–Kanade tracking inside hand ROIs with periodic YOLO relocalization and reset on quality loss; (3) temporal landmark/motion classifier as secondary evidence, with one Java state machine as the sole step authority; (4) optional HSV soap/foam cue only as weak corroboration; (5) independent, participant/session-separated validation across views, lighting and gloves, with per-step precision/recall, false transitions, abstention and latency.

Pattern fit: Singleton owns model lifecycle, not unbounded concurrent inference; Factory Method builds capture/decoder adapters; Strategy returns candidate+evidence per step; Chain adds quality→detect→track→features→temporal confirmation; Observer publishes via bounded nonblocking queues/coalescing. Keep all evidence fail-closed.

Clinical limit: current model manifest is NOT_READY and the project has seven friction classes, not the complete WHO soap-and-water workflow. WHO poster specifies numbered actions 0–11 and 40–60 s. Do not claim hospital readiness absent exact label mapping and independent clinical validation. Sources: https://github.com/bytedeco/javacv, https://docs.opencv.org/5.0/tutorials/others/optical_flow.html, https://cdn.who.int/media/docs/default-source/documents/health-topics/hand-hygiene-why-how-and-when-brochure.pdf

## Outcome

- Signal: useful

## Source Nodes

- run_yolo26_continuity_camera.py
- Receptor
- SessionManager
- ObserverPipelineConfig
- Notificador