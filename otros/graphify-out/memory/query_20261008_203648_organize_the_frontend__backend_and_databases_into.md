---
type: "query"
date: "2026-10-08T20:36:48.758279+00:00"
question: "Organize the frontend, backend and databases into clear folders and remove files that are no longer useful"
contributor: "graphify"
outcome: "corrected"
correction: "Do not relocate schema.sql without changing the exact Spring SQL-init allowlist and tests; the active source layout is already separated. Normalize only the H2 runtime file to the project-root .runtime path and preserve archives/model/data unless proven disposable."
source_nodes: ["frontend/AGENTS.md", "FailedAttemptRepository", "StationProfileSafetyGuard", "archive/README.md"]
---

# Q: Organize the frontend, backend and databases into clear folders and remove files that are no longer useful

## Answer

Expanded from graph vocabulary: [frontend, backend, database, schema, persistence, repository, archive, legacy, configuration, resource, build, directory]. The graph query was broad and partly stale; verified source shows frontend/ and backend/ are already separated, Java packages are grouped by responsibility, schema.sql must remain at the Spring classpath root because the station safety guard rejects schema-location overrides, and the H2 runtime file belongs in root .runtime/. Moved the closed 20 KiB H2 file intact from backend/.runtime/ to .runtime/; removed only generated Python .pyc caches. Preserved archive, model weights, datasets, and logs.

## Outcome

- Signal: corrected
- Correction: Do not relocate schema.sql without changing the exact Spring SQL-init allowlist and tests; the active source layout is already separated. Normalize only the H2 runtime file to the project-root .runtime path and preserve archives/model/data unless proven disposable.

## Source Nodes

- frontend/AGENTS.md
- FailedAttemptRepository
- StationProfileSafetyGuard
- archive/README.md