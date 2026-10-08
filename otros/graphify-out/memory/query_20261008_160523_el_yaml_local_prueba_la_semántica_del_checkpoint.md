---
type: "query"
date: "2026-10-08T16:05:23.312595+00:00"
question: "¿El YAML local prueba la semántica del checkpoint activo y permite validar su precisión para hospital?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["validate_step_model", "StationReleaseManifestVerifier", "model-manifest.json"]
---

# Q: ¿El YAML local prueba la semántica del checkpoint activo y permite validar su precisión para hospital?

## Answer

Expanded from graph vocabulary: dataset model manifest classes label taxonomy mapping validation yaml release readiness detector. Direct-source verification: the local grouped 7-class data.yaml names canonical project steps, but the active checkpoint is recorded with generic paso_1…paso_7 labels and trainingDataConfigPath=/content/YOLO_Handwash_7pasos_real_labels/data.yaml, which is not included and has no SHA-256. Therefore the local candidate YAML does not prove it produced those weights. The grouped test split is explicitly ineligible for active-checkpoint validation: 111 of 121 images overlap the original training split; video-level separation is unproven. Current preflight confirms structural compatibility only and emits the taxonomy warning. deploymentReadiness remains NOT_READY/hospitalUseAllowed=false. No model was trained and no source code changed.

## Outcome

- Signal: useful

## Source Nodes

- validate_step_model
- StationReleaseManifestVerifier
- model-manifest.json