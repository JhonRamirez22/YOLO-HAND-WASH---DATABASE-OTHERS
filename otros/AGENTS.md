# AGENTS.md — Sistema de Verificación de Lavado de Manos Clínico

## 1. Introducción

Este documento describe el ecosistema de agentes de software del proyecto de lavado de manos. El sistema opera íntegramente en esta Mac: el iPhone se utiliza únicamente como fuente de cámara; YOLO, la visualización, el dashboard y el backend Java se ejecutan localmente. El modelo actual reconoce siete clases de fricción definidas por el proyecto; su correspondencia uno-a-uno con los gestos numerados oficiales de la OMS no se ha validado. El sistema evalúa su secuencia y duración, pero **no certifica el procedimiento completo de la OMS** porque aún no detecta mojar las manos, aplicar jabón, enjuagar, secar ni cerrar el grifo.

El proyecto no requiere ni debe desarrollar una aplicación iPhone. El teléfono no ejecuta inferencia, no contiene un modelo CoreML y no es el cliente del backend; solo publica su cámara hacia la Mac mediante el mecanismo de cámara remota configurado para el proyecto. La interfaz principal y el resultado del lavado se muestran en la Mac.

El servidor no es un monolito de reglas: está organizado como un conjunto de **agentes especializados**, cada uno con una responsabilidad única, comunicados mediante notificación de eventos. Esta separación permite intercambiar el algoritmo de validación (lavado clínico vs. doméstico) sin tocar la máquina de estados, y agregar nuevos canales de alerta (push, sonido, UI) sin tocar la lógica de negocio.

Patrones de diseño aplicados:

| Patrón   | Problema que resuelve |
|----------|------------------------|
| **State**    | Modelar la progresión secuencial obligatoria de los pasos del lavado. |
| **Strategy** | Permitir múltiples protocolos de validación (duración, pasos requeridos) intercambiables en tiempo de ejecución. |
| **Observer** | Desacoplar la ingestión de detecciones de sus consumidores (evaluador de secuencia, validador de reglas, notificador). |
| **Factory Method** | `CreadorProtocolo` delega la creación de la Strategy a los creadores de objetivos de 40 y 60 segundos; `ReglaValidacionStrategyFactory` selecciona el creador. |
| **Chain of Responsibility** | `CadenaIntencionLavado` filtra evidencia reciente, medición bilateral válida y movimiento no nulo para confirmar intención y acreditar fases activas. |
| **Decorator** | `DecoratorConfig` compone decoradores de métricas de Strategy y validación de IDs de sesión en el repositorio. El SQL sigue protegido principalmente por consultas JDBC parametrizadas; los decoradores no sustituyen esa defensa ni cambian las reglas de lavado. |

La API REST canónica se versiona bajo `/api/v1/...`; los controladores conservan aliases `/api/...` por compatibilidad temporal. Los DTO HTTP viven en `backend/src/main/java/com/handwash/api/v1/dto/` y se convierten a modelos internos en el mapper. El capturador usa `POST /api/v1/auth/login` y credencial DEVICE; reemplazar el productor v2 invalida intencionalmente el epoch anterior. El dashboard se vincula por separado con `POST /api/v1/auth/dashboard-login` y recibe capacidad VIEWER de solo lectura, sin rotar DEVICE ni invalidar el epoch. `security/SessionCredentialRegistry` encapsula la emisión, rotación, autenticación y expiración de OWNER, DEVICE y VIEWER; vencen en un máximo de 24 horas y no se persisten. La configuración de composición de decoradores está en `backend/src/main/java/com/handwash/config/DecoratorConfig.java`. Ver `README.md` para rutas, TTL, responsabilidades y límites de seguridad.
`ApiNoStoreFilter` aplica `Cache-Control: no-store`, `Pragma: no-cache` y `Expires: 0` a todas las respuestas `/api/**`, incluidas las que contienen tokens o tickets; no altera recursos estáticos del dashboard.
El dashboard canjea su token VIEWER con `POST /api/v1/session/{sessionId}/websocket-ticket`; el WebSocket solo acepta el ticket ligado a esa sesión, de un solo uso y con TTL máximo de 30 s, nunca un token largo directamente en la URL. VIEWER no puede enviar detecciones, registrar epochs, invocar inferencia ni borrar la sesión.
`security/SessionPairingCodeRegistry` es dueño del índice bidireccional y de la normalización del código de vinculación; `SessionAuthenticationService` resuelve el login sin mantener mapas de credenciales o códigos.

---

## 2. Arquitectura del Sistema (iPhone como cámara, Mac como plataforma de ejecución)

```
iPhone (Continuity Camera)
          │ video
          ▼
Captura + YOLO en la Mac ── MJPEG anotado ───────────────────────────┐
          │ JSON (REST /api/v1/deteccion)                            │
          ▼                                                          ▼
Receptor Java (Subject) → State + Strategy → Notificador ── WebSocket → Dashboard Mac
```

**Flujo resumido:** la cámara de Continuidad entra al proceso YOLO local. El video anotado llega al dashboard por MJPEG; las detecciones se envían por REST al backend Java y sus resultados regresan por WebSocket.

### 2.1 Reglas operativas

- Antes de inferir, el capturador exige IDs de clase enteros y contiguos desde cero. El detector parcial debe mapear exactamente una etiqueta a cada uno de los siete pasos; solo admite además una clase `Fondo` para veto. Rechaza aliases semánticos duplicados y clases desconocidas. Un detector de release OMS debe tener exactamente las 36 clases aprobadas, sin extras; si no coincide, no entra a la ruta clínica.
- El gate hospitalario Python y Java exige que `trainingDataConfigPath` sea relativo al proyecto, apunte a un archivo regular acotado de hasta 2 MiB, su `trainingDataConfigSha256` coincida con el contenido y `names` enumere los 36 nombres de clase OMS en sus IDs canónicos exactos. Ambos verificadores rechazan clases reordenadas, IDs duplicados, claves YAML duplicadas y aliases. `trainingDataConfigIncluded=true` por sí solo no acredita que se entregó el YAML exacto; un archivo ausente, externo, alterado, sin hash o con taxonomía distinta bloquea el release.
- El mismo gate exige que `washingIntent` declare `startMinimumNormalizedMovement` y `stepMinimumNormalizedMovement`, activos y calibrados, más `validationEvidence` con estado `VALIDATED_FOR_HOSPITAL_PILOT`, validación independiente, ruta relativa dentro del proyecto y reporte regular de hasta 2 MiB ligado por SHA-256. Java exige que ambos valores coincidan exactamente con los umbrales del runtime empaquetado; variables externas no pueden alterarlos en `station`. Python y Java rechazan rutas externas, enlaces simbólicos, reportes ausentes/alterados y flags falsos. Los valores actuales `1e-8` son solo el piso numérico no calibrado: el manifiesto sigue bloqueado para uso hospitalario. El calentamiento de 3 s de manos solo prepara la inferencia; no sustituye la confirmación de intención ni es evidencia clínica.
- La Mac debe ejecutar el backend Java, el proceso YOLO y el dashboard.
- Para una estación empaquetada de un lavamanos, `scripts/run_handwash_station.py` es el supervisor local y Java admite como máximo una sesión no terminal; las sesiones completadas/expiradas se conservan durante su retención, pero no compiten por la cámara. Antes de iniciar procesos el supervisor evalúa `backend/models/model-manifest.json` y falla cerrado si falta evidencia de release hospitalario; además requiere una firma Ed25519 válida sobre los bytes exactos del manifiesto (`model-manifest.json.sig`), verificada con la clave pública externa `HANDWASH_RELEASE_PUBLIC_KEY_PATH`. La clave pública debe ser administrada fuera del repositorio; la privada pertenece a la autoridad de release y nunca se almacena en esta Mac/estación. Los booleanos documentan una decisión revisada, pero no prueban la evidencia ni reemplazan la revisión clínica; no deben marcarse manualmente para eludir la barrera. `--unvalidated-demo` permite exclusivamente una demostración interna, siempre se identifica como no clínica y no significa autorización clínica. En un release válido comprueba que `8080` y `8091` estén libres, inicia el perfil Java `station`, verifica el catálogo del backend y arranca el capturador. Las huellas y firma se vuelven a validar inmediatamente antes de cada arranque/reintento YOLO; las rutas CLI se normalizan a absolutas antes de validar o ejecutar procesos hijos. Solo administra los procesos que él mismo crea; no adopta ni mata servicios ajenos. YOLO puede reintentarse hasta tres veces con backoff solo si Java sigue activo y el código de vinculación de la sesión está disponible; el reintento vuelve a autenticar v2 y registra un epoch nuevo. Una salida normal de cámara inicia otra sesión limpia; una caída de Java es terminal porque pierde el estado en memoria. Ctrl+C detiene ordenadamente el grupo YOLO/FFmpeg y Java. No configura todavía autoarranque de macOS, watchdog del sistema operativo, respaldo ni despliegue/rollback.
- El supervisor no escribe códigos, tokens ni frames a disco; los procesos imprimen su salida en la terminal. Java y cámara reciben un entorno hijo allowlist, no una copia de las variables del shell: el backend conserva solo la clave pública externa y valores de estación fijados; YOLO no hereda tokens, perfiles Spring, overrides de modelo/umbral, variables `PYTHON*` ni proxies. Solo se propaga el código de vinculación obtenido por el supervisor y se permite `HANDWASH_CLASSIFIER_FALLBACK=0` como interruptor unidireccional de emergencia; el entorno no puede forzar el fallback encendido. Los argumentos de cámara siguen en allowlist y no pueden cambiar sesión/backend/puerto del stream, desactivar pose ni alterar modelos o umbrales.
- Los perfiles `station` y `station-demo` mantienen `handwash.oms.model-ready=false` y `handwash.oms.input-enabled=false` por defecto; las detecciones OMS reciben 409 sin mutar la sesión. El supervisor solo pone ambos valores en `true` para `station` después de verificar la firma externa del manifiesto, hashes, taxonomía y evidencia de release; Java repite esa verificación antes de completar el arranque. `station-demo` nunca habilita OMS y una variable de entorno por sí sola no autoriza el cambio. El modo OMS experimental solo puede ejercitarse en desarrollo y nunca aprueba mientras el modelo no esté validado. El guard rechaza habilitación sin release autorizado o cualquier intento de usar v1, y fija explícitamente umbrales del Receptor/intención, intervalos de secuencia, timeout/retención, TTL de credenciales, límites de creación/vinculación, frecuencia de expiración/persistencia, límites de publicación WebSocket y concurrencia del conector Tomcat (32 hilos, cola de aceptación 16, máximo 512 conexiones) a los valores revisados. Cualquier otro override Spring por entorno, JSON, `-D` o línea de comandos detiene el arranque; cambiar un valor requiere revisar evidencia y firmar un release nuevo. Creación/emparejamiento no aceptan una versión ausente o v1 en station; la ruta de login compartida también requiere que la sesión ya sea v2-estricta. El modelo y los datos actuales no acreditan el procedimiento OMS completo; quitar este bloqueo requiere evaluación independiente, un cambio de release revisado y su evidencia firmada, no solo una variable de entorno.
- En el evaluador OMS experimental, cambiar a la fase siguiente o reiniciar por una fase fuera de orden requiere dos observaciones válidas, distintas y consecutivas dentro de `maxDetectionGapMs`; un frame aislado no altera la fase. API/WS publica el candidato con su código canónico `OMS_*` y el dashboard lo identifica como no confirmado. Al confirmarse, el intervalo entre los dos candidatos se acredita a la fase entrante y se conserva en memoria la evidencia de jabón del primer candidato. `OMS_CONTACTO_RIESGO` y la pérdida de evidencia siguen siendo controles inmediatos fail-closed; esto no habilita OMS ni cambia su aprobación clínica desactivada.
- En `station`, Java verifica la firma Ed25519 detached y las evidencias obligatorias del manifiesto mediante `HANDWASH_RELEASE_PUBLIC_KEY_PATH` (PEM absoluto, externo al repositorio), incluida la SHA-256 del JAR Java realmente ejecutado, los SBOM Java/Python de cámara (CycloneDX 1.6), `run_handwash_station.py`/`run_yolo26_continuity_camera.py` y los locks de runtime y del generador. El supervisor repite esas comprobaciones y valida los hashes SHA-256 de los pesos antes de iniciar YOLO. Antes de arrancar Java y otra vez antes de cada inicio/reintento YOLO, comprueba que el Python seleccionado sea CPython 3.14.4/macOS arm64 y que las versiones instaladas coincidan exactamente con el lock de cámara; el proceso hijo no hereda `PYTHONPATH` ni paquetes del user-site. `requirements-camera.txt` instala ese perfil runtime exacto; para otra versión de Python o arquitectura se debe crear y revisar otro lock, no relajar esta validación. `scripts/build_handwash_station.sh` genera ambos SBOM: Java con dependencias Maven compile/runtime y cámara Python desde el lock exacto. El campo firmado requerido para Python es `stationArtifacts.cameraPythonSbomSha256`; ambos gates validan hash, formato, versión y que los paquetes/versiones Python coincidan exactamente con el lock. El lock del generador se resuelve para CPython 3.14.4/macOS arm64 con hashes de wheels y queda ligado mediante `stationArtifacts.sbomGeneratorLockSha256`; solo se usa en build, nunca se instala en el runtime de YOLO. Los SBOM no cubren pesos, macOS ni intérpretes. El lock de cámara fija versiones, pero no hashes de wheels. Ninguna firma sustituye la revisión clínica ni verifica el SO o el origen de los intérpretes.
- `--unvalidated-demo` usa el perfil Spring separado `station-demo`: conserva loopback, autenticación, productor v2, una sesión y OMS deshabilitado, pero no autoriza release. Si `station` y `station-demo` están activos a la vez, prevalece la verificación hospitalaria firmada.
- Si la cámara deja de entregar frames durante más de 2 s, el capturador reinicia solo FFmpeg y vuelve a enumerar el iPhone durante un plazo máximo de 45 s. Mantiene el MJPEG y la sesión, muestra «Cámara desconectada» en el video y no acredita observaciones antiguas. Al recuperarse continúa en la misma sesión; al agotarse el plazo termina con un error claro. El video muestra guías de encuadre para ambas manos y alerta cuando alguna caja toca el borde; no sustituye una calibración presencial con iluminación y posición reales.
- El dashboard en la Mac muestra el video del iPhone, las cajas y etiquetas YOLO y un inset del encuadre de manos. El proceso publica MJPEG local en `8091`; los frames solo viven en memoria. `yolo26s-pose-hands.pt` corre en hilo separado, con una clase `hand` y keypoints `[21,3]`: pasada a 320 px y recuperación a 640 px cada 0,5 s si encuentra menos de dos poses con al menos 7 keypoints visibles. Si el pase completo aún falla, ejecuta un lote de dos recortes solapados al 15 % sobre el eje mayor; mapea las poses al frame original, filtra por lado propietario para no duplicar en el solape y adopta el resultado solo si aumenta las poses válidas. La recuperación fuerza `save=False`; todo sigue en memoria y cuenta las inferencias de los dos recortes en el FPS. Una pose válida de una mano puede guiar el recorte mientras se busca la segunda, pero no habilita fases ordinarias. En `FRICCION_PARCIAL`, una caja de confianza >=0.15 puede guiar el recorte aunque falten keypoints, pero no cuenta como pose válida ni como evidencia OMS; las fases parciales requieren dos poses válidas y recientes y un recorte bilateral. Las fases OMS ordinarias requieren poses y evidencia espacial recientes. Mientras el gate bilateral no está listo, OMS ejecuta únicamente inferencia a cuadro completo para `OMS_CONTACTO_RIESGO`; no evalúa ni publica fases OMS ordinarias. El inset se recalcula con cajas recientes para mostrar el encuadre vivo; el borde rojo señala el último ROI realmente analizado. Cajas de pasos y borde se ocultan tras 0,5 s sin inferencia para evitar mostrar resultados viejos como actuales. Un reintento de pose que no mejora conserva la detección primaria y su timestamp; la recuperación toma el frame más reciente tras adquirir el acelerador. Las cajas se dibujan aunque los keypoints estén ocluidos. El hilo de manos tiene prioridad sobre los pasos: el detector procesa recortes a un máximo de 8 FPS y puede reintentar a 640 px cada 0,8 s si no acepta paso. `Fondo` veta un paso si su confianza es igual o superior a la del paso. Si pose falla, el stream continúa y se reintenta con espera exponencial; los pasos ordinarios se abstienen, conservándose solo la alerta OMS de contacto de riesgo. No hay respaldo de pasos parciales a cuadro completo. Las detecciones débiles no borran votos del capturador y solo se publican clases canónicas; una clase que llega a Java bajo su umbral se filtra y rompe únicamente la continuidad temporal de Java. Tras 0,9 s sin fase estable se envía `Fondo` a Java para reiniciar el intento. `--no-hand-pose` queda solo para depuración y el supervisor de estación lo rechaza.
- Las cajas de pose y de recorte conservan la secuencia y el snapshot que las produjo para analizar ese mismo frame. Las cajas visuales conservan su secuencia y caducidad; son la última localización disponible superpuesta al video vivo. Los snapshots de pose/recorte permanecen solo en memoria, sin historial de imágenes. El paso y su métrica de movimiento solo se emparejan si vienen de la misma secuencia; si la inferencia de pose, su recuperación o el respaldo producen snapshots distintos, no se reutiliza la métrica de otro frame. Cada secuencia aporta como máximo una observación temporal. La edad de resultados se mide desde la captura, no desde el fin de inferencia; los resultados que exceden `--hand-max-age` no acreditan pasos.
- La captura mantiene una vista de solo lectura del buffer de cámara para no copiar el frame completo a 30 FPS. Pose copia solo al adquirir el acelerador y pasos copia solo el recorte que realmente va a inferir. Las cajas primarias se publican antes de la recuperación a 640 px. El hilo de manos deja al menos 50 ms tras finalizar su ciclo para que pasos pueda acceder al acelerador; un intento de adquisición fallido no consume el intervalo de pasos. La codificación JPEG se omite sin dashboard conectado y el último JPEG se borra cuando se desconecta el último visor.
- `backend/models/handwash_who_yolo26m_cls.pt` se usa por defecto en `FRICCION_PARCIAL`, con `HANDWASH_CLASSIFIER_FALLBACK=0` como interruptor de emergencia. Su original se conserva en `ENTRENAMIENTO/derived_handwash_yolo26_cls_2fps_2026-09-26/`. Con dos poses válidas y frescas del mismo frame, el clasificador de video tiene prioridad para seis acciones compatibles y sus clases negativas; requiere confianza >=0,75. Abstenciones vuelven al detector, y la secuencia, los votos, los requisitos de inicio y las infracciones siguen bajo control de Java. En una muestra retenida de 180 imágenes dio 82/92 aciertos en las imágenes con dos poses; hubo 1 paso falso entre las clases negativas con poses bilaterales. Su CPU midió ~26 ms por inferencia elegible. No es validación clínica ni garantiza el dominio de la cámara del iPhone. `00_other_washing_movement`, `08_not_washing` y `07_turn_off_faucet_with_paper_towel` son negativas, nunca se mapean a `Paso7_Circulares`; el detector `Fondo` también veta pasos. El clasificador de video reconoce seis movimientos, no el paso 7 del proyecto.
- `OMS_CONTACTO_RIESGO` es una alerta de control fail-closed, no una fase: Java la acepta con confianza/credencial válidas aunque no haya pose bilateral medible, para que la oclusión no convierta un contacto de riesgo en un rechazo genérico. Las once fases OMS ordinarias continúan exigiendo dos manos y evidencia espacial fresca; `OMS_SIN_EVIDENCIA` conserva su transporte `CONTROL` independiente.
- Antes de cargar el detector, el localizador de manos y el clasificador auxiliar habilitado, el capturador canónico verifica el SHA-256 contra una única entrada de `backend/models/model-manifest.json`; un peso ausente, no registrado o cambiado detiene el arranque. Esto detecta deriva accidental, no verifica una firma ni certifica el origen del modelo. Un artefacto nuevo debe registrarse con rol y hash revisados antes de usarlo.
- La pérdida de evidencia se calcula por tiempo desde la última observación estable, aunque el bucle omita inferencias. Tras 0,9 s se encola la señal de pérdida y se vacían los votos temporales; una pausa prolongada no reutiliza votos anteriores. `--no-hand-pose` se rechaza para un modelo OMS completo.
- La anotación y publicación MJPEG corren en un hilo independiente de la inferencia de pasos, con un límite de 24 FPS por defecto (configurable con --stream-fps, máximo 30) y el frame de cámara más reciente. Ese hilo recibe un snapshot coherente de resultados en CPU; no ejecuta YOLO ni espera el acelerador. Los contadores previos de FPS se inicializan antes de usarse. El cierre de sesión también detiene este publicador.
- Cada proceso MJPEG queda ligado de forma inmutable al `sessionId` que devuelve Java al crear o vincular la sesión. El dashboard incluye ese mismo `sessionId` en la solicitud del stream; el capturador rechaza con HTTP 409 las solicitudes sin ID o de otra sesión. Sin sesión vinculada no se muestra video, evitando mezclar la cámara de un intento con el Stepper de otro.
- El capturador oficial usa protocolo de productor v2. Al crear o emparejar una sesión envía `producerProtocolVersion: "2"`; después registra el proceso con `POST /api/v1/session/{sessionId}/producer-epoch` y la credencial vigente en `X-Session-Token`. `service/ProducerProtocolRegistry` valida y reserva bajo el lock de la sesión el epoch, la clase canónica y las secuencias/watermarks del sobre antes de validar evidencia de dominio o entrar a State, Strategy u Observer. Un sobre v2 válido consume su secuencia aunque la validación posterior rechace timestamp, confianza o evidencia; ese mismo frame no se puede reparar/reintentar con la misma secuencia. Un epoch/clase wire inválidos, secuencia atrasada/duplicada o desajuste entre secuencias de evidencias se rechazan antes de reservar. Las detecciones v2 deben usar etiquetas wire canónicas exactas (`PASO_1_PALMAS`…`PASO_7_CIRCULARES` o las clases OMS exactas permitidas); los nombres CamelCase, alias históricos y etiquetas normalizadas se rechazan como `NON_CANONICAL_CLASS` antes de notificar observadores. Las sesiones v1 conservan compatibilidad con alias históricos. Si `evidenciaMovimiento` está presente, `secuencia` debe ser la misma que `frameSequence`. Un Python reiniciado solicita otro epoch; un reinicio interno de FFmpeg conserva el epoch y el contador global de frames de ese proceso. Las señales `FONDO`/`OMS_SIN_EVIDENCIA` usan `eventType: CONTROL`, `controlSequence` y `frameWatermark`; el watermark invalida inferencias en vuelo anteriores. Los pulsos bilaterales usan el evento independiente `PRESENCE`, la misma secuencia de control y su watermark de frame; nunca llevan evidencia de paso ni entran a los observadores. Java requiere 3 s continuos con dos manos antes de permitir pasos y reinicia el dwell si falta una mano o hay más de 500 ms entre pulsos antes del primer inicio. Las sesiones v1 conservan compatibilidad; v1 no puede rebajar una sesión estricta y el capturador v1 recibe HTTP 409 al intentar emparejarse con ella. `accepted`/`filtered` conservan el significado de ACK de transporte: ni siquiera `accepted: true` certifica que State acreditó un paso. `captureAgeMs` es exclusivamente diagnóstico; Java no compara relojes ni lo usa para tiempo clínico o acreditación.
- Emparejar una sesión activa indicando v2 la hace estricta e invalida cualquier epoch de productor que estuviera activo antes de devolver el token del dispositivo. Si el registro nuevo falla, la sesión permanece estricta sin aceptar eventos hasta que un productor autorizado consiga su epoch.
- Los rechazos de integridad v2 conservan el JSON ACK `{accepted, filtered}` y pueden añadir la cabecera `X-Producer-Rejection-Reason` de cardinalidad finita. El capturador detiene la publicación si el epoch fue sustituido o aún no está registrado; los rechazos de secuencia/evidencia descartan solo ese evento.
- Para ahorrar codificación y ancho de banda, la copia del dashboard se reduce por defecto a 720×405 después de anotar y se publica hasta 24 FPS (`--stream-fps`, 5–30); captura, crops, frames emparejados y entrada YOLO permanecen en 960×540. `--stream-width` y `--stream-jpeg-quality` controlan solo la salida visual, nunca los umbrales ni la evidencia de lavado.
- En el frontend TypeScript, mantener POO en servicios/adaptadores de dominio (`BackendMessageMapper`) y aplicar una sola actualización de Zustand por mensaje WebSocket. La presentación usa componentes y hooks funcionales propios de React; no migrarlos a class components.
- El dashboard muestra en todas las rutas el modo obtenido de `GET /api/v1/deployment/status`; desarrollo, demo, piloto o modo no verificado nunca deben presentarse como producción clínica. Si falla la consulta, mostrar advertencia no verificada y permitir reintentar.
- La comunicación entre YOLO y Java debe permanecer local (`localhost`) siempre que ambos procesos estén en la misma Mac.
- `service/ClinicalDecisionPolicy` es la única fuente de autorización clínica. Hoy todos los perfiles (`DEVELOPMENT`, `NON_CLINICAL_DEMO`, `HOSPITAL_PILOT`) devuelven `clinicalDecisionAllowed=false`; un resumen nunca puede publicar `aprobado=true` ni `APROBADO` solo porque la evidencia visual/protocolo esté completa. Un futuro perfil de producción necesita una autorización firmada y revisada por separado; no se habilita con una variable de entorno.
- La pose de manos acepta cajas desde 0,001 solo si cada mano mantiene al menos 7 keypoints con confianza >=0,10; NMS usa IoU 0,90 y conserva hasta 16 propuestas antes de deduplicar. En la misma secuencia retenida, bajar el umbral de caja de 0,005 a 0,001 aumentó las poses bilaterales de 6/84 a 56/84 y los acuerdos de paso tras filtros temporales/bilaterales de 0/74 a 26/74. La evidencia de inicio sigue exigiendo keypoints >=0,30 y medición espacial bilateral válida. Las cajas dibujadas y usadas como ROI conservan el umbral independiente >=0,15: una propuesta de confianza baja no se presenta como caja visible ni genera inset.
- En el modo parcial, Java exige una clase canónica con confianza aceptada por el receptor, dos manos recientes, medición espacial bilateral válida y movimiento superior a un umbral distinto para iniciar (`handwash.intention.start-minimum-normalized-movement`) y acreditar pasos (`handwash.intention.step-minimum-normalized-movement`). Ambos valen `1e-8` por defecto y no están calibrados clínicamente; en `station` deben coincidir con los valores firmados del runtime y un reporte independiente. No se exige una trayectoria ni un patrón articular fijo. El inicio requiere además palmas reconocidas de forma sostenida y confianza >=0,75. El productor mantiene en memoria solo las poses recientes necesarias para comparar frames y envía pose (`poseKeypoints`), cajas (`handBoxes`) y dimensiones del frame como metadatos numéricos efímeros; no envía imágenes. En v2 estricta, Java no confía en el escalar de movimiento del productor: OpenCV recalcula el desplazamiento residual entre observaciones, compensando una sola transformación global de cámara sobre ambas manos para preservar el movimiento relativo del frotado. Java conserva una pose previa por sesión/epoch, descarta las coordenadas antes de los observadores y el primer frame tras un reset solo establece la base temporal; no acredita movimiento ni paso. La localización de pose considera utilizable cada mano con 7 keypoints de confianza >=0,10; para medir movimiento cada mano requiere 7 keypoints >=0,30 en observaciones emparejadas. Las cajas de recorte siguen usando su propio umbral de confianza (>=0,15 por defecto). El overlay muestra cuatro cifras: propuestas crudas de YOLO pose, cajas mostrables, poses válidas tras keypoints/deduplicación y manos aptas para inicio; una propuesta no se presenta como mano válida. No añade otro modelo ni guarda frames. La recuperación a 640 px también aporta medidas; secuencias repetidas no suman evidencia.
- La intención es una heurística observable, no una lectura de intención humana ni un modelo de intención entrenado. Para iniciar se requieren palmas con confianza >=0,75, tres observaciones únicas y 650 ms consecutivos, separados como máximo 650 ms, además de superar el umbral de inicio configurado; los pasos activos deben superar el umbral de paso. La mera presencia o quietud de las manos no inicia el intento; el movimiento medible todavía puede incluir vibración/ruido y no demuestra por sí solo intención de lavado. Un cambio al siguiente paso requiere dos observaciones frescas de la misma clase para evitar que un solo frame erróneo avance la secuencia; un salto fuera de orden también requiere dos observaciones antes de reiniciar el intento, separadas por no más de `max-gap-ms` (650 ms por defecto). Una observación nueva rechazada por evidencia incompleta/caducada, movimiento insuficiente o baja confianza rompe los votos de confirmación de Java y el intervalo de permanencia; los frames duplicados o atrasados se ignoran. Ninguna transición exige una trayectoria ni un patrón articular fijo. Una pausa de más de 1500 ms sin fricción confirmada reinicia; `Fondo` conserva el reinicio por pérdida sostenida de evidencia. Los umbrales actuales `1e-8` requieren calibración real; la oclusión puede causar abstenciones.
- La API REST/WS publica `estadoIntencion`, `motivoIntencion`, `tiempoConfirmacionIntencionMs`, `umbralConfirmacionIntencionMs`, `manosVisibles` y el candidato de clase/confianza. `claseCandidata` usa `PASO_N_*` en `FRICCION_PARCIAL` y códigos canónicos `OMS_*` en el protocolo OMS; el candidato no equivale a un paso aceptado. En OMS, fase, candidata, infracción, tiempos, faltantes, intentos y catálogo usan el código wire `OMS_*` de `AccionOms.getClaseModelo()`, no el nombre interno del enum Java, para que el dashboard resuelva las etiquetas. El dashboard indica el motivo por el que todavía no inicia y muestra las manos, el tiempo y el candidato. La presencia sola no inicia intentos ni crea infracciones de secuencia. El modo OMS experimental conserva su propia validación y declara la intención `NO_EVALUADA`; no se habilita con esta heurística. Los clientes parciales sin evidencia bilateral espacial reciente pueden enviar detecciones, pero no acreditan lavado.
- El capturador consulta periódicamente el estado de la sesión; al completarse, expirar, eliminarse o quedar Java inaccesible durante 15 s, cierra la cámara y el stream MJPEG. Una interrupción breve se reintenta sin persistir frames.
- El iPhone solo necesita estar conectado y autorizado como cámara; no se compila, instala ni mantiene una aplicación iOS ni una página de captura en el iPhone para este proyecto.
- No se graban ni se guardan video, imágenes ni frames. Se procesan en memoria para inferencia y visualización. Solo si un error obliga a repetir se conserva una caché temporal y acotada de metadatos del fallo (tipo, paso, motivo y tiempos del intento fallido) en H2 local bajo `.runtime/`; la escritura se encola fuera de la ruta de cámara, `GET /api/v1/session/{sessionId}/attempts` fuerza su vaciado antes de responder y devuelve 503 si no puede confirmarlo, evitando presentar historial atrasado como completo. El cierre ordenado de Java vacía los intentos pendientes. Un cierre forzado aún puede perder metadatos que sigan en cola. No se guardan detecciones normales, tokens ni evidencia visual. La caché mantiene como máximo 100 resúmenes por sesión, se elimina al borrar la sesión o al terminar su período de retención. La base de desarrollo/pruebas no sustituye el estado activo de sesión, que sigue en memoria. El intento nuevo vuelve al primer paso y no hereda cobertura de jabón.
- `service/persistence/FailedAttemptPersistenceCoordinator` es dueño de la cola, los reintentos, la exclusión mutua por sesión y el borrado de la caché de intentos. `SessionManager` solo marca intentos pendientes durante la evaluación; la escritura JDBC se ejecuta fuera de la ruta de cámara. El borrado de sesión espera confirmación del borrado de caché; si H2 falla, la API devuelve 503 y conserva sesión/credenciales para poder reintentar, en lugar de reportar un borrado falso.
- Los artefactos iOS existentes se consideran descartados o fuera del flujo principal y no deben introducirse como requisito de ejecución.
- `--hand-presence-warmup-ms` vale 3000 por defecto: antes de inferir fases ordinarias, Python exige dos poses distintas y frescas durante 3 s consecutivos; un hueco mayor que `min(--hand-max-age, 650 ms)` reinicia el contador mientras Java no haya confirmado el primer inicio. Además, Python envía pulsos v2 `PRESENCE` al cambiar el conteo y con objetivo de 250 ms entre observaciones de pose nuevas; Java mide independientemente 3000 ms con reloj monotónico de recepción y hueco máximo de 500 ms. Los pulsos no son detecciones de paso, no invocan patrones ni guardan imágenes. Antes del inicio, 0/1 mano o un pulso ausente por más de 500 ms reinicia el dwell del servidor; un paso prematuro se descarta y no llega a State/Strategy/Observer. El contador local se muestra en el video. Durante el warm-up OMS conserva solo inferencia a cuadro completo de `OMS_CONTACTO_RIESGO`; las fases OMS ordinarias quedan filtradas hasta que ambos gates se abran. Tras `EN_PROGRESO`, la disponibilidad inicial queda latched para esa sesión; cada paso aún requiere evidencia bilateral fresca y la pérdida/antigüedad bloquea fases ordinarias, sin reiniciar el lavado; la alerta OMS de riesgo permanece habilitada. `run_handwash_station.py` fija 3000 ms y estación fija el hueco máximo en 500 ms; solo depuración directa puede reducir el dwell. La presencia sola no inicia ni aprueba. Este gate no constituye validación clínica ni multivista.

---

## 3. Catálogo de Agentes / Componentes del Servidor

Integridad de evidencia regional OMS: cuando `evidenciaJabon` está presente en una detección, el productor debe enviar `evidenciaJabonSecuencia` de la misma inferencia. En v2 debe coincidir con `frameSequence`; para una solicitud legada sin ese campo, debe coincidir con `evidenciaMovimiento.secuencia`. Evidencia ausente, huérfana, caducada o de otra secuencia no acredita cobertura. Si la secuencia no coincide, el sobre v2 se filtra sin consumir el frame; si el sobre sí es válido pero falta evidencia de dominio o está caducada, se consume el frame y la observación se rechaza, por lo que hay que esperar una inferencia nueva.

Los controles del productor v2 (`FONDO` y `OMS_SIN_EVIDENCIA`) no pueden incluir `frameSequence`, pose, `evidenciaJabon` ni `evidenciaJabonSecuencia`; un sobre que mezcle control e inferencia se rechaza como integridad de transporte y no altera la secuencia, el estado ni los votos de la sesión.

### 3.1 Agente Receptor (Ingestión de Datos)

- **Rol:** Punto único de entrada de las detecciones enviadas por el proceso YOLO que corre en la Mac.
- **Responsabilidad exacta:**
- Recibir detecciones por REST (`POST /api/v1/deteccion`; alias legada `/api/deteccion`). El WebSocket (`/ws/{sessionId}`) es de salida hacia el dashboard, no es la entrada del modelo.
  - Responder por REST con ACK compacto (`accepted`, `filtered`) para el flujo de cámara; solo `?includeState=true` agrega el snapshot de diagnóstico. El estado completo de UI se publica por WebSocket.
  - Deserializar el payload JSON a un DTO `DeteccionEvento`.
  - Validar la integridad estructural del mensaje (campos obligatorios, tipos, rango de confianza `[0.0, 1.0]`).
  - Publicar el evento validado a todos los observadores suscritos.
- **Patrón implementado:** **Observer — rol de Subject/Publisher**. No conoce a sus consumidores; solo mantiene una lista de `DeteccionObserver` y los notifica en cada mensaje entrante. Esto permite agregar nuevos consumidores (ej. un agente de auditoría/logging) sin modificar el receptor.
- **Edge cases que maneja:**
  - Payload malformado o campos obligatorios faltantes → responde `400` (REST) y no propaga el evento. El WebSocket es de salida; si el cliente intenta enviarle datos, se cierra con código `1003`.
  - Confianza (`confidence`) por debajo de un umbral configurable (default `0.35`; el inicio exige `0.75`) → el evento se descarta antes de notificar, evitando que ruido del modelo YOLO contamine la máquina de estados.
  - Desconexión abrupta de YOLO o de la cámara → la sesión deja de recibir eventos y expira por inactividad; el dashboard conserva su conexión para recibir el resumen parcial. La desconexión del dashboard no elimina una sesión válida.

### 3.2 Agente Evaluador de Secuencia (State Manager)

- **Rol:** Garantiza que el usuario ejecute los pasos del lavado de manos en el orden correcto, sin saltos.
- **Responsabilidad exacta:**
  - Mantener, por sesión de usuario, el estado actual dentro de la máquina de estados (`EsperandoInicio → Palmas → Dorsos → Interdigitales → ... → Completo`).
  - Al recibir una detección, delega en el estado actual la decisión de si la transición es válida.
  - Si la clase detectada corresponde al paso siguiente esperado → transiciona de estado.
  - Si corresponde a un paso fuera de secuencia → marca `PASO_OMITIDO` o `PASO_INVALIDO`, conserva el resumen acotado del intento fallido y reinicia desde `PASO_1_PALMAS`; detecciones repetidas del mismo error no crean intentos duplicados.
- **Patrón implementado:** **State**. Cada movimiento (`PalmasState`, `DorsosState`, `InterdigitalesState`, etc.) implementa `PasoLavadoState.procesarDeteccion(claseDetectada)` y retorna el estado siguiente o mantiene el actual si la transición no es válida. `SesionLavado` actúa como contexto y delega el comportamiento en el estado actual.
- **Edge cases que maneja:**
  - Detecciones repetidas del mismo paso (el usuario permanece en "Palmas" varios frames) → no se considera error; se acumula tiempo de permanencia (ver 3.3).
  - Salto de paso (de "Palmas" directo a "Interdigitales") → se registra la infracción, se informa el motivo y se reinicia el intento completo desde el primer paso; no se mezclan tiempos entre intentos.
  - Fin de sesión sin completar todos los pasos (timeout de inactividad) → se emite un resultado parcial con el detalle de pasos faltantes.

### 3.3 Agente Validador de Reglas (Strategy Executor)

- **Rol:** Determina si el tiempo de permanencia en cada paso cumple el umbral exigido por el tipo de lavado seleccionado.
- **Responsabilidad exacta:**
  - Recibir el tipo de protocolo al iniciar la sesión (`CLINICO_QUIRURGICO` o `DOMESTICO`) y resolver la estrategia concreta correspondiente.
  - Al cierre del paso (transición de estado), invocar a la estrategia activa para verificar si el tiempo observado cumple el mínimo exigido. `SesionLavado` acumula los intervalos consecutivos acreditables con el reloj monotónico del servidor y descarta huecos mayores al máximo configurado.
  - El `timestamp` ISO-8601 del cliente se valida por formato y desfase, pero no se usa para acreditar duración; `DetectionController` marca la entrada con `System.nanoTime()` y `Receptor` usa esa marca interna no serializada para el tiempo de paso. Así la espera por el lock Java no se acredita como lavado. Los callers internos sin marca usan el reloj monotónico local al procesar.
- **Patrón implementado:** **Strategy**. La interfaz `ReglaValidacionStrategy` define `validarTiempoPaso(paso, tiempoAcumuladoMs)` y `getDuracionTotalMs()`. Las implementaciones (`ClinicoQuirurgicoStrategy` con objetivo de 60 s y `DomesticoStrategy` con objetivo de 40 s) son intercambiables sin modificar al Evaluador de Secuencia ni al Receptor. Estos umbrales son del tiempo observado en los siete movimientos; no incluyen acciones no detectadas como mojar, aplicar jabón, enjuagar, secar o cerrar el grifo. La estrategia se selecciona una vez por sesión mediante `ReglaValidacionStrategyFactory`.
- **Edge cases que maneja:**
  - Paso completado antes del tiempo mínimo → se marca `TIEMPO_INSUFICIENTE`, pero se permite continuar la secuencia; queda como observación en el resumen y no acredita un procedimiento aprobado.
  - Ausencia de detecciones por un intervalo prolongado dentro del mismo paso → se corta la acumulación de tiempo para evitar que una pausa del usuario se compute como ejecución continua.
  - Cambio de estrategia a mitad de sesión (no soportado): se rechaza explícitamente y se documenta como `TODO` (ver sección 6).

### 3.4 Agente de Notificaciones (Observer)

- **Rol:** Traduce los resultados internos (transiciones de estado, infracciones, validaciones de tiempo) en eventos de salida hacia el dashboard local.
- **Responsabilidad exacta:**
  - Recibir las detecciones como observador del `Receptor`; la configuración registra Evaluador y Validador como observadores críticos que se ejecutan antes del Notificador.
  - Coalescer actualizaciones frecuentes en el estado más reciente y emitir `EstadoLavadoResponse` por WebSocket (`/ws/{sessionId}`); el callback Observer solo encola, el scheduler realiza el I/O fuera del lock de sesión y envía estado antes del resumen final. Los frames de estado llevan la infracción actual; el historial acotado completo se reserva para el resumen final.
  - Emitir el mensaje al dashboard por el canal WebSocket de la sesión.
  - Disparar un evento final de resumen (`ResumenSesionLavado`) al completarse o expirar la sesión.
- **Patrón implementado:** **Observer — rol de Observer/Subscriber**. No conoce el detalle interno de cómo se calculó el estado o la validación; consume el evento validado del `Receptor` después de que los observadores críticos (State y Strategy) procesan la detección.
- **Edge cases que maneja:**
  - Dashboard desconectado al momento de notificar → el evento se descarta silenciosamente (no se reintenta sobre un socket cerrado) y se registra en log.
  - Múltiples eventos en la misma ventana de tiempo (ej. cambio de estado + infracción simultánea) → se agregan en un único payload de salida para evitar chatter excesivo por WebSocket.

---

## 4. Ciclo de Vida y Protocolo de Comunicación (JSON)

### 4.1 Payload de entrada (YOLO en la Mac → Backend Java, `POST /api/v1/deteccion`)

El payload sin `producerProtocolVersion` corresponde al modo legado v1 y se conserva para sesiones antiguas. El capturador oficial crea o empareja con versión 2 y no publica detecciones hasta registrar un epoch autenticado.

```json
{
  "sessionId": "b3f1c2e4-1234-4a1b-9c3d-9a8b7c6d5e4f",
  "claseDetectada": "PASO_2_DORSOS",
  "confianza": 0.92,
  "timestamp": "2026-09-16T14:32:10.452Z"
}
```

| Campo             | Tipo    | Descripción |
|-------------------|---------|-------------|
| `sessionId`       | string  | Identifica la sesión de lavado activa; permite manejar múltiples usuarios concurrentes. |
| `claseDetectada`  | string  | Etiqueta del modelo para uno de los siete movimientos de fricción. |
| `confianza`       | float   | Score de confianza de la inferencia (0.0–1.0), usado como filtro de ruido. |
| `timestamp`       | ISO-8601| Momento del frame enviado; se valida por formato/desfase, pero no acredita duración. Java usa su marca monotónica al entrar al controlador, no el reloj del emisor ni el tiempo esperando el lock por sesión. |

Ejemplo v2 de una observación; la secuencia espacial, cuando existe, identifica exactamente el mismo frame:

```json
{
  "sessionId": "b3f1c2e4-1234-4a1b-9c3d-9a8b7c6d5e4f",
  "claseDetectada": "PASO_2_DORSOS",
  "confianza": 0.92,
  "timestamp": "2026-09-16T14:32:10.452Z",
  "producerEpoch": "5e7786ab-fde6-477f-8e38-3c00a83abf06",
  "eventType": "DETECTION",
  "frameSequence": 842,
  "captureAgeMs": 73,
  "evidenciaMovimiento": {
    "secuencia": 842,
    "manosVisibles": 2,
    "movimientoNormalizado": 0.2,
    "medicionValida": true,
    "antiguedadMs": 73
  }
}
```

`producerEpoch` identifica una sola ejecución de Python y se obtiene con el token de propietario/dispositivo ya existente. El contador de frame es creciente, único dentro de ese epoch y sigue avanzando cuando FFmpeg se reconecta dentro del mismo Python. Un `CONTROL` (`FONDO`/`OMS_SIN_EVIDENCIA`) y un `PRESENCE` contienen un `controlSequence` creciente compartido y `frameWatermark`; ninguno contiene `frameSequence` ni evidencia espacial. `PRESENCE` añade `presenceHandsVisible` (0–2) y se emite al cambiar el conteo y con objetivo de 250 ms entre observaciones nuevas de pose. Java guarda watermarks de inferencia, presencia y control bajo el lock de la sesión; una detección anterior a la presencia aceptada se filtra. La compuerta Java requiere dos manos durante 3000 ms de tiempo monotónico medido al recibir observaciones, separadas por no más de 500 ms; la pérdida reinicia el dwell antes del inicio y las fases prematuras no llegan a State/Strategy/Observer. Epoch incorrecto/antiguo, secuencia repetida/atrasada, watermark atrasado o desajuste se responden con el ACK filtrado actual (`HTTP 200`, `accepted: false`, `filtered: true`). `captureAgeMs` es diagnóstico del productor; Java no compara relojes entre procesos ni lo usa como tiempo de lavado o criterio de acreditación.

### 4.2 Payload de salida (Backend Java → Dashboard en la Mac)

```json
{
  "sessionId": "b3f1c2e4-1234-4a1b-9c3d-9a8b7c6d5e4f",
  "estadoActual": "PASO_2_DORSOS",
  "confianzaDeteccion": 0.92,
  "tiempoAcumuladoMs": 4200,
  "infraccion": null,
  "progreso": {
    "pasosCompletados": 1,
    "pasosTotales": 7
  }
}
```

En caso de infracción, el campo `infraccion` se completa así:

```json
"infraccion": {
  "tipo": "PASO_OMITIDO",
  "detalle": "Se detectó PASO_4_INTERDIGITALES sin completar PASO_3_PALMA_DORSO_DEDOS"
}
```

### 4.3 Reacción de la tubería de agentes

1. `SessionManager` autentica `X-Session-Token` y, en v2, coordina con `ProducerProtocolRegistry` la validación de epoch, secuencia y correspondencia de evidencia bajo el lock de la sesión. Los rechazos de integridad no alcanzan a los agentes.
2. El **Agente Receptor** valida la estructura JSON del evento aceptado por transporte.
3. Publica el evento a los observadores críticos (State y Strategy) y después al Notificador.
4. El **Evaluador de Secuencia** procesa la clase detectada contra el estado actual de la sesión.
   Antes de ello, en modo parcial ejecuta la cadena de intención y su confirmación temporal por sesión. Si se rechaza la observación, no se avanza State ni se acredita duración; Observer puede notificar el motivo de espera.
5. `SesionLavado` acumula los intervalos de observación válidos; el **Validador de Reglas** aplica la estrategia activa al tiempo cerrado del paso.
6. El **Agente de Notificaciones** envía el último estado coalescido por WebSocket al dashboard local; al completar/expirar la sesión envía el resumen.

---

## 5. Diagrama de Interacción / Workflow

### 5.1 Flujo Normal (lavado correcto)

```
YOLO en Mac       Receptor Java       State/Strategy       Notificador       Dashboard Mac
    │                  │                    │                   │                  │
    │──POST PALMAS────▶│                    │                   │                  │
    │                  │──detección────────▶│                   │                  │
    │                  │                    │ actualiza paso    │                  │
    │                  │                    │ y tiempo          │                  │
    │                  │                    │──────────────────▶│                  │
    │                  │                    │                   │──WS estado──────▶│
    │                  │                    │                   │                  │
    │──POST DORSOS────▶│──detección────────▶│ PALMAS→DORSOS     │                  │
    │                  │                    │ valida PALMAS     │                  │
    │                  │                    │──────────────────▶│──WS estado──────▶│
    │         ... se repite para los siete movimientos ...                         │
    │                  │                    │                   │──WS resumen─────▶│
```

### 5.2 Flujo Alternativo (salto de paso)

```
YOLO en Mac       Receptor Java       State/Strategy       Notificador       Dashboard Mac
    │──POST PALMAS────▶│──detección────────▶│                  │                  │
    │                  │                    │ estado: PALMAS   │──WS estado──────▶│
    │──POST INTERDIG.─▶│──detección────────▶│                  │                  │
    │                  │                    │ detecta salto    │                  │
    │                  │                    │ registra falta   │                  │
    │                  │                    │ de DORSOS        │──WS infracción─▶│
    │──POST DORSOS────▶│──detección────────▶│ PALMAS→DORSOS    │──WS estado──────▶│
    │                  │                    │                  │                  │
    │         ... el resumen incluye las infracciones de la sesión ...              │
```

> **Nota de alcance:** completar los siete movimientos solo completa la secuencia de fricción. El resumen no declara aprobado el procedimiento completo porque el modelo aún no detecta mojar manos, aplicar jabón, enjuagar, secar ni cerrar el grifo.

---

## 6. Deuda Técnica / Extensiones Futuras

- `TODO:` soportar cambio de estrategia de validación (`ReglaValidacionStrategy`) a mitad de sesión, para escenarios donde el tipo de lavado se reclasifica dinámicamente (ej. detección automática de contexto quirúrgico).

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).

## Ponytail

- Para cambios técnicos: entiende y sigue el flujo real, reutiliza lo existente y elige la solución correcta más pequeña; evita abstracciones y dependencias especulativas.
- No sacrifiques los requisitos explícitos del proyecto, sus patrones/POO, seguridad, validaciones ni pruebas para reducir el cambio.
- Responde en español de forma directa y concisa, sin saludos ni repeticiones; usa listas breves cuando ayuden.
