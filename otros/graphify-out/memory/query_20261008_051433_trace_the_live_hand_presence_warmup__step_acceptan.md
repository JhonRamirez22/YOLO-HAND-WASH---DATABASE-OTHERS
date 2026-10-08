---
type: "query"
date: "2026-10-08T05:14:33.549832+00:00"
question: "Trace the live hand-presence warmup, step acceptance, and clinical-approval path for production readiness."
contributor: "graphify"
outcome: "useful"
source_nodes: ["HandPresenceWarmup", "SessionManager", "ProducerProtocolRegistry", "ClinicalDecisionPolicy", "Notificador"]
---

# Q: Trace the live hand-presence warmup, step acceptance, and clinical-approval path for production readiness.

## Answer

Expanded from graph vocabulary: [clinical, authorized, model, manifest, detection, evidence, sequence, session, hands, intent, warmup, yolo]. Graph query surfaced HandPresenceWarmup, SessionManager, ProducerProtocolRegistry, ClinicalDecisionPolicy, Notificador, and the YOLO producer, but the graph path was broad/ambiguous and did not prove correctness. Direct source review plus scripts/verify_handwash_project.sh confirmed: 3000 ms bilateral presence is server-timed and stale presence blocks steps; presence alone does not start a wash; clinical approval remains false-only. Current active model remains NOT_READY because its training YAML/rubric and independent camera/video validation are absent. Do not weaken release gates; source-of-truth files and full tests must be rechecked.

## Outcome

- Signal: useful

## Source Nodes

- HandPresenceWarmup
- SessionManager
- ProducerProtocolRegistry
- ClinicalDecisionPolicy
- Notificador