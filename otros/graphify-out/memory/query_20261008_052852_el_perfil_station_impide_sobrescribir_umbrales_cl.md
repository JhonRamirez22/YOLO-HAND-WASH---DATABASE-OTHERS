---
type: "query"
date: "2026-10-08T05:28:52.113729+00:00"
question: "¿El perfil station impide sobrescribir umbrales clínicos de movimiento sin calibración y firma?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["StationProfileSafetyGuard", "StationReleaseManifestVerifier", "StationProfileSafetyGuardTest", "StationReleaseManifestVerifierTest"]
---

# Q: ¿El perfil station impide sobrescribir umbrales clínicos de movimiento sin calibración y firma?

## Answer

Expandido desde el vocabulario real del grafo: [start, minimum, movement, threshold, station, release, manifest, signed, calibration, intention, override, guard]. La búsqueda ubicó StationProfileSafetyGuard y StationReleaseManifestVerifier; verifiqué el código directamente: station bloquea overrides externos, exige evidencia calibrada con hash en manifiesto Ed25519 y compara umbrales runtime con los firmados. El manifiesto actual conserva el suelo 1e-8 y la evidencia no calibrada, así que sigue NOT_READY. Añadí regresión para bloquear variables de entorno de ambos umbrales.

## Outcome

- Signal: useful

## Source Nodes

- StationProfileSafetyGuard
- StationReleaseManifestVerifier
- StationProfileSafetyGuardTest
- StationReleaseManifestVerifierTest