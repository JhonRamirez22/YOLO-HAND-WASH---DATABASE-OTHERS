---
type: "query"
date: "2026-10-07T18:33:29.058247+00:00"
question: "How does the producer gate partial handwashing step detection until bilateral hand presence has been continuously confirmed?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["HandPresenceWarmup", "run_yolo26_continuity_camera.py", "SessionManager", "CadenaIntencionLavado"]
---

# Q: How does the producer gate partial handwashing step detection until bilateral hand presence has been continuously confirmed?

## Answer

Graphify links HandPresenceWarmup to the camera producer run(); source inspection confirms the gate counts only unique fresh frames with two distinct valid poses, resets on a missing hand or gap > min(hand-max-age, 650ms), suppresses step-model inference until default 3000ms, and leaves Java's start/sequence rules authoritative. The station supervisor blocks overrides; manifest remains NOT_READY because models lack independent multiview/clinical validation.

## Outcome

- Signal: useful

## Source Nodes

- HandPresenceWarmup
- run_yolo26_continuity_camera.py
- SessionManager
- CadenaIntencionLavado