---
type: "query"
date: "2026-10-08T05:43:15.265083+00:00"
question: "Is the stored DataSet5 YAML safe for training, and does the full verifier enforce that?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["FONDO", "prepare_dataset5.py", "validate_dataset5_contract_file()", "dataset_contracts.py"]
---

# Q: Is the stored DataSet5 YAML safe for training, and does the full verifier enforce that?

## Answer

Expanded from the original audit with graph vocabulary [dataset, movement, code, step, faucet, fondo, circulares, labels, taxonomy, yaml, training, mapping]. Direct inspection confirms DataSet5 movement_code 7 means faucet closure and maps to Fondo, not Paso7_Circulares. The committed dataset5_combined.yaml is explicitly marked historical and has no projectDatasetContractVersion; both train_dataset5.py and train_v2.py call validate_dataset5_contract_file before training. Added a regression that loads this exact file and asserts preflight rejects it, and added test_dataset_contracts to verify_handwash_project.sh. Targeted tests passed 10/10; full offline verification passed with 210 Python tests, 371 Java, 63 frontend, builds/lint, and SCA scans. No training or camera was used. Model semantics and clinical validation remain unproven.

## Outcome

- Signal: useful

## Source Nodes

- FONDO
- prepare_dataset5.py
- validate_dataset5_contract_file()
- dataset_contracts.py