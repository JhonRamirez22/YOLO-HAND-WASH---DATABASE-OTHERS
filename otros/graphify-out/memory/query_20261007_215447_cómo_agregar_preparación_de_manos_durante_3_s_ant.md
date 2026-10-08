---
type: "architecture"
date: "2026-10-07T21:54:47.735723+00:00"
question: "¿Cómo agregar preparación de manos durante 3 s antes del inicio del lavado sin acreditar presencia como paso?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["CadenaIntencionLavado", "SeguimientoIntencion", "SesionLavado", "SessionManager", "ProducerProtocolRegistry"]
---

# Q: ¿Cómo agregar preparación de manos durante 3 s antes del inicio del lavado sin acreditar presencia como paso?

## Answer

El backend exige actualmente fricción de palmas con evidencia bilateral fresca durante 650 ms y 3 observaciones. El productor v2 envía FONDO de presencia como CONTROL sin pose, y el protocolo prohíbe adjuntarle evidencia; Java no puede verificar continuidad bilateral desde ese control. Propuesta: evento v2 PRESENCE separado con frameSequence/epoch/evidencia bilateral; Java mide 3000 ms con reloj monotónico y reinicia si falta una mano, caduca evidencia o el hueco supera 650 ms. Al terminar solo queda LISTO_PARA_INICIAR; iniciar y acreditar Paso 1 siguen exigiendo gesto de palmas válido y las reglas actuales.

## Outcome

- Signal: useful

## Source Nodes

- CadenaIntencionLavado
- SeguimientoIntencion
- SesionLavado
- SessionManager
- ProducerProtocolRegistry