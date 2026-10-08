---
type: "architecture"
date: "2026-10-07T21:59:05.244718+00:00"
question: "¿Existe ya la espera de dos manos durante tres segundos y cómo afectan los controles FONDO al inicio?"
contributor: "graphify"
outcome: "corrected"
correction: "La nota previa sobre necesidad de un evento PRESENCE para implementar la espera omitió la compuerta de 3000 ms ya existente en Python. Solo sería necesario para verificación independiente en Java; no para la espera actual."
source_nodes: ["HandPresenceWarmup", "ProducerProtocolRegistry", "SesionLavado"]
---

# Q: ¿Existe ya la espera de dos manos durante tres segundos y cómo afectan los controles FONDO al inicio?

## Answer

Inspección directa: HandPresenceWarmup del capturador ya exige 3000 ms de dos poses únicas y frescas antes de inferir pasos, y el supervisor fija ese argumento. El backend aún no tiene temporizador independiente de presencia, pero el flujo principal sí implementa la espera. Se reprodujo que publicar FONDO repetido en reposo con watermark superior a la pose descarta indefinidamente primeros pasos; se eliminó ese envío redundante y se conserva un único control tras pérdida de un paso estable.

## Outcome

- Signal: corrected
- Correction: La nota previa sobre necesidad de un evento PRESENCE para implementar la espera omitió la compuerta de 3000 ms ya existente en Python. Solo sería necesario para verificación independiente en Java; no para la espera actual.

## Source Nodes

- HandPresenceWarmup
- ProducerProtocolRegistry
- SesionLavado