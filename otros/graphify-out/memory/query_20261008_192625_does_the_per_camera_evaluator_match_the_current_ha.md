---
type: "query"
date: "2026-10-08T19:26:25.924866+00:00"
question: "Does the per-camera evaluator match the current hand-pose recovery path?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["hand_recovery_tiles", "run_yolo26_continuity_camera.py", "evaluate_derived_detector.py"]
---

# Q: Does the per-camera evaluator match the current hand-pose recovery path?

## Answer

Expanded from graph vocabulary via [pose, camera, model, recovery, hand, evaluate, motion, sequence, tile]. Direct source confirmed evaluator had only full-frame recovery, unlike active capture's recover_hand_pose full-frame plus two overlapping tiles. Evaluator now shares that function and reports extra inference count. Balanced inference-only sample: 161/235 bilateral-pose frames, 178/235 combined pre-gate matches, 5 negative-class proposals. Diagnostic only, not clinical or angle-holdout evidence.

## Outcome

- Signal: useful

## Source Nodes

- hand_recovery_tiles
- run_yolo26_continuity_camera.py
- evaluate_derived_detector.py