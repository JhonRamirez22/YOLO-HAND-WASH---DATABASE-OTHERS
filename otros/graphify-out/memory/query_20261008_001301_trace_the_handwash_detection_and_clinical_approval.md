---
type: "query"
date: "2026-10-08T00:13:01.656892+00:00"
question: "Trace the handwash detection and clinical-approval safeguards across YOLO, Java, and dashboard."
contributor: "graphify"
outcome: "useful"
source_nodes: ["HandPresenceWarmup", "SessionManager", "ProducerProtocolRegistry", "CadenaIntencionLavado", "ClinicalDecisionPolicy", "run_yolo26_continuity_camera.py"]
---

# Q: Trace the handwash detection and clinical-approval safeguards across YOLO, Java, and dashboard.

## Answer

Expanded from graph vocabulary: [hand, hands, presence, warmup, sequence, intent, detection, evidence, model, yolo, clinical, failure, threshold, session, movement, state, strategy, observer]. Graph indicates Python YOLO sends detections to Java SessionManager/ProducerProtocolRegistry, Java applies presence, intent, State/Strategy and publishes via Notificador; ClinicalDecisionPolicy is the separate fail-closed approval owner. Source inspection confirmed the three-second bilateral warmup and that the active checkpoint taxonomy and validation evidence remain unverified; the graph is navigation only, source files and tests are authoritative.

## Outcome

- Signal: useful

## Source Nodes

- HandPresenceWarmup
- SessionManager
- ProducerProtocolRegistry
- CadenaIntencionLavado
- ClinicalDecisionPolicy
- run_yolo26_continuity_camera.py