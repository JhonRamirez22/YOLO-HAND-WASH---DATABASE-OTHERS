# Seis patrones Java e intención de lavado

## Implementación efectiva

| Patrón | Código principal | Responsabilidad |
| --- | --- | --- |
| State | `state/PasoLavadoState`, estados concretos, `model/SesionLavado` | Secuencia y transiciones de los siete movimientos. |
| Strategy | `strategy/ReglaValidacionStrategy` y sus implementaciones | Duraciones del protocolo seleccionado; independiente de State. |
| Observer | `observer/Subject`, `agent/Receptor`, Evaluador, Validador, Notificador | Procesamiento crítico antes de publicar estado REST/WS. |
| Factory Method | `strategy/CreadorProtocolo`, creadores Objetivo40Segundos y Objetivo60Segundos | Cada creador implementa `crearEstrategia()`; valida que las siete fases tengan duración positiva y que su suma coincida con el total publicado. `ReglaValidacionStrategyFactory` selecciona el creador al abrir sesión. |
| Chain of Responsibility | `intention/FiltroIntencion`, `CadenaIntencionLavado` | Cada filtro rechaza con motivo concreto o delega al siguiente. |
| Decorator | `decorator/strategy/DecoradorMetricasEstrategiaLavado`; `decorator/repository/SqlInjectionGuardFailedAttemptStoreDecorator` | Instrumenta decisiones de Strategy sin cambiar reglas y valida identificadores antes de persistir metadatos. La protección SQL primaria son las consultas parametrizadas, no el patrón por sí solo. |

Los nombres de archivo anteriores son relativos a `backend/src/main/java/com/handwash/`.
El registro por sí solo sería una Simple Factory; el Factory Method está en
la operación sobrescrita `CreadorProtocolo.crearEstrategia()`.

## Decorator y responsabilidades

`config/DecoratorConfig` compone el `FailedAttemptStore` protegido y la fábrica
del decorador de métricas de Strategy. En lavado, el decorador cuenta decisiones
por protocolo/resultado y delega sin cambiar duraciones, secuencia ni criterios
de evidencia; mejora la observabilidad, no la exactitud de YOLO. En persistencia,
el decorador rechaza IDs de sesión que no sean UUID canónicos. Cada consulta de
`FailedAttemptRepository` mantiene placeholders JDBC (`?`) para todos los valores.
No se construyen fragmentos SQL concatenando entrada externa; si se agrega una
columna dinámica en el futuro, deberá validarse con una allowlist, pues los
placeholders no protegen nombres de tablas o columnas.

## Presencia no equivale a lavado

Flujo: YOLO y keypoints en Mac → Receptor → cadena de intención → confirmación
temporal por sesión → State → Strategy → Observer de notificaciones.

La cadena comprueba, en orden:

1. Evidencia válida y no más antigua de 500 ms.
2. Dos manos visibles. Cada medición usada para iniciar o acreditar un paso requiere al menos siete keypoints con confianza >=0,3 por mano en observaciones emparejadas y una caja aceptable; las manos deben estar lo bastante próximas para medir el residuo.
3. Para comenzar, pose bilateral espacialmente medible y movimiento normalizado
   mayor que `1e-8`; este suelo numérico rechaza movimiento nulo, no es un
   umbral clínico de fricción.
4. Clase compatible; para comenzar debe ser Palmas con confianza >=0,75. En una
   sesión iniciada se admite cualquier clase canónica aceptada por el Receptor
   (umbral predeterminado configurable de 0,35 en el backend Java; el umbral de
   inferencia/clasificación del capturador es independiente).

El inicio y cada crédito de fase activa exigen medición espacial bilateral válida
y movimiento medido >`1e-8`. El suelo solo excluye movimiento numéricamente nulo;
no es un umbral clínico de amplitud. El movimiento bajo pero positivo se admite,
pero la vibración/ruido aún puede superar ese suelo. Una observación no medible
o estática no acredita tiempo ni pasos. No se requiere repetir una trayectoria.
Un cambio al paso siguiente necesita dos observaciones frescas de la misma clase
separadas como máximo 650 ms por defecto para amortiguar un frame aislado
inexacto; ambas deben incluir medición válida y movimiento no nulo. Una
clasificación aislada fuera de orden también se trata
como candidata; dos observaciones frescas consecutivas de la misma clase
confirman el salto. Mientras una fase está pendiente, `motivoIntencion` indica
qué clase se está confirmando y el conteo de observaciones; ambas manos siguen
marcándose visibles cuando hay evidencia bilateral reciente. Una observación
nueva rechazada por evidencia incompleta/caducada o baja confianza rompe los
votos de confirmación de Java y el intervalo acreditable; frames duplicados o
atrasados no cambian la confirmación pendiente. Los votos temporales internos
del capturador mantienen su política independiente.

Python compara dos conjuntos de keypoints, sin imágenes almacenadas. Prueba
ambas correspondencias de manos y compensa el movimiento común de cámara
(traslación, rotación y escala) antes de medir el residuo por segundo. Solo
conserva el último conjunto válido durante un intervalo acotado. El resultado
es una medida geométrica, **no una probabilidad de intención**. El ruido del
modelo, las oclusiones y otros gestos parecidos pueden causar errores.

Java requiere al menos tres observaciones únicas y 650 ms consecutivos,
sin huecos mayores de 650 ms, de la clase Palmas, dos manos y medición espacial
bilateral válida para confirmar el inicio. Mide esos intervalos con el reloj
monotónico que Java marca al entrar al controlador, no con el timestamp del
cliente ni con el tiempo esperando el lock por sesión. No acredita retrospectivamente la
confirmación. La falta de manos frescas o de una clase aceptada sí corta la
acumulación; 1500 ms sin fricción confirmada reinician el intento. Un `Fondo`
sostenido mantiene el reinicio de evidencia visual. La reanudación empieza por
Palmas. Cada sesión conserva contadores independientes, sin historial de frames.

Estados de salida: `SIN_EVIDENCIA`, `MANOS_PRESENTES`, `INTENCION_CANDIDATA`,
`LAVADO_PROBABLE`, `PAUSA`. `motivoIntencion` explica el filtro que rechazó o
la confirmación pendiente. `manosVisibles` no equivale al estado de lavado.

## Contrato adicional de POST /api/v1/deteccion

La cámara recibe por defecto únicamente `accepted` y `filtered` para minimizar
serialización y tráfico por frame; el estado completo llega al dashboard por
WebSocket. Los consumidores de diagnóstico pueden añadir `?includeState=true`
para solicitar el snapshot en la respuesta REST.

```json
{
  "evidenciaMovimiento": {
    "secuencia": 123,
    "manosVisibles": 2,
    "movimientoNormalizado": 0.18,
    "medicionValida": true,
    "antiguedadMs": 140
  },
  "evidenciaJabon": {
    "PALMA_IZQUIERDA": { "estado": "ESPUMA_VISIBLE", "confianza": 0.94 }
  },
  "evidenciaJabonSecuencia": 123
}
```

En productor v2 estricto, los pasos ordinarios añaden dentro de
`evidenciaMovimiento` `poseKeypoints` (`[2,21,3]`), `handBoxes` (`[2,4]`) y las
dimensiones del frame. Son solo metadatos numéricos: no se envían ni guardan
imágenes. Java valida la estructura y recalcula el movimiento con OpenCV; no
confía en el escalar del productor. La primera pose tras un reset solo establece
la base temporal y no acredita un paso. Las coordenadas se eliminan antes del
pipeline Observer.

Se añade a los campos existentes de detección. En protocolo v2,
`frameSequence` aumenta dentro del `producerEpoch` y se reinicia únicamente al
registrar un epoch nuevo tras reiniciar Python; la reconexión interna de FFmpeg
conserva epoch y contador. Cada frame se acepta como máximo una vez. La
evidencia regional de espuma se liga al mismo frame que generó la detección y la
pose; Java rechaza la secuencia ausente o distinta, evitando acumular una
clasificación antigua bajo una observación nueva. La antigüedad se mide en Python
para diagnóstico e incluye espera de cola y
reintentos; no se compara con el reloj de Java ni acredita duración clínica.
Los metadatos se aceptan únicamente por la ruta autenticada local; no son una
defensa contra un emisor autorizado malicioso.

`accepted=true` indica que el receptor aceptó el evento, **no** que el gesto
haya acreditado tiempo. El resultado está en `estado.estadoIntencion`, el
paso y los tiempos. Clientes sin evidencia bilateral reciente no inician ni
acreditan pasos; esto incluye la inferencia alternativa de imágenes individuales.
`GET /api/v1/session/{sessionId}` con `Authorization: Bearer <token>` o la
cabecera compatible `X-Session-Token` permite recuperar el mismo snapshot en
`evaluacion`; el WebSocket lo publica en sus actualizaciones.
El modo OMS
experimental no usa esta heurística y devuelve intención `NO_EVALUADA`.

## Ajustes y límites

En `application.yml`, bloque `handwash.intention`:

- `confirmation-ms`: 650; `min-observations`: 3.
- `max-gap-ms`: 650; `pause-reset-ms`: 1500.
- `start-confidence`: 0.75. El inicio rechaza únicamente movimiento normalizado
  <=`1e-8` para no activar con manos quietas; no es un umbral clínico calibrado.
  Cada fase activa también requiere medición bilateral válida y movimiento
  >`1e-8`; se tolera cualquier movimiento positivo, sin umbral de amplitud
  clínicamente calibrado.

Todos se pueden sobrescribir con las variables `HANDWASH_INTENTION_*` del
archivo de configuración. Son valores iniciales, no métricas validadas.
El inicio requiere palmas reconocidas de forma sostenida, confianza inicial,
dos manos visibles, medición espacial bilateral válida y movimiento positivo
por encima del suelo numérico. Esto evita el caso de movimiento exactamente
nulo, pero no descarta toda vibración ni prueba intención. Un detector por
fotograma no puede determinar la intención humana ni distinguir una pose de
palmas sostenida de un frotado real si ambos producen imágenes equivalentes.
Sin evidencia espacial reciente, el sistema se abstiene aunque el detector de
pasos dibuje una caja.

Esta funcionalidad no detecta agua/jabón por sí misma ni certifica el lavado
completo de la OMS. Su precisión debe evaluarse con manos quietas, fricción,
gestos ajenos al lavado, cambios de luz, oclusiones y cámara en movimiento.
El 25-09-2026, con autorización, pasaron 72 pruebas Java y 31 pruebas Python
del capturador y estimador de movimiento. Son pruebas automatizadas con
metadatos/keypoints sintéticos, no validación de exactitud del modelo en vivo.
Se corrigió la acreditación de huecos mayores de 650 ms y el reinicio por
un Fondo de secuencia antigua. La señal de timeout del capturador no adjunta
una secuencia de pose vieja: comunica una pérdida actual de evidencia.
La prueba visual sigue pendiente mientras macOS no publique el iPhone.
