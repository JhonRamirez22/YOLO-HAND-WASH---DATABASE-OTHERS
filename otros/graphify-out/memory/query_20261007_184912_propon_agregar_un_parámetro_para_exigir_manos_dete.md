---
type: "query"
date: "2026-10-07T18:49:12.471981+00:00"
question: "Propon agregar un parámetro para exigir manos detectadas y presentes durante 3 segundos antes de iniciar el lavado por pasos, con calidad para uso clínico hospitalario."
contributor: "graphify"
outcome: "useful"
source_nodes: ["HandPresenceWarmup", "run_yolo26_continuity_camera.py"]
---

# Q: Propon agregar un parámetro para exigir manos detectadas y presentes durante 3 segundos antes de iniciar el lavado por pasos, con calidad para uso clínico hospitalario.

## Answer

Expanded from original query via vocab: [hand, presence, warmup]. La funcionalidad ya existe en scripts/run_yolo26_continuity_camera.py: --hand-presence-warmup-ms tiene default 3000; HandPresenceWarmup cuenta dos poses bilaterales frescas durante 3000 ms, reinicia al faltar una mano o excederse el hueco, y la estación impide sobrescribir el valor. Esto solo desbloquea inferencia de pasos; no inicia automáticamente una sesión: Java aún requiere detección de Palmas, evidencia bilateral y movimiento, y conserva secuencia/reglas. No duplicar el parámetro. No equivale a autorización o validación clínica: el modelo/procedimiento siguen no validados para release hospitalario. Los tests Java de intención pasaron (19); Python quedó sin ejecutar porque el intérprete disponible no tiene cv2.

## Outcome

- Signal: useful

## Source Nodes

- HandPresenceWarmup
- run_yolo26_continuity_camera.py