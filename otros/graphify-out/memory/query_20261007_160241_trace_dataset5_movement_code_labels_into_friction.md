---
type: "query"
date: "2026-10-07T16:02:41.530358+00:00"
question: "Trace DataSet5 movement-code labels into friction classes and identify the faucet-closure mislabel."
contributor: "graphify"
outcome: "useful"
source_nodes: ["DataSet5 Dataset Preparation Pipeline", "dataset_contracts.py", ".test_faucet_closure_is_never_circular_friction", "train_dataset5.py", "train_v2.py"]
---

# Q: Trace DataSet5 movement-code labels into friction classes and identify the faucet-closure mislabel.

## Answer

Historical movement_code 7 meant faucet closure but was mapped to Paso7_Circulares; code 0 and code 7 now map to Fondo. The source contains no verified circular-friction class, so preparation fails closed. Versioned train/val contracts reject the historical YAML and validate all classes, paired files, and YOLO boxes. Training scripts no longer copy exported ONNX into backend/models. The active checkpoint's exact training YAML is absent, so its relation to this dataset remains unknown.

## Outcome

- Signal: useful

## Source Nodes

- DataSet5 Dataset Preparation Pipeline
- dataset_contracts.py
- .test_faucet_closure_is_never_circular_friction
- train_dataset5.py
- train_v2.py