# Entrenamiento robusto en Google Colab

El modelo actual obtuvo métricas altas en un split pequeño, pero una auditoría
posterior encontró numerosos fotogramas casi duplicados entre train y val; esos
resultados no demuestran generalización. Las pruebas con la cámara del iPhone
también muestran que una imagen aislada no representa todos los ángulos, manos
izquierdas/derechas, oclusiones y cambios de velocidad. Para mejorar la
generalización se preparó
`scripts/train_handwash_robust.py`.

## Fuente recomendada

El proyecto público [`handwash-hygiene-zepmy/2`](https://universe.roboflow.com/tutorial-7lcvi/handwash-hygiene-zepmy) muestra 2.823 imágenes en su vista general y la
versión 2 usada por el modelo contiene 7.040 imágenes. Separa los movimientos
en 12 clases (`Step_2_Left`, `Step_2_Right`, etc.). El
script fusiona izquierda/derecha en las 7 clases que ya entiende el backend
Java. La página publica métricas del modelo de referencia, pero la descarga
del dataset requiere una clave gratuita de Roboflow.

Como alternativa sin Roboflow, el proyecto [Steps-auto-data211](https://github.com/Qunmasj-Vision-Studio/Steps-auto-data211)
declara 7.057 imágenes con las mismas 12 clases y enlaza un descargable
público en [KDocs](https://kdocs.cn/l/cszuIiCKVNis). El repositorio no publica
`best.pt`, por lo que esta fuente también requiere ejecutar el entrenamiento
de Colab, pero evita depender del export de Roboflow.

También se encontró el [modelo público de 5.555 imágenes](https://universe.roboflow.com/lavadodemanos/hand-washing-tlve7-gfp0v-fu3hu) con seis clases y
mAP50 99.5%, pero no incluye el séptimo movimiento requerido por este
protocolo; por eso no se conecta al backend como si fuera un modelo de siete
pasos.

## Opción recomendada para muchos ángulos: MFH

El dataset académico [MFH](https://github.com/willogy-team/hand-gesture-recognition-smc2021)
contiene 731.147 imágenes de siete pasos en seis escenas/cámaras. Descarga el
ZIP desde el [enlace de Google Drive del proyecto](https://drive.google.com/file/d/1BPuj5HGIOFwE8JQmHobgmnL05ifA60In/view?usp=sharing),
descomprímelo en Colab y ejecuta:

```bash
!python scripts/train_handwash_mfh.py \
    --dataset-dir /content/SceneCategory_Frame_final_7classes_6scenes \
    --epochs 40 --imgsz 224 --batch 64 --device 0 --install-model
```

Este resultado es un clasificador multivista opcional. Se instala como
`backend/models/handwash_multiview.pt` y se activa con
`HANDWASH_YOLO_MULTIVIEW_ENABLED=1`; el detector YOLO principal permanece como
primera opinión. La validación se separa por escenas: escenas 1–4 para
entrenamiento y 5–6 para validación cuando el ZIP conserva esa estructura.
También queda preparado el notebook [HandWash_MFH_Colab.ipynb](./HandWash_MFH_Colab.ipynb).

## Pasos en Colab

También queda listo el notebook [HandWash_Robust_Colab.ipynb](./HandWash_Robust_Colab.ipynb), que instala dependencias, solicita la clave sin mostrarla y descarga el `best.pt` resultante.

1. Abre un runtime con GPU T4/L4.
2. Sube el proyecto o clónalo desde tu repositorio.
3. Antes de entrenar, si tu export ya tiene `data.yaml` y los splits YOLO, prepara una
   separación nueva agrupando imágenes exactas y casi duplicadas. Primero revisa el
   diagnóstico sin escribir nada:

```bash
python scripts/prepare_grouped_yolo_dataset.py \
    --data /ruta/al/dataset/data.yaml --dry-run
```

   Si los conteos por clase y por grupo son razonables, crea una carpeta derivada nueva
   (la fuente queda intacta):

```bash
python scripts/prepare_grouped_yolo_dataset.py \
    --data /ruta/al/dataset/data.yaml \
    --output /ruta/handwash_grouped
```

   Copia el proyecto y esa carpeta a Colab/PC con GPU, y pasa su directorio al entrenador:

```bash
python scripts/train_handwash_robust.py \
    --dataset-dir /content/handwash_grouped \
    --epochs 120 --device 0 --install-model \
    --output-dir runs/handwash_robust_grouped
```

   `--dry-run` es solo diagnóstico. El agrupamiento por SHA-256/pHash/MAE reduce la fuga
   de fotogramas visualmente repetidos, pero no prueba independencia por video, persona,
   escena ni lavamanos. Revisa el manifiesto `group_split_manifest.json`; pocos grupos
   de similitud por clase o pocos ejemplos en `val/test` implican que la estimación de
   generalización sigue siendo débil; esos grupos no son necesariamente escenas o sesiones
   independientes. La herramienta requiere anotaciones
   explícitas: un `.txt` vacío significa negativo anotado; si falta el `.txt`, aborta.
   Acepta tanto la estructura Roboflow (`train/images`) como YOLO (`images/train`), y
   conserva los nombres canónicos `Paso1_Palmas`…`Paso7_Circulares`.

4. Ejecuta el entrenamiento en Colab/PC con GPU usando la carpeta derivada:

```bash
!pip install -q ultralytics pyyaml opencv-python-headless
%cd /content/PROYECTO-HAND-WASH-YOLO
!python scripts/train_handwash_robust.py \
    --dataset-dir /content/handwash_grouped \
    --epochs 120 --device 0 --install-model \
    --output-dir runs/handwash_robust_grouped
```

   Si todavía no descargaste un dataset, puedes omitir `--dataset-dir` y configurar
   `ROBOFLOW_API_KEY` mediante Colab Secrets. El preflight puede detenerse si encuentra
   solapamiento visual; en ese caso descarga el export, agrupa sus splits con la utilidad
   anterior y vuelve a ejecutar apuntando al directorio agrupado.

Antes de invocar Ultralytics, el script audita todas las particiones preparadas
(`train`, `val` y `test`, cuando existe) con SHA-256, pHash y error medio de
píxel. Si encuentra copias exactas o candidatos casi duplicados con los
umbrales predeterminados (distancia pHash <=4 y MAE <=5/255), se detiene y no
inicia entrenamiento. Los candidatos son una alerta conservadora, no prueba
automática de que dos imágenes provengan del mismo video. Revisa los pares y
rehaz las particiones agrupando por video/escena/persona antes de reintentar;
no repartas fotogramas aleatoriamente. El preflight no elimina ni reescribe las
imágenes de origen.

También rechaza IDs/clases/cajas YOLO inválidas en vez de reinterpretarlas o
descartarlas silenciosamente. Las carpetas de preparación y de resultados deben
ser nuevas: no se limpian ni reutilizan salidas anteriores, para evitar mezclar
un `best.pt` viejo con un entrenamiento fallido. Si repites la corrida en el
mismo runtime, asigna otro `--output-dir`.

`--install-model` exige un split `test` no vacío y sin candidatos duplicados
con train/val, y se detiene antes de entrenar si falta. El umbral mAP50 de 0,75
es un filtro adicional, no una aceptación clínica.

5. `--install-model` copia el detector como
   `backend/models/handwash_yolo26s_robust.pt` y agrega su SHA-256 a
   `backend/models/model-manifest.json`. Descarga ambos archivos; al llevarlos
   al proyecto, integra la entrada del candidato en el manifiesto local (no
   reemplaces un manifiesto que tenga cambios posteriores).
6. Valida estructura y huella con
   `python scripts/validate_handwash_models.py --model backend/models/handwash_yolo26s_robust.pt`.
   El nombre indica correctamente que es un detector (`detect`), no un
   clasificador.
7. Para una prueba explícita, configura
   `HANDWASH_YOLO_MODEL=backend/models/handwash_yolo26s_robust.pt`; el candidato
   no reemplaza ni se activa automáticamente como modelo de producción. El
   backend Java sigue recibiendo `PASO_1_*` a `PASO_7_*` y aplica
   State/Strategy/Observer.

El script aplica rotación, perspectiva, escala, traslación, mosaico, mezcla y
volteo horizontal. El volteo es seguro porque las etiquetas izquierda y
derecha se fusionan antes del entrenamiento. Si el export trae `test`, también
se evalúa ese conjunto y se guarda `runs/handwash_robust/test_metrics.json`;
con `--install-model` no copia el peso si el mAP50 de test queda por debajo de
0,75. Si ejecutas otra vez en el mismo runtime, por ejemplo usa
`--output-dir runs/handwash_robust_run2`; no borres salidas anteriores para
liberar el nombre.

Ese umbral de mAP es solo un filtro técnico: no compensa fuga entre particiones,
etiquetas incorrectas ni sustituye la evaluación por sesión completa en una
cámara y entorno representativos. Este notebook debe ejecutarse en Colab o en
la PC externa con GPU, nunca en la Mac usada como estación de cámara.

## Alternativa clínica más fuerte

Para máxima robustez temporal, el [dataset PSKUS de Zenodo](https://zenodo.org/records/4537209) contiene 3.185
episodios reales de personal médico y anotaciones por frame. No es un peso
YOLO listo: requiere entrenar un clasificador temporal GRU/LSTM en Colab. La
ventaja es que aprende el movimiento y no solo la apariencia de un frame. El
el [repositorio académico `edi-riga/handwash`](https://github.com/edi-riga/handwash) ya contiene scripts para PSKUS,
METC y el dataset Kaggle, pero tampoco publica checkpoints finales.

No se puede garantizar detección perfecta sin validar con grabaciones tomadas
desde el mismo ángulo y distancia del iPhone. La métrica de entrenamiento no
sustituye esa prueba de generalización.
