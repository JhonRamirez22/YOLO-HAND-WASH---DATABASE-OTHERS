---
type: "query"
date: "2026-10-08T20:47:39.434037+00:00"
question: "Reorganize this software project professionally without changing behavior"
contributor: "graphify"
outcome: "corrected"
correction: "The graph query overmatches across code and history; verify paths in source. Do not create a separate database directory: Spring's default schema discovery and station guard require schema.sql at classpath root. Use Maven from repository root so ./\\.runtime is canonical."
source_nodes: ["frontend/AGENTS.md", "FailedAttemptRepository", "StationProfileSafetyGuard", "archive/README.md"]
---

# Q: Reorganize this software project professionally without changing behavior

## Answer

Expanded from graph vocabulary: [frontend, backend, database, schema, persistence, repository, archive, legacy, configuration, resource, build]. The current active layout already follows ecosystem conventions: React/Vite sources under frontend/src; Spring Java packages, tests, SQL schema and model assets under backend; camera/YOLO and operational tooling under scripts; docs and historical archive are separate. H2 stays embedded: schema.sql must remain at the classpath root and data at root .runtime/handwash.mv.db. README now documents exact locations and launches Maven from repository root to prevent creating backend/.runtime. Removed only OS-generated .DS_Store in root/frontend/backend. Kept historical archives, datasets, models, local logs and tracked empty frontend/.gitkeep.

## Outcome

- Signal: corrected
- Correction: The graph query overmatches across code and history; verify paths in source. Do not create a separate database directory: Spring's default schema discovery and station guard require schema.sql at classpath root. Use Maven from repository root so ./\.runtime is canonical.

## Source Nodes

- frontend/AGENTS.md
- FailedAttemptRepository
- StationProfileSafetyGuard
- archive/README.md