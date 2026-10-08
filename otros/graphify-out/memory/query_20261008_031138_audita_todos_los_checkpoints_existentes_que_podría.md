---
type: "query"
date: "2026-10-08T03:11:38.770095+00:00"
question: "audita todos los checkpoints existentes que podrían mejorar la detección de lavado/intención sin entrenar"
contributor: "graphify"
outcome: "useful"
source_nodes: ["verify_model_artifact", "validate_step_model", "run_yolo26_continuity_camera.py"]
---

# Q: audita todos los checkpoints existentes que podrían mejorar la detección de lavado/intención sin entrenar

## Answer

Expanded from graph vocabulary: active, artifact, candidate, checkpoint, detector, hash, manifest, model, source, training, weights. Graphify located the artifact/hash gate and active model validation; direct inventory of ignored files found a pre-existing context checkpoint at runs/detect/handwash-hygiene-transfer/20260925-230123/context/weights/best.pt. Its YAML config declares only Performing-Hand-Hygiene, not seven steps; args record 3/20 epochs on CPU, validation mAP50 0.97888 and mAP50-95 0.53631 at epoch 3, with no independent idle-hands negative evaluation. The planned seven-step weights are absent. Classified as context/intent research only, not a step detector or release candidate; recorded this and the observed digest in model-manifest.json without a runtime sha256 registration. verify_model_artifact correctly rejects this checkpoint as unregistered. No checkpoint was loaded for inference, activated, or trained; no camera was used.

## Outcome

- Signal: useful

## Source Nodes

- verify_model_artifact
- validate_step_model
- run_yolo26_continuity_camera.py