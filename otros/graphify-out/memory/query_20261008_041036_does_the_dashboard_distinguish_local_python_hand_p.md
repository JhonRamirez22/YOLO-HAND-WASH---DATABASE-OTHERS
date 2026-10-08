---
type: "query"
date: "2026-10-08T04:10:36.091955+00:00"
question: "Does the dashboard distinguish local Python hand-presence warmup readiness from Java server-side warmup readiness? Trace the health endpoint, WebSocket state, SessionManager rejected-step reason, and frontend rendering."
contributor: "graphify"
outcome: "useful"
source_nodes: ["enqueue_latest_detection", "run_yolo26_continuity_camera.py", "SessionManager", "HandPresenceWarmup", "LiveCameraFeed.tsx", "StepStepper.tsx", "SessionManagerPresenceWarmupTest.java"]
---

# Q: Does the dashboard distinguish local Python hand-presence warmup readiness from Java server-side warmup readiness? Trace the health endpoint, WebSocket state, SessionManager rejected-step reason, and frontend rendering.

## Answer

Expanded from exact graph vocabulary: [dashboard, health, websocket, presence, warmup, readiness, session, server, steps, intention, state, reason]. Direct source review shows Java publishes a warmup rejection reason over the session state, while the camera health UI shows producer readiness. Found and reproduced a separate same-frame queue race: enqueue_latest_detection selected DETECTION before PRESENCE on equal source sequence due stable sort after priority ordering. This could drop the first candidate as Java reaches its 3s dwell. Added deterministic tie ordering CONTROL, PRESENCE, DETECTION and a regression test; synthetic replay now orders PRESENCE then DETECTION. Python camera tests 120 pass; Java warmup/integration tests 47 pass.

## Outcome

- Signal: useful

## Source Nodes

- enqueue_latest_detection
- run_yolo26_continuity_camera.py
- SessionManager
- HandPresenceWarmup
- LiveCameraFeed.tsx
- StepStepper.tsx
- SessionManagerPresenceWarmupTest.java