---
type: "architecture"
date: "2026-10-07T21:13:50.342896+00:00"
question: "Does the camera gate reliably wait for both hands before step inference and preserve independent Java intent confirmation?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["HandPresenceWarmup", "CadenaIntencionLavado", "SeguimientoIntencion", "StationSupervisor"]
---

# Q: Does the camera gate reliably wait for both hands before step inference and preserve independent Java intent confirmation?

## Answer

Yes, source inspection and tests confirm the existing --hand-presence-warmup-ms defaults to 3000 ms, requires two fresh bilateral poses continuously, resets before Java start on a missing hand or excessive gap, blocks partial step inference until fresh bilateral evidence, and the hospital supervisor rejects attempts to override it. Java independently requires canonical palms, confidence, fresh bilateral spatial evidence, motion above numerical zero, and temporal confirmation. This is a readiness safeguard, not clinical validation; the active model still lacks WHO action coverage and hospital release remains NOT_READY.

## Outcome

- Signal: useful

## Source Nodes

- HandPresenceWarmup
- CadenaIntencionLavado
- SeguimientoIntencion
- StationSupervisor