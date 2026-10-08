---
type: "query"
date: "2026-10-08T19:22:45.900164+00:00"
question: "Evalúa viabilidad JavaCV, YOLO y patrones para lavado OMS"
contributor: "graphify"
outcome: "useful"
source_nodes: ["ObserverPipelineConfig", "ReglaValidacionStrategyFactory", "SesionLavado"]
---

# Q: Evalúa viabilidad JavaCV, YOLO y patrones para lavado OMS

## Answer

Expanded from graph vocabulary via [strategy, observer, factory, pipeline, pose, camera, model, intent, sequence, state, motion, chain]. Graph confirms active Java workflow; direct README and pom are authoritative: current system is Python YOLO camera producer plus Java/Spring, JavaCPP OpenCV presets (not JavaCV artifact), and the repository implements State, Strategy, Observer, Factory Method, Chain of Responsibility and Decorator. model-manifest marks hospital use NOT_READY. Recommend sparse Lucas-Kanade tracking between periodic YOLO redetections, temporal action evidence with abstention, quality gates, auxiliary HSV/segmentation only as corroboration, and independent site/video validation. JavaCV is viable with native-memory lifecycle controls; .pt requires an inference runtime or compatible ONNX export.

## Outcome

- Signal: useful

## Source Nodes

- ObserverPipelineConfig
- ReglaValidacionStrategyFactory
- SesionLavado