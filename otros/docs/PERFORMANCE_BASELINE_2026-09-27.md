# Backend latency baseline — 2026-09-27

## Scope and environment

The opt-in benchmark uses `DetectionApiPerformanceBaselineBenchmark` and real HTTP requests to an embedded Spring Boot 3.4.1 / Tomcat server bound to loopback. The observed environment was Java 25, Mac OS X 27.0, `aarch64`, 8 processors, H2 in memory, and one HTTP request in flight at a time. All request bodies contain synthetic JSON metadata; YOLO is not invoked and no images, frames, or videos are created or saved.

Each run reports p50/p95/p99 using nearest-rank percentiles. The rejected and active-step cases contain 500 requests each. Start confirmation contains 100 independent sessions and 300 HTTP requests; transition confirmation contains 100 independent sessions and 200 HTTP requests. Request latency measures client send-to-response on the local loopback. Confirmation wall time includes the benchmark's deliberate observation spacing and cohort batching; it is not the time spent executing Java rules.

Run the benchmark explicitly; its class name is intentionally outside default Surefire patterns:

```bash
mvn -f backend/pom.xml -Dtest=DetectionApiPerformanceBaselineBenchmark -Dsurefire.useFile=false test
```

The benchmark prints one `DETECTION_PERFORMANCE_BASELINE` JSON record. The ACK's `accepted` value retains its existing transport meaning; a low-confidence event below is expected to return HTTP 200 with `accepted=false`.

This historical benchmark ran with `/actuator/metrics` exposed on the test server. The current base application profile exposes only `/actuator/health`; the local launcher opts into the `local` profile to expose aggregate metrics for development. Do not enable that profile on a hospital-facing network listener without a separately authenticated management boundary. The default `SERVER_ADDRESS` remains `127.0.0.1`.

This baseline recorded the then-current `handwash.session.expiration-check-ms` default of 10 s. The current application default was reduced to 1 s on 2026-10-02; the historical benchmark values below were not rerun as part of that change. `handwash.notification.expired-summary-recovery-ms` remains a separate 10 s fallback scan. When the expiry sweep detects a transition, it notifies the Observer in that same sweep and the normal WebSocket flush is 33 ms. `handwash.session.expiration.detection.delay` records deadline-to-detection lag; `handwash.websocket.terminal.delivery` records terminal-pair enqueue-to-summary-send completion.

## Results

| Scenario | Samples | Before p50 / p95 / p99 | After p50 / p95 / p99 |
|---|---:|---:|---:|
| Confidence-rejected event (`Paso1_Palmas`, confidence 0.10) | 500 | 0.644 / 1.146 / 2.041 ms | 0.640 / 1.060 / 1.708 ms |
| Fresh bilateral evidence during active Palmas | 500 | 0.361 / 1.017 / 1.816 ms | 0.364 / 0.623 / 0.988 ms |
| Start confirmation — individual POSTs | 300 | 0.226 / 0.692 / 1.263 ms | 0.252 / 0.444 / 1.179 ms |
| Start confirmation — first request to third-observation ACK | 100 | 770.608 / 778.437 / 778.646 ms | 768.226 / 769.770 / 769.926 ms |
| Transition confirmation — individual POSTs | 200 | 0.216 / 0.691 / 1.226 ms | 0.195 / 0.348 / 0.540 ms |
| Transition confirmation — first candidate to confirming ACK | 100 | 164.719 / 168.466 / 168.884 ms | 154.735 / 155.469 / 155.750 ms |

The transition benchmark primes Palmas with enough synthetic dwell to satisfy the existing project Strategy, then sends two distinct, evidence-bearing Dorsos observations. The first-to-second cohort gap is 125 ms plus the request time for the cohort. The start benchmark uses three distinct bilateral Palmas observations spaced 350 ms apart; its approximately 0.77 s wall result includes those configured observations and the batched requests.

## Concurrent producer-integrity load

Run the comparison with:

```bash
mvn -f backend/pom.xml -Dtest=DetectionApiPerformanceBaselineBenchmark#reportConcurrentSingleAndMultipleSessionTransportLoad -Dsurefire.useFile=false test
```

Both runs used the same Mac OS X 27.0 / Java 25 / aarch64 environment, embedded Tomcat on loopback, H2 in memory, 8 workers, 1,600 synthetic POSTs per scenario, and 200 requests per worker. No YOLO, camera, image, frame, video, inference or frontend was involved. Before v2, the request bodies carried epoch/frame/age-shaped JSON fields, which the then-current v1 backend ignored. After v2, those fields were checked against registered epochs and frame watermarks; the after payload additionally names `eventType: DETECTION`. Epoch setup is outside the timed request interval.

| Scenario | Sessions / workers | Before p50 / p95 / p99 (ms) | Before req/s / filtered | After p50 / p95 / p99 (ms) | After req/s / filtered |
|---|---|---:|---:|---:|---:|
| One session, eight concurrent clients sharing an increasing frame allocator | 1 / 8 | 2.342 / 5.306 / 9.100 | 2,249.14 / 0 of 1,600 | 2.572 / 5.056 / 7.970 | 2,191.99 / 680 of 1,600 |
| Eight sessions, one sequential client each, concurrent across sessions | 8 / 8 | 1.989 / 4.128 / 5.248 | 3,383.56 / 0 of 1,600 | 1.901 / 4.098 / 5.553 | 3,380.01 / 0 of 1,600 |

The shared-session stress case deliberately dispatches sequence numbers from
eight concurrent clients. Their HTTP arrival order can differ from assignment
order, so v2 filters older frames after a newer one has won the session lock;
the 699–700 filtered ACKs are integrity rejections, not HTTP failures. The multi-
session case models one serialized camera sender per session and finds no
cross-session rejection. Throughput and percentiles are single-run local
measurements, not a statistically controlled benchmark or an expected camera
rate. Across three post-change repeats, the one-session case varied from 1,683.82
to 2,191.99 req/s and p99 from 7.970 to 29.373 ms, with 680–700 integrity
filters. The eight-session case varied from 2,886.91 to 3,380.01 req/s and p99
from 5.336 to 6.605 ms, with no filters. Repeat under a quiescent target
workload before interpreting small differences.

## Re-ejecución del 2026-10-02

Se volvió a ejecutar el mismo benchmark optativo después de integrar login/TTL,
API v1, DTOs y los decoradores. Entorno: Java 25, macOS 27.2, `aarch64`, 8
procesadores visibles, Spring Boot 3.4.1, Tomcat aleatorio en loopback y H2 en
memoria. Los bodies son JSON sintético; YOLO y la cámara no se invocan.

| Escenario | Muestras | p50 / p95 / p99 | Observaciones |
|---|---:|---:|---|
| Evento rechazado por confianza | 500 | 0.611 / 1.219 / 1.878 ms | HTTP 200, ACK filtrado |
| Evidencia bilateral fresca en paso activo | 500 | 0.170 / 0.342 / 0.495 ms | Una solicitud en vuelo |
| Requests de confirmación de inicio | 300 | 0.161 / 0.401 / 0.819 ms | 100 sesiones, 3 observaciones |
| Inicio: primera observación a ACK confirmatorio | 100 | 754.668 / 756.272 / 756.327 ms | Incluye pausas deliberadas |
| Requests de confirmación de transición | 200 | 0.190 / 0.604 / 1.709 ms | 100 sesiones |
| Transición: primer candidato a ACK confirmatorio | 100 | 156.226 / 161.259 / 162.867 ms | Incluye separación configurada |
| Una sesión, 8 clientes concurrentes | 1,600 | 2.303 / 4.668 / 6.187 ms | 2,409.54 req/s; 660 ACK filtrados por llegada fuera de orden |
| Ocho sesiones, 8 clientes concurrentes | 1,600 | 1.787 / 3.317 / 4.903 ms | 3,942.48 req/s; 0 ACK filtrados |

Es una ejecución aislada, no una comparación causal con el 2026-09-27: cambió
el entorno reportado y la variabilidad del sistema puede explicar diferencias.
Los ACK filtrados del caso de una sesión reflejan secuencias que llegan fuera
de orden entre clientes concurrentes; no son errores HTTP. El benchmark no
demuestra FPS, precisión, calidad de encuadre ni desempeño de inferencia.

## Repetición posterior a ProducerProtocolRegistry — 2026-10-02

Corrida adicional después de extraer epochs, secuencias y watermarks de
`SessionManager` a `ProducerProtocolRegistry`. El entorno reportó Java 25,
macOS 27.2, `aarch64`, 8 procesadores visibles, Spring Boot 3.4.1, Tomcat en
puerto aleatorio loopback y H2 en memoria. Se usaron únicamente solicitudes
HTTP con JSON sintético; YOLO y medios no participaron.

Comando reproducible:

```sh
mvn -f backend/pom.xml -Dtest=DetectionApiPerformanceBaselineBenchmark -Dsurefire.useFile=false test
```

| Escenario | Muestras | p50 / p95 / p99 | Observaciones |
|---|---:|---:|---|
| Evento rechazado por confianza | 500 | 0.476 / 0.794 / 1.009 ms | HTTP 200, ACK filtrado |
| Evidencia bilateral fresca en paso activo | 500 | 0.193 / 0.447 / 0.727 ms | Una solicitud en vuelo |
| Requests de confirmación de inicio | 300 | 0.174 / 0.387 / 0.780 ms | 100 sesiones, 3 observaciones |
| Inicio: primera observación a ACK confirmatorio | 100 | 756.499 / 758.251 / 758.491 ms | Incluye pausas deliberadas |
| Requests de confirmación de transición | 200 | 0.176 / 0.396 / 0.554 ms | 100 sesiones |
| Transición: primer candidato a ACK confirmatorio | 100 | 154.884 / 155.739 / 155.798 ms | Incluye separación configurada |
| Una sesión, 8 clientes concurrentes | 1,600 | 2.382 / 4.283 / 6.261 ms | 2,404.83 req/s; 707 ACK filtrados por llegada fuera de orden |
| Ocho sesiones, 8 clientes concurrentes | 1,600 | 1.315 / 2.479 / 3.188 ms | 5,221.54 req/s; 0 ACK filtrados |

Esta es otra observación, no una medición pareada. Aunque la versión de macOS
reportada coincide con la corrida anterior, el benchmark es sensible a la carga
del host y el orden de solicitudes concurrentes. No atribuir las diferencias
al refactor ni interpretar la variación como una mejora garantizada. Los
rechazos de la prueba de una sesión son secuencias
asignadas concurrentemente que llegaron fuera de orden, no errores HTTP.

## Repetición actual — 2026-10-02

Se repitió el comando después de la última ejecución completa de pruebas. El
entorno fue Java 25, macOS 27.2, `aarch64`, 8 procesadores visibles, Spring
Boot 3.4.1, Tomcat en loopback y H2 en memoria. Son cuerpos JSON sintéticos;
no se abrió la cámara, no se ejecutó YOLO y no se procesaron medios.

| Escenario | Muestras | p50 / p95 / p99 | Observaciones |
|---|---:|---:|---|
| Evento rechazado por confianza | 500 | 0.600 / 1.016 / 1.575 ms | HTTP 200, ACK filtrado |
| Evidencia bilateral fresca en paso activo | 500 | 0.163 / 0.246 / 0.445 ms | Una solicitud en vuelo |
| Requests de confirmación de inicio | 300 | 0.166 / 0.266 / 0.708 ms | 100 sesiones, 3 observaciones |
| Inicio: primera observación a ACK confirmatorio | 100 | 748.584 / 749.261 / 749.306 ms | Incluye pausas deliberadas |
| Requests de confirmación de transición | 200 | 0.174 / 0.270 / 0.564 ms | 100 sesiones |
| Transición: primer candidato a ACK confirmatorio | 100 | 146.848 / 147.250 / 147.296 ms | Incluye separación configurada |
| Una sesión, 8 clientes concurrentes | 1,600 | 2.167 / 4.080 / 5.590 ms | 2,544.79 req/s; 672 ACK filtrados por llegada fuera de orden |
| Ocho sesiones, 8 clientes concurrentes | 1,600 | 1.947 / 4.181 / 6.605 ms | 3,382.38 req/s; 0 ACK filtrados |

En el estrés de una sola sesión, la latencia máxima aislada fue 119.37 ms;
en ocho sesiones fue 15.14 ms. Ambos casos tuvieron 0 respuestas HTTP no-2xx.
La prueba de una sesión comparte deliberadamente una secuencia entre ocho
emisores concurrentes: el orden de llegada puede diferir y Java rechaza los
frames atrasados. No representa el productor canónico, que serializa la
publicación por sesión. La dispersión y los máximos aislados muestran por qué
estos valores son referencia de una ejecución, no una garantía de latencia ni
una comparación causal con corridas anteriores.

## Interpretation and limits

The before and after runs use the same benchmark code, sample sizes, sequential client, H2 setup, and synthetic paths. The two post-change repeats listed above are individual observations, not a controlled causal comparison. Earlier post-change repeats also showed transition-request p95 varying from 0.348 to 0.769 ms and p99 from 0.540 to 1.965 ms. Treat all tables as local references, not statistically controlled performance claims; repeat on an otherwise idle target Mac before drawing conclusions.

The start/transition confirmation wall values are dominated by the required votes and test pacing, not Java execution. These tests do not measure YOLO inference, camera capture, Python queueing, video encoding, clinical accuracy, or a full wash procedure. The metrics endpoint exposes aggregate low-cardinality timers/counters; it does not emit raw session identifiers, tokens, or frame sequence labels.

## Medición focalizada del rechazo temprano v2 — 2026-10-04

Se añadió al benchmark una ruta sintética que acepta una detección v2 y luego
repite 500 veces exactamente su `frameSequence`; las repeticiones deben recibir
ACK filtrado y no alcanzar validación de dominio ni observadores. En una corrida
local: Java 25, Spring Boot 4.1.1, macOS 27.2, `aarch64`, 8 procesadores,
Tomcat loopback y H2 en memoria. La petición contiene solo JSON; cámara y YOLO
no se ejecutan.

| Escenario | Muestras | p50 / p95 / p99 |
|---|---:|---:|
| Rechazo de duplicado v2 por secuencia | 500 | 0.362 / 0.517 / 0.598 ms |
| Evidencia bilateral válida, paso activo | 500 | 0.210 / 0.428 / 0.847 ms |

Es una caracterización de una sola corrida, no una comparación controlada con
la implementación previa ni una garantía de FPS. Sirve para detectar una
regresión futura en la ruta HTTP Java; no mide captura, inferencia YOLO,
precisión, comportamiento de Continuity Camera ni aptitud clínica. Repetir con
la misma carga y en un equipo objetivo antes de sacar conclusiones.

Comando focalizado:

```sh
mvn -f backend/pom.xml '-Dtest=DetectionApiPerformanceBaselineBenchmark#reportFourDecisionPathLatencyDistributions' -Dsurefire.useFile=false test
```
