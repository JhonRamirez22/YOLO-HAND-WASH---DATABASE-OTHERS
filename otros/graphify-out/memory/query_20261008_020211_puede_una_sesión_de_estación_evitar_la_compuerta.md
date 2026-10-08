---
type: "query"
date: "2026-10-08T02:02:11.980315+00:00"
question: "¿Puede una sesión de estación evitar la compuerta de presencia v2 usando el flujo legacy?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["SessionController", "SessionManager", "SessionManagerPresenceWarmupTest", "StationProfileSafetyGuardTest"]
---

# Q: ¿Puede una sesión de estación evitar la compuerta de presencia v2 usando el flujo legacy?

## Answer

El controlador de estación rechaza creación y emparejamiento sin producerProtocolVersion 2; las pruebas SessionControllerTest cubren ambos casos y aseguran que no se crea sesión legacy ni se rota token al rechazar. El guard station también exige handwash.producer.require-v2=true. SessionManagerPresenceWarmupTest ahora cubre presencia bilateral de 3000 ms, ausencia de auto-inicio y bloqueo de pasos cuando la presencia supera 500 ms de antigüedad. Suite Java: 361 aprobadas.

## Outcome

- Signal: useful

## Source Nodes

- SessionController
- SessionManager
- SessionManagerPresenceWarmupTest
- StationProfileSafetyGuardTest