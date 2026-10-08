---
type: "query"
date: "2026-10-08T04:20:51.952232+00:00"
question: "Continue improving the clinical handwash project by auditing the hand-presence gate and step recognition end to end."
contributor: "graphify"
outcome: "useful"
source_nodes: ["backend/src/main/java/com/handwash/intention/HandPresenceWarmup.java", "SessionManager", "SessionManagerPresenceWarmupTest.java", "run_yolo26_continuity_camera.py", "ClinicalDecisionPolicy"]
---

# Q: Continue improving the clinical handwash project by auditing the hand-presence gate and step recognition end to end.

## Answer

Expanded from exact graph vocabulary: [hand, presence, warmup, step, evidence, sequence]. The graph locates HandPresenceWarmup, SessionManager, and SessionManagerPresenceWarmupTest. Direct source review confirms Python and Java gates require fresh bilateral presence for 3000 ms; Java uses its monotonic receive clock and a 500 ms maximum gap, and rejects ordinary step events before readiness. The camera queue must deliver a same-frame PRESENCE pulse before its DETECTION candidate; the regression now enqueues detection first to prove the sorter restores that safe order. ClinicalDecisionPolicy remains false-only; model taxonomy and independent clinical accuracy remain unverified.

## Outcome

- Signal: useful

## Source Nodes

- backend/src/main/java/com/handwash/intention/HandPresenceWarmup.java
- SessionManager
- SessionManagerPresenceWarmupTest.java
- run_yolo26_continuity_camera.py
- ClinicalDecisionPolicy