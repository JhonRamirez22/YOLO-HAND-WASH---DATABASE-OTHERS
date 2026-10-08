---
type: "query"
date: "2026-10-08T00:41:56.285967+00:00"
question: "¿Qué bloquea hoy el paso a producción hospitalaria en el flujo de lavado YOLO-Java?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["hospital_readiness_blockers", "ClinicalDecisionPolicy"]
---

# Q: ¿Qué bloquea hoy el paso a producción hospitalaria en el flujo de lavado YOLO-Java?

## Answer

Expanded from graph vocabulary via [readiness, blockers, clinical, policy]. Graphify located hospital_readiness_blockers() and ClinicalDecisionPolicy; source review confirms hospital release requires signed evidence, exact data.yaml and taxonomy, independent video validation, camera pilot, clinical safety approval, and all WHO phases. ClinicalDecisionPolicy remains false for every current profile, so no success may be certified. The current gap is objective model/clinical evidence, not a code bypass; current tests should preserve these fail-closed gates.

## Outcome

- Signal: useful

## Source Nodes

- hospital_readiness_blockers
- ClinicalDecisionPolicy