---
type: "query"
date: "2026-10-07T06:51:58.412165+00:00"
question: "¿La firma de release autoriza aprobación clínica automática?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["StationReleaseManifestVerifier", "StationProfileSafetyGuard", "ClinicalDecisionPolicy", "DeploymentStatusController", "Notificador"]
---

# Q: ¿La firma de release autoriza aprobación clínica automática?

## Answer

Expanded from graph vocab [clinical, decision, policy, station, release, manifest, verifier]. El verificador firmado permite únicamente el perfil HOSPITAL_PILOT después de evidencias, hash y taxonomía; StationProfileSafetyGuard habilita OMS solo después de ese chequeo. ClinicalDecisionPolicy continúa retornando false y Notificador nunca reporta aprobado hasta una autorización clínica de producción independiente. No conectar los booleanos de piloto con aprobación clínica; es un bloqueo deliberado y vigente.

## Outcome

- Signal: useful

## Source Nodes

- StationReleaseManifestVerifier
- StationProfileSafetyGuard
- ClinicalDecisionPolicy
- DeploymentStatusController
- Notificador