---
type: "query"
date: "2026-10-07T20:08:15.761883+00:00"
question: "propón agregar un parámetro para exigir detectar ambas manos y esperar 3 segundos antes de iniciar los pasos, con objetivo de uso clínico hospitalario"
contributor: "graphify"
outcome: "useful"
source_nodes: ["HandPresenceWarmup", "run_yolo26_continuity_camera.py"]
---

# Q: propón agregar un parámetro para exigir detectar ambas manos y esperar 3 segundos antes de iniciar los pasos, con objetivo de uso clínico hospitalario

## Answer

Expanded from original query via graph vocabulary: [hand, warmup, presence, intent, sequence, capture, detector]. Graph and source inspection show this already exists: --hand-presence-warmup-ms defaults to 3000 in scripts/run_yolo26_continuity_camera.py. HandPresenceWarmup requires two distinct fresh hand poses for 3 continuous seconds; missing a hand or a gap over the freshness limit resets the initial countdown. It then opens partial step inference, but still requires current bilateral evidence. Java separately gates session start on valid Palmas/intent and ordered evidence. The station supervisor rejects overrides, keeping 3000 ms fixed. No duplicate parameter needed. This does not make the product clinically ready: model-manifest.json remains NOT_READY/hospitalUseAllowed=false and ClinicalDecisionPolicy always returns false.

## Outcome

- Signal: useful

## Source Nodes

- HandPresenceWarmup
- run_yolo26_continuity_camera.py