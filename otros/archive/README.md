# Archivo histórico

El contenido de este directorio fue apartado del flujo activo tras verificar que el arranque canónico usa Continuity Camera → YOLO Python local → backend Java → dashboard React. Se conserva de forma reversible para no destruir código local modificado ni perder contexto. Nada aquí es requisito para compilar o iniciar el sistema actual.

- `ios-prototype/`: prototipos Swift/Xcode y el generador del proyecto iOS. El teléfono no ejecuta una app en la arquitectura vigente.
- `legacy-fastapi/`: backend FastAPI antiguo y pruebas manuales asociadas.
- `experimental_fastapi_yolo/`: gateway de inferencia multipart FastAPI y prueba manual, archivados; no se instalan ni arrancan en la estación soportada.
- `java-static-ui/`: dashboard HTML antiguo y página de prueba de cámara móvil. Se retiraron de los recursos estáticos de Spring para evitar que parezcan ser la interfaz activa.
- `windows-training/`: comprobación PowerShell con una ruta fija de Windows que no existe en esta Mac.
- `docs/SUMMARY_legacy.md`: resumen previo con instrucciones iOS y arquitectura obsoletas; consultar el `SUMMARY.md` raíz para el estado actual.

Antes de recuperar algo, comprobar sus dependencias y actualizar su documentación. No ejecutar archivos archivados como parte del arranque canónico.
