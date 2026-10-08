---
type: "architecture"
date: "2026-10-08T17:15:24.630711+00:00"
question: "Evalúa si JavaCV+OpenCV+YOLO y cinco patrones son viables para auditar lavado OMS; propone mejoras aditivas sin reemplazar la arquitectura"
contributor: "graphify"
outcome: "useful"
source_nodes: ["HandPresenceWarmup", "SessionManagerPresenceWarmupTest", "HandMotionEstimator", "DetectionController", "InferenceService", "ProducerProtocolRegistry"]
---

# Q: Evalúa si JavaCV+OpenCV+YOLO y cinco patrones son viables para auditar lavado OMS; propone mejoras aditivas sin reemplazar la arquitectura

## Answer

Viable como prototipo, no garantiza precisión clínica. JavaCV envuelve OpenCV/FFmpeg pero no ejecuta automáticamente el .pt. En este repo la inferencia y captura activas son Python; Java recibe JSON y pom.xml no incluye JavaCV. El modelo actual reconoce fricciones parciales y no el procedimiento OMS completo. Ya existen warmup bilateral 3s, secuenciación temporal y compensación de movimiento; evitar duplicarlos. Recomendaciones: tracking LK/Kalman solo como ROI puente con re-detección, fusionar señales con abstención, control de calidad/calibración por cámara, validación por sujeto/sesión/ángulo y liberar memoria nativa determinísticamente. No sumar TTA ni recuperación 960: no recuperó manos y elevó latencia. OMS poster: 12 actos de lavado, duración completa 40-60s.

## Outcome

- Signal: useful

## Source Nodes

- HandPresenceWarmup
- SessionManagerPresenceWarmupTest
- HandMotionEstimator
- DetectionController
- InferenceService
- ProducerProtocolRegistry