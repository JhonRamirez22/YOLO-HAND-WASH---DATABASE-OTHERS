---
type: "architecture"
date: "2026-10-08T03:13:33.714320+00:00"
question: "¿La advertencia de taxonomía de pasos no verificada llega al dashboard o queda solo en logs?"
contributor: "graphify"
outcome: "useful"
---

# Q: ¿La advertencia de taxonomía de pasos no verificada llega al dashboard o queda solo en logs?

## Answer

La advertencia sí llega al video MJPEG: run_yolo26_continuity_camera.py dibuja TAXONOMIA DE PASOS NO VALIDADA cuando las etiquetas son paso_1…paso_7. La App también muestra DeploymentNotice global (desarrollo/demo/piloto/no verificado), StepStepper etiqueta el avance como informativo si no hay autorización clínica, y SessionSummary nunca presenta aprobación sin clinicalDecisionAllowed. Fuente verificada directamente; no se requiere cambio.

## Outcome

- Signal: useful