---
type: "query"
date: "2026-10-08T20:48:57.342379+00:00"
question: "Reestructura el proyecto según convenciones profesionales sin cambiar comportamiento"
contributor: "graphify"
outcome: "corrected"
correction: "The active structure needed documentation and a corrected Maven working directory, not source moves. Keep H2 schema at backend/src/main/resources/schema.sql; do not create a separate database/ folder. Preserve archives, datasets and models unless explicitly approved."
source_nodes: ["frontend/AGENTS.md", "FailedAttemptRepository", "StationProfileSafetyGuard", "archive/README.md"]
---

# Q: Reestructura el proyecto según convenciones profesionales sin cambiar comportamiento

## Answer

Expanded from graph vocabulary: [frontend, backend, database, schema, persistence, repository, archive, legacy, configuration, resource, build]. Source inspection confirms the existing separation is already appropriate: React/Vite under frontend, Java/Spring packages and tests under backend, Python camera/YOLO under scripts. H2 remains embedded; schema.sql stays at Spring's classpath root, and persistent data is in root .runtime/handwash.mv.db. README now documents the structure and uses Maven from repository root, preventing a second backend/.runtime database. Removed 11 Finder .DS_Store metadata files and the empty backend/.runtime directory; preserved model/data/log files and archive. No behavior or dependencies changed.

## Outcome

- Signal: corrected
- Correction: The active structure needed documentation and a corrected Maven working directory, not source moves. Keep H2 schema at backend/src/main/resources/schema.sql; do not create a separate database/ folder. Preserve archives, datasets and models unless explicitly approved.

## Source Nodes

- frontend/AGENTS.md
- FailedAttemptRepository
- StationProfileSafetyGuard
- archive/README.md