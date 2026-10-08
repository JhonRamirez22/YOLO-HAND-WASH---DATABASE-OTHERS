---
type: "query"
date: "2026-10-08T15:56:47.403008+00:00"
question: "Audita el flujo de presencia de manos, estado Java y dashboard para mejorar el sistema clínico"
contributor: "graphify"
outcome: "useful"
source_nodes: ["SessionManagerPresenceWarmupTest", "HandPresenceWarmup", "HandPresenceWarmupTest", "LiveCameraFeed.tsx", "SessionManager"]
---

# Q: Audita el flujo de presencia de manos, estado Java y dashboard para mejorar el sistema clínico

## Answer

Expanded from original query via graph vocabulary [hand, presence, warmup, session, state, status, step, feed, enabled, reason]. Graph and direct source inspection confirm the local YOLO warmup is not the authority: Java independently gates v2 step events using monotonic receive time and fresh bilateral presence; StepStepper shows Java intention state/reason, while LiveCameraFeed reports camera-side warmup. No demonstrated correctness defect in this gate, so avoid duplicating it or auto-starting a wash from mere hand presence. Full verification passed SCA, 372 Java tests, 213 Python tests, 63 frontend tests, TypeScript build, lint, and model structural preflight. The active checkpoint's generic paso_1…paso_7 mapping remains unverified; manifest remains NOT_READY and hospital use disallowed. No model training, live camera, or source changes.

## Outcome

- Signal: useful

## Source Nodes

- SessionManagerPresenceWarmupTest
- HandPresenceWarmup
- HandPresenceWarmupTest
- LiveCameraFeed.tsx
- SessionManager