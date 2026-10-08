---
type: "query"
date: "2026-10-08T18:05:13.313001+00:00"
question: "Evalúa la viabilidad de JavaCV, OpenCV, YOLO y cinco patrones para detectar pasos OMS; propone complementos aditivos de precisión."
contributor: "graphify"
outcome: "useful"
source_nodes: ["SessionManager", "Receptor", "EvidenciaMovimiento", "HandMotionEstimator", "ReglaValidacionStrategyFactory", "ObserverPipelineConfig"]
---

# Q: Evalúa la viabilidad de JavaCV, OpenCV, YOLO y cinco patrones para detectar pasos OMS; propone complementos aditivos de precisión.

## Answer

Expanded from original query via graph vocabulary: [javacv, opencv, yolo, hand, motion, evidence, step, strategy, factory, chain, observer, singleton]. Graph points to Receptor, ReglaValidacionStrategyFactory, ObserverPipelineConfig and session flow; direct source verification shows Python HandMotionEstimator handles motion, Java EvidenciaMovimiento carries only scalar evidence, and Maven has no JavaCV/OpenCV dependency. Architecture technically viable; useful additions: sparse Lucas-Kanade tracking with periodic YOLO reacquisition and quality gates, temporal step-specific evidence with abstention, bounded latest-frame pipeline, explicit native-resource lifecycle, and independent clinical validation against WHO taxonomy. HSV should not be sole evidence; no clinical-readiness claim.

## Outcome

- Signal: useful

## Source Nodes

- SessionManager
- Receptor
- EvidenciaMovimiento
- HandMotionEstimator
- ReglaValidacionStrategyFactory
- ObserverPipelineConfig