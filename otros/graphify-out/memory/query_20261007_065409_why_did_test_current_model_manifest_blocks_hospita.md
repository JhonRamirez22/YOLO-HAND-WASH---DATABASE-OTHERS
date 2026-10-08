---
type: "query"
date: "2026-10-07T06:54:09.793129+00:00"
question: "Why did test_current_model_manifest_blocks_hospital_station_readiness fail?"
contributor: "graphify"
outcome: "corrected"
correction: "The runtime gate was not broken. Update the assertion to check the current blocker phrase, real rubbing intent is not independently validated."
source_nodes: ["test_current_model_manifest_blocks_hospital_station_readiness", "model-manifest.json"]
---

# Q: Why did test_current_model_manifest_blocks_hospital_station_readiness fail?

## Answer

The hospital station test was stale after the model manifest blocker wording changed to describe real rubbing intent as not independently validated. Updated its assertion to the current semantic blocker; the station suite then passed 41 tests.

## Outcome

- Signal: corrected
- Correction: The runtime gate was not broken. Update the assertion to check the current blocker phrase, real rubbing intent is not independently validated.

## Source Nodes

- test_current_model_manifest_blocks_hospital_station_readiness
- model-manifest.json