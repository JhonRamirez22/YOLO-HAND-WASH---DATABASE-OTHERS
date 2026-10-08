---
type: "query"
date: "2026-10-07T23:38:10.769412+00:00"
question: "propon agregar un parametro que haga que primero se deban detectar las manos, y cuando ya esten manos presentes despues de 3 segundos de detectar las manos, empiece el lavado por los pasos correspondientes, esto que quede super bien funcional para el uso clinico en hospitales"
contributor: "graphify"
outcome: "useful"
source_nodes: ["HandPresenceWarmup", "run_yolo26_continuity_camera.py", "run_handwash_station.py", "SeguimientoIntencion", "CadenaIntencionLavado", "LiveCameraFeed.tsx"]
---

# Q: propon agregar un parametro que haga que primero se deban detectar las manos, y cuando ya esten manos presentes despues de 3 segundos de detectar las manos, empiece el lavado por los pasos correspondientes, esto que quede super bien funcional para el uso clinico en hospitales

## Answer

Expanded from original query via graph vocabulary: [hand, presence, warmup, bilateral, intencion, lavado, inicio, session, state, detection]. Source review confirms this already exists: --hand-presence-warmup-ms defaults to 3000; fresh bilateral poses must remain continuous with <=500 ms gaps, and step inference is suppressed until ready. The station supervisor locks 3000 ms and rejects override to 0. After warmup, Java still starts only on valid palms/friction evidence, not mere hand presence; this avoids false starts. Dashboard shows the timer. This is not clinical approval: current ClinicalDecisionPolicy always returns false; OMS gates and clinical validation remain closed/pending.

## Outcome

- Signal: useful

## Source Nodes

- HandPresenceWarmup
- run_yolo26_continuity_camera.py
- run_handwash_station.py
- SeguimientoIntencion
- CadenaIntencionLavado
- LiveCameraFeed.tsx