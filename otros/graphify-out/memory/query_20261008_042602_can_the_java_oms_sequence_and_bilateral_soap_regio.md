---
type: "query"
date: "2026-10-08T04:26:02.097537+00:00"
question: "Can the Java OMS sequence and bilateral soap-region evidence drift from the clinical protocol?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["SesionOms", "AccionOms", "RegionJabon", "StationReleaseManifestVerifier", "AccionOmsClinicalContractTest"]
---

# Q: Can the Java OMS sequence and bilateral soap-region evidence drift from the clinical protocol?

## Answer

Expanded from exact graph vocabulary: [oms, soap, region, evidence, sequence, phase]. Graph nodes SesionOms, AccionOms, RegionJabon, and StationReleaseManifestVerifier locate the sequence, temporal evaluator, 12 regional foam states, and release taxonomy gate. Direct WHO source review confirms the soap-and-water procedure is 11 ordered actions over 40–60 seconds. Source review showed the runtime order and six bilateral rubbing-region mappings are present; existing tests derived expected behavior from those same enums, so drift could escape. Added an independent Java contract test that pins the 11 wire-class order, next-action transitions, and exactly two regions for each rubbing phase. Java suite: 370 tests pass. This verifies software contract only; active weights, class semantics, clinical accuracy, and hospital release remain unvalidated.

## Outcome

- Signal: useful

## Source Nodes

- SesionOms
- AccionOms
- RegionJabon
- StationReleaseManifestVerifier
- AccionOmsClinicalContractTest