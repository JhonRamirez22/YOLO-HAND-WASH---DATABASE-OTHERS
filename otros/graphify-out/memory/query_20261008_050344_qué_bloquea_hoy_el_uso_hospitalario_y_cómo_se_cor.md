---
type: "query"
date: "2026-10-08T05:03:44.766914+00:00"
question: "¿Qué bloquea hoy el uso hospitalario y cómo se corrigió el desfase entre la compuerta local y Java?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["HandPresenceWarmup", "run_yolo26_continuity_camera.py", "StationReleaseManifestVerifier", "ClinicalDecisionPolicy", "validate_step_model"]
---

# Q: ¿Qué bloquea hoy el uso hospitalario y cómo se corrigió el desfase entre la compuerta local y Java?

## Answer

Expanded from original query via vocab: [model, manifest, station, release, clinical, validation, class, taxonomy, checkpoint, signature, approval, label]. Verificación del código: run_yolo26_continuity_camera.HandPresenceWarmup podría reiniciar su espera local de 3 s durante la demora de monitor_session aunque Java ya hubiese aceptado el inicio; al recibir session_started ahora se reconcilia el estado local, pero solo observaciones bilaterales frescas abren pasos y Java conserva su compuerta autoritativa. La regresión falló antes del fix y pasó después. Gate de release: el detector real declara paso_1…paso_7; no se encontró el data.yaml exacto ni la rúbrica del entrenamiento activo; el manifiesto está NOT_READY, la verificación independiente no es elegible y ClinicalDecisionPolicy mantiene aprobación false. No entrenar ni relajar el gate: se requieren pesos/taxonomía verificables, validación independiente por video/ángulo y revisión clínica.

## Outcome

- Signal: useful

## Source Nodes

- HandPresenceWarmup
- run_yolo26_continuity_camera.py
- StationReleaseManifestVerifier
- ClinicalDecisionPolicy
- validate_step_model