---
type: "codebase"
date: "2026-10-08T00:57:00.814461+00:00"
question: "¿La secuencia OMS y sus instrucciones del catálogo coinciden con la lámina oficial en español?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["AccionOms", "AccionOms.SECUENCIA", "ProtocolCatalogMapper", "DetectionApiIntegrationTest", "SesionOms"]
---

# Q: ¿La secuencia OMS y sus instrucciones del catálogo coinciden con la lámina oficial en español?

## Answer

La lámina oficial WHO en español especifica 40–60 s y acciones desde mojar hasta cerrar el grifo con una toalla; 'sus manos están seguras' es conclusión, no acción. AccionOms.SECUENCIA publica 11 acciones OMS_01…OMS_11. Se corrigieron dos instrucciones para alinearlas con la técnica oficial: dorso de dedos agarrando los dedos opuestos y puntas de dedos con movimiento de rotación. El catálogo REST ahora enlaza la lámina española exacta y su integración prueba orden, códigos, instrucciones y duración. Esto verifica catálogo y copy, no el modelo visual ni la eficacia clínica.

## Outcome

- Signal: useful

## Source Nodes

- AccionOms
- AccionOms.SECUENCIA
- ProtocolCatalogMapper
- DetectionApiIntegrationTest
- SesionOms