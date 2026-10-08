---
type: "architecture"
date: "2026-10-08T05:19:06.252240+00:00"
question: "¿Cómo funciona y se bloquea el calentamiento de presencia bilateral de 3 segundos antes de detectar pasos?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["HandPresenceWarmup", "HandPresenceWarmupTest", "SessionManager", "HandPresenceWarmupTest.java"]
---

# Q: ¿Cómo funciona y se bloquea el calentamiento de presencia bilateral de 3 segundos antes de detectar pasos?

## Answer

El grafo ubicó HandPresenceWarmup, SessionManager y sus pruebas. Confirmado directamente en Java/Python: ambos exigen dos manos frescas por 3000 ms; supervisor station fija el valor y pruebas rechazan desactivarlo. El grafo orientó, pero la evidencia final procede del código y pruebas.

## Outcome

- Signal: useful

## Source Nodes

- HandPresenceWarmup
- HandPresenceWarmupTest
- SessionManager
- HandPresenceWarmupTest.java