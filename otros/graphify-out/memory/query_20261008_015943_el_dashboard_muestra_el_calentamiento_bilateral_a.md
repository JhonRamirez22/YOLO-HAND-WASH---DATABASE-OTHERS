---
type: "query"
date: "2026-10-08T01:59:43.032418+00:00"
question: "¿El dashboard muestra el calentamiento bilateral antes del primer paso?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["LiveCameraFeed.tsx", "LiveCameraFeed.test.tsx", "sessionStore.ts"]
---

# Q: ¿El dashboard muestra el calentamiento bilateral antes del primer paso?

## Answer

Sí. La sesión del dashboard queda activa desde que se crea o vincula; LiveCameraFeed consulta /health y muestra el progreso de presencia antes de que Java reciba el primer paso. El test LiveCameraFeed.test.tsx verifica el estado 1.5/3.0 s; los cinco tests de ese componente pasan. No se detectó defecto que justifique cambiar el flujo.

## Outcome

- Signal: useful

## Source Nodes

- LiveCameraFeed.tsx
- LiveCameraFeed.test.tsx
- sessionStore.ts