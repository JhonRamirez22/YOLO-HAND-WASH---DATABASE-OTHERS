---
type: "query"
date: "2026-10-08T03:09:01.939018+00:00"
question: "¿Es utilizable runs/detect/handwash-v2-yolo26s como reemplazo del detector activo?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["StationReleaseManifestVerifier", "StationReleaseManifestVerifierTest", "validate_step_model", "run_yolo26_continuity_camera.py"]
---

# Q: ¿Es utilizable runs/detect/handwash-v2-yolo26s como reemplazo del detector activo?

## Answer

Expanded from graph vocabulary: class, clinical, demo, label, manifest, mapping, model, release, station, step, taxonomy, validation. The graph located the model validation/release gate; authoritative source inspection found this run has args.yaml and results.csv only, with no weights/best.pt. It was configured for 300 epochs but has 33 recorded; best mAP50=0.38866 and mAP50-95=0.27392 at epoch 21; final mAP50=0.29943 and mAP50-95=0.20036 at epoch 33. args.yaml points to a machine-specific DataSet5 dataset path but does not bind its exact bytes; the matching local dataset5_combined.yaml is explicitly marked as historically invalid because movement_code 7 (faucet closure) was mislabeled Paso7_Circulares. Therefore it is not loadable or eligible as a release candidate. Recorded this finding in backend/models/model-manifest.json under investigatedTrainingRuns. No training or camera test was performed.

## Outcome

- Signal: useful

## Source Nodes

- StationReleaseManifestVerifier
- StationReleaseManifestVerifierTest
- validate_step_model
- run_yolo26_continuity_camera.py