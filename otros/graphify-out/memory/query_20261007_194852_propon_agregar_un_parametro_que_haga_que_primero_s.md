---
type: "query"
date: "2026-10-07T19:48:52.811327+00:00"
question: "propon agregar un parametro que haga que primero se deban detectar las manos, y cuando ya esten manos presentes despues de 3 segundos de detectar las manos, empiece el lavado por los pasos correspondientes, esto que quede super bien funcional para el uso clinico en hospitales"
contributor: "graphify"
outcome: "useful"
source_nodes: ["HandPresenceWarmup", "bilateral_presence_is_fresh()"]
---

# Q: propon agregar un parametro que haga que primero se deban detectar las manos, y cuando ya esten manos presentes despues de 3 segundos de detectar las manos, empiece el lavado por los pasos correspondientes, esto que quede super bien funcional para el uso clinico en hospitales

## Answer

Expanded from original using graph vocabulary: hand, presence, warmup, bilateral, sequence, intention, java, steps, wash. The feature already exists as --hand-presence-warmup-ms with default 3000 in FRICCION_PARCIAL. It gates YOLO step inference after three seconds of fresh bilateral hand poses; Java separately waits for the palms step and its intention criteria. This is not clinical validation; the active model and full WHO routine remain unapproved.

## Outcome

- Signal: useful

## Source Nodes

- HandPresenceWarmup
- bilateral_presence_is_fresh()