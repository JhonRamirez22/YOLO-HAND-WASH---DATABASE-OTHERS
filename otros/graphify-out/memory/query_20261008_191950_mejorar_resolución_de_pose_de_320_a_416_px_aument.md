---
type: "query"
date: "2026-10-08T19:19:50.985583+00:00"
question: "¿Mejorar resolución de pose de 320 a 416 px aumenta la detección bilateral por cámara en el test de video?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["evaluate_derived_detector.py", "YOLO", "HandMotionEstimator", "camera"]
---

# Q: ¿Mejorar resolución de pose de 320 a 416 px aumenta la detección bilateral por cámara en el test de video?

## Answer

Query ampliada desde vocabulario del grafo: camera, classifier, evaluation, video, pose, dataset, split, hand, step, test. Sobre la misma muestra balanceada de 235 frames (5 por cámara/clase disponible), 320 px produjo 152/235 poses bilaterales y 173/235 candidatos combinados; 416 px produjo 117/235 poses y 158/235 candidatos. Cobertura bilateral por cámara 320→416: 100 34→28/45; 101 3→1/10 (solo negativos); 102 37→26/45; 103 30→26/45; 104 17→15/45; 105 31→21/45. No subir el tamaño: empeora cobertura para todas las vistas muestreadas; mantener 320 hasta nueva evidencia. Es diagnóstico de videos de test con cámaras ya presentes en train, no validación de ángulos no vistos ni de secuencia Java/iPhone.

## Outcome

- Signal: useful

## Source Nodes

- evaluate_derived_detector.py
- YOLO
- HandMotionEstimator
- camera