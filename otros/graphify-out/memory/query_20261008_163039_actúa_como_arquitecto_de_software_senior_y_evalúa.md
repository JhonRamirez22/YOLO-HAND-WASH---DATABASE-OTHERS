---
type: "query"
date: "2026-10-08T16:30:39.482638+00:00"
question: "Actúa como Arquitecto de Software Senior y evalúa aditivamente JavaCV + OpenCV + YOLO y los cinco patrones para el lavado de manos OMS."
contributor: "graphify"
outcome: "corrected"
correction: "Antes de afirmar arquitectura actual, contrastar el grafo con backend/pom.xml, README.md, AGENTS.md y model-manifest.json; los nodos archive/legacy no describen el flujo activo."
source_nodes: ["run_yolo26_continuity_camera.py", "SessionManager", "ReglaValidacionStrategyFactory", "TemporalStepFilter"]
---

# Q: Actúa como Arquitecto de Software Senior y evalúa aditivamente JavaCV + OpenCV + YOLO y los cinco patrones para el lavado de manos OMS.

## Answer

Graphify dio nodos históricos mezclados con archive/ios-prototype y legacy-fastapi; se contrastó en fuente actual. En este repositorio la cámara/YOLO corre en scripts Python y Java/Spring recibe detecciones; backend/pom.xml no declara JavaCV. AGENTS.md documenta State, Strategy, Observer, Factory Method, Chain of Responsibility y Decorator, no el conjunto Singleton+JavaCV pedido. model-manifest.json declara el modelo activo como fricción parcial, no soporta el procedimiento OMS completo, y deploymentReadiness es NOT_READY con hospitalUseAllowed=false. Para diseño hipotético, JavaCV/OpenCV es técnicamente viable si se gestiona explícitamente la memoria nativa; las adiciones más útiles son tracker de ROI no autoritativo con redetección YOLO, landmarks de manos y asociación bilateral, compuerta de calidad/abstención, fusión temporal de evidencia por fase y validación independiente por persona/video/ángulo. No tratar HSV ni optical flow solos como prueba clínica.

## Outcome

- Signal: corrected
- Correction: Antes de afirmar arquitectura actual, contrastar el grafo con backend/pom.xml, README.md, AGENTS.md y model-manifest.json; los nodos archive/legacy no describen el flujo activo.

## Source Nodes

- run_yolo26_continuity_camera.py
- SessionManager
- ReglaValidacionStrategyFactory
- TemporalStepFilter