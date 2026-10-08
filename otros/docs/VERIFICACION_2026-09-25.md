# Verificación de intención, pasos y cámara — 25-09-2026

## Resultado comprobado

- Java: 72 pruebas, cero fallos/errores. Incluye API HTTP/WS local, validación, secuencia, tiempos, concurrencia y diez casos nuevos de intención.
- Python: 23 pruebas del capturador y ocho del estimador de movimiento, todas correctas.
- No se grabaron imágenes, frames ni video. Los casos de movimiento utilizan puntos sintéticos.

## Fallos reproducidos y corregidos

1. Un intervalo sin eventos de 900 ms sumaba 900 ms de fricción aunque superaba el máximo de continuidad de intención (650 ms). Ahora corta el intervalo; una pausa de 1500 ms reinicia.
2. Un Fondo con secuencia anterior a la observación vigente reiniciaba el intento. Ahora se ignora sin modificar tiempos, pasos ni intentos. El timeout real sigue reiniciando por una señal de control sin secuencia antigua.
3. Una prueba HTTP todavía suponía que una etiqueta de palmas bastaba para iniciar. Se adaptó al nuevo contrato y comprueba tanto el rechazo sin movimiento como el inicio con confirmación temporal.

La primera ejecución de integración no podía abrir sockets dentro del sandbox;
se repitió fuera de él en un puerto efímero local y pasó. No era un fallo de detección.

## Casos automatizados añadidos

Manos quietas; evidencia ausente/caducada; otro gesto antes de empezar; confirmación
sin acreditar tiempo retrospectivo; salto de paso y nuevo intento; pausa corta;
hueco sin eventos; pausa larga; Fondo antiguo; duplicados durante confirmación.
También inmovilidad geométrica, traslación/rotación/escala comunes de cámara,
intercambio de orden de manos, movimiento relativo, recuperación tras pose
incompleta, edad de observación, oclusión y envejecimiento en la cola HTTP.

## Pendiente — prueba real con iPhone

AVFoundation y `system_profiler SPCameraDataType` no enumeran el iPhone;
solo aparece la cámara FaceTime HD (AVFoundation también enumera la pantalla).
No se sustituyó silenciosamente por otra cámara.

No se puede afirmar todavía que se reconozcan correctamente las manos o los
siete movimientos en las condiciones reales del usuario. Pasar tests no mide
precisión/recall del modelo. Tampoco hay medición nueva de FPS de esta versión.

Cuando aparezca el iPhone: verificar sin manos, manos quietas, fricción de
palmas sostenida, todos los pasos en orden, salto deliberado de paso, pausa,
salida de encuadre, oclusión y movimientos ajenos al lavado. Comparar la acción
real con etiquetas, intención, tiempo acreditado, infracción y reinicio, sin
guardar evidencia visual ni historial de detecciones normales.
