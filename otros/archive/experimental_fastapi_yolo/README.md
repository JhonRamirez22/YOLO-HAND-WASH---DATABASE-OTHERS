# Gateway FastAPI experimental (archivado)

Este gateway multipart `/infer` no forma parte del runtime soportado ni del
arranque de la estación. El flujo canónico es Continuity Camera → capturador
YOLO Python → REST/WebSocket Java. El backend de negocio y la máquina de
estados permanecen en Java/Spring Boot.

Se conserva el código y sus dependencias de forma reversible como referencia
histórica. No se instala ni se inicia para operar el sistema. Su prueba manual
de seguridad se puede ejecutar explícitamente, si se necesitan inspeccionar los
artefactos archivados, con:

```bash
.venv/bin/python archive/experimental_fastapi_yolo/archived_gateway_security_check.py
```

Sus dependencias están aisladas en este directorio; la estación activa usa
`requirements-camera.txt` en la raíz del proyecto.
