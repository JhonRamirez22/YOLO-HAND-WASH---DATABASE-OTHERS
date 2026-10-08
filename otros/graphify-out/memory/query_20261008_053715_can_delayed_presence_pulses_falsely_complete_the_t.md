---
type: "query"
date: "2026-10-08T05:37:15.711018+00:00"
question: "Can delayed presence pulses falsely complete the three-second hand warmup?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["HandPresenceWarmup", "SessionManager", "ProducerEpochStream", "StationReleaseManifestVerifier"]
---

# Q: Can delayed presence pulses falsely complete the three-second hand warmup?

## Answer

Expanded from the original audit using graph vocabulary [hand, presence, warmup, step, sequence, intention, clinical, movement, evidence, station, manifest, release]. Graph path identifies HandPresenceWarmup and SessionManager; direct source verification shows the Python sender drops a presence sample once its same-process age exceeds 500 ms and does not retry bilateral-presence pulses. Java separately measures the dwell with its monotonic ingress clock, requires increasing frame watermarks, two hands, and gaps no greater than 500 ms; stale bilateral evidence blocks step events before State, Strategy, and Observer. Existing sender and Java tests cover stale presence and the server dwell. No delayed-pulse defect found. Separate release blocker remains: model labels are generic paso_1...paso_7, training YAML/rubric absent, and hospital readiness is NOT_READY.

## Outcome

- Signal: useful

## Source Nodes

- HandPresenceWarmup
- SessionManager
- ProducerEpochStream
- StationReleaseManifestVerifier