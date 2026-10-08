# ADR-0001: Epoch autenticado y secuencia de frames del productor

## Estado

Aceptada

## Fecha

2026-09-27

## Contexto

El capturador local ya empareja la evidencia espacial con una secuencia de frame
en Python, pero esa identidad no llegaba a Java. El backend aceptaba un evento
REST autenticado sin distinguir un frame repetido, atrasado o producido por una
ejecución anterior de Python. Una respuesta HTTP perdida también podía ocasionar
que se reintentara un evento ya procesado.

### Restricciones

- Mantener el recorrido local Python/YOLO → REST Java → WebSocket → dashboard.
- Reutilizar la credencial owner/device existente; no introducir un método de
  autenticación alternativo.
- Conservar el ACK de `/api/v1/deteccion` (y su alias legado `/api/deteccion`)
  y el soporte deliberado de productores v1.
- No usar relojes monotónicos de procesos diferentes para tiempo clínico.
- No cambiar clases, umbrales, votos, duración, intención o secuencia clínica.
- Mantener los frames en memoria y no guardar media.

## Decisión

Se incorpora el protocolo de productor v2. Al crear o emparejar una sesión, el
capturador oficial declara `producerProtocolVersion: "2"`. La sesión queda en
modo estricto antes de iniciar la publicación. Luego Python registra cada
ejecución en `POST /api/v1/session/{sessionId}/producer-epoch` usando el mismo
`X-Session-Token` owner/device ya emitido por Java. El endpoint devuelve un UUID
`producerEpoch` nuevo; volver a registrarse lo rota e invalida el anterior bajo
el lock de esa sesión.

Cada observación YOLO v2 lleva `eventType: "DETECTION"`, el epoch y un
`frameSequence` entero no negativo, estrictamente creciente dentro de dicho
epoch. Si hay `evidenciaMovimiento`, `secuencia` debe coincidir exactamente con
ese frame. Si el evento lleva evidencia regional de jabón, `evidenciaJabonSecuencia`
también debe coincidir exactamente con `frameSequence`; en v1 se contrasta con
la secuencia de la evidencia espacial. Java valida el sobre v2 y reserva
atómicamente la secuencia antes de validar timestamp/calidad de evidencia en
`Receptor`. Si el sobre es válido, el frame queda consumido aun cuando la
validación de dominio lo rechace; se necesita una inferencia nueva, no un
reintento corregido del mismo frame. Epoch incorrecto, clase no canónica,
secuencia repetida/atrasada o secuencias de evidencia desalineadas se rechazan
antes de reservar y no invocan State, Strategy u Observer ni tocan votos/duración.
El ACK JSON se conserva; las respuestas filtradas pueden añadir
`X-Producer-Rejection-Reason`, y el capturador se detiene cuando el header
indica que su epoch dejó de estar activo.

Las señales de control generadas por el productor, como la pérdida sostenida de
evidencia, usan `eventType: "CONTROL"`, un `controlSequence` propio y el
`frameWatermark` más reciente. El watermark invalida inferencias que seguían en
vuelo de frames anteriores, sin convertir el control en una detección espacial.
Los controles no pueden llevar evidencia de pose ni regional de jabón; esos sobres
se filtran sin invocar observers ni consumir las secuencias de control. Solo `FONDO`
y `OMS_SIN_EVIDENCIA` pueden usar el tipo CONTROL. El productor también envía
`eventType: "PRESENCE"` con `controlSequence`, `frameWatermark` y el conteo de
manos visibles (0–2), sin evidencia de fase. Java exige 3 s continuos de dos
manos y un máximo de 500 ms entre observaciones antes de permitir fases; el pulso
no invoca State, Strategy u Observer. Cada registro reinicia los watermarks de
frame, control y presencia; un reinicio de FFmpeg dentro del mismo Python mantiene
el epoch y el contador de captura del proceso.

La versión v1 se conserva sólo para sesiones que se crearon/emparejaron sin
declarar v2. Esas sesiones aceptan el payload antiguo sin campos v2. Al
emparejar una sesión activa con v2, Java invalida cualquier epoch previo antes
de devolver el token al nuevo capturador. Una sesión estricta no puede volver a
v1: un emparejamiento v1 recibe `409`, y una detección v1 presentada al endpoint
recibe el ACK filtrado. Un payload con campos v2 tampoco se acepta en una sesión
v1 hasta completar el registro autenticado.

La edad `captureAgeMs` es opcional y sólo diagnóstica. Java la mide en una
métrica agregada, sin compararla con su propio reloj y sin usarla para acreditar
duración ni rechazar frames.

### Diagrama

```text
Python crea/empareja con v2
          │ token owner/device existente
          ▼
POST /api/v1/session/{id}/producer-epoch ──► Java rota producerEpoch
          │                                     │
          │ DETECTION(epoch, frameSequence)      │ guarda watermark bajo lock
          └─────────────────────────────────────►│ valida coincidencia de evidencia
                                                ├─ válido → Receptor → State/Strategy → Observer
                                                └─ duplicado/antiguo/mismatch → ACK filtrado

FFmpeg reconecta: mismo Python, epoch y secuencia de captura
Python reinicia: nuevo registro, epoch nuevo, contador local nuevo
```

### Interfaces principales

- `POST /api/v1/session` y `POST /api/v1/auth/login` admiten `producerProtocolVersion`
  (`1` por defecto, `2` para el capturador oficial).
- `POST /api/v1/session/{sessionId}/producer-epoch` requiere `X-Session-Token` y
  devuelve `producerEpoch`, `protocolVersion` y si hubo rotación.
- `POST /api/v1/deteccion` v2 lleva `producerEpoch`, `eventType`, `frameSequence`,
  `captureAgeMs` opcional y, si corresponde, secuencias coincidentes en
  `evidenciaMovimiento.secuencia` y `evidenciaJabonSecuencia`.
- Los controles v2 llevan `eventType: CONTROL`, `controlSequence` y
  `frameWatermark`; no llevan evidencia espacial.
- Los pulsos v2 de manos llevan `eventType: PRESENCE`, secuencia de control,
  watermark y conteo `presenceHandsVisible`; no acreditan pasos.

## Alternativas consideradas

### Seguir usando sólo el token de sesión

- **Descripción:** mantener la autorización actual sin identificar el proceso
  ni la fuente de cada frame.
- **Ventajas:** no cambia los mensajes ni la memoria del backend.
- **Desventajas:** el token no distingue ejecuciones y no permite deduplicar ni
  invalidar inferencias en tránsito.
- **Motivo de rechazo:** no resuelve el problema de integridad solicitado.

### Usar el timestamp del cliente para deduplicar

- **Descripción:** inferir orden o edad desde el ISO-8601 aportado por Python.
- **Ventajas:** no requiere epoch ni contadores adicionales.
- **Desventajas:** el reloj de pared puede saltar, repetirse o desincronizarse y
  no sirve como reloj monotónico clínico.
- **Motivo de rechazo:** el timestamp se mantiene como validación de formato,
  no como identidad de frame ni medida de duración.

## Consecuencias

### Positivas

- Reintentos y eventos retrasados se filtran sin duplicar procesamiento.
- Un registro nuevo invalida inmediatamente el epoch anterior para esa sesión.
- El estado de una sesión no comparte epochs o watermarks con otras sesiones.
- El payload conserva el significado del ACK y los observadores reciben sólo
  eventos que superan la integridad del transporte.

### Costes y riesgos

- Se conserva un UUID y tres watermarks en memoria por sesión (frames de paso,
  presencia y controles).
- Una cola acotada puede saltar números de frame; se exige crecimiento, no
  contigüidad.
- Un cliente autorizado que registra otra ejecución rota el epoch anterior;
  esto es intencional para que un reinicio prevalezca sobre procesos viejos.
- Clientes antiguos no pueden publicar en sesiones ya marcadas estrictas.
- `captureAgeMs` sigue siendo dato aportado por el productor y sólo vale como
  diagnóstico aproximado.

## Implicaciones de rendimiento

- **CPU:** comparación de epoch y enteros bajo el lock que ya serializa la
  sesión; ningún I/O adicional en la ruta crítica.
- **Memoria:** campos escalares por sesión; no se almacena historial de frames.
- **Red:** unos pocos campos JSON por detección, sin transferir imágenes.
- **Medición:** benchmark loopback sintético de un y ocho flujos, separado de
  YOLO, cámara e inferencia; resultados y límites en
  `docs/PERFORMANCE_BASELINE_2026-09-27.md`.

## Migración y validación

Los clientes existentes siguen v1 al crear/emparejar sin `producerProtocolVersion`.
El capturador canónico solicita v2 al crear o emparejar y registra el proceso
con la credencial ya recibida. V2 no se degrada a v1 en una sesión estricta.
Las pruebas Java cubren secuencia creciente, repetición, atraso, rotación,
desajuste de evidencia, carreras, control/watermark, separación de sesiones,
sesiones terminales y ACK/compatibilidad. Las pruebas Python cubren registro,
payload, relación evidencia-frame y persistencia del contador durante una
reconexión interna de FFmpeg.

## Decisiones relacionadas

- `AGENTS.md`, secciones 2.1 y 4: arquitectura local y payloads.
- `docs/BACKEND_JAVA.md`: autenticación, política v1/v2 y métricas.
