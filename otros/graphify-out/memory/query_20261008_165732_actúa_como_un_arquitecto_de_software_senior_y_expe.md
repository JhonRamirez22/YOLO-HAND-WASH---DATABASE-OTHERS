---
type: "query"
date: "2026-10-08T16:57:32.906230+00:00"
question: "Actúa como un Arquitecto de Software Senior y Experto en Visión por Computadora en Java.\n\nEstoy diseñando un sistema de auditoría en tiempo real para validar el lavado de manos según el protocolo de la OMS. Ya tengo una arquitectura base definida y aprobada. Tu objetivo NO es reemplazarla, rediseñarla ni cambiar los componentes actuales; tu tarea es EVALUAR su viabilidad y PROPONER ADICIONES O COMPLEMENTOS técnicos que enriquezcan la solución para resolver el problema de precisión.\n\n### Arquitectura Base Actual (NO REEMPLAZAR):\n1. Stack Tecnológico: Backend en Java utilizando la biblioteca JavaCV (wrapper de OpenCV y YOLO).\n2. Rol de YOLO: Localización inicial de las manos (detección de la Región de Interés - ROI).\n3. Rol de OpenCV: Preprocesamiento de frames, segmentación por color (HSV para espuma) y flujo óptico (Optical Flow) para medir la fricción/movimiento en la ROI.\n4. Patrones de Diseño Implementados (Regla de negocio obligatoria de 5 patrones):\n   - Singleton: Para la carga única en memoria del modelo YOLO.\n   - Factory Method: Para inicializar componentes de captura y procesamiento según el stream de video.\n   - Strategy: Para intercambiar la lógica de validación específica de cada paso de la OMS.\n   - Chain of Responsibility (Pipeline): Para el flujo secuencial del frame (Preprocesamiento -> YOLO -> ROI OpenCV -> Estrategia).\n   - Observer: Para notificar el estado y progreso de los pasos en tiempo real (vía WebSockets/DB).\n\n### Tareas solicitadas:\n1. Confirmación de Viabilidad Base: Valida brevemente que la combinación actual de JavaCV + los 5 patrones es viable, identificando si existe algún riesgo menor de rendimiento (como el Garbage Collector con memoria nativa C++) que debamos prever en la implementación.\n2. Extensiones y Adiciones de Precisión (Qué agregar): Proponme componentes, técnicas, librerías complementarias o capas lógicas adicionales que se integren de forma natural dentro de esta estructura para asegurar que el sistema no falle al distinguir los pasos finos de la OMS. (Por ejemplo: algoritmos específicos de tracking de OpenCV para no saturar a YOLO, clasificadores secundarios ligeros dentro de las \"Strategies\", o control de estados temporales).\n3. Ajuste de Patrones: Explica brevemente cómo las adiciones propuestas se acoplan o enriquecen los 5 patrones ya existentes sin romperlos (por ejemplo, cómo una nueva técnica de análisis se sumaría como un eslabón extra en la Chain of Responsibility o una nueva clase en la Strategy).\n\nMantén un enfoque estrictamente aditivo: construye sobre lo que ya tengo construido."
contributor: "graphify"
outcome: "useful"
source_nodes: ["run_yolo26_continuity_camera.py", "HandMotionEstimator", "SessionManager", "CadenaIntencionLavado"]
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

Expanded from original query via graph vocab: [yolo hand motion pipeline presence roi sequence strategy camera detector classifier].
Resultado: JavaCV sirve como binding de OpenCV/FFmpeg, pero no ejecuta por sí solo un modelo YOLO .pt. Para Java se necesita un runtime de inferencia aparte (p. ej., ONNX Runtime con exportación y decoder verificados). FrameGrabber/Frame son AutoCloseable y reutilizan buffers: liberar recursos determinísticamente y copiar frames solo si deben persistir.
El repositorio real hoy usa Python/Ultralytics/OpenCV para cámara y YOLO; Java/Spring procesa detecciones REST. Java no declara JavaCV/OpenCV en pom.xml; su InferenceService ONNX es opcional. El backend documenta seis patrones (State, Strategy, Observer, Factory Method, Chain, Decorator), no el conjunto JavaCV/Singletón descrito. Ya existe warm-up de 3 s para dos manos y cadena de intención: no duplicar esa compuerta.
Adiciones: (1) mantener YOLO como detector/pose principal; probar Lucas–Kanade escaso en el ROI para seguimiento corto, con redetección periódica y abstención/reinicialización ante oclusión, deriva o baja calidad; nunca acreditar un paso solo por tracker. (2) OpenCV flow, keypoints y geometría bilateral como evidencia complementaria de movimiento relativo tras compensar movimiento de cámara; el flow no clasifica por sí solo gestos parecidos. (3) HSV de espuma solo como señal auxiliar calibrada por estación; jabón transparente, reflejos e iluminación invalidan el uso como prueba única. (4) añadir clasificador temporal ligero de candidatos por paso dentro de Strategy, con ventana de evidencias frescas, histéresis y abstención; Java conserva la autoridad de orden/tiempo. (5) fijar cámara/encuadre y evaluar por persona, vídeo, dispositivo, iluminación y ángulo en particiones independientes; una cámara no ofrece multivista simultánea. Para varias cámaras se requiere sincronización y fusión explícitas.
Bloqueo crítico: manifiesto NOT_READY; el checkpoint tiene siete clases de fricción con semántica/orden no verificados y no valida mojar, aplicar jabón, enjuagar, secar o cerrar grifo. La OMS describe el procedimiento con jabón/agua en 40–60 s y fases 0–10. Precisión clínica requiere datos etiquetados por secuencia, validación independiente y revisión clínica; la arquitectura no la garantiza.


## Outcome

- Signal: useful

## Source Nodes

- run_yolo26_continuity_camera.py
- HandMotionEstimator
- SessionManager
- CadenaIntencionLavado