---
type: "query"
date: "2026-10-07T23:34:11.294509+00:00"
question: "Auditoría del estado actual para producción hospitalaria: detectar mejoras corregibles en Java, YOLO y verificación"
contributor: "graphify"
outcome: "useful"
source_nodes: ["ClinicalDecisionPolicy", "ProducerProtocolRegistry", "SessionManager", "StationSupervisorPolicyTest", "run_yolo26_continuity_camera.py"]
---

# Q: Auditoría del estado actual para producción hospitalaria: detectar mejoras corregibles en Java, YOLO y verificación

## Answer

El gate clínico permanece fail-closed: ClinicalDecisionPolicy devuelve false y el model-manifest declara NOT_READY; no habilitar ni presentar el sistema como clínicamente aprobado. El preflight oficial de run_yolo26_continuity_camera.py --check-model --check-hand-model --check-classifier-model valida hashes, tareas y roles de los tres pesos sin cámara ni entrenamiento, pero el detector paso_1…paso_7 no acredita semántica sin su data.yaml y rúbrica exactos. Se incorporó ese preflight a scripts/verify_handwash_project.sh y se aclaró que la suite técnica no autoriza uso hospitalario. Verificación completa: 347 Maven, 185 Python, 63 frontend, build/lint y SCA sin vulnerabilidades conocidas. Continuity Camera y evidencia clínica siguen pendientes. Query expanded from graph vocabulary: [clinical, station, model, validation, producer, session, step, sequence, backend, evidence].

## Outcome

- Signal: useful

## Source Nodes

- ClinicalDecisionPolicy
- ProducerProtocolRegistry
- SessionManager
- StationSupervisorPolicyTest
- run_yolo26_continuity_camera.py