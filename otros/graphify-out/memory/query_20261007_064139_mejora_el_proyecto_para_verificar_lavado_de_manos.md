---
type: "query"
date: "2026-10-07T06:41:39.354515+00:00"
question: "Mejora el proyecto para verificar lavado de manos con precisión y preparación hospitalaria"
contributor: "graphify"
outcome: "useful"
source_nodes: ["HandMotionEstimator", "CadenaIntencionLavado", "SeguimientoIntencion", "SesionLavado", "ClinicalDecisionPolicy"]
---

# Q: Mejora el proyecto para verificar lavado de manos con precisión y preparación hospitalaria

## Answer

Query expanded from graph vocabulary: [hand, motion, evidence, intention, sequence, state, detector, clinical, policy, soap, hospital, model]. Graph traces the critical path HandMotionEstimator (scripts/run_yolo26_continuity_camera.py:L1434) -> Receptor/DetectionController -> CadenaIntencionLavado -> SeguimientoIntencion -> SesionLavado; ClinicalDecisionPolicy gates Notificador and DeploymentStatusController. Updated evaluator to share runtime hand-pose confidence and primary image-size constants, added configurable --pose-imgsz with validation, then measured 256/320/416 on the same held-out 90-frame sample: 320 remained the best balance (44 bilateral frames, 40/44 combined agreements; 10.61 s whole-command), 256 had 41 and 36/41 for only 0.22 s less, and 416 had 29 and 26/29 at 13.07 s. Added repeatable results to model-manifest. A 40-pair-per-class motion diagnostic had too few valid bilateral samples and overlapping positive/other-washing scores; no safe movement cutoff is supported. Full verifier: 336 Java, 165 Python, 58 frontend tests passed; dependency scans clear. Hospital readiness and OMS compliance remain unproven; no training or camera access.

## Outcome

- Signal: useful

## Source Nodes

- HandMotionEstimator
- CadenaIntencionLavado
- SeguimientoIntencion
- SesionLavado
- ClinicalDecisionPolicy