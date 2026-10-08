---
type: "query"
date: "2026-10-08T15:42:39.685786+00:00"
question: "¿Qué evidencia exige el gate de release para validar la taxonomía del checkpoint antes del uso hospitalario?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["StationReleaseManifestVerifierTest", "validate_dataset5_contract()", "create_yaml()"]
---

# Q: ¿Qué evidencia exige el gate de release para validar la taxonomía del checkpoint antes del uso hospitalario?

## Answer

Expandido desde vocabulario Graphify: [manifest, checkpoint, taxonomy, yaml, validation, release]. El grafo relaciona el manifiesto con StationReleaseManifestVerifierTest, la validación del YAML y la preparación del dataset. La lectura directa confirma que el gate exige un data.yaml interno con SHA-256 coincidente y nombres/clases canónicos, además de evidencia de validación firmada. El checkpoint actual no incluye su YAML de entrenamiento ni rúbrica; el manifiesto permanece NOT_READY y hospitalUseAllowed=false. La normalización de etiquetas en runtime no acredita la semántica aprendida.

## Outcome

- Signal: useful

## Source Nodes

- StationReleaseManifestVerifierTest
- validate_dataset5_contract()
- create_yaml()