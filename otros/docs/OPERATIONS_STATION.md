# Operación segura de una estación local

Este documento es un procedimiento de operación y recuperación; no es una autorización clínica ni una declaración de que el proyecto esté listo para hospitales. La estación ejecuta Java, YOLO y el dashboard en la Mac; el iPhone solo aporta Continuity Camera.

## Estado de uso

El `backend/models/model-manifest.json` actual declara `deploymentReadiness.status: NOT_READY` y `hospitalUseAllowed: false`. Por tanto:

- No usar el sistema con pacientes, para decisiones clínicas ni para registros hospitalarios.
- `--unvalidated-demo` es solo para demostración técnica interna y no simula un release.
- No activar OMS editando variables, manifiesto, hashes o firmas. La barrera solo puede cambiar después de completar y revisar la evidencia independiente indicada en el manifiesto.
- El modelo activo detecta siete movimientos de fricción; no observa todo el procedimiento OMS. Una sesión “completada” no equivale a lavado validado ni aprobado.

## Precondiciones de una demostración técnica

1. Usar una Mac con sesión de usuario iniciada, pantalla desbloqueada y Continuity Camera disponible y autorizada en macOS. El proyecto no requiere app ni navegador en el iPhone.
2. Confirmar que la estación corresponde a un único lavamanos y que no hay otra instancia usando los puertos locales `8080` o `8091`.
3. Usar el checkout y los modelos declarados en `backend/models/model-manifest.json`; no sustituir pesos ni umbrales para “hacer que pase”. No entrenar modelos en esta Mac.
4. Mantener abierta la Terminal supervisora mientras opere la demo. Los códigos de vinculación aparecen solo en la terminal y en memoria; no copiarlos a logs, tickets ni capturas.

La preparación del entorno de cámara documentada en `README.md` usa CPython 3.14.4/macOS arm64 y `requirements-camera.txt`. El supervisor vuelve a validar el runtime exacto, los pesos y los puertos antes de arrancar.

## Inicio y cierre de demostración

Desde la raíz del proyecto:

```bash
./scripts/build_handwash_station.sh
./.venv/bin/python scripts/run_handwash_station.py --unvalidated-demo
```

El build compila el dashboard y Java, y muestra huellas SHA-256 candidatas. No firma el manifiesto ni vuelve clínico el resultado. El supervisor inicia Java y YOLO; abre `http://127.0.0.1:8080/` en la Mac y vincula el dashboard con el código impreso por el capturador. Mantén la terminal abierta.

Detén la estación con `Ctrl+C` en esa terminal. No mates procesos por nombre ni cierres procesos que no haya iniciado el supervisor. Si un puerto está ocupado, identifica primero su dueño y cierra esa otra aplicación de forma controlada; el supervisor deliberadamente no la termina.

## Recuperación ante incidentes

| Incidente | Comportamiento actual y acción segura |
|---|---|
| Cámara sin frames | Tras más de 2 s, el capturador intenta recuperar FFmpeg y volver a enumerar Continuity Camera por hasta 45 s. El dashboard debe mostrar desconexión; la evidencia antigua no acredita pasos. Si agota el plazo, detén la demo y comprueba conexión, permisos y encuadre antes de iniciar una sesión nueva. |
| YOLO termina inesperadamente | El supervisor puede reintentar hasta tres veces (2, 5 y 15 s), solo si Java sigue vivo y conserva el código de la sesión; registra un epoch nuevo. Si agota reintentos, no sigas presentando la sesión como monitorizada. |
| Java termina o deja de responder | La sesión activa estaba en memoria y no se puede reanudar con certeza. El supervisor trata la caída como terminal; declara el intento interrumpido, detén la estación y, tras resolver la causa, inicia una sesión nueva desde el primer paso. Nunca reconstruyas progreso a partir del último frame o de la pantalla anterior. |
| Mac reiniciada o sesión cerrada | No hay autoarranque ni recuperación de estado. Después de iniciar sesión, verifica Continuity Camera, trata cualquier lavado en curso como interrumpido y arranca una sesión nueva. |
| Dashboard desconectado | Vuelve a abrir el dashboard local y permite que se reconecte a la sesión viva; no crees otra sesión ni vuelvas a emparejar el productor salvo que la interfaz/supervisor lo requiera. La reconexión no acredita pasos ocurridos sin evidencia. |
| Resultado final o error de secuencia | Conserva el resultado como informativo/no clínico. No cambies manualmente estados, evidencias, modelo ni umbrales para obtener un resultado favorable. |

No existe todavía un watchdog de macOS, respaldo/restauración de sesión activa, monitoreo remoto ni despliegue/rollback automatizado. No copies `.runtime/` como “respaldo clínico”: contiene metadatos locales limitados de intentos fallidos, no un registro verificable de lavado. Cualquier política futura de respaldo, retención o auditoría requiere aprobación institucional de privacidad y una prueba de restauración; los frames y videos no se guardan.

## Puerta de un futuro release hospitalario

El modo hospitalario no se inicia hasta que la autoridad responsable haya revisado, como mínimo:

- Modelo y taxonomía exactos, con `data.yaml` incluido bajo el proyecto, SHA-256 coincidente, 36 clases OMS en orden canónico y rúbrica trazable al checkpoint.
- Validación independiente por video/persona/entorno, con sensibilidad, falsos positivos y falsos aprobados por fase; secuencias completas y errores deliberados; piloto de cámara en el lavamanos y la iluminación objetivo.
- Revisión clínica, de seguridad, privacidad, riesgo y aprobación institucional; procedimiento de operación, interrupción, mantenimiento y respuesta a incidentes.
- Build final de Java y frontend, scripts de estación, checkpoint, ambos SBOM (Java y cámara Python), y locks runtime/generador con todas sus huellas revisadas. `scripts/build_handwash_station.sh` genera los SBOM y solo imprime huellas candidatas; no actualiza ni firma el manifiesto.
- Manifiesto final revisado y firmado con Ed25519 por la autoridad de release. La clave privada permanece fuera de esta Mac; la clave pública confiable se provisiona externamente y en solo lectura. No reutilizar una firma de otro build ni firmar un manifiesto modificado después.
- Prueba de aceptación en el puesto real, autorización formal del hospital y criterio documentado de reversión a un paquete íntegro previamente aprobado.

Solo después de esa puerta, el comando normal —sin `--unvalidated-demo`— puede intentar arrancar `station`; tanto el supervisor como Java vuelven a comprobar la firma, los artefactos y la evidencia. Si falla una verificación, no la eludas: detén el despliegue y corrige el release con la autoridad responsable.

El paquete actual no supera esa puerta. La documentación describe el procedimiento futuro, no autoriza instalarlo para uso clínico.
