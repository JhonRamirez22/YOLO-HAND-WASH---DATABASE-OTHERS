---
type: "codebase"
date: "2026-10-08T00:55:17.505761+00:00"
question: "Can a negative System.nanoTime origin corrupt server event timestamps in the clinical evaluator?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["Receptor", "DeteccionEvento", "SeguimientoIntencion", "SesionOms", "EvaluadorSecuencia"]
---

# Q: Can a negative System.nanoTime origin corrupt server event timestamps in the clinical evaluator?

## Answer

The HTTP Receptor derives a process-relative elapsed timestamp from MONOTONIC_ORIGIN_NANOS and clamps the resulting milliseconds to at least 1 before observers receive the event. Direct source review confirms the partial and OMS evaluators consume this normalized positive value; don't remove their zero/negative validation without changing the shared clock contract.

## Outcome

- Signal: useful

## Source Nodes

- Receptor
- DeteccionEvento
- SeguimientoIntencion
- SesionOms
- EvaluadorSecuencia