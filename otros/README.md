# Hand Wash Compliance System

Sistema de evaluación de movimientos de lavado de manos con backend Java (Spring Boot), dashboard React y YOLO26, todos ejecutados en esta Mac. El iPhone funciona únicamente como cámara de Continuidad.

## Runtime canónico (actual)

- **Backend principal:** `backend/` Spring Boot
- **Inferencia y captura:** `scripts/run_yolo26_continuity_camera.py` con `backend/models/handwash_yolo26n_7pasos.pt`
- **Manos y dedos:** `backend/models/yolo26s-pose-hands.pt` (1 mano + 21 keypoints)
- **Video anotado:** stream MJPEG local en `http://127.0.0.1:8091/video.mjpg`
- **Puerto por defecto:** `8080` (configurable con `SERVER_PORT`)
- **API REST canónica:** `/api/v1/...`
  - `POST /api/v1/session` (crea sesión y token OWNER)
  - `GET /api/v1/session/active`
  - `POST /api/v1/auth/login` (login de cámara con código de vinculación; crea token DEVICE)
  - `POST /api/v1/auth/dashboard-login` (vincula el visor con token VIEWER, sin reemplazar YOLO)
  - `POST /api/v1/session/pair` (alias de compatibilidad para el login)
  - `POST /api/v1/session/{sessionId}/producer-epoch`
  - `POST /api/v1/session/{sessionId}/websocket-ticket` (canjea Bearer por ticket WebSocket de un solo uso)
  - `GET /api/v1/session/{sessionId}`
  - `GET /api/v1/session/{sessionId}/attempts` (solo metadatos de fallos; token vigente)
  - `DELETE /api/v1/session/{sessionId}`
  - `GET /api/v1/protocols` y `/api/v1/protocols/oms`
  - `POST /api/v1/deteccion` (captura canónica; DTO v1 y ACK compacto)
  - `POST /api/v1/infer` (diagnóstico opcional, deshabilitado por defecto)
  - `WS /ws/{sessionId}`
- **Compatibilidad:** los endpoints Java anteriores bajo `/api/...` continúan como alias temporales. El dashboard y los productores activos usan `/api/v1/...`.
- **Backend activo:** Java/Spring Boot; la única ruta Python activa es el productor local de cámara/YOLO, que envía detecciones a Java.
- **Código experimental archivado:** gateways FastAPI, prototipos iOS, páginas estáticas duplicadas y documentación previa se conservan fuera del runtime en [`archive/`](archive/README.md).

## Configuración backend Java

El backend aplica seis patrones: State, Strategy, Observer, Factory Method,
Chain of Responsibility y Decorator. La cadena de intención distingue presencia de manos
de fricción sostenida antes de iniciar o acreditar pasos. El productor envía
solo metadatos numéricos de keypoints, sin imágenes; para v2, Java recalcula con
OpenCV el movimiento bilateral y no confía en el escalar del productor. Java
confirma el inicio y controla la secuencia y las pausas. Detalles, contrato y límites en
[Patrones e intención](docs/PATRONES_E_INTENCION.md).
El Factory Method comprueba al crear la Strategy que las siete duraciones de
fase sean positivas y sumen exactamente el objetivo anunciado de 40 o 60 s.

### API v1, login y vencimiento de credenciales

Los controladores REST aceptan el prefijo canónico `/api/v1`. Las solicitudes y
respuestas HTTP de sesión, autenticación, detecciones y catálogo de protocolos
usan DTOs explícitos bajo `backend/src/main/java/com/handwash/api/v1/dto/`.
`DetectionRequestMapper` traduce también la evidencia anidada al modelo de
dominio; `SessionResponseMapper` proyecta las respuestas internas mutables a
DTOs inmutables; y `ProtocolCatalogMapper` transforma las estrategias internas
en respuestas versionadas. El contrato v1 conserva sus nombres y valores JSON
sin exponer las clases de negocio dentro de sus DTOs.
La respuesta de descubrimiento `GET /api/v1/session/active` usa el DTO
`ActiveSessionResponse` y conserva los cuatro campos que consume el dashboard.
Los errores REST con cuerpo usan `ApiErrorResponse`, que omite los campos
opcionales vacíos y conserva los códigos/mensajes publicados; los `404` que ya
eran respuestas vacías permanecen así. Los comandos que devuelven un mensaje
usan `MessageResponse`.
`ApiExceptionHandler` normaliza también los errores de infraestructura de MVC
para JSON mal formado, parámetros/partes obligatorios ausentes, tipos de
parámetro inválidos, `Content-Type` no admitido y cargas multipart demasiado
grandes. Mantiene los códigos HTTP (`400`, `413` y `415`) y no expone trazas ni
mensajes internos de Spring.
Antes de la deserialización, `ApiPayloadLimitFilter` limita los cuerpos de las
rutas mutables `/api/**` a 64 KiB y las detecciones (`/api/v1/deteccion` y su
alias legacy) a 16 KiB; los excesos reciben `413 CARGA_EXCEDE_LIMITE`. Para
conservar el camino rápido de cámara, si hay `Content-Length` válido dentro del
límite el filtro no copia ni lee el cuerpo; solo almacena en memoria, con cota,
las solicitudes sin longitud declarada. `/api/v1/infer` y `/api/infer` quedan
fuera de este filtro porque son multipart y conservan sus límites específicos
de Spring y `ImagePayloadValidator`.
La ruta diagnóstica opcional `/api/v1/infer` responde mediante `InferenceResponse`:
mantiene aplanados los campos variables de salida del modelo para compatibilidad,
mientras reserva y controla desde Java `inferenceSource`, `sessionId` y
`estadoSesion` cuando están presentes.
Si también envía una clase/confianza a la sesión, la credencial se vuelve a
validar atómicamente después de ONNX. `resultadoIngresoBackend` informa
`PROCESADA` o `FILTRADA`; no equivale a paso acreditado ni a lavado aprobado.
Una sesión terminada, una credencial rotada o un sobre incompatible con v2 se
devuelve como error HTTP, no como inferencia procesada.

El acceso de esta aplicación local es **basado en capacidades de sesión**, no
en cuentas con usuario/contraseña: al crear la sesión se emite un token OWNER;
el capturador usa `POST /api/v1/auth/login` con el código y recibe un token
DEVICE nuevo; el dashboard usa `POST /api/v1/auth/dashboard-login` y recibe un
token VIEWER independiente. El login VIEWER no rota credenciales DEVICE ni
invalida el epoch activo del productor. Cada token es aleatorio,
opaco, se guarda únicamente en memoria y vence a las 24 horas como máximo.
La respuesta incluye `accessTokenExpiresAt` en ISO-8601. Al volver a iniciar
login de productor con el código se rota el token DEVICE anterior. No se persisten tokens
ni se implementa renovación silenciosa; tras vencer, se requiere iniciar sesión
otra vez. Esa rotación también cierra el WebSocket anterior durante el siguiente
flush programado, mediante una revisión interna no secreta de la credencial.
Todas las respuestas de `/api/**` incluyen `Cache-Control: no-store`,
`Pragma: no-cache` y `Expires: 0` para impedir que se almacenen tokens, tickets
o datos de sesión. La aplicación comprueba la expiración con tiempo monotónico para que
un ajuste del reloj hacia atrás no prolongue el acceso; también contrasta la
fecha de pared para que el tiempo suspendido/sueño de la Mac cuente hacia el TTL.
El WebSocket conserva ambos límites al autenticarse y se cierra cuando vence
cualquiera de ellos; una conexión ya abierta no puede sobrevivir a un ajuste del
reloj de pared hacia atrás.
El dashboard puede leer estado e intentos fallidos, pero su token VIEWER no puede
enviar detecciones, registrar epochs, ejecutar inferencia ni borrar la sesión.
Canjea su token por `POST /api/v1/session/{sessionId}/websocket-ticket`;
Java emite un ticket aleatorio, ligado a la sesión, de un solo uso y válido por
un máximo de 30 segundos. Se consume durante el handshake y se vuelven a validar
la sesión y la credencial; ningún token largo de sesión viaja
en la URL del WebSocket. Los tickets pendientes son efímeros y están acotados.
El TTL se configura con `HANDWASH_SESSION_ACCESS_TOKEN_TTL_MS` (por defecto
`86400000` ms). Se aceptan valores de 1 segundo a 24 horas inclusive; nunca se
puede configurar un token por encima de un día.
La expiración de sesiones por inactividad combina reloj monotónico y fecha de
pared: un ajuste hacia atrás no prolonga el timeout y el tiempo suspendido de
la Mac cuenta. El barrido predeterminado cada 1 s puede añadir hasta un
intervalo después de alcanzar el timeout; un salto de reloj hacia delante
también puede anticipar la expiración.
El límite deslizante de login y creación de sesiones usa `System.nanoTime`,
no la fecha del sistema, de modo que ajustes NTP o manuales no acortan ni
prolongan la ventana anti-fuerza-bruta. Sus buckets están acotados por cliente;
por defecto se permiten 10 intentos de vinculación y 20 creaciones por minuto.
Las rutas HTTP protegidas aceptan `Authorization: Bearer <accessToken>` y
mantienen `X-Session-Token` para el capturador y clientes existentes. Si ambas
cabeceras llegan, deben contener el mismo token.

### Decorator y protección SQL

`backend/src/main/java/com/handwash/config/DecoratorConfig.java` cablea los
decoradores y sus dependencias:

- `decorator/repository/SqlInjectionGuardFailedAttemptStoreDecorator` valida
  que el identificador de sesión tenga formato UUID antes de permitir consultas
  de caché. La defensa primaria contra SQL injection sigue siendo el uso de
  `JdbcTemplate` con parámetros `?` en `repository/FailedAttemptRepository`;
  el decorador es defensa en profundidad, no una sustitución de consultas
  parametrizadas ni una promesa de proteger SQL dinámico inseguro.
- `decorator/strategy/DecoradorMetricasEstrategiaLavado` envuelve la Strategy
  de 40/60 s y cuenta resultados de validación agregados y por paso mediante
  etiquetas fijas de protocolo, enum de paso y resultado. Delega las reglas sin
  alterar umbrales, pasos ni tiempos; ayuda a localizar qué validación temporal
  Java acepta o rechaza, pero **no mide la precisión de YOLO ni aumenta por sí
  mismo la precisión de detección**. Estas métricas tampoco equivalen a
  ground truth: cuentan invocaciones de la Strategy.
- `strategy/ReglaValidacionStrategyFactory` crea la Strategy del protocolo y
  la decora al crear la sesión. State sigue gobernando la secuencia; Chain of
  Responsibility filtra intención/evidencia; Observer comunica los resultados.

Estructura de responsabilidades añadida para esta API:

```text
api/v1/                 DTOs, mapper y login HTTP versionado
api/v1/ApiExceptionHandler  errores MVC convertidos al DTO estable
api/v1/dto/InferenceResponse  envelope del endpoint diagnóstico /infer
controller/             adaptadores REST de sesión, detección e inferencia
service/                 ciclo de vida y coordinación de sesiones
service/persistence/     cola, reintentos y serialización de caché de fallos
security/                login por código, resolver Bearer y registro de credenciales
security/SessionCredentialRegistry  emisión, rotación, comparación y expiración de tokens
security/SessionPairingCodeRegistry  generación, normalización y revocación de códigos de vinculación
service/ProducerProtocolRegistry  epochs, secuencias y watermarks del productor v2
decorator/repository/    protección adicional de la persistencia
decorator/strategy/      instrumentación decorativa de Strategy
config/DecoratorConfig   composición Spring de los decoradores
repository/              SQL parametrizado para metadatos de fallos
```

`SessionManager` coordina la sesión activa y la tubería de detección;
`ProducerProtocolRegistry` encapsula el estado v1/v2, la rotación de epochs y
la validación/reserva atómica de secuencias y watermarks mientras se mantiene
el lock de la sesión. En v2 Java solo admite etiquetas wire canónicas exactas
(`PASO_1_PALMAS`…`PASO_7_CIRCULARES` y clases OMS permitidas); alias históricos
como `Paso3_PalmaDorsoDedos` se rechazan antes de reservar el frame y solo
siguen disponibles para sesiones legadas v1. Un sobre v2 válido consume su
secuencia antes de validar timestamp/calidad de evidencia; si esa validación
posterior falla, el productor debe enviar un frame nuevo. `SessionCredentialRegistry`
encapsula la emisión, rotación, autenticación y expiración de credenciales, y
`SessionPairingCodeRegistry` posee el índice y la normalización de códigos.
`SessionAuthenticationService` compone ambos flujos de login sin exponer esos
mapas. El TTL predeterminado es 24 horas y la configuración no permite exceder
ese máximo. `FailedAttemptPersistenceCoordinator` mantiene aparte la cola y
los reintentos de resúmenes fallidos; el I/O de H2 no se ejecuta en el hilo de
cámara y el coordinador no recibe ni conserva imágenes o detecciones normales.
El backoff de 5 s tras un fallo de escritura usa tiempo monotónico, por lo que
un ajuste del reloj del sistema no deja resúmenes pendientes bloqueados; el
timestamp de creación persistido sigue siendo epoch para aplicar retención.
El GET del historial responde `503 CACHE_INTENTOS_NO_DISPONIBLE` si no puede
confirmar el vaciado de la cola, en vez de devolver `200` con un historial
potencialmente atrasado. El DELETE de sesión borra primero esa caché; si H2 no
confirma el borrado, responde `503 ELIMINACION_NO_CONFIRMADA` y mantiene la
sesión disponible para reintentar, sin cerrar su WebSocket ni revocar su
credencial como si el borrado hubiera concluido.

Los alias legacy `/api/...` se conservan para transición; nuevos consumidores
deben apuntar a `/api/v1/...`. El versionado de REST no cambia el WebSocket.

Archivo: `backend/src/main/resources/application.yml`

Variables clave:

- `SERVER_PORT` (default `8080`)
- `SERVER_ADDRESS` (default `127.0.0.1`, solo loopback)
- `HANDWASH_HAND_DETECTOR_PATH` (default `models/hand_detector.onnx`, opcional)
- `HANDWASH_STEP_CLASSIFIER_PATH` (default `models/step_classifier.onnx`)
- `HANDWASH_RECEPTOR_CONFIDENCE_THRESHOLD` (default `0.35`; inicio sigue exigiendo `0.75`)
- `HANDWASH_HAND_CONFIDENCE_THRESHOLD` (default `0.25`)
- `HANDWASH_STEP_CONFIDENCE_THRESHOLD` (default `0.15`)
- `HANDWASH_CORS_ALLOWED_ORIGINS` (default solo `127.0.0.1:5173` y `localhost:5173`)
- `HANDWASH_OMS_MODEL_READY` / `HANDWASH_OMS_INPUT_ENABLED` (ambas `false` por defecto; solo `run_handwash_station.py` puede habilitarlas juntas tras validar un release hospitalario firmado; Java repite la verificación)
- `HANDWASH_DETECTION_HEARTBEAT_MS` (default `200`; publicaciones de estado del mismo paso; los cambios de paso salen inmediatamente)
- `HANDWASH_SCHEDULER_POOL_SIZE` (default `4`; separa el flush WebSocket del mantenimiento y la persistencia programados)
- `HANDWASH_SESSION_EXPIRATION_CHECK_MS` (default `1000`; frecuencia de detección de timeout, no cambia el timeout de sesión)
- `HANDWASH_ONNX_MAX_CONCURRENT` (default `1`; inferencias locales concurrentes de la ruta diagnóstica, exceso responde `429`)
- `HANDWASH_DB_URL` (default `jdbc:h2:file:./.runtime/handwash;DB_CLOSE_ON_EXIT=FALSE`)
- `HANDWASH_SESSION_ACCESS_TOKEN_TTL_MS` (default `86400000`; tope obligatorio de 24 h)
- `HANDWASH_RATE_LIMIT_WINDOW_MS` (default `60000`; ventana deslizante monotónica)
- `HANDWASH_SESSION_PAIR_RATE_LIMIT` / `HANDWASH_SESSION_CREATE_RATE_LIMIT` (default `10` / `20` por ventana)
- `HANDWASH_RATE_LIMIT_MAX_CLIENTS` (default `10000`; máximo de buckets de cliente)
- `HANDWASH_RATE_LIMIT_CLEANUP_MS` (default `60000`; limpieza de buckets expirados)

Estas variables describen principalmente desarrollo local. `station` y
`station-demo` tienen un perfil propio: además de los controles de red/OMS,
`StationProfileSafetyGuard` exige valores explícitos y exactos para los umbrales
de confianza e intención, continuidad, timeout/retención y TTL, además de los
límites de rate limiting, expiración, entrega WebSocket y concurrencia Tomcat
(32 workers, 16 conexiones en espera y 512 conexiones máximas, para una cámara
local por estación). Una modificación operativa por variable de entorno,
argumentos Spring o `-D` hace fallar el arranque; cambiar la política requiere
revisión y nuevo release.

### Rendimiento Java medido

En una caracterización HTTP sintética focalizada (2026-10-04, Java 25, Spring
Boot 4.1.1, macOS 27.2), el rechazo de un frame v2 duplicado tuvo p50/p95/p99
de 0,362/0,517/0,598 ms; una detección con evidencia bilateral válida en paso
activo, 0,210/0,428/0,847 ms. Son 500 muestras por caso en loopback con H2 en
memoria. Es una corrida aislada, no una comparación causal. No mide inferencia
YOLO, FPS, precisión ni cámara; el benchmark completo y su protocolo están en
[la referencia de rendimiento Java](docs/PERFORMANCE_BASELINE_2026-09-27.md).

### Verificación automatizada

Para verificar de forma reproducible las capas Java, Python y frontend en serie,
usa el verificador integral. Requiere el entorno `.venv`, Maven, Go, `uvx` y las
dependencias ya instaladas en `frontend/node_modules`; las auditorías SCA y npm
necesitan conexión a internet:

```bash
./scripts/verify_handwash_project.sh
```

El script ejecuta escaneos de vulnerabilidades de dependencias y suites offline
y sintéticas, de manera serial; incluye dependencias de producción y de build,
excluye deliberadamente los tests de entrenamiento (`test_train_*`), no carga
cámara física y no entrena ni modifica pesos. El estado y alcance de seguridad
de dependencias está documentado en
[la auditoría de dependencias](docs/DEPENDENCY_SECURITY_AUDIT_2026-10-04.md).
La integración Java y el servidor MJPEG pueden abrir puertos loopback efímeros.

### Persistencia local de fallos

Java guarda en una base H2 local, ignorada por Git, únicamente los resúmenes de
intentos que se reiniciaron: número de intento, causa, duración, tiempos por
paso e infracciones. No almacena frames, imágenes, videos, detecciones normales,
tokens ni credenciales. Se conservan como máximo 100 resúmenes por sesión y se
eliminan al borrar la sesión o al alcanzar la retención terminal configurada
(`HANDWASH_SESSION_TERMINAL_RETENTION_MINUTES`, 30 minutos por defecto). El
endpoint de historial acepta `Authorization: Bearer <token>` y mantiene
`X-Session-Token` para clientes existentes; durante una caída de disco la
inferencia continúa y el backend registra el problema para reintentar el guardado.
Para mover la base, define `HANDWASH_DB_URL`; por defecto se crea en `.runtime/`
al ejecutar el proyecto desde su raíz.

> El detector reconoce siete movimientos de fricción; no observa el procedimiento OMS completo. El modelo preentrenado de pose de manos está activado por defecto: localiza las manos, recorta esa región y el detector de pasos analiza el recorte. Las dos inferencias se limitan y coordinan para no bloquear el hilo de video.

En el modo parcial, Java marca `manoDetectada` a partir de una caja reciente de
un paso YOLO y lo retira cuando llega `Fondo`, termina el intento o caduca la
observación. Antes de inferir el paso, el modelo preentrenado independiente
localiza una o dos manos. Una pose completa requiere al menos siete keypoints
visibles; en `FRICCION_PARCIAL`, una caja YOLO con confianza `>=0.15` también
puede guiar el recorte cuando los keypoints se ocluyen durante la fricción.
Esa caja solo enfoca la imagen: no cuenta como pose ni como evidencia OMS, que
sigue exigiendo pose completa y evidencia espacial. El recorte conserva 45% de
contexto por eje y calcula los márgenes horizontal y vertical por separado,
evitando ampliar de más la zona vacía cuando las manos están separadas en un
solo eje. El detector principal recibe el recorte bilateral y sus cajas se
dibujan en la posición original. Después del calentamiento inicial, cada
inferencia parcial de pasos requiere dos poses válidas y recientes y un recorte
con ambas manos. Si se pierde una mano, la pose caduca o el recorte no contiene
ambas, YOLO se abstiene, limpia los votos locales y oculta el candidato: no hay
inferencia de pasos a cuadro completo. La ruta OMS conserva sus validaciones
independientes. La cámara y ambos modelos siguen en la Mac; Java recibe
únicamente etiquetas, confianza, tiempos y metadatos de movimiento por REST y
envía el estado por WebSocket. No recibe ni almacena fotogramas en este flujo.

La presencia bilateral es solo una condición de encuadre; no demuestra lavado.
Java aún exige evidencia espacial reciente y la secuencia de Palmas antes de
iniciar. `LAVADO_PROBABLE` es una heurística, no una certeza de intención humana
ni una certificación del procedimiento.

### Estado del objetivo OMS completo

El backend Java y el dashboard ya tienen una ruta experimental para once acciones
OMS, evidencia visual de espuma en doce regiones bilaterales, reinicio del
intento al detectar una fase fuera de orden, una región sin jabón durante su
frotado, pérdida sostenida de evidencia visual o contacto de riesgo y duración
activa de 40 o 60 segundos según la estrategia elegida. El peso activo es
`backend/models/handwash_yolo26n_7pasos.pt`, que solo detecta siete movimientos.
No existe todavía `backend/models/handwash_oms_candidate.pt`, así que la ruta
OMS no se puede ejecutar con la cámara actual y la aprobación completa está
desactivada.

La [secuencia OMS de agua y jabón](https://www.who.int/publications/m/item/how-to-handwash)
incluye mojar, aplicar jabón, seis movimientos de fricción, enjuagar, secar y
cerrar el grifo con la toalla; el procedimiento completo dura 40–60 s. Los
umbrales por movimiento de las estrategias Java son reglas de esta aplicación,
**no tiempos individuales prescritos por la OMS**. El backend reinicia una
evaluación OMS si la evidencia se interrumpe más que el máximo configurado
(1,5 s por defecto), incluso si la siguiente predicción repite la misma fase.
`CLINICO_QUIRURGICO` es un identificador heredado de API para el objetivo de
60 s: no representa ni valida preparación quirúrgica de manos.

El plan y los 36 nombres exactos de anotación están en
`docs/REQUISITOS_MODELO_OMS.md`. El script
`scripts/train_handwash_who.py` valida clases, coordenadas, splits y separación
por participante o video; también normaliza rutas de los ZIP de Roboflow
antes de entrenar un candidato. La revisión de falsos aprobados en videos
completos sigue siendo necesaria antes de activar la puerta OMS.

## Ejecución

### Desarrollo y demostración local (no clínica)

> **No usar este flujo en hospitales, con pacientes ni para decisiones clínicas.**
> `scripts/start_handwash.sh` arranca el perfil local de desarrollo y no ejecuta
> la puerta de release hospitalario firmada. El manifiesto actual permanece en
> `NOT_READY`; el único arranque hospitalario futuro será el supervisor
> `scripts/run_handwash_station.py` con un release autorizado y firmado. Consulta
> [`docs/OPERATIONS_STATION.md`](docs/OPERATIONS_STATION.md).

El runtime de cámara/inferencia es Python y el backend de negocio es Java. Si
todavía no existe `.venv`, créalo e instala solo las dependencias del productor
de cámara (esto no inicia ni ejecuta entrenamiento):

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-camera.txt
```

`requirements-camera.txt` fija el perfil observado CPython 3.14.4/macOS arm64
mediante `requirements-camera-macos-arm64.lock`. El supervisor valida esas
versiones antes de iniciar y reintentar YOLO; en otra versión de Python o
arquitectura hace falta un lock compatible revisado. El lock no contiene hashes
de wheels, por lo que fija versiones pero no acredita por sí solo el origen
criptográfico de cada paquete.

```bash
./scripts/start_handwash.sh
```

El launcher identifica el backend por el catálogo `/api/v1/protocols` y el
dashboard por la marca `handwash-monitor-v1` de `frontend/index.html`. Si los
puertos `8080` o `5173` responden con otra aplicación, se detiene y muestra el
proceso que ocupa el puerto; no reutiliza ni cierra un sitio ajeno.

El script inicia Java y el dashboard, comprueba que respondan y ejecuta YOLO sobre Continuity Camera. La cámara crea una sesión e imprime el código para vincularla desde el dashboard. Mantén la terminal abierta durante la captura; los servicios guardan sus logs en `.runtime/`.

Si en el futuro se entrena y revisa un peso OMS con las 36 clases requeridas,
puede probarse sin reemplazar el modelo de siete movimientos:

```bash
HANDWASH_YOLO_MODEL=backend/models/handwash_oms_candidate.pt ./scripts/start_handwash.sh
```

Esto solo selecciona el detector; **no** habilita la aprobación OMS. Sin
validación de videos completos y de falsos aprobados, deja
`HANDWASH_OMS_MODEL_READY=false`.
El perfil de estación falla al iniciar si esa variable se fuerza a `true` sin un
release hospitalario autorizado. El supervisor solo la establece junto con
`HANDWASH_OMS_INPUT_ENABLED=true` después de validar la firma externa, los hashes,
la taxonomía y todas las evidencias exigidas; Java repite esa validación antes
de arrancar. `station-demo` nunca habilita OMS. Con el manifiesto actual
(`NOT_READY`), el supervisor mantiene ambas variables en `false` y bloquea el
uso hospitalario. Habilitarlo en el futuro requiere aportar y revisar la
evidencia faltante y firmar un release nuevo; una variable operativa por sí
sola no basta.
Los dos perfiles de estación también verifican los valores revisados de
confianza, confirmación de intención y continuidad temporal; el código de
desarrollo puede seguir usando configuración de entorno para pruebas.

### Backend Java

Desde la raíz del repositorio, para que la H2 use la ruta canónica `.runtime/`:

```bash
mvn -f backend/pom.xml spring-boot:run
```

### Paquete de estación local (una Mac por lavamanos)

El comando de desarrollo anterior usa Maven en modo `spring-boot:run` y el
servidor Vite. Para generar una aplicación local sin depender de Vite:

```bash
./scripts/build_handwash_station.sh
./.venv/bin/python scripts/run_handwash_station.py --unvalidated-demo
```

El lanzador requiere `--unvalidated-demo` mientras el manifiesto actual no
registre evidencia completa de release. Sin esa opción, falla cerrado antes
de iniciar Java o la cámara. Este modo es exclusivamente para demostraciones
internas y pruebas técnicas: no debe utilizarse para decisiones clínicas,
registros hospitalarios ni para afirmar que el sistema está listo para un
hospital. El modo demo no altera el modelo ni sus umbrales. En ese modo el
supervisor inicia Java con el perfil separado `station-demo`, que conserva las
restricciones locales, rechaza clases OMS no aprobadas y no simula autorización
de release; el perfil
hospitalario `station` sigue exigiendo manifiesto firmado. En ese único perfil,
el supervisor habilita la ingestión OMS solo después de validar el release
completo; Java repite la verificación antes de arrancar. La demo y la
configuración base mantienen OMS apagado.
El dashboard consulta `/api/v1/deployment/status` en cada carga y muestra una
franja visible de desarrollo/demo/piloto; si Java no responde o el contrato es
inválido, mantiene la advertencia de modo no verificado y permite reintentar.

La barrera comprueba que exista evidencia declarada en
`backend/models/model-manifest.json` —taxonomía y rúbrica verificadas, `data.yaml`
exacto incluido bajo el proyecto y ligado por SHA-256, con los 36 nombres de
clase en los IDs canónicos y sin claves duplicadas ni aliases,
validación independiente por video, piloto de cámara en el puesto objetivo,
revisión clínica/de seguridad, cobertura del protocolo completo y calibración
independiente de umbrales de movimiento separados para intención inicial y
acreditación de pasos. El manifiesto registra ambos valores y Java comprueba que
coincidan con los umbrales del runtime empaquetado. La calibración requiere un
reporte regular relativo al proyecto, de hasta 2 MiB, ligado por SHA-256 en
`washingIntent.validationEvidence`; Python y Java rechazan rutas externas,
symlinks o cambios del archivo. Los 3 s de
presencia de manos son solo calentamiento de inferencia, no demuestran intención
ni reemplazan esa validación. Los campos
del manifiesto son una lista de control de release, no una firma ni una
validación automática de la evidencia: cambiarlos manualmente no vuelve seguro
al sistema. No se debe marcar un release hospitalario como listo hasta revisar
los informes y aprobar formalmente el cambio. El supervisor empaquetado valida
el manifiesto y los hashes de los pesos antes de iniciar; además, el perfil Java
`station` vuelve a verificar la firma y los campos de evidencia obligatorios,
por lo que iniciar directamente el JAR con ese perfil tampoco omite la barrera.
Los perfiles de desarrollo (`local`/default) sí están deliberadamente fuera de
esa puerta y no deben usarse para desplegar en un hospital.

Además, el arranque hospitalario exige `backend/models/model-manifest.json.sig`,
una firma Ed25519 sobre los bytes exactos del manifiesto, y la clave pública
confiable en la ruta absoluta configurada por
`HANDWASH_RELEASE_PUBLIC_KEY_PATH`. La clave pública debe provisionarse fuera
del repositorio, bajo control administrativo y en solo lectura; la clave
privada de firma permanece fuera de la estación y solo debe usarla la autoridad
de release designada. Sin clave o firma válidas, cambiar los booleanos no abre
la barrera. La firma acredita integridad y origen conforme a esa clave
confiable; no demuestra que los informes sean clínicamente correctos ni
sustituye la revisión independiente. Java verifica firma, estado de evidencia y
las huellas SHA-256 del JAR, los SBOM Java/Python de cámara, los scripts de
supervisión/cámara y el lock exacto del runtime. El supervisor
comprueba la versión del intérprete y todos los paquetes bloqueados antes de
arrancar Java; vuelve a validar runtime, firma, manifiesto y los siete
artefactos (JAR, dos SBOM, scripts y dos locks) inmediatamente antes de cada arranque/reintento de YOLO. Ambos
procesos reciben un entorno allowlist, no las variables arbitrarias del shell;
YOLO no hereda tokens, overrides de modelo/umbrales, variables `PYTHON*` ni
proxies (solo recibe el código de vinculación actual). `HANDWASH_CLASSIFIER_FALLBACK=0`
se conserva únicamente como interruptor de emergencia unidireccional. La cámara
omite paquetes user-site y `PYTHONPATH`; las
rutas de JAR, Python y capturador se normalizan antes de validar y ejecutar
procesos hijos. El capturador verifica los hashes de los modelos antes de
cargarlos. `scripts/build_handwash_station.sh` genera los SBOM Java y Python
de cámara e imprime las huellas candidatas; ambos gates cotejan las dependencias
Python con el lock exacto y verifican el lock con hashes del generador. La autoridad de release debe revisarlas,
registrarlas en `stationArtifacts` y firmar el manifiesto exacto fuera de esta
Mac. Un cambio posterior del JAR, los scripts o el lock detiene el arranque.
Esta comprobación no autentica el sistema operativo, Java ni el intérprete.
`--unvalidated-demo` siempre se identifica como demo no clínica, incluso si el
manifiesto aparenta estar listo.

El perfil `station` mantiene Java en `127.0.0.1`, exige autenticación de
sesión y el protocolo de productor v2 (epoch autenticado, secuencias y
watermarks), desactiva `/api/infer`, limita Actuator a `health`, restringe CORS
a orígenes loopback y exige H2 en archivo local sin modo servidor compartido.
La creación y el emparejamiento rechazan v1 o una versión omitida; la
compatibilidad v1 queda solo en perfiles no estacionarios para transición.
La estación limita a una sesión no terminal por vez, porque la cámara pertenece
a un único lavamanos; las sesiones terminales siguen disponibles durante su
período de retención sin bloquear el siguiente lavado.
Las URLs REST/WS del paquete se derivan del origen actual del dashboard. Si se
cambia `SERVER_PORT`, también define
`HANDWASH_CORS_ALLOWED_ORIGINS=http://127.0.0.1:PUERTO,http://localhost:PUERTO`;
el perfil valida que ambos orígenes coincidan y sean locales. Si se intenta
abrir el backend/stream a la LAN o relajar otras protecciones, falla al arrancar.
El dashboard compilado se sirve
desde el mismo JAR, en `http://127.0.0.1:8080/`; el build ejecuta TypeScript,
tests de Maven y comprueba que el HTML del dashboard quedó dentro del artefacto.

El lanzador supervisado inicia el JAR local y el capturador YOLO; no inicia
Vite ni crea una aplicación para iPhone. Comprueba que los puertos `8080` y
`8091` estén libres, sirve el dashboard desde el JAR y mantiene cámara y Java
en la misma estación. No reutiliza ni termina procesos ajenos que ocupen esos
puertos. Ejecuta el lanzador desde una terminal y detén todo con Ctrl+C.

Si el proceso YOLO falla inesperadamente, reintenta como máximo tres veces
(esperas de 2, 5 y 15 s) solo mientras Java siga vivo y se haya obtenido el
código de la misma sesión; cada reintento registra un epoch v2 nuevo. Si Java
cae, el supervisor termina y declara perdida la sesión: no reinicia Java ni
presenta una evaluación anterior como continua. Cuando el capturador termina
con código normal, el supervisor descarta el código anterior y crea una sesión
nueva para el siguiente lavado; imprime un nuevo código para vincular el
dashboard. Los códigos solo viven en memoria/terminal; el supervisor no los
escribe a disco.

La sintonía opcional se limita a dispositivo, precisión y presentación del
stream; el lanzador no permite modificar la sesión, exponer el stream fuera de
loopback, quitar pose de manos ni sustituir modelos o umbrales desde argumentos.
Por ejemplo:

```bash
./.venv/bin/python scripts/run_handwash_station.py \
  --camera-arg=--device=mps --camera-arg=--stream-fps=20
```

`scripts/start_handwash.sh` sigue siendo el iniciador de desarrollo con Vite.
Este supervisor mejora la recuperación local, pero no configura el arranque
automático de macOS tras reinicio eléctrico, monitoreo remoto, copias de
seguridad ni una política de actualización/rollback. La operación hospitalaria
requiere además validar el puesto real, el modelo, el protocolo y los riesgos
con el hospital. La estación no debe presentarse como certificación clínica:
el modelo actual evalúa siete clases de fricción y no cubre todas las acciones
del procedimiento OMS.

El procedimiento para inicio, interrupciones, cierre y puerta de release está
en [`docs/OPERATIONS_STATION.md`](docs/OPERATIONS_STATION.md). Es una guía
operativa; no cambia el estado `NOT_READY` del manifiesto ni habilita uso
hospitalario.

### Frontend React

`frontend/.env.example` ya apunta al backend Java y al stream local por defecto:

```env
VITE_API_URL=http://127.0.0.1:8080
VITE_WS_URL=ws://127.0.0.1:8080
VITE_CAMERA_STREAM_URL=http://127.0.0.1:8091/video.mjpg
```

```bash
cd frontend
npm install
npm run dev
```

El dashboard está en `http://127.0.0.1:5173/`. Inicia el proyecto con `./scripts/start_handwash.sh`; el capturador de la Mac creará una sesión. Copia el código que imprime Terminal y pégalo en “Vincular sesión creada por el visor YOLO”. El iPhone debe aparecer como cámara de Continuidad; no se abre Safari ni se instala una aplicación móvil.

En TypeScript, la capa de dominio/adaptación usa clases POO: `BackendMessageMapper` valida y normaliza los mensajes del backend antes de una única actualización atómica de Zustand. La UI conserva componentes y hooks funcionales, que son el modelo idiomático de React; no se duplican efectos con componentes de clase.

El iniciador comprueba la presencia del iPhone, la huella SHA-256 declarada en `backend/models/model-manifest.json` y la compatibilidad estructural del peso YOLO **antes** de levantar Java y el dashboard. Un checkpoint nuevo debe incorporarse al manifiesto con su hash y rol antes de habilitarlo; un peso sin registro o modificado detiene el arranque. Esta comprobación detecta deriva accidental, no sustituye firma criptográfica del manifiesto ni revisión del origen del artefacto. Para diagnosticar solo la cámara, ejecuta `.venv/bin/python scripts/run_yolo26_continuity_camera.py --check-camera`; para validar solo el peso, usa `.venv/bin/python scripts/validate_handwash_models.py`. El modelo activo traduce sus etiquetas `paso_1`…`paso_7` a los nombres canónicos antes de enviar los eventos a Java. Si el iPhone no aparece, revisa Continuidad y los permisos de cámara de macOS; el proyecto no lo sustituye silenciosamente por FaceTime ni por la captura de pantalla.

Si primero pulsaste **Iniciar nueva sesión** en el dashboard, usa el código que muestra allí al abrir el visor, para evitar dos sesiones diferentes: `HANDWASH_PAIRING_CODE=XXXXX-XXXXX ./scripts/start_handwash.sh`. Si inicias con `./scripts/start_handwash.sh` sin esa variable, el visor crea su propia sesión y debes pegar en el dashboard el código impreso en Terminal; no pulses «Iniciar nueva sesión» en ese caso.

El backend escucha solo en `127.0.0.1` por defecto y REST/WebSocket aceptan únicamente los orígenes locales del dashboard. Para otro origen local personalizado, define `HANDWASH_CORS_ALLOWED_ORIGINS` como lista separada por comas.

### Inferencia YOLO en la Mac

> **Uso diagnóstico/desarrollo únicamente; no es un arranque de estación hospitalaria.**
> Este comando directo no ejecuta el supervisor ni la verificación del release
> firmado. El manifiesto actual está en `NOT_READY`; no usarlo para atención ni
> registros clínicos.

```bash
# desde la raíz del proyecto, con el entorno virtual que contiene ultralytics
./.venv/bin/python scripts/run_yolo26_continuity_camera.py
```

El capturador lee Continuity Camera con FFmpeg, ejecuta Ultralytics, superpone las detecciones y publica el video al dashboard por MJPEG local. Envía los pasos detectados al backend Java (`POST /api/v1/deteccion`); el endpoint responde por defecto con un ACK DTO compacto (`accepted`/`filtered`), mientras Java publica el estado del dashboard por WebSocket. Los clientes de diagnóstico pueden pedir el snapshot REST con `?includeState=true`; ese estado se proyecta al DTO v1 `EvaluationResponse`, sin serializar el modelo de dominio. Si la cámara deja de entregar frames por más de 2 s, el capturador cierra solamente el dispositivo, vuelve a buscar el iPhone y reintenta durante un máximo de 45 s (`--camera-reconnect-timeout`; intervalo `--camera-retry-interval=2`). La sesión y el puerto MJPEG permanecen abiertos durante ese período: el video muestra «CÁMARA DESCONECTADA», `/health` informa `camera: reconnecting`, y ninguna imagen antigua acredita un paso. Al agotarse el plazo, termina con error explícito. El video indica cuando falta una mano o alguna caja queda cerca del borde; es una guía de encuadre, no una calibración del modelo. Fija el iPhone y mantén ambas manos completas, centradas e iluminadas junto al lavabo antes de evaluar los siete pasos.

`--hand-presence-warmup-ms` (3000 ms por defecto) bloquea las fases ordinarias hasta observar dos poses válidas y frescas durante 3 s consecutivos; frames repetidos no cuentan. Mientras Java aún no haya confirmado el inicio (`EN_PROGRESO`), perder una mano o superar el intervalo permitido reinicia el contador. Después de confirmado el inicio, la preparación queda latched para esa sesión: una oclusión pausa las fases ordinarias hasta recuperar ambas manos frescas, sin imponer otros 3 s ni reiniciar por sí sola el lavado. En `FRICCION_PARCIAL`, toda inferencia ordinaria requiere además un recorte bilateral; si falta una mano, YOLO se abstiene y limpia sus votos, sin analizar el cuadro completo. En `PROTOCOLO_OMS`, mientras el gate está cerrado se permite exclusivamente inferencia a cuadro completo de `OMS_CONTACTO_RIESGO`; las fases OMS ordinarias no se evalúan ni publican hasta disponer de ambas manos y su evidencia espacial. Java conserva la confirmación de intención por Palmas en el modo parcial, la evidencia espacial fresca y el orden de los pasos, incluso cuando reinicia un intento. Java aplica umbrales distintos en `handwash.intention.start-minimum-normalized-movement` y `handwash.intention.step-minimum-normalized-movement`; ambos son `1e-8` por defecto, un piso numérico no calibrado que el ruido de cámara puede superar. En desarrollo se ajustan mediante `HANDWASH_INTENTION_START_MINIMUM_NORMALIZED_MOVEMENT` y `HANDWASH_INTENTION_STEP_MINIMUM_NORMALIZED_MOVEMENT`; la estación solo arranca si coinciden con los valores del manifiesto firmado y su reporte de calibración. Una medición inválida o inferior/al umbral no acredita el paso. La presencia y la espera no equivalen a inicio ni aprobación clínica. El parámetro de calentamiento acepta 0–10000 ms para diagnóstico directo; 0 omite el calentamiento y no debe usarse en evaluación clínica. `run_handwash_station.py` no permite sobrescribirlo y mantiene los 3000 ms predeterminados. La espera no valida precisión clínica ni detección desde otros ángulos.

El `/health` local del capturador incluye `handPresence` para sincronizar el conteo de manos y el calentamiento con el dashboard. Este resumen contiene solo contadores; se invalida si la cámara se desconecta o no hay una actualización en 650 ms, y no acredita ningún paso en Java.

El proceso conserva la captura/inferencia a 960×540 y reduce únicamente el MJPEG del dashboard a 720×405 para bajar codificación y transferencia sin sacrificar píxeles al modelo. Publica hasta 24 FPS por defecto (`--stream-fps`, configurable entre 5 y 30); `--stream-width` (mínimo 320; usa 960 para salida nativa) y `--stream-jpeg-quality` (50–95) ajustan solo lo visual, no la cadencia de inferencia. El publicador evita codificar si no hay un dashboard suscrito; las imágenes siguen solo en memoria.

El servidor MJPEG admite como máximo dos visores simultáneos y aplica un timeout de socket de 2 s para evitar que pestañas lentas retengan workers; al alcanzar el límite responde `503` con `Retry-After: 2`. Estos límites protegen la vista local y no alteran YOLO, la secuencia ni la evidencia enviada a Java.

El endpoint multipart `POST /api/v1/infer` de Java está deshabilitado por defecto y solo se habilita con `HANDWASH_INFERENCE_API_ENABLED=true` para diagnóstico local mediante ONNX. No tiene llamadores activos en el dashboard ni en el capturador, y no puede delegar a otro servicio de inferencia. El gateway FastAPI anterior está archivado. Si una respuesta diagnóstica incluye estado de sesión, se proyecta a `EvaluationResponse`, no al modelo de dominio. La cámara envía detecciones JSON directamente a `POST /api/v1/deteccion`.

Cuando la ruta Java opcional está habilitada, `ImagePayloadValidator` rechaza cargas mayores de 8 MB o 16 megapíxeles antes de decodificarlas para ONNX. El tamaño del archivo se comprueba antes de copiar el multipart a memoria y las dimensiones se consultan desde la cabecera con `ImageReader` antes de crear el raster. El lector usa un stream respaldado por memoria para no crear archivos temporales de imagen. Los límites Java se configuran con `HANDWASH_INFERENCE_MAX_IMAGE_BYTES` y `HANDWASH_INFERENCE_MAX_IMAGE_PIXELS`, junto con el máximo multipart de Spring. Una carga fuera de límite responde `413 IMAGEN_EXCEDE_LIMITE`; un formato inválido responde `400 IMAGEN_INVALIDA`. Esta protección pertenece a la ruta diagnóstica, no añade inferencia de imágenes al flujo canónico de cámara.

El fallback ONNX Java también usa `InferenceAdmissionGate`: acepta como máximo una inferencia simultánea por defecto y rechaza solicitudes concurrentes con `429 INFERENCIA_OCUPADA` en vez de acumularlas detrás del video. Configurable mediante `HANDWASH_ONNX_MAX_CONCURRENT`; aumentarlo consume más CPU y memoria.

El proceso precalienta los modelos activos antes de abrir la cámara para que la primera inferencia no congele el video. Usa Apple Metal/MPS cuando está disponible, `imgsz=416` para la ruta primaria de pasos y `--hand-imgsz=320` para localizar manos. Si encuentra menos de dos poses suficientes (7 keypoints visibles por mano), reintenta a `--hand-recovery-imgsz=640` como máximo cada `--hand-recovery-interval=0.5` s y toma el frame más reciente tras adquirir el acelerador. Si ese pase aún detecta menos de dos manos, hace una sola pasada batched sobre dos recortes solapados en el eje mayor (15 %); mapea cajas y keypoints al frame completo y asigna cada detección al lado propietario para evitar duplicados en el solape. Solo conserva esa recuperación si aumenta las poses válidas; la recuperación completa mantiene `save=False` y los frames permanecen en memoria. Una pose primaria válida se conserva si la recuperación no mejora la evidencia. Las cajas YOLO con confianza válida se dibujan aunque la pose esté incompleta; en `FRICCION_PARCIAL`, las cajas con confianza `>=--hand-crop-confidence=0.15` también pueden enfocar el recorte cuando faltan keypoints. El umbral se puede ajustar con `HANDWASH_YOLO_HAND_CROP_CONFIDENCE`. Esto no se usa como evidencia OMS, que sigue exigiendo pose válida. El inset muestra el encuadre vivo calculado con las manos recientes; el borde rojo del plano completo señala el último recorte realmente analizado. Cajas de pasos y borde desaparecen tras 0,5 s sin inferencia nueva. Todo sigue en memoria. El overlay separa propuestas crudas de YOLO pose, cajas mostrables, poses válidas tras keypoints/deduplicación y manos aptas para inicio; una propuesta no se presenta como mano válida. Conserva la última localización durante `--hand-max-age=0.5` s. La caja y el frame que la originó permanecen emparejados: el detector de pasos corre sobre el snapshot exacto en que YOLO localizó la mano, evitando recortes desplazados por movimiento entre frames. Si el recorte no da un paso aceptable a 416 px, ejecuta una segunda inferencia del mismo recorte a 640 px (`--fallback-imgsz`) como máximo cada `--step-recovery-interval=0.8` s, usando el filtro de clases canónicas. El modelo activo no tiene clase `Fondo`; la falta de cajas hace expirar la evidencia y el capturador envía `Fondo` al cumplirse la ventana de 0,9 s. Otros detectores que sí incluyan `Fondo` conservan ese control negativo y bloquean un paso si su confianza es mayor o igual. Si la pose está incompleta o caduca, el hilo la vuelve a intentar con espera exponencial y se abstiene de inferir pasos en vez de usar el cuadro completo. El localizador de manos tiene prioridad de acceso al acelerador; la ruta primaria de pasos está limitada a 8 FPS más hasta 1,25 recuperaciones/s a 640 px; las manos se localizan a 6 FPS más recuperaciones de alta resolución cuando falta alguna de las dos. En `FRICCION_PARCIAL`, la inferencia de pasos exige dos poses recientes y un recorte bilateral; al perder cualquiera de las dos manos se limpian los votos y se oculta el candidato hasta recuperar el encuadre. El dashboard captura a 960x540 y publica hasta 24 FPS por defecto (configurable con --stream-fps, máximo 30) con frames recientes, sin cola de latencia. Tras `--missing-detection-grace=0.9` s sin fase estable se envía `Fondo` para reiniciar el intento, antes del límite predeterminado de 1.5 s de Java. Ambos FPS reales aparecen sobre el video. `--no-hand-pose` deja solo el análisis del cuadro completo y se rechaza en el supervisor de estación. En Macs sin MPS se usa CPU automáticamente.

La publicación del video corre en un hilo propio: recibe las detecciones ya
convertidas a CPU y anota el frame reciente sin esperar a que termine la siguiente
inferencia de pasos. Su límite es 24 FPS por defecto (configurable con --stream-fps, máximo 30); la frecuencia real de video, manos y
pasos se muestra por separado. Cada fotograma cuenta una sola vez como evidencia
de pasos, y los resultados caducan según el momento de captura.

El stream de cámara se sirve solo en `127.0.0.1:8091`; no se expone a la red.

El clasificador experimental `handwash_who_yolo26m_cls.pt` está habilitado por
defecto en `FRICCION_PARCIAL` mediante el script de arranque (equivalente a
`HANDWASH_CLASSIFIER_FALLBACK=1`). Con dos poses válidas y recientes, puede
priorizar sus seis movimientos compatibles o vetar sus clases negativas; si
abstiene, Java aún recibe el candidato del detector. Desactívalo explícitamente
con `HANDWASH_CLASSIFIER_FALLBACK=0`. No cubre el paso 7 del proyecto: su clase
`07_turn_off_faucet_with_paper_towel` es negativa y nunca se mapea a
`Paso7_Circulares`. Las cifras disponibles son evaluaciones pequeñas offline,
no validación de secuencia en vivo ni clínica; sus medidas y límites están en
`backend/models/README.md` y `backend/models/model-manifest.json`.

Repetí el 2026-10-02 la evaluación de 180 imágenes de prueba: el localizador
halló dos poses en **92/180 (51,1%)**; dentro de ese subconjunto la propuesta
coincidió en **82/92 (89,1%)**, con un falso paso en negativas. Ese resultado
condicional no equivale a precisión global ni a cobertura de una sesión. Antes
de la compuerta de dos manos, la propuesta combinada coincidió en 117/180 y
produjo 8 propuestas falsas en negativas. Los resultados más débiles fueron
dedos entrelazados (9/13) y pulgar (10/13)
dentro de la pequeña muestra bilateral. Esto no demuestra precisión temporal
ni rendimiento con Continuity Camera. La tabla por clase y el comando reproducible
están en [la ficha de modelos](backend/models/README.md). El localizador alternativo
de manos obtuvo solo 50/180 poses bilaterales en la misma muestra, frente a 92/180
con el activo, por lo que se conserva como candidato desactivado.

### Flujo recomendado: Cámara de Continuidad, sin AirDrop ni despliegue web

AirDrop sirve para transferir fotos o vídeos, pero no es una fuente de vídeo continuo. En macOS, activa `Ajustes del iPhone > General > AirPlay y Continuidad > Cámara de Continuidad`; con Wi‑Fi y Bluetooth activos, el iPhone aparecerá como cámara AVFoundation. Apple permite usarla inalámbricamente o por USB.

Lista los dispositivos AVFoundation:

```bash
ffmpeg -f avfoundation -list_devices true -i ''
```

Cuando el iPhone aparezca, ejecuta el visor local indicando su índice (normalmente será el siguiente después de FaceTime):

```bash
./.venv/bin/python scripts/run_yolo26_continuity_camera.py
```

Si ya abriste una sesión en el dashboard, añade `--pairing-code XXXXX-XXXXX`
para que el visor envíe detecciones a esa sesión en vez de crear otra. Si
usas `--session-id`, define `HANDWASH_SESSION_TOKEN` en el entorno; no pongas
el token en argumentos de línea de comandos.

El dashboard muestra las cajas de pasos y puntos de la mano sobre el video. El índice se detecta por el nombre de Continuity Camera; nunca usa `Capture screen 0` por accidente. macOS puede pedir permiso de cámara para Python/Terminal. Pulsa Ctrl+C en la terminal para terminar la captura.

### Por qué no se usa el OBB oficial sin ajuste

`yolo26n-obb.pt` es una base oficial de Ultralytics, pero sus pesos vienen entrenados con DOTA y sus clases son avión, barco, vehículos, puentes e infraestructura. No detecta manos ni dedos sin fine-tuning. Por eso se conserva como base experimental (`yolo26n-obb.pt`); el runtime usa el detector de siete pasos y deja el modelo YOLO26 pose de manos (21 keypoints) como opción `--hand-pose`. Para entrenar un OBB específico de manos harían falta etiquetas de cuatro esquinas por mano; el dataset actual solo tiene cajas de pasos.

### Segmentación con máscaras

`backend/models/handwash_yolo26n_7pasos.pt` es actualmente un modelo de detección, por lo que dibuja cajas. Para obtener máscaras como `yolo26n-seg`, las etiquetas deben contener polígonos de segmentación; las etiquetas actuales de DataSet5 solo contienen cajas. El entrenamiento preparado está en:

```bash
HANDWASH_SEG_DATA=/ruta/a/segmentation.yaml \
./.venv/bin/python scripts/train_yolo26_seg.py
```

Después, ejecuta el visor con el `best.pt` generado mediante `--model`; `result.plot()` mostrará automáticamente cajas y máscaras.

### Aplicación iOS

No existe una aplicación iOS en el flujo requerido. Las carpetas iOS históricas se conservan como material heredado y no forman parte de la instalación ni de la ejecución.

## Contratos de compatibilidad

- Protocolo clínico canónico: `CLINICO_QUIRURGICO` (se acepta `CLINICO` como alias de entrada por compatibilidad).
- Se mantiene `DOMESTICO`.
- El modelo activo detecta siete clases de fricción; la ruta OMS opcional exige las 36 clases exactas documentadas.
- La ausencia de cajas no se convierte en un paso: el capturador aplica la ventana de pérdida de evidencia y Java controla el reinicio.
- Mensajes WS mantienen `EstadoLavadoResponse` y agregan `messageType`/`estadoSesion` para el dashboard React.

## Modelo / entrenamiento

- `backend/models/handwash_yolo26n_7pasos.pt` es el detector activo de siete pasos y
  `backend/models/yolo26s-pose-hands.pt` localiza las manos con una caja y 21
  puntos clave; el runtime usa sus cajas para recortar la entrada del detector.
- El checkpoint activo es byte a byte el `weights/best.pt` de
  `yolo26n_7pasos_b64` (SHA-256 coincidente). Su `args.yaml` apunta a
  `/content/YOLO_Handwash_7pasos_real_labels/data.yaml`, pero ese YAML y la
  rúbrica no están en el artefacto descargado ni en este proyecto. Por ello,
  `paso_1`…`paso_7` sí se normalizan para el flujo técnico, pero el significado
  real de cada etiqueta —en particular `paso_7`— no queda probado por el
  `results.csv`. No confundir la métrica reportada con validación de etiquetas,
  una sesión real o precisión con Continuity Camera.
- Se añadió `datasets/handwash_public_7steps.yaml`; sus imágenes y etiquetas
  están disponibles localmente en carpetas ignoradas por Git (567 train y 140
  val). La auditoría nueva `scripts/audit_yolo_split_duplicates.py` detectó
  107/140 imágenes de val con un candidato casi duplicado en train (pHash <=4,
  diferencia media en gris <=5/255); no encontró copias binarias exactas.
  Inspeccioné dos pares y ambos muestran prácticamente el mismo fotograma y la
  misma clase. Por tanto, las métricas previas de precisión 1.0, recall 1.0,
  mAP50 0.995 y mAP50-95 0.8644 son reproducibles como conteos del split, pero
  **no son evidencia independiente de generalización** y no deben anunciarse
  como precisión del modelo. Hace falta volver a dividir por video/escena fuente
  y repetir evaluación en el PC de entrenamiento; no se modificaron datos ni
  pesos aquí. La muestra diagnóstica retenida de videos y la
  comparación de localizadores de manos, con sus límites, están en
  `backend/models/README.md` y `backend/models/model-manifest.json`.
- El preflight valida que el modelo elegido sea `detect` y contenga exactamente
  una etiqueta por cada uno de los siete pasos (canónica o alias secuencial
  `paso_1`…`paso_7`); permite además una clase `Fondo` para veto, pero rechaza
  aliases semánticos duplicados y clases desconocidas. La alternativa OMS exige
  exactamente las 36 clases aprobadas. Rechaza un peso
  OMS parcial; los modelos OBB, segmentación y pose no entran como fases.
  Esta validación es estructural. Si se usan alias genéricos, el capturador
  advierte en el arranque que su mapeo por orden no comprueba la rúbrica, el
  significado aprendido ni la precisión del checkpoint.
- Para mejorar la generalización entre ángulos hay una ruta de entrenamiento
  en Colab en `docs/GOOGLE_COLAB_ENTRENAMIENTO.md`. Usa un dataset de 12 clases
  izquierda/derecha y lo fusiona a las siete clases del backend antes de
  entrenar YOLO26s con aumentos fuertes. Antes de entrenar, el script rechaza
  particiones con duplicados exactos o candidatos casi duplicados entre
  train/val/test; el split debe agruparse por video o escena. Ejecuta el
  entrenamiento en Colab o en la PC externa con GPU, nunca en la Mac de la
  estación.
- `step_classifier.onnx` está disponible para la ruta ONNX opcional del backend. CoreML/iOS no forma parte del flujo actual; el visor local usa el `.pt`.
- Los scripts históricos de DataSet5 quedan bloqueados para entrenamiento hasta
  contar con etiquetas verificadas de los siete movimientos y contrato completo
  train/val. `movement_code 7` significa cerrar el grifo, no fricción circular;
  se corrige a `Fondo`. El YAML existente es histórico y no se reutiliza. La
  preparación exige una carpeta de salida nueva mediante
  `HANDWASH_DATASET5_OUTPUT_DIR` y no borra ni mezcla datasets anteriores.

El checkpoint activo expone etiquetas genéricas `paso_1`…`paso_7`; falta su
`data.yaml`, por lo que la correspondencia gestual no está verificada. El
resultado no certifica el procedimiento completo de la OMS. Cualquier
entrenamiento futuro debe ejecutarse en otra PC con GPU, nunca en esta Mac; los
scripts legacy rechazan el export actual y ya no copian ONNX automáticamente a
`backend/models`.

```bash
HANDWASH_PROJECT_ROOT=/ruta/PROYECTO-HAND-WASH-YOLO \
HANDWASH_DATASET5_OUTPUT_DIR=/ruta/dataset-verificado \
python scripts/train_v2.py
```

El arranque canónico necesita `handwash_yolo26n_7pasos.pt` y `yolo26s-pose-hands.pt`; valida ambos antes de iniciar los servicios. El clasificador experimental de pasos 1–6 está habilitado por defecto; `HANDWASH_CLASSIFIER_FALLBACK=0` lo desactiva como interruptor de emergencia (este valor prevalece sobre `--classifier-fallback`). Para seleccionar otro peso, define `HANDWASH_YOLO_CLASSIFIER_MODEL` con una ruta dentro del repositorio y registra esa ruta junto con su SHA-256 único en `backend/models/model-manifest.json`; los pesos externos o no registrados se rechazan. `--no-hand-pose` permite desactivar explícitamente el recorte para depuración. `step_classifier.onnx` y `hand_detector.onnx` pertenecen al camino de inferencia ONNX alternativo y no son requisitos para YOLO nativo ni para recibir detecciones en Java. Los archivos grandes y el dataset pueden existir localmente sin estar versionados en Git.

## Circuito (futuro)

La carpeta `circuito/` se conserva intacta como integración futura ESP32/BLE. Podría acoplarse al dashboard local para activar o pausar la captura sin mezclar la clasificación YOLO actual.

## Organización del repositorio

- `backend/`: API/reglas canónicas Java/Spring, perfiles local/station y empaquetado; `backend/models/` conserva pesos, no ejecuta YOLO desde Java.
- `backend/src/main/java/com/handwash/`: clases agrupadas por responsabilidad; las pruebas Java viven en `backend/src/test/java/`.
- Base local: H2 está embebida en el backend. `backend/src/main/resources/schema.sql` permanece en la raíz del classpath para la inicialización de Spring; los datos locales se guardan en `.runtime/handwash.mv.db` (ignorado por Git). No se necesita una carpeta o servicio `database/` separado.
- `frontend/`: dashboard React/TypeScript; Vite en desarrollo o recursos estáticos dentro del JAR station.
- `frontend/src/`: `components/`, `hooks/`, `lib/`, `stores/`, `types/` y `test/`.
- `scripts/`: captura/inferencia YOLO Python en la Mac, arranque de desarrollo, evaluación y preparación de entrenamiento.
- `datasets/`, `ENTRENAMIENTO/`, `runs/` y `backend/models/`: datos, resultados y pesos; no borrar por ser artefactos grandes.
- `circuito/`: integración ESP32/BLE futura, no requerida para ejecutar el sistema actual.
- `archive/`: prototipos y notas históricas que no forman parte del arranque ni del build.

Los entornos locales (`.venv/`, `frontend/node_modules/`), las salidas de compilación y `.runtime/` son generados pero necesarios para desarrollo o ejecución. No eliminarlos mientras haya servicios activos; `.runtime/` puede contener el estado local de desarrollo.
