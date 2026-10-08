---
type: "codebase"
date: "2026-10-08T00:48:19.686891+00:00"
question: "¿Ya existe un parámetro que exija detectar ambas manos de forma continua durante 3 segundos antes de habilitar los pasos?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["HandPresenceWarmup", "SessionManager", "SessionManagerPresenceWarmupTest", "HandPresenceWarmupTest", "LiveCameraFeed", "CadenaIntencionLavado", "StationProfileSafetyGuard"]
---

# Q: ¿Ya existe un parámetro que exija detectar ambas manos de forma continua durante 3 segundos antes de habilitar los pasos?

## Answer

Sí. El capturador tiene --hand-presence-warmup-ms con default 3000, y Java confirma bilateralidad bajo lock de sesión usando reloj monotónico, secuencias del productor y huecos máximos de 500 ms; el perfil station bloquea el valor en 3000. Python y el servidor bloquean la inferencia/acreditación de fases hasta presencia bilateral fresca. Esto arma la secuencia, pero no inicia lavado por mera presencia: Java exige palmas con confianza, evidencia bilateral/espacial y observaciones sostenidas. El frontend ya muestra conteo y progreso. La función es una compuerta técnica, no evidencia de autorización clínica; los perfiles siguen sin permitir decisión clínica.

## Outcome

- Signal: useful

## Source Nodes

- HandPresenceWarmup
- SessionManager
- SessionManagerPresenceWarmupTest
- HandPresenceWarmupTest
- LiveCameraFeed
- CadenaIntencionLavado
- StationProfileSafetyGuard