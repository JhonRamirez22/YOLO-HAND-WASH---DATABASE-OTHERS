---
type: "query"
date: "2026-10-08T17:06:46.334475+00:00"
question: "Actúa como un Arquitecto de Software Senior y evalúa aditivamente JavaCV + OpenCV + YOLO y los cinco patrones para el lavado de manos OMS."
contributor: "graphify"
outcome: "useful"
source_nodes: ["run_yolo26_continuity_camera.py", "InferenceService", "CadenaIntencionLavado", "DetectionController.java", "YOLO"]
---

# Q: Actúa como un Arquitecto de Software Senior y evalúa aditivamente JavaCV + OpenCV + YOLO y los cinco patrones para el lavado de manos OMS.

## Answer

Expanded from original query via vocab: [camera, chain, detector, evidence, factory, inference, java, motion, observer, pipeline, strategy, yolo]. The real repository currently runs camera and YOLO in Python and sends JSON evidence to Java; pom.xml contains ONNX Runtime but no JavaCV/OpenCV. Existing Java has State, Strategy, Observer, Factory Method, Chain of Responsibility and Decorator, but no Java YOLO model singleton or frame pipeline. The seven-class active detector is not a verified WHO-complete model and deploymentReadiness remains NOT_READY. Add only sequence-bound sparse optical flow on validated hand ROIs, temporal step scoring with abstention, camera-motion compensation, and independent video/angle validation; never treat HSV foam or optical flow alone as clinical proof. Manage JavaCPP native memory explicitly and bound queues. JavaCV/OpenCV are viable additions but require ONNX-compatible model export if inference moves into Java.

## Outcome

- Signal: useful

## Source Nodes

- run_yolo26_continuity_camera.py
- InferenceService
- CadenaIntencionLavado
- DetectionController.java
- YOLO