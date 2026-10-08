---
type: "query"
date: "2026-10-07T20:22:04.271706+00:00"
question: "¿El contador de 3 segundos de manos puede mostrar progreso desactualizado cuando YOLO deja de actualizar poses?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["HandPresenceWarmup", "run_yolo26_continuity_camera.py", "ContinuityCameraDetectionTest"]
---

# Q: ¿El contador de 3 segundos de manos puede mostrar progreso desactualizado cuando YOLO deja de actualizar poses?

## Answer

Expanded from original query via graph vocabulary: [presence, warmup, step, render, fresh, stream, detector, camera, hand, sequence]. Direct source inspection found that the camera renderer displayed HandPresenceWarmup.elapsed_ms without checking the age of the last bilateral pose, while step inference separately blocked stale evidence. Fixed only the display projection with fresh_hand_presence_progress_ms: it reports zero progress for stale, unilateral, invalid, or future-dated presence samples and clamps progress to required_ms. Added a regression test for the freshness boundary and unilateral pose. No inference thresholds, warmup timing, Java state, model, or clinical policy changed. Relevant source: scripts/run_yolo26_continuity_camera.py and scripts/test_run_yolo26_continuity_camera.py.

## Outcome

- Signal: useful

## Source Nodes

- HandPresenceWarmup
- run_yolo26_continuity_camera.py
- ContinuityCameraDetectionTest