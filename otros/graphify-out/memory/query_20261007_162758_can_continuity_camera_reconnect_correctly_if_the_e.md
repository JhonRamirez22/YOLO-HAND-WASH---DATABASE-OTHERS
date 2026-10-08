---
type: "trace"
date: "2026-10-07T16:27:58.442927+00:00"
question: "Can Continuity Camera reconnect correctly if the explicit AVFoundation index changes?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["Continuity Camera capture_frames reconnect select_iphone_camera avfoundation_listing"]
---

# Q: Can Continuity Camera reconnect correctly if the explicit AVFoundation index changes?

## Answer

Source inspection found capture_frames reused args.camera_index for every retry. If macOS reorders devices, it can keep probing the stale index and fail to recover even while the iPhone is available. Added reopen_iphone_camera() to re-enumerate and select only the iPhone for retries; initial explicit selection still validates device identity. Verified the extracted production functions with a mocked AVFoundation listing where FaceTime is index 0 and iPhone is index 3; reconnect launched FFmpeg with index 3. No inference or training run. The standard camera test module could not import because cv2 is absent from this Python environment; no dependency was installed.

## Outcome

- Signal: useful

## Source Nodes

- Continuity Camera capture_frames reconnect select_iphone_camera avfoundation_listing