---
type: "codebase"
date: "2026-10-08T00:55:17.505814+00:00"
question: "How is the WHO handwashing sequence represented and prevented from producing an unsupported clinical approval?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["AccionOms", "SesionOms", "Notificador", "ClinicalDecisionPolicy", "DetectionApiIntegrationTest"]
---

# Q: How is the WHO handwashing sequence represented and prevented from producing an unsupported clinical approval?

## Answer

AccionOms.SECUENCIA contains 11 ordered actions from wetting through closing the faucet with a towel; the active OMS evaluator requires order, phase observation and duration, while Notificador combines procedure evidence with ClinicalDecisionPolicy. ClinicalDecisionPolicy returns false for every current profile. Direct source review is authoritative; the graph traversal was broad/noisy.

## Outcome

- Signal: useful

## Source Nodes

- AccionOms
- SesionOms
- Notificador
- ClinicalDecisionPolicy
- DetectionApiIntegrationTest