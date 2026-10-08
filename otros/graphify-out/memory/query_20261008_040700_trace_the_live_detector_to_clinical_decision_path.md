---
type: "query"
date: "2026-10-08T04:07:00.206705+00:00"
question: "Trace the live detector-to-clinical-decision path: YOLO hand pose and step/classifier candidates, transport v2 validation, bilateral evidence, Java intention start, State/Strategy acceptance, and the ACK. Identify inconsistencies that can make a visible/correct step be missed or a false step credited."
contributor: "graphify"
outcome: "useful"
source_nodes: ["run_yolo26_continuity_camera.py", "validate_step_model()", "best_detection()", "ProducerEpochStream", "ProducerProtocolRegistry", "SessionManager", "Receptor", "CadenaIntencionLavado", "SesionLavado", "PasoLavado"]
---

# Q: Trace the live detector-to-clinical-decision path: YOLO hand pose and step/classifier candidates, transport v2 validation, bilateral evidence, Java intention start, State/Strategy acceptance, and the ACK. Identify inconsistencies that can make a visible/correct step be missed or a false step credited.

## Answer

La revisión de fuentes no encontró desalineación nueva en el flujo: Python emite secuencia/candidato canónico y evidencia de pose emparejada; ProducerProtocolRegistry reserva epoch/secuencia; SessionManager vuelve a exigir presencia bilateral fresca; CadenaIntencionLavado requiere Palmas/medición/confirmación; State/Strategy controla orden/tiempo; ACK aceptado es solo transporte. La verificación completa pasó técnicamente, pero el preflight confirma que el modelo activo solo es estructuralmente compatible: paso_1…paso_7 se asignan por orden y no se verifican sin el data.yaml/rúbrica. El manifiesto marca NOT_READY, sin validación independiente, cámara piloto ni aprobación clínica; ClinicalDecisionPolicy devuelve false. No alterar umbrales/mapeo sin esas evidencias.

## Outcome

- Signal: useful

## Source Nodes

- run_yolo26_continuity_camera.py
- validate_step_model()
- best_detection()
- ProducerEpochStream
- ProducerProtocolRegistry
- SessionManager
- Receptor
- CadenaIntencionLavado
- SesionLavado
- PasoLavado
- ClinicalDecisionPolicy
- model-manifest.json
- verify_handwash_project.sh