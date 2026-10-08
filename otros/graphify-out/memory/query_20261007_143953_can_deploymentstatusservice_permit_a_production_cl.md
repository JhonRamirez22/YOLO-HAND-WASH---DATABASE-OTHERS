---
type: "query"
date: "2026-10-07T14:39:53.429119+00:00"
question: "Can DeploymentStatusService permit a production clinical decision today?"
contributor: "graphify"
outcome: "corrected"
correction: "Do not loosen the current false-only validator. Current profiles must stay unauthorized; introduce an explicit production mode only alongside a separately signed and reviewed backend authorization path."
source_nodes: ["DeploymentStatusController", "ClinicalDecisionPolicy", "DeploymentStatusService"]
---

# Q: Can DeploymentStatusService permit a production clinical decision today?

## Answer

Expanded from the graph vocabulary: [deployment, status, clinical, decision, policy]. The backend currently emits only DEVELOPMENT, NON_CLINICAL_DEMO, or HOSPITAL_PILOT, and ClinicalDecisionPolicy keeps authorization false in all profiles. The frontend rejecting true for those current modes is intentional fail-closed behavior, not a present defect. A future production mode must be separately authorized and added coherently to the backend response and frontend mode union.

## Outcome

- Signal: corrected
- Correction: Do not loosen the current false-only validator. Current profiles must stay unauthorized; introduce an explicit production mode only alongside a separately signed and reviewed backend authorization path.

## Source Nodes

- DeploymentStatusController
- ClinicalDecisionPolicy
- DeploymentStatusService