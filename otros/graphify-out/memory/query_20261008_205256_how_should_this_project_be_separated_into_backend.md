---
type: "query"
date: "2026-10-08T20:52:56.135807+00:00"
question: "How should this project be separated into backend, frontend, database, and other folders for a copy?"
contributor: "graphify"
outcome: "corrected"
correction: "Graphify BFS can overmatch; verify exact filesystem paths and AGENTS.md before deciding folder boundaries. Keep schema.sql in backend and copy a second copy to the requested database folder; do not move it."
source_nodes: ["backend", "frontend", "scripts"]
---

# Q: How should this project be separated into backend, frontend, database, and other folders for a copy?

## Answer

Filesystem inspection is authoritative: copy backend/ and frontend/ separately; database consists of the active .runtime/handwash.mv.db plus backend/src/main/resources/schema.sql; other assets include scripts, docs, archives, datasets, training, runs, circuit, root manifests and YOLO weights. The graph query overmatched unrelated historical/test nodes, so it does not determine copy boundaries.

## Outcome

- Signal: corrected
- Correction: Graphify BFS can overmatch; verify exact filesystem paths and AGENTS.md before deciding folder boundaries. Keep schema.sql in backend and copy a second copy to the requested database folder; do not move it.

## Source Nodes

- backend
- frontend
- scripts