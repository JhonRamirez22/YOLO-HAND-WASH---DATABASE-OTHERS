---
type: "query"
date: "2026-10-08T02:38:04.727061+00:00"
question: "Audit the YOLO handwashing detector class contract for incorrect step mappings"
contributor: "graphify"
outcome: "useful"
source_nodes: ["validate_step_model", "ProducerProtocolRegistry", "SessionManager"]
---

# Q: Audit the YOLO handwashing detector class contract for incorrect step mappings

## Answer

Expanded graph vocabulary used: [detector, evidence, hands, movement, pose, producer, sequence, session, step, transition, yolo]. Graph traversal located validate_step_model and producer/session sequence checks, but direct source verification was required because the graph edges were incomplete. Reproduced that partial detector preflight incorrectly accepted duplicate semantic aliases and unknown classes. The validator now requires exactly one label for each of the seven canonical steps, optionally allows Fondo for veto, and rejects duplicate aliases or unknown labels; regression tests pass. This is structural taxonomy validation only, not proof that model labels match handwashing semantics or clinical accuracy.

## Outcome

- Signal: useful

## Source Nodes

- validate_step_model
- ProducerProtocolRegistry
- SessionManager