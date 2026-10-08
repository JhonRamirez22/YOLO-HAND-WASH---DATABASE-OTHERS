---
type: "query"
date: "2026-10-08T19:12:36.784916+00:00"
question: "Comprueba si el estado nativo de OpenCV se libera al expirar/eliminar sesiones y si Java valida manos duplicadas o solapadas."
contributor: "graphify"
outcome: "useful"
source_nodes: ["SessionManager", "OpenCvHandMotionEstimator", "HandPresenceWarmup", "EvidenciaPoseManosTest", "run_yolo26_continuity_camera.py"]
---

# Q: Comprueba si el estado nativo de OpenCV se libera al expirar/eliminar sesiones y si Java valida manos duplicadas o solapadas.

## Answer

Query ampliada desde vocabulario del grafo: motion, session, remove, cleanup, expiration, hand, evidence, presence. Verificación directa: SessionManager.limpiarSesionesTerminadas delega en eliminarSesion; eliminarSesion llama ProducerProtocolRegistry.removeSession, OpenCvHandMotionEstimator.removeSession y elimina el warmup, por lo que no se confirmó fuga de mapas. Se añadieron dos regresiones en EvidenciaPoseManosTest: esqueletos distintos con cajas solapadas cuentan como dos manos; predicciones idénticas cuentan como una. Maven completo: 382 pruebas aprobadas; suite Python de cámara: 130 aprobadas. La cámara de Continuidad no está enumerada; preflight de modelos pasa estructuralmente pero no verifica semántica del checkpoint.

## Outcome

- Signal: useful

## Source Nodes

- SessionManager
- OpenCvHandMotionEstimator
- HandPresenceWarmup
- EvidenciaPoseManosTest
- run_yolo26_continuity_camera.py