---
type: "query"
date: "2026-10-07T05:26:32.010058+00:00"
question: "¿Qué ruta valida el gate clínico y los eventos v2 del productor?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["ClinicalDecisionPolicy", "SessionManager", "ProducerProtocolRegistry", "StationReleaseManifestVerifier"]
---

# Q: ¿Qué ruta valida el gate clínico y los eventos v2 del productor?

## Answer

Expanded from graph vocabulary: [station, clinical, decision, policy, release, manifest, producer, protocol, registry, session, manager, sequence]. Graph traverses ClinicalDecisionPolicy (backend/src/main/java/com/handwash/service/ClinicalDecisionPolicy.java:L12), SessionManager (backend/src/main/java/com/handwash/service/SessionManager.java:L33), and ProducerProtocolRegistry (backend/src/main/java/com/handwash/service/ProducerProtocolRegistry.java:L18). Source inspection confirms SessionManager authenticates and serializes registerEpoch/assessAndReserve under the per-session monitor; the detector HTTP controller is the handoff. ClinicalDecisionPolicy currently returns false for every profile. StationReleaseManifestVerifier requires signed readiness, exact model/taxonomy and artifact hashes. Current manifest is NOT_READY with a seven-class detector, so no hospital approval is possible. Graph may lag uncommitted tree; verify current source before relying on edges.

## Outcome

- Signal: useful

## Source Nodes

- ClinicalDecisionPolicy
- SessionManager
- ProducerProtocolRegistry
- StationReleaseManifestVerifier