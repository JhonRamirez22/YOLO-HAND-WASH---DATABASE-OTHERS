---
type: "query"
date: "2026-10-08T01:58:12.615807+00:00"
question: "¿La espera de tres segundos debe iniciar la sesión automáticamente?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["HandPresenceWarmup", "SessionManagerPresenceWarmupTest", "IntencionLavadoTest"]
---

# Q: ¿La espera de tres segundos debe iniciar la sesión automáticamente?

## Answer

No. La compuerta bilateral de 3000 ms solo habilita la inferencia de pasos; la estación fija 3000 ms y un hueco máximo de 500 ms, y Java la valida independientemente con reloj monotónico. La presencia no inicia la sesión: la intención requiere el gesto Palmas, evidencia bilateral reciente y movimiento medible; manos quietas se rechazan. Se añadió una aserción de regresión que confirma que solo las pulsaciones PRESENCE no cambian ESPERANDO_INICIO ni crean intento. Suite Java completa: 361 pruebas aprobadas. OpenCV no está instalado en el Python usado, por lo que no se ejecutó la suite del capturador. El manifiesto sigue bloqueando uso hospitalario; no cambiar umbrales sin validación independiente.

## Outcome

- Signal: useful

## Source Nodes

- HandPresenceWarmup
- SessionManagerPresenceWarmupTest
- IntencionLavadoTest