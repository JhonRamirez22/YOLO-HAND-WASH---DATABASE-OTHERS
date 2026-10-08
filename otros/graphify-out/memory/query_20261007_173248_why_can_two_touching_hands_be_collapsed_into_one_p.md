---
type: "query"
date: "2026-10-07T17:32:48.114987+00:00"
question: "Why can two touching hands be collapsed into one pose in the camera pipeline?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["HandMotionEstimator", "MotionTest", "poses"]
---

# Q: Why can two touching hands be collapsed into one pose in the camera pipeline?

## Answer

Expanded from graph vocabulary: [camera, evidence, estimator, friction, keypoint, motion, pose, recent, sequence, threshold, valid, validate]. The graph locates HandMotionEstimator and its tests, but the exact duplicate-suppression cause was verified in scripts/run_yolo26_continuity_camera.py: hand_pose_candidates marks overlapping boxes as duplicates when both center distance and median shared-keypoint shift pass thresholds. A synthetic regression reproduced two close poses being collapsed at the former 0.18-diagonal joint threshold; tightening to 0.14 retains the 10 px shifted pair while 5 px jitter remains deduplicated. This is a geometric regression check only; live camera and model-level accuracy remain unverified.

## Outcome

- Signal: useful

## Source Nodes

- HandMotionEstimator
- MotionTest
- poses