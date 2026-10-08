# Modelos y entrenamientos revisados

## Resultado incorporado

`backend/models/handwash_stage_classifier.pt` proviene de
[`Vishwakarma-Atul/handWash`](https://github.com/Vishwakarma-Atul/handWash). Es
un YOLO de clasificación con 13 salidas: pasos 1–7 separados por mano y
`background`. Su integración pertenecía al gateway FastAPI experimental, que
ahora está archivado y no forma parte del runtime soportado. Además, en la
validación local del proyecto acertó únicamente el 3,57% del paso. Un peso
entrenado en otro dominio no se debe promover a
producción solo porque el repositorio lo publique.

## Candidatos no integrados directamente

- El repositorio [`S-Kia/Enhancing-generalized-hand-hygiene-recognition`](https://github.com/S-Kia/Enhancing-generalized-hand-hygiene-recognition)
  publica `generalized_lstm_model.keras` para siete pasos y reporta 91,33% de
  accuracy, pero depende de MediaPipe/TensorFlow, usa landmarks en vez de
  imágenes YOLO y su README indica que fue entrenado con una sola vista. No es
  compatible con el capturador canónico sin añadir una segunda tubería de inferencia.
- El dataset [HandWash Hygiene de Roboflow](https://universe.roboflow.com/tutorial-7lcvi/handwash-hygiene-zepmy)
  tiene variantes izquierda/derecha y una versión de 7.040 imágenes. Es el
  mejor candidato para el reentrenamiento robusto, pero la descarga requiere
  autenticación/API key; por eso se dejó el script y el notebook de Colab.
- El dataset clínico [PSKUS de Zenodo](https://zenodo.org/records/4537209)
  aporta 3.185 episodios reales y anotación por fotograma. Es mejor para un
  modelo temporal, pero sus archivos ocupan muchos gigabytes y no publica un
  peso YOLO listo.
- El dataset [MFH multivista y multiescena](https://github.com/willogy-team/hand-gesture-recognition-smc2021)
  contiene 731.147 muestras de siete pasos tomadas en seis ubicaciones/cámaras
  y enlaza el archivo `SceneCategory_Frame_final_7classes_6scenes.zip` en
  Google Drive. El repositorio publica código de ResNet18/AMDIM, pero no un
  checkpoint final listo para descargar. Se añadió
  `scripts/train_handwash_mfh.py` para preparar sus carpetas y producir un
  clasificador opcional `handwash_multiview.pt` en Colab.
- El clasificador académico de [8.538 imágenes](https://github.com/pyaesoneaungmitch/hand-washing-stage-image-classifier)
  reporta 78,3% en ocho clases, pero no publica el dataset ni un peso final y
  no coincide con las siete clases/formatos de este backend; no se incorpora.

## Criterio de aceptación

Un modelo nuevo de detección se conserva como candidato
`handwash_yolo26s_robust.pt`; no se debe confundir con un clasificador ni
activar automáticamente. Antes de usarlo hay que comprobar: tarea `detect`,
siete clases canónicas y semántica documentada, evaluación sin solapamiento por
video/escena/persona/ángulo y una prueba representativa con el iPhone. Ninguna
métrica publicada por otro proyecto garantiza detección perfecta en la cámara
de este sistema.
