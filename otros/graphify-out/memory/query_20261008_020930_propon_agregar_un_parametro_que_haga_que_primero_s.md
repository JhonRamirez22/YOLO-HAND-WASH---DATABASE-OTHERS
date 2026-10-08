---
type: "query"
date: "2026-10-08T02:09:30.115014+00:00"
question: "propon agregar un parametro que haga que primero se deban detectar las manos, y cuando ya esten manos presentes despues de 3 segundos de detectar las manos, empiece el lavado por los pasos correspondientes, esto que quede super bien funcional para el uso clinico en hospitales"
contributor: "graphify"
outcome: "useful"
source_nodes: ["HandPresenceWarmup", "SessionManager", "HandPresenceWarmupTest", "SessionManagerPresenceWarmupTest", "run_yolo26_continuity_camera.py", "LiveCameraFeed.tsx"]
---

# Q: propon agregar un parametro que haga que primero se deban detectar las manos, y cuando ya esten manos presentes despues de 3 segundos de detectar las manos, empiece el lavado por los pasos correspondientes, esto que quede super bien funcional para el uso clinico en hospitales

## Answer

Expanded from original query via vocab: [hand, presence, bilateral, continuous, warmup, second, start, step, session, intent, detection]. El código ya implementa hand-presence-warmup-ms=3000 en Python y Java. Exige dos manos frescas de forma continua; si falta una o hay una pausa mayor al límite, reinicia el dwell antes del inicio. El supervisor station y el guard Java fijan 3000 ms. La presencia habilita inferencia de pasos, pero no inicia el lavado: Java requiere el gesto Paso 1 Palmas con evidencia bilateral, confianza y confirmación temporal. Mantener esta separación evita iniciar por mera presencia; esto no valida aptitud clínica, y el perfil OMS sigue bloqueado hasta revisión independiente.

## Outcome

- Signal: useful

## Source Nodes

- HandPresenceWarmup
- SessionManager
- HandPresenceWarmupTest
- SessionManagerPresenceWarmupTest
- run_yolo26_continuity_camera.py
- LiveCameraFeed.tsx