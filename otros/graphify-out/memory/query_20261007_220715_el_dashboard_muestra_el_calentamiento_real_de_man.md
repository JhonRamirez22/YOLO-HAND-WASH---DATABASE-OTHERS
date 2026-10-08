---
type: "architecture"
date: "2026-10-07T22:07:15.831337+00:00"
question: "¿El dashboard muestra el calentamiento real de manos antes del primer paso?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["MjpegFrameServer", "LiveCameraFeed", "HandPresenceWarmup"]
---

# Q: ¿El dashboard muestra el calentamiento real de manos antes del primer paso?

## Answer

El capturador ya aplica 3000 ms, pero antes del cambio /health solo publicaba estado de cámara y sessionId. Java no ve manos hasta recibir una detección de paso; el dashboard mostraba 0/2 y decía esperar manos aunque el video contaba el calentamiento. Añadí un snapshot acotado handPresence al health local, ligado por sessionId en el frontend y caducado a los 650 ms o al desconectar. No transporta imágenes ni acredita pasos.

## Outcome

- Signal: useful

## Source Nodes

- MjpegFrameServer
- LiveCameraFeed
- HandPresenceWarmup