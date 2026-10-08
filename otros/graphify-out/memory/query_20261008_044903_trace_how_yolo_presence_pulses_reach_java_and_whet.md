---
type: "query"
date: "2026-10-08T04:49:03.872428+00:00"
question: "Trace how YOLO presence pulses reach Java and whether queued stale hand evidence can count toward warmup."
contributor: "graphify"
outcome: "useful"
source_nodes: ["detection_sender", "enqueue_latest_detection", "ProducerProtocolRegistry", "HandPresenceWarmup"]
---

# Q: Trace how YOLO presence pulses reach Java and whether queued stale hand evidence can count toward warmup.

## Answer

Expanded from graph vocabulary: [producer, evidence, frame, sequence, presence, epoch, watermark, step, stale, accepted]. Graph traversal connected the Python producer sender and queue to ProducerProtocolRegistry, SessionManager, HandPresenceWarmup, and integration/unit tests. Direct source verification reproduced a concrete defect: positive PRESENCE observations older than Java's 500 ms freshness window were still posted after queue delay; Java then measured only receipt time. The producer now discards malformed, future-dated, or over-age presence pulses using its own monotonic capture timestamp before HTTP. Java's cross-process captureAgeMs remains diagnostic only. Added a regression test that failed before the fix; focused camera tests passed 121, Java presence/protocol tests passed 55, and full project verification passed including dependency scans, all Java/Python/frontend tests, preflight, build, and lint. No training or physical camera access.

## Outcome

- Signal: useful

## Source Nodes

- detection_sender
- enqueue_latest_detection
- ProducerProtocolRegistry
- HandPresenceWarmup