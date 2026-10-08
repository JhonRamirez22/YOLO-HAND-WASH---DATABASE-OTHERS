---
type: "query"
date: "2026-10-07T19:44:15.642986+00:00"
question: "Audit whether the hand-presence warmup makes clinical handwashing verification production-ready"
contributor: "graphify"
outcome: "useful"
source_nodes: ["CadenaIntencionLavado", "SeguimientoIntencion", "EvidenciaMovimiento", "motion_evidence_matches_frame()", "ClinicalDecisionPolicy", "StationReleaseManifestVerifier"]
---

# Q: Audit whether the hand-presence warmup makes clinical handwashing verification production-ready

## Answer

Expanded from graph vocabulary: [intention, motion, evidence, hands, confidence, sequence, fresh, gesture, threshold, start, pose]. Source-check confirms Java's intention chain requires fresh bilateral movement and sustained high-confidence palms, while its 1e-8 floor is not clinically calibrated. A seeded synthetic keypoint-jitter probe at 0.25–3 px crossed the numerical floor in 100/100 cases; this is a synthetic risk signal, not camera validation. Do not raise the threshold without target-camera stationary-hands and intentional-rubbing datasets. Clinical release remains NOT_READY: active seven-class checkpoint lacks its exact YAML/rubric, WHO full sequence is unsupported, split contamination is suspected, and independent camera/clinical approval is missing. Full project verification passed: 341 Java, 174 Python, 61 frontend tests; builds/lint and dependency scans clean. No training or physical camera access.

## Outcome

- Signal: useful

## Source Nodes

- CadenaIntencionLavado
- SeguimientoIntencion
- EvidenciaMovimiento
- motion_evidence_matches_frame()
- ClinicalDecisionPolicy
- StationReleaseManifestVerifier