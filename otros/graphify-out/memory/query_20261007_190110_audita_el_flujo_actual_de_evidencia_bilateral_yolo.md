---
type: "query"
date: "2026-10-07T19:01:10.904432+00:00"
question: "Audita el flujo actual de evidencia bilateral YOLO→Java y los bloqueos de producción hospitalaria."
contributor: "graphify"
outcome: "useful"
source_nodes: ["HandMotionEstimator", "motion_evidence_matches_frame()", "DetectionController.java", "SessionManager"]
---

# Q: Audita el flujo actual de evidencia bilateral YOLO→Java y los bloqueos de producción hospitalaria.

## Answer

Expanded from original query via vocab: [hand, pose, sequence, evidence, camera, motion, session, clinical, steps, detector, state, model, receptor, soap, wash, inference]. Graphify señaló HandMotionEstimator y motion_evidence_matches_frame; por limitación del grafo entre Python/Java, verifiqué los archivos directamente. El productor vincula evidencia al mismo frame/sequence y Java valida recencia/bilateralidad. Riesgo aún abierto: el inicio usa solo un piso numérico 1e-8; el test de intención acepta 1e-6 sintético, por lo que jitter real no está calibrado. No se ajusta sin clips etiquetados. Auditoría de dataset grouped: 0 near-duplicate candidatos entre train 465 y val 121, pero 111/121 test vienen del sourceSplit train y sourceVideoSeparationProven=false; no es evaluación independiente del checkpoint actual. Manifest sigue NOT_READY/hospitalUseAllowed=false; activo 7 clases de fricción, falta YAML/rúbrica exactos y secuencia OMS completa. Maven 341, frontend 61, Python cámara/movimiento/estación 153 pruebas pasaron. SCA Java/Python/npm sin vulnerabilidades conocidas. No entrené ni inferí modelos; no modifiqué código.

## Outcome

- Signal: useful

## Source Nodes

- HandMotionEstimator
- motion_evidence_matches_frame()
- DetectionController.java
- SessionManager