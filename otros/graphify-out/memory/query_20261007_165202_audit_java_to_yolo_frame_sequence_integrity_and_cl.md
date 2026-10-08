---
type: "trace"
date: "2026-10-07T16:52:02.977515+00:00"
question: "Audit Java-to-YOLO frame sequence integrity and clinical approval gates"
contributor: "graphify"
outcome: "useful"
source_nodes: ["ClinicalDecisionPolicy StationReleaseManifestVerifier ProducerProtocolRegistry SessionManager Receptor EvaluadorSecuencia"]
---

# Q: Audit Java-to-YOLO frame sequence integrity and clinical approval gates

## Answer

Expanded from graph vocabulary: [clinical, decision, evidence, manifest, producer, protocol, release, security, sequence, signature, station, verify]. Graph located ClinicalDecisionPolicy, StationReleaseManifestVerifier, ProducerProtocolRegistry, SessionManager, Receptor, and EvaluadorSecuencia. Direct source audit confirmed v2 epoch/class/frame/evidence sequence checks and watermark reservation happen under the per-session lock before domain evaluation; invalid fresh observations break transition votes, while duplicate/out-of-order envelopes do not mutate the state. ClinicalDecisionPolicy remains false-only, consistent with current model evidence. No additional backend bypass was demonstrated. Verification: Maven backend suite 341/341 passed; frontend 61 tests, build, and lint passed; camera producer unit suite 93/93 passed without opening camera or loading model inference. The full handwash model is still not release-eligible: the signed release/model/data.yaml and independent clinical video validation are absent, and the active checkpoint's step semantics are unverified.

## Outcome

- Signal: useful

## Source Nodes

- ClinicalDecisionPolicy StationReleaseManifestVerifier ProducerProtocolRegistry SessionManager Receptor EvaluadorSecuencia