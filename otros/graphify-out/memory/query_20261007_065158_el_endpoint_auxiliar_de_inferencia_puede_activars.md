---
type: "query"
date: "2026-10-07T06:51:58.471057+00:00"
question: "¿El endpoint auxiliar de inferencia puede activarse en la estación hospitalaria?"
contributor: "graphify"
outcome: "corrected"
correction: "El endpoint diagnóstico no puede habilitarse en station: el supervisor lo fija en false y el guard Java rechaza true."
source_nodes: ["station_backend_environment", "InferenceController", "StationProfileSafetyGuard", "StationSupervisorPolicyTest"]
---

# Q: ¿El endpoint auxiliar de inferencia puede activarse en la estación hospitalaria?

## Answer

Expanded from graph vocab [station, inference, api, diagnostic, environment, override]. El grafo señala station_backend_environment y una prueba de inferencia sin epoch v2. Inspección directa confirma que el supervisor fija HANDWASH_INFERENCE_API_ENABLED=false y StationProfileSafetyGuard.validateConfiguration rechaza handwash.inference.api-enabled=true (L236-237); el endpoint también está condicionado por esa propiedad. No hay bypass corregible aquí; preservar el cierre.

## Outcome

- Signal: corrected
- Correction: El endpoint diagnóstico no puede habilitarse en station: el supervisor lo fija en false y el guard Java rechaza true.

## Source Nodes

- station_backend_environment
- InferenceController
- StationProfileSafetyGuard
- StationSupervisorPolicyTest