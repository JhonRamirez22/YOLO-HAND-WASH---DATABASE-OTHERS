---
type: "query"
date: "2026-10-08T17:43:29.853167+00:00"
question: "¿Cómo se mejora la detección bilateral de manos sin ralentizar cada frame?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["hand_recovery_tiles", "recover_hand_pose", "HandMotionEstimator"]
---

# Q: ¿Cómo se mejora la detección bilateral de manos sin ralentizar cada frame?

## Answer

La ruta de manos conserva la detección primaria a 320 px. Solo cuando el barrido de recuperación a 640 px sigue con menos de dos poses ejecuta un lote de dos recortes solapados (15 % del eje largo), mapea cajas/keypoints al frame original y asigna cada pose al lado propietario para evitar duplicados. Solo adopta más poses válidas; fuerza save=False y contabiliza las inferencias. En 47 fotogramas diagnósticos del test derivado, el runtime simulado conservó 19/47 cuadros con dos poses de la pasada primaria y promovió 9 fallos, dando 28/47; no es recall ni validación independiente. Java sigue sin JavaCV/OpenCV en su pom y no recibe frames; el gate hospitalario del manifiesto continúa NOT_READY. No se entrenó ni se accedió a cámara.

## Outcome

- Signal: useful

## Source Nodes

- hand_recovery_tiles
- recover_hand_pose
- HandMotionEstimator