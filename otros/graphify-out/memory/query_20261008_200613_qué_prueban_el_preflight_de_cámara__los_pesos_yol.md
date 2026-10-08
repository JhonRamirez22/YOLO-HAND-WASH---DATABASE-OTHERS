---
type: "validation"
date: "2026-10-08T20:06:13.255883+00:00"
question: "¿Qué prueban el preflight de cámara, los pesos YOLO activos y el warmup bilateral en el estado actual?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["HandPresenceWarmup", "HandPresenceWarmupTest", "ContinuityCameraDetectionTest", "StationReleaseManifestVerifierTest", "YOLO"]
---

# Q: ¿Qué prueban el preflight de cámara, los pesos YOLO activos y el warmup bilateral en el estado actual?

## Answer

La cámara de Continuidad no aparece en AVFoundation; solo FaceTime HD y Capture screen 0, por lo que no hubo prueba en vivo. El preflight estructural acepta el detector parcial YOLO26, pose de manos y clasificador activo, pero advierte que las clases paso_1 a paso_7 se mapean por orden y no prueba la rúbrica ni precisión. El backend usa hand-presence-warmup-ms=3000; 11 pruebas Java de warmup, integración por sesión y OpenCV pasaron. El manifiesto sigue NOT_READY y hospitalUseAllowed=false.

## Outcome

- Signal: useful

## Source Nodes

- HandPresenceWarmup
- HandPresenceWarmupTest
- ContinuityCameraDetectionTest
- StationReleaseManifestVerifierTest
- YOLO