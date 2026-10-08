---
type: "query"
date: "2026-10-07T15:32:57.197619+00:00"
question: "Trace OMS phase transitions and canonical wire codes through API, summaries, and dashboard."
contributor: "graphify"
outcome: "useful"
source_nodes: ["SesionOms", "OmsActionResponse", "ProtocolCatalogMapper.java"]
---

# Q: Trace OMS phase transitions and canonical wire codes through API, summaries, and dashboard.

## Answer

Expanded from original query via graph vocabulary: [oms, action, phase, candidate, response, stepper, mapper, sequence, infraction, summary, soap]. Root cause: OMS exposed internal enum names for catalog, infrared step labels, timing/missing-step summaries; the dashboard maps only canonical OMS_* values. Corrected outputs to AccionOms.getClaseModelo(), preserving internal retry reason strings and fail-closed clinical gate. Java 341/341 tests and frontend 61/61 tests, build, and lint pass. No camera validation or model training.

## Outcome

- Signal: useful

## Source Nodes

- SesionOms
- OmsActionResponse
- ProtocolCatalogMapper.java