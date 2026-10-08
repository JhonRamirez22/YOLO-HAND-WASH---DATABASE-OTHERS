---
type: "query"
date: "2026-10-07T20:02:38.103238+00:00"
question: "Diagnose the isolated DetectionApiIntegrationTest failure for OMS_SIN_EVIDENCIA and verify actual behavior"
contributor: "graphify"
outcome: "useful"
source_nodes: ["DetectionApiIntegrationTest", "SesionOms", "SessionManager", "CONTACTO_RIESGO"]
---

# Q: Diagnose the isolated DetectionApiIntegrationTest failure for OMS_SIN_EVIDENCIA and verify actual behavior

## Answer

Expanded from graph vocabulary: oms, contact, risk, session, manager, integration, restart. One full Maven run with other checks running concurrently showed a single OMS integration assertion failure. The exact test passed alone, the complete DetectionApiIntegrationTest class passed, and a subsequent isolated full Maven suite passed 341 tests. No implementation defect was reproduced; do not change fail-closed OMS behavior based on the transient result. Revisit only if the failure recurs under an isolated run.

## Outcome

- Signal: useful

## Source Nodes

- DetectionApiIntegrationTest
- SesionOms
- SessionManager
- CONTACTO_RIESGO