---
type: "query"
date: "2026-10-08T05:26:30.411807+00:00"
question: "Trace the live YOLO-to-Java sequence path and identify any producer/consumer sequencing race."
contributor: "graphify"
outcome: "useful"
source_nodes: ["run_yolo26_continuity_camera.py", "ProducerProtocolRegistry", "SessionManager", "DetectionApiIntegrationTest"]
---

# Q: Trace the live YOLO-to-Java sequence path and identify any producer/consumer sequencing race.

## Answer

Expanded against graph vocabulary with [yolo, step, classifier, producer, bilateral, evidence, intention, strategy, state, sequence, detection, ack]. The graph locates the camera producer, ProducerProtocolRegistry, SessionManager and integration tests, but its Python-to-Java relations are not proof. Direct source review confirms: presence pulses carry a separate controlSequence and frameWatermark; the same-frame step may follow a presence pulse, older detections are rejected, and the sender coalesces updates by class and source sequence. No sequencing defect reproduced. Continue validating clinically against independent video; current model remains NOT_READY.

## Outcome

- Signal: useful

## Source Nodes

- run_yolo26_continuity_camera.py
- ProducerProtocolRegistry
- SessionManager
- DetectionApiIntegrationTest