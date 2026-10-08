---
type: "query"
date: "2026-10-08T19:38:09.582709+00:00"
question: "Actúa como un Arquitecto de Software Senior y Experto en Visión por Computadora en Java. Estoy diseñando un sistema de auditoría en tiempo real para validar el lavado de manos según el protocolo de la OMS. Evalúa la viabilidad de JavaCV + OpenCV + YOLO con Singleton, Factory Method, Strategy, Chain of Responsibility y Observer; propone adiciones de precisión sin reemplazar la arquitectura."
contributor: "graphify"
outcome: "useful"
source_nodes: ["ObserverPipelineConfig.java", "ReglaValidacionStrategyFactory", "OpenCvHandMotionEstimator", "run_yolo26_continuity_camera.py", "SessionManager"]
---

# Q: Actúa como un Arquitecto de Software Senior y Experto en Visión por Computadora en Java. Estoy diseñando un sistema de auditoría en tiempo real para validar el lavado de manos según el protocolo de la OMS. Evalúa la viabilidad de JavaCV + OpenCV + YOLO con Singleton, Factory Method, Strategy, Chain of Responsibility y Observer; propone adiciones de precisión sin reemplazar la arquitectura.

## Answer

Expanded from graph vocabulary: yolo opencv java hand pose motion sequence strategy factory observer pipeline classifier. Graph locates the active strategy/observer and motion estimator, but code verification is authoritative: the actual project runs camera YOLO in Python; Java has JavaCPP/OpenCV plus ONNX Runtime, but no org.bytedeco:javacv dependency or Java YOLO model singleton. Keep the proposed chain additive: frame quality gate, YOLO, short-lived LK optical-flow tracking with detector reacquisition, bilateral ROI feature extraction, temporal evidence aggregation, step Strategy, nonblocking Observer. HSV/foam and any secondary classifier should be supporting evidence with abstention, not sole proof. Current model lacks WHO wetting, soap, rinse, dry, and faucet-close phases; active taxonomy/data rubric and independent clinical validation are absent, so no code-only addition makes it production/clinical-ready. For native allocations use try-with-resources and monitor process RSS; current motion estimator already closes Mat/indexers deterministically. Sources checked: backend pom, OpenCvHandMotionEstimator, ObserverPipelineConfig, ReglaValidacionStrategyFactory, active Python YOLO script and model manifest.

## Outcome

- Signal: useful

## Source Nodes

- ObserverPipelineConfig.java
- ReglaValidacionStrategyFactory
- OpenCvHandMotionEstimator
- run_yolo26_continuity_camera.py
- SessionManager