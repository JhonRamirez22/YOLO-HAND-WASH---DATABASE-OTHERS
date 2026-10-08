---
type: "query"
date: "2026-10-08T20:17:47.149692+00:00"
question: "What owns the current Continuity Camera-to-dashboard video path?"
contributor: "graphify"
outcome: "corrected"
correction: "Ignore archived iOS camera nodes; current source is local Python capture plus MJPEG viewer, and latest user requirement excludes any iPhone app or separate iPhone webpage."
source_nodes: ["LiveCameraFeed", "MjpegFrameServer", "run_yolo26_continuity_camera.py", "frontend/AGENTS.md"]
---

# Q: What owns the current Continuity Camera-to-dashboard video path?

## Answer

Direct source verification: frontend LiveCameraFeed renders the local MJPEG endpoint and polls its health; it does not capture browser camera. scripts/run_yolo26_continuity_camera.py owns camera capture and YOLO locally. Archived iOS CameraManager is not active. For the requested AWS-hosted dashboard, preserve a single Mac browser UI and no iPhone app/page; camera input would need an explicit browser capture or local-agent transport path.

## Outcome

- Signal: corrected
- Correction: Ignore archived iOS camera nodes; current source is local Python capture plus MJPEG viewer, and latest user requirement excludes any iPhone app or separate iPhone webpage.

## Source Nodes

- LiveCameraFeed
- MjpegFrameServer
- run_yolo26_continuity_camera.py
- frontend/AGENTS.md