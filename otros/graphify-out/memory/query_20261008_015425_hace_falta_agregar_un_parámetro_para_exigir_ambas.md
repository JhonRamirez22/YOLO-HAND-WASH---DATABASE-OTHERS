---
type: "query"
date: "2026-10-08T01:54:25.386392+00:00"
question: "¿Hace falta agregar un parámetro para exigir ambas manos durante 3 segundos antes de habilitar los pasos?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["HandPresenceWarmup", "HandPresenceWarmupTest", "SessionManagerPresenceWarmupTest"]
---

# Q: ¿Hace falta agregar un parámetro para exigir ambas manos durante 3 segundos antes de habilitar los pasos?

## Answer

El parámetro --hand-presence-warmup-ms ya existe con 3000 ms. Python y Java aplican compuertas independientes de presencia bilateral fresca; Java usa reloj monotónico y bloquea el pipeline hasta confirmar el dwell. La estación fija además un hueco máximo de 500 ms y bloquea overrides. Cumplir la espera habilita inferencia, pero no inicia la sesión: el modo parcial requiere intención de lavado con Palmas y evidencia bilateral. No se debe auto-iniciar solo por manos presentes. La manifestación de readiness sigue NOT_READY para uso hospitalario por taxonomía y validación clínica insuficientes. Vocabulario usado en la consulta: manos, hand, hands, presence, warmup, intention, inicio, steps.

## Outcome

- Signal: useful

## Source Nodes

- HandPresenceWarmup
- HandPresenceWarmupTest
- SessionManagerPresenceWarmupTest