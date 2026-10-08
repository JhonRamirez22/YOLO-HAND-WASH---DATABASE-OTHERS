---
type: "query"
date: "2026-10-07T21:22:54.546934+00:00"
question: "Can an active wash step be credited when bilateral motion measurement is invalid or zero?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["CadenaIntencionLavado", "EvidenciaMovimiento", "SeguimientoIntencion", "HandwashMetrics"]
---

# Q: Can an active wash step be credited when bilateral motion measurement is invalid or zero?

## Answer

Expanded from graph vocabulary: [evidencia, movimiento, bilateral, sesion, intencion, paso, valida, activo, medicion, secuencia, manos, credit]. Direct Java inspection and a regression test reproduced that active steps were accepted even when medicionValida=false or movement was zero. CadenaIntencionLavado now fails closed on invalid bilateral measurement and numerical zero (1e-8 floor) during every active step; low positive measurable motion remains accepted. Rejection reason is mapped to bounded Micrometer metrics and translated in the dashboard. Full Java suite and frontend tests/build pass. This numerical floor does not reject detector jitter; clinical validation and full WHO action coverage remain missing.

## Outcome

- Signal: useful

## Source Nodes

- CadenaIntencionLavado
- EvidenciaMovimiento
- SeguimientoIntencion
- HandwashMetrics