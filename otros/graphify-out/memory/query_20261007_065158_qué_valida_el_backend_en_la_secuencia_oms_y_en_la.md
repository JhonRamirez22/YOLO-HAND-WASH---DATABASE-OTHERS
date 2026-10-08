---
type: "query"
date: "2026-10-07T06:51:58.354875+00:00"
question: "¿Qué valida el backend en la secuencia OMS y en la cobertura regional de jabón?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["SesionOms", "RegionJabon", "Receptor", "SoapEvidenceRequest"]
---

# Q: ¿Qué valida el backend en la secuencia OMS y en la cobertura regional de jabón?

## Answer

Expanded from graph vocab [soap, evidence, region, oms, phase, sequence]. Graph locations: SesionOms en .phaseHasEnoughEvidence (L262), collectSoapEvidence (L267) y hasFullSoapCoverage (L300); RegionJabon mapea las 12 regiones bilaterales a las seis fases de fricción; Receptor valida pose bilateral fresca y vincula evidencia regional con la misma secuencia del frame. Inspección del código y SesionOmsTest no mostró otro defecto corregible en este flujo. El modo OMS sigue fail-closed y deshabilitado sin release/modelo validado.

## Outcome

- Signal: useful

## Source Nodes

- SesionOms
- RegionJabon
- Receptor
- SoapEvidenceRequest