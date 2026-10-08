---
type: "query"
date: "2026-10-07T20:52:47.837269+00:00"
question: "propon agregar un parametro que haga que primero se deban detectar las manos, y cuando ya esten manos presentes despues de 3 segundos de detectar las manos, empiece el lavado por los pasos correspondientes, esto que quede super bien funcional para el uso clinico en hospitales"
contributor: "graphify"
outcome: "useful"
source_nodes: ["HandPresenceWarmup", "monitor_session", "SesionLavado"]
---

# Q: propon agregar un parametro que haga que primero se deban detectar las manos, y cuando ya esten manos presentes despues de 3 segundos de detectar las manos, empiece el lavado por los pasos correspondientes, esto que quede super bien funcional para el uso clinico en hospitales

## Answer

Expanded from original query via vocab: [session, state, step, start, monitor, warmup, hand, presence, timer, intent, attempt]. Direct graph query plus source inspection confirmed the existing --hand-presence-warmup-ms parameter defaults to 3000 ms and HandPresenceWarmup gates partial-step inference until two distinct fresh hand poses persist. monitor_session observes Java EN_PROGRESO, while SesionLavado remains the authority for intention and accepted step order. Fixed a real edge case: after a pre-start hand-loss or excessive-gap reset, preserve the current bilateral observation as the first sample of the new timer; do not preserve prior elapsed time. Once Java has confirmed start, occlusion blocks stale step inference but does not restart the warmup. This gate controls when YOLO analyzes steps; it does not certify a clinical wash or hospital readiness.

## Outcome

- Signal: useful

## Source Nodes

- HandPresenceWarmup
- monitor_session
- SesionLavado