---
type: "query"
date: "2026-10-08T04:40:40.777432+00:00"
question: "Do the release manifest flags for active movement magnitude thresholds match Java behavior?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["CadenaIntencionLavado", "StationReleaseManifestVerifier", "run_handwash_station.py"]
---

# Q: Do the release manifest flags for active movement magnitude thresholds match Java behavior?

## Answer

Expanded from graph vocabulary: [clinical, threshold, movement, manifest, verifier, intent, calibrated, evidence, release, station]. Source verification shows CadenaIntencionLavado rejects movement at or below both configured start and step thresholds; StationReleaseManifestVerifier and the Python supervisor require both usage flags true and separately require clinical-calibration evidence. Corrected only the two factual usage flags to true. Calibration flags remain false, validationEvidence remains NOT_VALIDATED, and deploymentReadiness remains NOT_READY; no threshold behavior or clinical authorization changed.

## Outcome

- Signal: useful

## Source Nodes

- CadenaIntencionLavado
- StationReleaseManifestVerifier
- run_handwash_station.py