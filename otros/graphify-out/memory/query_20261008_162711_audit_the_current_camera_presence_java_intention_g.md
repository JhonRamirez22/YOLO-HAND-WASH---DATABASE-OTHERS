---
type: "query"
date: "2026-10-08T16:27:11.705735+00:00"
question: "Audit the current camera-presence/Java-intention gate and fix any UI mismatch that could make step progression appear stuck."
contributor: "graphify"
outcome: "corrected"
correction: "Treat graph results from archive/legacy-fastapi as historical, not the active clinical workflow. The active server-owned presence gate and UI mismatch were verified in current source; the release manifest still blocks hospital use."
source_nodes: ["SessionManager", "ProducerProtocolRegistry", "ClinicalDecisionPolicy"]
---

# Q: Audit the current camera-presence/Java-intention gate and fix any UI mismatch that could make step progression appear stuck.

## Answer

Expanded query tokens from graph vocabulary: [model, yolo, hand, detection, evidence, intention, sequence, strategy, session, protocol, clinical, validation]. The broad graph traversal included archived legacy FastAPI/WHO nodes; those are not the active path. Direct source inspection confirms the current producer reports a local Python presence gate while Java independently enforces a server-received 3 s bilateral warmup in SessionManager/HandPresenceWarmup. LiveCameraFeed previously used local stepsEnabled to say to begin with palms, even while Java intention state could still be MANOS_PRESENTES or PAUSA. Updated only the UI status copy to distinguish local hand detection from Java-confirmed step tracking; added two regressions. Frontend suite (65 tests), typecheck/build, lint, and Impeccable detector pass. Clinical readiness remains NOT_READY; the active model taxonomy, full WHO phases, calibrated intent and independent validation remain unverified.

## Outcome

- Signal: corrected
- Correction: Treat graph results from archive/legacy-fastapi as historical, not the active clinical workflow. The active server-owned presence gate and UI mismatch were verified in current source; the release manifest still blocks hospital use.

## Source Nodes

- SessionManager
- ProducerProtocolRegistry
- ClinicalDecisionPolicy