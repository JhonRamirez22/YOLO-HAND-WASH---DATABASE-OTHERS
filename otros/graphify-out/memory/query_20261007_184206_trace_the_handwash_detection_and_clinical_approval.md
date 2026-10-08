---
type: "query"
date: "2026-10-07T18:42:06.973420+00:00"
question: "Trace the handwash detection and clinical-approval safeguards across YOLO, Java, and dashboard."
contributor: "graphify"
outcome: "useful"
source_nodes: ["SesionLavado", "CadenaIntencionLavado", "SeguimientoIntencion", "ClinicalDecisionPolicy", "SessionSummary"]
---

# Q: Trace the handwash detection and clinical-approval safeguards across YOLO, Java, and dashboard.

## Answer

Expanded query from the exact graph vocabulary: [sesion, secuencia, intencion, clinical, decision, state, bilateral, evidence]. Graph links DetectionController/SessionManager with SesionLavado and CadenaIntencionLavado. Source verification and tests show producer-v2 observations require fresh bilateral movement evidence; Java confirms sustained Palmas and ordered State transitions, while ClinicalDecisionPolicy always returns false and the dashboard downgrades any backend approval unless deployment authorization and procedure validation are both true. The current active model still covers only seven unverified friction classes; the OMS/full procedure and hospital release remain NOT_READY, so code tests do not prove clinical accuracy.

## Outcome

- Signal: useful

## Source Nodes

- SesionLavado
- CadenaIntencionLavado
- SeguimientoIntencion
- ClinicalDecisionPolicy
- SessionSummary