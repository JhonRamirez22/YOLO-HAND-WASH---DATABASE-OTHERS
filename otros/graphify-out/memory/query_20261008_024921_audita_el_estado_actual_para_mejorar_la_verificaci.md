---
type: "query"
date: "2026-10-08T02:49:21.385561+00:00"
question: "audita el estado actual para mejorar la verificación YOLO paso a paso y el backend Java hacia uso hospitalario"
contributor: "graphify"
outcome: "useful"
source_nodes: ["run_yolo26_continuity_camera.py", "validate_step_model", "StationReleaseManifestVerifier", "StationProfileSafetyGuard", "HandPresenceWarmup"]
---

# Q: audita el estado actual para mejorar la verificación YOLO paso a paso y el backend Java hacia uso hospitalario

## Answer

Expanded from graph vocabulary: bilateral, confidence, evidence, friction, intention, motion, movement, pose, sequence, step, threshold, validation. Graphify guided source inspection; direct source and the repository verification script were authoritative. The 3 s two-hand warmup exists on both Python and Java. Full verification passed: dependency scans found no known vulnerabilities, Java 368 tests, Python 195 tests, active model structural preflight, frontend 63 tests/build/lint. Crucial unresolved clinical blockers remain in backend/models/model-manifest.json: NOT_READY, generic paso_1..paso_7 labels without exact data.yaml/rubric, non-independent/leaky validation splits, partial friction-only coverage instead of complete WHO sequence, unvalidated movement threshold/intent, no target-camera hospital pilot or independent safety review, and unsigned/missing release artifacts. Do not bypass the release gate or call the system hospital-ready; no training or camera test was performed.

## Outcome

- Signal: useful

## Source Nodes

- run_yolo26_continuity_camera.py
- validate_step_model
- StationReleaseManifestVerifier
- StationProfileSafetyGuard
- HandPresenceWarmup