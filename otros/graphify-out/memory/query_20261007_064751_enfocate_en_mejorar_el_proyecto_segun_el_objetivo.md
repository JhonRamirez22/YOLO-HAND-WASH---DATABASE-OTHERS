---
type: "query"
date: "2026-10-07T06:47:51.492427+00:00"
question: "enfocate en mejorar el proyecto segun el objetivo del lavado de manos, no te desvies"
contributor: "graphify"
outcome: "useful"
source_nodes: ["HandMotionEstimator", "CadenaIntencionLavado", "SeguimientoIntencion", "IntencionLavadoTest", "StepStepper"]
---

# Q: enfocate en mejorar el proyecto segun el objetivo del lavado de manos, no te desvies

## Answer

Graphify rastreó HandMotionEstimator → CadenaIntencionLavado → SeguimientoIntencion. Java aceptaba iniciar con dos manos y movimiento normalizado exactamente cero, por lo que añadí un piso numérico de 1e-8 solo al inicio; las fases activas mantienen su tolerancia a baja amplitud. Añadí motivo visible en el dashboard, métrica de cardinalidad finita, pruebas Java/frontend y actualicé AGENTS.md, docs/PATRONES_E_INTENCION.md y el blocker del manifiesto. El piso no está calibrado clínicamente y el jitter aún puede parecer movimiento; no valida intención real. No entrené, no accedí a la cámara ni guardé medios. Pruebas: Java 337, frontend 59, build/lint y movimiento sintético 13 aprobados.

## Outcome

- Signal: useful

## Source Nodes

- HandMotionEstimator
- CadenaIntencionLavado
- SeguimientoIntencion
- IntencionLavadoTest
- StepStepper