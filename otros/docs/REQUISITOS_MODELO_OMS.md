# Requisitos para un modelo que evalúe el lavado OMS

## Estado comprobado del proyecto

El peso activo `backend/models/handwash_yolo26n_7pasos.pt` y `datasets/handwash_public_7steps.yaml` cubren siete clases de fricción definidas por el proyecto; su correspondencia uno-a-uno con los gestos numerados oficiales de la OMS no se ha validado. El dataset local no contiene etiquetas de manos mojadas, aplicación/visibilidad de jabón, cobertura por superficie, enjuague, secado ni cierre del grifo. El modelo actual, por tanto, solo puede dar retroalimentación de fricción; no puede emitir una aprobación del procedimiento completo.

No se debe convertir una detección del modelo en evidencia de que una acción no observable ocurrió. En particular, la ausencia de espuma visible puede significar jabón transparente, una mano ocluida o un ángulo insuficiente; los tres casos deben quedar como `NO_VERIFICABLE`, no como cobertura confirmada.

La descarga de una sola clase (`Performing-Hand-Hygiene`) no se incorpora como
fuente de este entrenamiento: no distingue fases ni superficies. Como punto
de partida verificable para **movimientos** existe el [dataset clínico PSKUS
en Zenodo](https://zenodo.org/records/4537209): 3.185 episodios y anotación
por fotograma de seis movimientos, cierre del grifo con toalla y una clase
genérica de otros movimientos. No ofrece etiquetas específicas para mojado,
jabón por región, enjuague o secado, ni un detector YOLO completo listo para
activar. Reutilizarlo exigiría revisar licencia/consentimiento, relabelar
clips completos y crear las anotaciones faltantes; no se pueden inferir esas
etiquetas a partir de la clase genérica.

## Taxonomía de anotación requerida

El detector YOLO debe exportarse con **estos nombres exactos** para que el
runtime Java pueda reconocer sus salidas. Los primeros 12 nombres son fases o
riesgo; los 24 restantes son estados visuales por región:

```text
OMS_01_MOJAR_MANOS
OMS_02_APLICAR_JABON
OMS_03_FROTAR_PALMAS
OMS_04_FROTAR_DORSOS
OMS_05_FROTAR_ENTRE_DEDOS
OMS_06_FROTAR_DORSO_DE_DEDOS
OMS_07_FROTAR_PULGARES
OMS_08_FROTAR_PUNTAS_DE_DEDOS
OMS_09_ENJUAGAR_MANOS
OMS_10_SECAR_TOALLA_DESECHABLE
OMS_11_CERRAR_GRIFO_CON_TOALLA
OMS_CONTACTO_RIESGO
ESPUMA_VISIBLE_PALMA_IZQUIERDA
SIN_ESPUMA_VISIBLE_PALMA_IZQUIERDA
ESPUMA_VISIBLE_PALMA_DERECHA
SIN_ESPUMA_VISIBLE_PALMA_DERECHA
ESPUMA_VISIBLE_DORSO_IZQUIERDO
SIN_ESPUMA_VISIBLE_DORSO_IZQUIERDO
ESPUMA_VISIBLE_DORSO_DERECHO
SIN_ESPUMA_VISIBLE_DORSO_DERECHO
ESPUMA_VISIBLE_INTERDIGITALES_IZQUIERDA
SIN_ESPUMA_VISIBLE_INTERDIGITALES_IZQUIERDA
ESPUMA_VISIBLE_INTERDIGITALES_DERECHA
SIN_ESPUMA_VISIBLE_INTERDIGITALES_DERECHA
ESPUMA_VISIBLE_DORSO_DE_DEDOS_IZQUIERDO
SIN_ESPUMA_VISIBLE_DORSO_DE_DEDOS_IZQUIERDO
ESPUMA_VISIBLE_DORSO_DE_DEDOS_DERECHO
SIN_ESPUMA_VISIBLE_DORSO_DE_DEDOS_DERECHO
ESPUMA_VISIBLE_PULGAR_IZQUIERDO
SIN_ESPUMA_VISIBLE_PULGAR_IZQUIERDO
ESPUMA_VISIBLE_PULGAR_DERECHO
SIN_ESPUMA_VISIBLE_PULGAR_DERECHO
ESPUMA_VISIBLE_PUNTAS_DE_DEDOS_IZQUIERDA
SIN_ESPUMA_VISIBLE_PUNTAS_DE_DEDOS_IZQUIERDA
ESPUMA_VISIBLE_PUNTAS_DE_DEDOS_DERECHA
SIN_ESPUMA_VISIBLE_PUNTAS_DE_DEDOS_DERECHA
```

Las cajas OMS de fase deben encerrar **ambas manos de una sola persona** durante
la acción; las cajas de espuma/no-espuma describen la región anatómica dentro
de esa misma caja. En vivo, una caja de jabón solo se acredita si al menos
el 80 % de su área cae dentro de la caja de la fase correspondiente. Si hay
dos cajas de acción espacialmente incompatibles o personas separadas, el visor se abstiene
de acreditar la fase; no mezcla regiones de personas distintas. Esta regla
geométrica reduce mezclas evidentes, pero una caja demasiado amplia aún puede
incluir otras manos: el dataset y la prueba final deben incluir escenas con
varias personas para medir falsas aprobaciones.

Una región
ocluida o dudosa se deja **sin una caja positiva**, por lo que en runtime
permanece `NO_VERIFICABLE` y nunca suma cobertura. No se debe etiquetar una
superficie no visible como `SIN_ESPUMA_VISIBLE` solo para completar el mapa.

El script `scripts/train_handwash_who.py` valida esta taxonomía antes de
entrenar y acepta `valid` o `val` como nombre del split de validación.

Anotar clips completos y temporalmente continuos, desde abrir el grifo hasta cerrarlo:

1. `MOJAR_MANOS`
2. `APLICAR_JABON`
3. `FROTAR_PALMAS`
4. `FROTAR_DORSOS`
5. `FROTAR_ENTRE_DEDOS`
6. `FROTAR_DORSO_DE_DEDOS`
7. `FROTAR_PULGARES`
8. `FROTAR_PUNTAS_DE_DEDOS`
9. `ENJUAGAR_MANOS`
10. `SECAR_TOALLA_DESECHABLE`
11. `CERRAR_GRIFO_CON_TOALLA`

Como protección temporal, Java exige al menos dos observaciones con marcas
monotónicas distintas de cada acción y que su duración observada alcance el
mínimo configurado antes de avanzar; una etiqueta aislada no acredita una
fase. La primera observación de la fase siguiente cierra el intervalo anterior
solo si no excede el máximo de separación permitido. Esa asignación temporal
es una regla de software basada en tiempos de recepción del backend, no una
medición exacta del instante físico de transición ni una validación clínica; la
prueba independiente debe medir sus errores antes de habilitar aprobación.

Durante los movimientos de fricción, anotar evidencia positiva de espuma en
cada superficie y lado de la mano cuando sea visible. La evaluación acredita
cada par bilateral **únicamente durante su movimiento correspondiente**:

- palmas izquierda y derecha;
- dorsos izquierdo y derecho;
- espacios interdigitales de ambas manos;
- dorsos de los dedos de ambas manos;
- pulgares izquierdo y derecho;
- puntas de los dedos de ambas manos.

El detector emite `ESPUMA_VISIBLE` o `SIN_ESPUMA_VISIBLE` cuando una región
está claramente visible. Si está ocluida, fuera de cuadro, con resolución
insuficiente o espuma no distinguible, se deja sin caja de evidencia y el
runtime conserva `NO_VERIFICABLE`. Solo dos observaciones cercanas de
`ESPUMA_VISIBLE` durante el movimiento correspondiente acreditan una región.
Si se intenta pasar al movimiento siguiente sin ambas regiones confirmadas,
la sesión se reinicia inmediatamente desde mojar las manos. La evidencia
detectada al aplicar jabón, o en una fase distinta, no sustituye este control.

Si el detector deja de observar una acción OMS de forma sostenida, el visor
envía `OMS_SIN_EVIDENCIA`: Java reinicia el intento y borra la cobertura ya
acreditada. Es una regla conservadora porque una salida de cuadro podría
ocultar un contacto de riesgo. Puede producir reinicios por oclusión o fallo
del detector; una sola cámara RGB no puede certificar que no hubo
contaminación fuera de cuadro.
Esto comprueba evidencia visual de espuma, no presencia química de jabón ni
eliminación de microorganismos.

La sesión debe asociar todas las cajas/regiones a la misma persona y a la misma secuencia; no mezclar manos de otro participante ni evidencia de otro momento o usuario.

## Cómo preparar el dataset

### Datos externos para entrenamiento; sin grabación en el uso normal

El sistema en ejecución usa la cámara del iPhone en directo y **no graba
video**. Como historial de reintentos, Java conserva en RAM un número acotado
de infracciones, tiempos por fase y motivos de reinicio; al eliminar la sesión,
esa memoria se libera (por defecto, la limpieza ocurre tras unos 30 minutos
de retención de una sesión terminada). Este caché sirve para explicar por qué
repetir, no para entrenar a YOLO ni para reproducir imágenes.

Si más adelante se recibe un dataset externo autorizado, debe contener
anotaciones revisadas de las 36 clases y el origen de cada imagen. El script
`scripts/prepare_oms_review_frames.py` queda como herramienta opcional de
preparación **offline** de material que ya exista, no como requisito del
dashboard ni como grabador. No conviertas automáticamente una sugerencia del
detector actual en verdad de mojado o jabón. El validador de entrenamiento
rechazará el dataset sin etiquetas suficientes y sin muestras de las 36
clases en cada split. También rechazará etiquetas de espuma/no-espuma fuera
de la caja de su fase de fricción: el entrenamiento debe respetar la misma
asociación espacial que exige el visor en vivo.

- Exigir que los datos externos cubran ciclos enteros con consentimiento/licencia apropiados y diversidad de personas, tonos de piel, tamaños de mano, ángulos, iluminación, tipos de jabón y baños.
- Etiquetar fases por intervalos temporales y regiones de jabón por mano; conservar los frames sin acción como fondo/negativos.
- Dividir train/validation/test por participante y por grabación, nunca por frames aleatorios del mismo video. Reservar personas, baños y cámaras nunca vistos para test.
- Mantener las secuencias completas en un split; si se exportan frames, el CSV `image,person,video,split` debe relacionar **cada** imagen con su participante y grabación. Ambos identificadores deben quedar en un solo split. El script exige este CSV con `--group-manifest` antes de copiar el candidato.
- Incluir ejemplos difíciles: espuma escasa, manos superpuestas, agua que oculta la espuma, jabón transparente, guantes, objetos fuera de cuadro y contactos de riesgo visibles.
- Mantener procedencia, versión, licencia/consentimiento, mapa de clases y conteos por acción/superficie junto a cada exportación.

Ejemplo mínimo del manifiesto:

```csv
image,person,video,split
train/images/frame_0001.jpg,participante_01,grabacion_01,train
valid/images/frame_0020.jpg,participante_02,grabacion_02,valid
test/images/frame_0040.jpg,participante_03,grabacion_03,test
```

Con la exportación ya anotada en las 36 clases, ejecutar desde la raíz:

```bash
./.venv/bin/python scripts/train_handwash_who.py \
  --dataset-dir /ruta/al/dataset-oms \
  --group-manifest /ruta/al/dataset-oms/grupos.csv \
  --device mps \
  --copy-candidate
```

En Colab con GPU CUDA se usa `--device 0`. El script crea un directorio nuevo
para cada entrenamiento y guarda `data.normalized.yaml` junto con las métricas
de test; no reemplaza el peso activo. Por defecto parte del `yolo26n.pt` que
ya está en este proyecto para evitar una descarga implícita; si hay GPU y
memoria suficientes, `--base-model yolo26s.pt` permite ensayar un modelo mayor.
Para copiar un candidato exige mAP50 global y mínimos de mAP50-95, precisión
y recall **por cada una de las 36 clases**. El archivo `test_metrics.json`
guarda esas métricas individuales; no se debe aceptar un promedio que oculte
una clase de riesgo o una región sin detección.

## Puerta de aceptación antes de activar

1. Evaluar el modelo por acción y por cada una de las 12 regiones en test independiente; informar precisión, recall y confusiones, no solo mAP global.
2. Evaluar secuencias completas: orden, omisiones, falsas transiciones y duración medida en tiempo monotónico del servidor.
3. Medir específicamente la tasa de **falsas aprobaciones** en videos con pasos omitidos, jabón sin cobertura completa, superficies no visibles, enjuague/secado omitidos y contacto de riesgo.
4. No activar la aprobación OMS si falta una clase, una región, una anotación de visibilidad o un umbral validado. El modo actual sigue siendo `FRICCION_PARCIAL`.
5. Una cámara RGB no puede determinar esterilidad, carga microbiana ni todos los contactos/contaminaciones fuera de cuadro. La aplicación debe decir “evidencia visual no verificable” donde aplique y nunca “sin contaminación” como garantía.

El poster oficial de la OMS describe la secuencia de lavado con agua y jabón y el tiempo total de 40–60 segundos: https://www.who.int/docs/default-source/patient-safety/how-to-handwash-poster.pdf
