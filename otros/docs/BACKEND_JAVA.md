# Backend Java: evaluación de lavado

El backend Spring Boot es la autoridad de sesiones y de validación. La cámara o
el servicio de inferencia envía una clase detectada, confianza y timestamp; el
backend no interpreta imágenes en la ruta de detección.

La API REST vigente usa el prefijo `/api/v1/...`; los mappings `/api/...` se
mantienen como aliases de compatibilidad. Las solicitudes y respuestas HTTP
tipadas están en `api/v1/dto/`. `DetectionRequestMapper` adapta la solicitud de
inferencia y su evidencia anidada al modelo interno; `SessionResponseMapper`
proyecta el snapshot de dominio a DTOs inmutables; y `ProtocolCatalogMapper`
convierte las estrategias y acciones del catálogo a DTOs versionados,
conservando los nombres JSON publicados. Los controladores no construyen
manualmente esos catálogos ni exponen modelos de dominio como DTOs HTTP.
La respuesta `200` de `GET /api/v1/session/active` usa `ActiveSessionResponse`;
mantiene `sessionId`, `protocolo`, `estado` y `accessRequired` para el dashboard.
Los errores REST con cuerpo se serializan mediante `ApiErrorResponse` con
campos opcionales omitidos; los errores `404` que previamente no tenían cuerpo
conservan ese contrato. Las respuestas de comandos con mensaje usan
`MessageResponse`. `ApiExceptionHandler` aplica el mismo DTO a JSON ilegible,
parámetros o partes requeridas ausentes, parámetros con tipo inválido,
`Content-Type` no admitido y cargas multipart demasiado grandes. Conserva los
estados HTTP `400`, `413` y `415` y no devuelve mensajes internos del framework.
El endpoint optativo `/api/v1/infer` usa `InferenceResponse`: conserva en el
nivel superior sus campos de modelo para no romper el contrato diagnóstico,
pero Java controla el origen de inferencia y cualquier estado/sessionId que
añada a la respuesta.
Cuando la salida contiene una clase y confianza, el controlador vuelve a
autenticar la credencial dentro de la operación atómica que procesa la
detección; una rotación o terminación durante ONNX no deja aplicar una salida
con autorización obsoleta. La respuesta añade `resultadoIngresoBackend` con
`PROCESADA` o `FILTRADA`; esos valores describen solo el ingreso al pipeline,
no significan que la máquina de estados haya acreditado un paso ni que el
procedimiento esté aprobado. Eventos incompatibles con el epoch v2,
inválidos, no autorizados o terminales producen su error HTTP en lugar de
devolver una inferencia aparentemente procesada.
El login del productor de cámara se hace con `POST /api/v1/auth/login` y el
código de vinculación. El dashboard usa `POST /api/v1/auth/dashboard-login` y
recibe un token VIEWER distinto. No hay cuentas humanas con usuario/contraseña:
se emiten tokens OWNER, DEVICE y VIEWER, opacos y solo en memoria, con vencimiento
máximo de 24 horas (por defecto, 24 h). Solo el login de productor rota el token
DEVICE y el epoch activo; el login VIEWER no modifica credenciales del productor.
La conexión WebSocket asociada al token previo se cierra en el siguiente ciclo
de publicación disponible tras detectar la revisión revocada, sin esperar al
vencimiento natural del TTL; la demora depende de la planificación del flush.
Todas las respuestas bajo `/api/**` se envían con `Cache-Control: no-store`,
`Pragma: no-cache` y `Expires: 0`. El filtro no modifica la entrega de recursos
estáticos del dashboard.
En el perfil `station`, `StationProfileSafetyGuard` requiere la clave PEM Ed25519
externa configurada en `HANDWASH_RELEASE_PUBLIC_KEY_PATH`; valida la firma
detached de los bytes exactos de `backend/models/model-manifest.json` y exige
las banderas de evidencia del piloto, validación independiente y aprobación
clínica. También rechaza cualquier blocker declarado en el manifiesto. El
verificador exige SHA-256 para el JAR Java realmente ejecutado, ambos SBOM
(Java y Python de cámara), el supervisor Python, el productor de cámara y los
locks de runtime y generador,
comparándolos con el manifiesto firmado. El supervisor verifica CPython 3.14.4,
macOS arm64 y todas las versiones exactas del lock antes de iniciar Java y
antes de cada inicio/reintento YOLO. El proceso hijo no hereda paquetes
user-site ni `PYTHONPATH`; ambos procesos arrancan con un entorno allowlist para
que variables accidentales no alteren políticas de sesión, detección o modelos.
Las lecturas del manifiesto, firma, clave, configuración de entrenamiento y
artefactos son acotadas; los hash/read abren archivos regulares sin seguir un
enlace simbólico sustituido y rechazan cambios detectados durante la lectura.
La cámara no hereda credenciales ni proxies; solo recibe el pairing code actual
y permite desactivar el clasificador auxiliar como interruptor unidireccional.
`scripts/build_handwash_station.sh` genera `backend/target/handwash-java-sbom.json`
y `backend/target/handwash-camera-python-sbom.json` en CycloneDX 1.6. El primero
incluye dependencias Maven compile/runtime; el segundo deriva de
`requirements-camera-macos-arm64.lock`. Los gates exigen sus hashes firmados en
`stationArtifacts.javaSbomSha256`, `stationArtifacts.cameraPythonSbomSha256` y
`stationArtifacts.sbomGeneratorLockSha256`;
además de validar formato y contenido, Java y Python cotejan nombres/versiones
del SBOM de cámara con el lock exacto. El generador se fija en
`cyclonedx-bom==7.5.0` y su closure de build queda fijado en
`requirements-sbom-generator-macos-arm64.lock` con hashes; ese entorno se usa
solo para generar el inventario, nunca para YOLO. Los SBOM no cubren pesos,
macOS o intérpretes; el lock runtime de cámara fija versiones, no hashes de
wheels. La firma tampoco demuestra la validez
clínica ni autentica el sistema operativo/intérprete.
El gate también exige que el `data.yaml` exacto del entrenamiento esté dentro
del proyecto, que su SHA-256 coincida con el valor firmado y que `names` asigne
los 36 IDs en el orden canónico de la taxonomía OMS firmada. Se rechazan YAML
ambiguos (claves duplicadas o aliases); un booleano `trainingDataConfigIncluded`
sin archivo verificable y taxonomía coincidente no permite arrancar.
La opción explícita `--unvalidated-demo` inicia Java con `station-demo`, que
mantiene las restricciones locales, v2, una sesión y rechaza la ingestión de
clases OMS no aprobadas; emite una advertencia no clínica y no representa
autorización de release. Solo el perfil de desarrollo permite ejercitar el
contrato experimental OMS y esa ruta tampoco autoriza una evaluación clínica.
Los dos flags OMS permanecen `false` en la configuración base. El supervisor
solo los cambia a `true` en `station` después de validar la firma y todas las
evidencias del release; Java repite el gate antes de completar el arranque y
falla cerrado si los flags no coinciden. `station-demo` nunca habilita OMS, y
forzar los flags manualmente no sustituye la autorización criptográfica.
Ambos perfiles de estación fijan y verifican los valores exactos de confianza,
confirmación de intención, continuidad temporal, timeout/retención y TTL de
credenciales. También fijan los límites de frecuencia de creación/vinculación,
la cadencia de expiración y persistencia, y los topes de publicación WebSocket;
cualquier otro override de esos valores desde variables Spring, JSON, `-D` o
argumentos de línea provoca un fallo cerrado. Para cambiar esos valores hace
falta modificar el perfil firmado y revalidar la política; las pruebas de
desarrollo conservan la posibilidad de configurar parámetros.
La base del perfil estación también queda fijada a H2 local en
`.runtime/handwash`, relativo a la raíz del proyecto que inicia el supervisor.
El guard rechaza rutas absolutas o alternativas, opciones H2 distintas de
`DB_CLOSE_ON_EXIT=FALSE`, inicialización SQL personalizada, datasources
alternativos y enlaces simbólicos en el directorio o archivos de la base; así
un override de entorno no puede redirigir ni inicializar otra base al arrancar.
Tras aceptar el inicio de `station` o `station-demo`, `.runtime` se crea si falta
y se restringe a permisos POSIX `rwx------`; los archivos existentes no se
eliminan ni reescriben.
`GET /api/v1/deployment/status` publica el modo sin secretos; el dashboard
presenta una advertencia persistente y, ante fallo de red o contrato, conserva
el estado `UNVERIFIED` con una opción de reintento. `clinicalDecisionAllowed`
permanece `false` también para `HOSPITAL_PILOT`: un piloto no equivale a
autorización de producción clínica.
`ClinicalDecisionPolicy` es la única fuente de autorización y actualmente no
hay ningún perfil que habilite decisiones clínicas. El resumen REST/WebSocket
separa `procedimientoCompletoValidado` (evidencia/modelo) de
`clinicalDecisionAllowed`; mientras la política sea falsa, `aprobado` también
es falso y el resultado se etiqueta como secuencia informativa, aunque el
procedimiento visual se haya completado.
Configuración: `HANDWASH_SESSION_ACCESS_TOKEN_TTL_MS`.
La expiración se verifica tanto con un reloj monotónico como con la fecha de
pared: una corrección hacia atrás no alarga el TTL y el tiempo de suspensión de
la Mac sí cuenta para vencerlo. El WebSocket recibe ambos límites al abrirse y
cierra la conexión al alcanzar cualquiera; la expiración no depende solo de una
fecha de pared capturada al conectar.

`POST /api/v1/infer` es una ruta heredada de diagnóstico para cargas multipart y
está deshabilitada por defecto. Se habilita explícitamente con
`HANDWASH_INFERENCE_API_ENABLED=true`; no es usada por el dashboard ni por el
capturador canónico. Si se habilita, usa exclusivamente ONNX local en Java; no
delega a un servicio de inferencia externo. El flujo activo es Python/YOLO en la Mac → JSON a
`POST /api/v1/deteccion` → validación Java → WebSocket al dashboard. Si se habilita
la ruta multipart, exige una sesión activa y token; Spring limita el archivo a
10 MB y la solicitud a 12 MB. La ruta ONNX Java aplica además límites de 8 MB
y 16 megapíxeles y rechaza concurrencia excesiva. El gateway FastAPI que
implementaba el proxy está archivado en `archive/experimental_fastapi_yolo/`;
no se inicia ni mantiene como servicio de producción. Ninguna de estas rutas de imagen acredita por sí sola la evidencia
bilateral ni sustituye la autoridad de secuencia de Java.

## Patrones y flujo

1. `Receptor`/`Subject` valida el mensaje y publica la detección (Observer).
2. `EvaluadorSecuencia` delega la progresión al State de `SesionLavado`.
3. `ValidadorReglas` ejecuta la Strategy elegida al crear la sesión.
4. `CreadorProtocolo` implementa Factory Method para crear la Strategy de 40 o
   60 segundos.
5. `CadenaIntencionLavado` aplica Chain of Responsibility a la evidencia previa
   al inicio.
6. `Notificador` observa cambios y publica estado/resumen (Observer); los
   decoradores añaden métricas y validación de persistencia sin cambiar reglas.

`DecoratorConfig` compone el Decorator de métricas alrededor de la Strategy y el
Decorator de validación alrededor del almacén de intentos fallidos. La
validación de identificadores es solo defensa en profundidad: la protección
primaria contra inyección SQL son placeholders JDBC parametrizados en cada
consulta. Los decoradores no alteran la secuencia, los umbrales ni la precisión
del modelo YOLO.

`SessionManager` serializa la tubería de observadores por sesión; sesiones
distintas pueden procesarse en paralelo. La estrategia no cambia durante una
sesión. Una detección del siguiente paso puede avanzar aun si el anterior no
cumplió el mínimo: se registra `TIEMPO_INSUFICIENTE` y el resumen queda con
observaciones. Un paso saltado no avanza la máquina de estados.
Los State solo modelan transiciones; `SesionLavado` mantiene el único contador
de tiempo acreditado. La expiración por inactividad combina tiempo monotónico
con hora de pared para que un ajuste hacia atrás no extienda el timeout y el
tiempo de suspensión de la Mac cuente; el barrido predeterminado de 1 s añade
hasta un intervalo de latencia, y un salto de reloj hacia delante puede
anticipar la expiración.
Al crear una sesión se debe indicar `CLINICO_QUIRURGICO` o `DOMESTICO`;
no se selecciona un protocolo implícitamente. `CLINICO_QUIRURGICO` se conserva
como valor wire heredado, pero su etiqueta visible aclara que la aplicación
solo evalúa siete movimientos y que el resultado es parcial; no representa
lavado quirúrgico ni certificación OMS.

`Notificador` no escribe sockets desde la tubería de detecciones ni desde el
monitor global. Usa cuatro trabajadores fijos y una cola de 128 tareas; por
cliente conserva como máximo el estado pendiente más reciente y un resumen
terminal. En saturación conserva esos slots y los reintenta en los siguientes
flushes. El estado terminal se envía antes del resumen. Si un `sendMessage`
supera `HANDWASH_NOTIFICATION_SEND_TIMEOUT_MS` (3 s por defecto), se desconecta
ese cliente lento; la sesión retiene su resultado para una instantánea al
reconectar dentro del periodo de retención.

## Vinculación del capturador de la Mac

`POST /api/v1/session` devuelve `sessionId`, `pairingCode` y `accessToken` del
propietario. El código aleatorio de 10 caracteres se muestra como
`XXXXX-XXXXX`. `POST /api/v1/auth/login` con el código y
`producerProtocolVersion: "2"` devuelve el ID y un token distinto para el
capturador. `POST /api/v1/session/pair` se conserva como alias de compatibilidad.
El dashboard vinculado a una sesión creada por YOLO usa
`POST /api/v1/auth/dashboard-login` con `{ "code": "XXXXX-XXXXX" }`; devuelve
`role: "VIEWER"` y no llama a la operación de reemplazo del productor.
El código deja de resolver
cuando la sesión termina o se elimina. Solo el token del propietario permite
recuperar el código con `GET /api/v1/session/{id}` o eliminar la sesión.
El proceso YOLO de la Mac usa la cámara de Continuidad del iPhone; no se instala
una app en el teléfono. El dashboard puede iniciar una sesión y pasar el código
al capturador, o vincularse con el código que el capturador imprime al crearla.

Con `HANDWASH_SESSION_ACCESS_REQUIRED=true` (valor predeterminado),
`GET /api/v1/session/{id}` y `GET /api/v1/session/{id}/attempts` admiten OWNER,
DEVICE o VIEWER; el código de vinculación solo se devuelve a OWNER. Las rutas
`DELETE/PATCH /api/v1/session/{id}`, `POST /api/v1/session/{sessionId}/producer-epoch`,
`POST /api/v1/deteccion` y, si se habilita, `POST /api/v1/infer` requieren
credencial de productor/propietario y sesión activa. El
WebSocket requiere un ticket de un solo uso en
`/ws/{sessionId}?ticket=...`. El dashboard obtiene el ticket con
`POST /api/v1/session/{sessionId}/websocket-ticket` y un Bearer vigente; vence
en 30 s, se consume en el handshake, está ligado a una sesión y se rechaza si
la credencial fue rotada. El token largo nunca viaja en la URL. Sin ticket válido
se cierra con código `1008`. El capturador oficial presenta el token de
dispositivo directamente al API Java al registrar el epoch y enviar
detecciones. DEVICE permite leer estado y enviar detecciones, pero no eliminar
la sesión ni consultar el código. VIEWER solo puede leer estado/historial y
recibir actualizaciones WebSocket; no puede afectar al productor ni a la sesión.

## Protocolo del productor y deduplicación

La ausencia de `producerProtocolVersion` conserva explícitamente la modalidad
legada v1 para sesiones antiguas y clientes de prueba: esos productores siguen
enviando el payload anterior sin epoch ni número de frame. Una sesión v1 no
acepta campos v2 hasta que un cliente autenticado la registre como v2; dichos
payloads reciben el ACK filtrado. El registro v2 no se negocia como un fallback
silencioso.
El gateway experimental FastAPI quedó archivado en
`archive/experimental_fastapi_yolo/`; sus solicitudes multipart representan un
flujo heredado v1 y no son parte de la estación. `/api/v1/infer` continúa
deshabilitado por defecto. El único productor soportado es el capturador de
Continuity Camera, que usa el protocolo v2.

El capturador oficial indica `producerProtocolVersion: "2"` al crear una sesión
o al emparejarse. Al emparejar una sesión existente como productor, Java habilita
el requisito v2 e invalida cualquier epoch activo antes de devolver el token del
dispositivo; esto no aplica al login VIEWER separado del dashboard.
una vinculación v1 posterior a una sesión estricta responde
`409 CAPTURADOR_PROTOCOL_VERSION_REQUIRED`. Luego Python envía
`POST /api/v1/session/{sessionId}/producer-epoch` con el token de propietario o
dispositivo. El capturador oficial conserva `X-Session-Token`; otros clientes
HTTP pueden usar `Authorization: Bearer`. Java devuelve un UUID nuevo en
`producerEpoch`; cada registro siguiente rota el epoch y reinicia el watermark
de secuencias. El código de emparejamiento conserva su papel actual de
vinculación y no sustituye el token que autentica el endpoint de registro.

```http
POST /api/v1/auth/login
Content-Type: application/json

{"code":"XXXXX-XXXXX","producerProtocolVersion":"2"}
```

El login declara `tokenType: "Bearer"`. Las rutas HTTP protegidas aceptan
`Authorization: Bearer <accessToken>`; `X-Session-Token` sigue admitido para el
capturador Python y el dashboard existentes. Si se mandan ambas cabeceras, sus
tokens deben coincidir; una cabecera `Authorization` mal formada o en conflicto
se rechaza con `401`.

```http
POST /api/v1/session/{sessionId}/producer-epoch
Authorization: Bearer <owner-or-device-token>

{"sessionId":"...","producerEpoch":"...","protocolVersion":2,"rotated":false}
```

Cada detección v2 incluye `eventType: "DETECTION"`, `producerEpoch`, un
`frameSequence` no negativo y creciente dentro del epoch, y opcionalmente
`captureAgeMs`. Si lleva `evidenciaMovimiento`, su campo `secuencia` debe ser
igual a `frameSequence`. Si lleva `evidenciaJabon`, también debe incluir
`evidenciaJabonSecuencia`, igual al frame de la inferencia que produjo el mapa
regional. En solicitudes v1 sin `frameSequence`, debe coincidir con
`evidenciaMovimiento.secuencia`. Java rechaza evidencia ausente, huérfana o de
otro frame antes de incorporarla a la cobertura OMS. El productor genera el frame
ID en el bucle de captura; reiniciar FFmpeg dentro del mismo proceso conserva el
epoch y el contador global.

Para acreditar pasos ordinarios de un productor v2 estricto, `evidenciaMovimiento`
incluye además `poseKeypoints` (`[2,21,3]`), `handBoxes` (`[2,4]`), `frameWidth`
y `frameHeight`. Son coordenadas/confianzas numéricas del mismo frame, nunca
píxeles. Java valida forma y límites antes de copiarlas a arreglos primitivos,
ignora el escalar `movimientoNormalizado` recibido y recalcula el movimiento con
OpenCV sobre las dos poses, compensando una transformación afín global de cámara.
Mantiene solo la pose previa por sesión/epoch; la primera observación establece
la base y no acredita paso. Las coordenadas se descartan antes de notificar los
observadores y no se persisten. La presencia bilateral de tres segundos es una
compuerta separada; no sustituye esta evidencia por frame.

Al reiniciar Python se vuelve a registrar y Java invalida de inmediato cualquier
evento pendiente del epoch anterior. La secuencia puede saltar cuando la cola
acotada reemplaza una observación; no tiene que ser contigua.

Las señales locales `FONDO` y `OMS_SIN_EVIDENCIA` no describen una inferencia de
YOLO. En v2 se transportan como `eventType: "CONTROL"` con un `controlSequence`
propio y `frameWatermark`. Java usa ese watermark para rechazar inferencias
anteriores que todavía estuvieran en vuelo; el control no incluye evidencia de
manos, evidencia regional de jabón ni reutiliza el `frameSequence` de una detección.
Java solo admite esas dos clases de control; una clase de paso no puede evitar el
requisito de frame al
marcarse como control.

Antes de aceptar fases ordinarias, el productor envía un evento independiente
`PRESENCE` al cambiar el número de manos y con objetivo de 250 ms entre poses
nuevas. El
evento usa el `controlSequence` compartido y el `frameWatermark`, añade
`presenceHandsVisible` (0, 1 o 2) y no incluye secuencia de detección ni evidencia
de movimiento/jabón. Java valida epoch, orden y conteo, pero el pulso no entra a
State, Strategy u Observer. Java mide por separado con su reloj monotónico de
recepción 3000 ms continuos de dos manos; `captureAgeMs` sigue siendo diagnóstico,
no aporta duración a la compuerta. Antes del primer inicio,
conteo menor a dos o intervalo mayor a 500 ms reinicia el dwell. Las detecciones
de fase prematuras conservan el ACK de transporte, pero se descartan y no llegan
a los observadores. Tras el inicio, el gate inicial queda latched; cada fase
todavía exige su evidencia bilateral fresca. `OMS_CONTACTO_RIESGO` mantiene su
excepción de seguridad.

```json
{
  "sessionId": "...",
  "claseDetectada": "PRESENCIA_MANOS",
  "confianza": 1.0,
  "timestamp": "2026-10-07T12:00:00.000Z",
  "producerEpoch": "...",
  "eventType": "PRESENCE",
  "controlSequence": 19,
  "frameWatermark": 911,
  "captureAgeMs": 24,
  "presenceHandsVisible": 2
}
```

`OMS_CONTACTO_RIESGO` es una detección fail-closed y no una fase del protocolo:
si está autenticada y supera el umbral OMS, Java permite procesarla aunque falte
la medición bilateral de pose, para que la oclusión no degrade el evento a un
rechazo genérico. Las once fases ordinarias siguen requiriendo exactamente dos
manos, medición espacial válida y evidencia fresca.

```json
{
  "sessionId": "...",
  "claseDetectada": "FONDO",
  "confianza": 1.0,
  "timestamp": "2026-09-27T18:00:00.000Z",
  "producerEpoch": "...",
  "eventType": "CONTROL",
  "controlSequence": 18,
  "frameWatermark": 910,
  "captureAgeMs": 12
}
```

El guard de epoch, secuencia y correspondencia de evidencia corre bajo el lock
de la sesión antes de `Receptor`, State, Strategy y Observer. Epoch no registrado
o antiguo, secuencia ausente/duplicada/atrasada, evidencia desparejada y campos
v2 en sesión v1 responden `HTTP 200` con el ACK existente
`{"accepted":false,"filtered":true}`; incrementan un contador por motivo y no
alteran estado, votos ni duración. El ACK aceptado sigue significando que el
receptor procesó el mensaje, nunca que el State acreditó un paso ni que el lavado
quedó validado. Las respuestas filtradas por la guarda v2 pueden incluir la
cabecera diagnóstica `X-Producer-Rejection-Reason` sin cambiar ese JSON; el
capturador se detiene ante epoch no registrado/antiguo. Sesión terminada y sesión
borrada conservan sus respuestas `409` y `404`, respectivamente.

`captureAgeMs` lo mide Python desde captura hasta envío/reintento. Java puede
registrarlo en `handwash.producer.capture.age`, pero no compara relojes de
procesos, no rechaza por antigüedad y no usa el valor para tiempo clínico. Las
métricas agregadas `handwash.producer.epoch.registrations`,
`handwash.producer.epoch.rotations` y
`handwash.producer.rejections{reason=...}` usan etiquetas constantes, sin ID de
sesión, token, frame ni secuencia. La configuración base expone únicamente
`/actuator/health`; las métricas no se publican en ese perfil. El launcher local
activa `local` y expone `/actuator/metrics` para diagnóstico. No uses ese perfil
al enlazar el servidor a una red hospitalaria. En despliegue, mantén las
métricas fuera del listener público o protégelas con una frontera de
administración autenticada.

Los fallos al persistir o borrar la caché acotada de intentos se cuentan en
`handwash.failed-attempt.persistence.failures{operation=write|delete|retention_cleanup}`.
La etiqueta es un conjunto fijo; no se publican IDs de sesión ni detalles del
error de base de datos en esa métrica. Los logs de persistencia tampoco imprimen
el ID de sesión ni el mensaje SQL/error; los eventos de conexión WebSocket omiten
los IDs de sesión/cliente y la dirección remota para reducir datos correlacionables.

Para separar problemas de encuadre de fallos de clasificación, el evaluador
registra `handwash.detection.intent.rejections{reason=...}` al rechazar una
observación parcial. Sus razones son categorías fijas (`sin_evidencia_reciente`,
`encuadre_incompleto`, `evidencia_espacial_no_verificable`,
`sin_gesto_de_lavado`, `inicie_con_palmas`, `gesto_incierto` y `otro`). No
incluye clase libre, ID de sesión ni datos de imagen. Una ausencia de rechazo
no equivale a paso acreditado: los ACK siguen siendo de transporte y la
confirmación de secuencia permanece en State.

`GET /api/v1/session/active` sigue sirviendo para la configuración de una sola
cámara: devuelve `204` sin sesiones, `200` con una única sesión y `409`
(`SESIONES_ACTIVAS_AMBIGUAS`) con dos o más. En modo protegido, esa respuesta
no entrega token: el capturador debe vincularse con el código aun si hay una sola
sesión. `HANDWASH_SESSION_ACCESS_REQUIRED=false` conserva el flujo antiguo
sin token solo para pruebas locales controladas.
La memoria se limita a 128 sesiones por defecto (`HANDWASH_MAX_SESSIONS`);
`POST /api/v1/session` devuelve `429 LIMITE_SESIONES` al alcanzar el límite.
Las sesiones terminales se purgan tras el periodo de retención configurado.

Los tokens son capacidades efímeras de sesión; no autentican la identidad
humana y desaparecen al reiniciar Java. Tampoco prueban que una detección haya
venido de una cámara real: un cliente autorizado aún podría enviar metadatos
fabricados. El canal HTTP/WS sin TLS transmite tokens y tickets en claro; use
HTTPS/WSS antes de operar en una red no confiable. La URL WebSocket solo lleva
un ticket aleatorio, de un uso y máximo 30 s; no registre URLs ni tickets.

Los observadores de State y Strategy son críticos: si uno falla, el evento
recibe un error, la sesión expira con `ERROR_PROCESAMIENTO` y no puede quedar
aprobada. Un fallo aislado del canal de notificación se registra sin interrumpir
la validación. `/api/v1/protocols` publica los umbrales de las mismas Strategy que
usa el evaluador.

## Tiempo y resultados

- Solo se acreditan intervalos entre detecciones consecutivas de la misma
  clase con separación máxima de 1500 ms por defecto. Se puede ajustar con
  `HANDWASH_MAX_DETECTION_GAP_MS` (100 a 5000 ms) para cámaras más lentas.
  `FONDO`, otra clase o una pausa mayor cortan la continuidad. Los fotogramas
  atrasados no cambian la sesión.
- `timestamp` es ISO 8601 y obligatorio en la API. Se aceptan eventos entre
  60 segundos atrás y 30 segundos adelante del reloj del servidor. El tiempo
  acreditado usa el instante de recepción en Java; el cliente no puede
  adelantar su reloj para simular la duración del lavado. Una confianza bajo
  el umbral configurado se filtra sin alterar la sesión.
- El resumen usa `resultado`: `INCOMPLETO`,
  `SECUENCIA_COMPLETADA_SIN_VALIDAR_PROCEDIMIENTO_COMPLETO`,
  `SECUENCIA_OMS_COMPLETADA_SIN_VALIDAR_MODELO_Y_EVIDENCIA`,
  `SECUENCIA_COMPLETADA_CON_INFRACCIONES` o `APROBADO` solo cuando una futura
  ruta OMS validada cumpla todas sus puertas. Incluye `pasosFaltantes`, tiempos
  por paso e infracciones. El
  historial se limita a 500 entradas y cuenta las anteriores en
  `infraccionesOmitidas`.
- `tiempoTotalSegundos` suma la actividad observada acreditada, redondeada a
  segundos enteros; `duracionMs` en el detalle de sesión es tiempo de reloj.
  No son intercambiables.

## Alcance del protocolo OMS

El detector actual reconoce siete clases de fricción definidas por el proyecto;
su correspondencia uno-a-uno con los gestos numerados oficiales de la OMS no se
ha validado. No observa si se
mojan las manos, se aplica jabón o producto, se enjuagan, se secan, ni el
apagado del grifo; por ello evalúa la secuencia de movimientos detectables y
no certifica por sí solo el procedimiento completo. La OMS publica métodos
distintos: lavado con agua y jabón (40–60 s, con preparación y cierre) y
fricción con solución alcohólica (20–30 s, que termina al secarse). Las
duraciones de `CLINICO_QUIRURGICO` (60 s) y `DOMESTICO` (40 s) son reglas
configuradas para este proyecto, no una declaración de equivalencia clínica
con esos métodos. Consulta los [pasos OMS para lavado con jabón](https://www.who.int/docs/default-source/patient-safety/how-to-handwash-poster.pdf)
y los [pasos OMS para fricción alcohólica](https://www.who.int/docs/default-source/patient-safety/how-to-handrub-poster.pdf)
antes de presentar un resultado como evaluación integral.

## Verificación

Desde `backend/`, ejecutar `mvn test`. La prueba de integración abre un puerto
local temporal; el entorno que la ejecuta debe permitir conexiones localhost.
Las pruebas cubren el flujo REST, la serialización por sesión, la validación de
mensajes, las pausas de cámara, el orden de fotogramas, el resumen expirado,
los permisos de sesión y el WebSocket real. Un WebSocket sin token válido o
con sesión inexistente se cierra; si una sesión
conectada termina, el siguiente mensaje recibe `SESION_TERMINADA`.

Los umbrales de los protocolos son parámetros de este proyecto. Antes de usar
el resultado para decisiones clínicas, requieren validación experimental con
el modelo, cámaras y población objetivo.

## Límites actuales

Falta identidad de usuarios, persistencia de auditoría y
política de reconexión después de reiniciar el servidor. La validez clínica
del modelo y de los umbrales tampoco está demostrada. Ningún resultado debe
usarse como evidencia clínica hasta validar esos aspectos y el transporte TLS.

La instancia incorpora un límite local configurable para creación de sesiones
y emparejamiento (`HANDWASH_SESSION_CREATE_RATE_LIMIT`,
`HANDWASH_SESSION_PAIR_RATE_LIMIT`). En despliegues con varias réplicas debe
moverse al gateway o a un almacén compartido.
