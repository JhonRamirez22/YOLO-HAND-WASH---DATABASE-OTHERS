---
type: "query"
date: "2026-10-08T03:23:57.408454+00:00"
question: "¿Cómo se sincroniza la frescura de presencia bilateral entre YOLO, el dashboard y Java?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["HandPresenceWarmup", "bilateral_presence_is_fresh", "run_yolo26_continuity_camera.py", "application-station.yml"]
---

# Q: ¿Cómo se sincroniza la frescura de presencia bilateral entre YOLO, el dashboard y Java?

## Answer

Expanded from graph vocabulary: [bilateral, detection, evidence, frame, hand, intent, motion, pose, presence, sequence, threshold, warmup]. Graph located HandPresenceWarmup, bilateral_presence_is_fresh(), the camera run loop, and station profile tests. Direct source audit found Python had a 650 ms freshness window while Java station requires 500 ms; this could show steps enabled while Java filtered them. Aligned Python warmup, inference gate, health endpoint, and dashboard progress to a 500 ms ceiling, tested both locked Spring profiles and the exact 500/501 ms boundary. Java station remains authoritative.

## Outcome

- Signal: useful

## Source Nodes

- HandPresenceWarmup
- bilateral_presence_is_fresh
- run_yolo26_continuity_camera.py
- application-station.yml