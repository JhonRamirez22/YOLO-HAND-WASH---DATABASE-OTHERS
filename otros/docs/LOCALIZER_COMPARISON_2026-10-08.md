# Diagnóstico de localización de manos — 2026-10-08

## Alcance

Comparación de inferencia, sin entrenamiento y sin escribir imágenes, sobre el split `test` de `ENTRENAMIENTO/derived_handwash_yolo26_cls_2fps_2026-09-26`. Se usaron hasta dos imágenes por clase y por ID de cámara; la muestra común resultó en 94 imágenes de seis IDs. Los IDs no contienen una rúbrica de ángulos y no representan una validación leave-camera-out.

## Comandos reproducibles

Desde `scripts/`:

```bash
../.venv/bin/python evaluate_derived_detector.py --with-pose --per-camera 2 --pose-box-confidence 0.001 --pose-model ../backend/models/yolo26s-pose-hands.pt
../.venv/bin/python evaluate_derived_detector.py --with-pose --per-camera 2 --pose-box-confidence 0.001 --pose-model ../backend/models/yolo26_hand_pose_candidate.pt
../.venv/bin/python evaluate_derived_detector.py --with-pose --per-camera 2 --pose-imgsz 640 --pose-recovery-imgsz 640 --pose-box-confidence 0.001 --pose-model ../backend/models/yolo26s-pose-hands.pt
```

El evaluador usa `save=False`. YOLO de pasos, clasificador auxiliar y opciones de inferencia fueron iguales; solo cambió el localizador de pose.

## Cobertura bilateral observada

| ID de cámara del dataset | Imágenes | Activo `yolo26s-pose-hands.pt` | Candidato `yolo26_hand_pose_candidate.pt` |
|---|---:|---:|---:|
| 100 | 18 | 14/18 (77,8 %) | 13/18 (72,2 %) |
| 101 | 4 | 1/4 (25,0 %) | 1/4 (25,0 %) |
| 102 | 18 | 16/18 (88,9 %) | 9/18 (50,0 %) |
| 103 | 18 | 15/18 (83,3 %) | 3/18 (16,7 %) |
| 104 | 18 | 7/18 (38,9 %) | 8/18 (44,4 %) |
| 105 | 18 | 9/18 (50,0 %) | 7/18 (38,9 %) |
| **Total** | **94** | **62/94 (66,0 %)** | **41/94 (43,6 %)** |

El candidato produjo 195 inferencias de recuperación de pose frente a 125 del activo (pasada de alta resolución y recortes); esto es un conteo de inferencias, no una medición de FPS. Aunque mejoró una cámara por 1/18, perdió 21 poses bilaterales netas en la muestra y no es un reemplazo justificado.

## Resolución primaria 640 px frente a 320 px

Se volvió a evaluar el mismo modelo activo y las mismas 94 imágenes cambiando solo la pasada primaria a 640 px; la recuperación también quedó en 640 px. La configuración primaria actual es 320 px con recuperación a 640 px.

| Cámara | 320 px primaria | 640 px primaria |
|---|---:|---:|
| 100 | 14/18 | 11/18 |
| 101 | 1/4 | 1/4 |
| 102 | 16/18 | 12/18 |
| 103 | 15/18 | 9/18 |
| 104 | 7/18 | 5/18 |
| 105 | 9/18 | 4/18 |
| **Total** | **62/94 (66,0 %)** | **42/94 (44,7 %)** |

La pasada primaria a 640 px generó 201 inferencias de recuperación frente a 125 con 320 px. La evaluación no midió latencia/FPS. Con esta muestra no hay base para elevar la resolución primaria: redujo poses bilaterales y aumentó el trabajo de recuperación. Mantener 320/640.

## Salida de pasos condicionada por la pose

- Propuestas combinadas antes del gate bilateral: 59/94 de acuerdo con las etiquetas de la muestra usando el activo; 49/94 con el candidato.
- Propuestas de paso en clases negativas antes del gate: 6 con el activo; 7 con el candidato.
- El clasificador solo, independiente de la pose usada, coincidió en 75/94; la combinación no equivale a pasos aceptados por Java.
- La medición de movimiento válida fue 0 en ambos replays porque cada entrada es una imagen aislada; no es una prueba temporal del estimador Java ni de una sesión completa.

## Clasificador externo de ocho clases como challenger

Se comparó por inferencia, sin entrenamiento ni escritura de medios, el clasificador activo `handwash_who_yolo26m_cls.pt` con `/Users/jhon/Downloads/yolo26n_cls_who_8codes/weights/best.pt`. Ambos son clasificadores de imagen completa, no detectores de manos. El challenger declara ocho clases y omite `08_not_washing`; su `args.yaml` apunta a `/content/WHO_Handwashing_8class_frames`, cuyo dataset y rúbrica no están disponibles para esta auditoría. El cierre del grifo se mapeó explícitamente como negativo, nunca como `Paso7_Circulares`.

Se tomó una muestra balanceada determinista común de 20 imágenes por cada una de las nueve clases del split `test` local (180 imágenes; semilla 20261008), con Ultralytics 8.4.157, CPU, `batch=1`, `save=False`; se respetó `imgsz=320` del activo y `imgsz=224` del challenger. Para comparar la función runtime se mapearon los seis movimientos compatibles a Paso 1–6 y los demás a negativo; una salida con confianza menor que 0,75 se contó como abstención.

| Métrica | Activo 9 clases | Challenger 8 clases |
|---|---:|---:|
| Top-1 tras mapeo semántico | 158/180 (87,8 %) | 138/180 (76,7 %) |
| Decisiones con confianza ≥ 0,75 | 155/180 (86,1 %) | 102/180 (56,7 %) |
| Decisiones aceptadas correctas | 144/155 (92,9 %) | 89/102 (87,3 %) |
| Pasos falsos aceptados en las tres clases negativas | 2 | 1 |

El challenger queda 11,1 puntos porcentuales por debajo en top-1, con menor cobertura aceptada (102 frente a 155) y menor precisión entre decisiones aceptadas; aunque tuvo un paso falso menos en negativos (1 frente a 2), no es una mejora útil para el runtime. En el activo, `08_not_washing` dio 18/20 correctas y dos pasos falsos; los pasos más débiles de esta muestra fueron Paso 2 y Paso 3 (15/20 cada uno). No integrar el challenger ni cambiar pesos/umbrales: la comparación es diagnóstica, el origen del split del challenger no se puede verificar y estas imágenes no prueban secuencia, generalización por cámara ni uso clínico.

## Decisión y límites

Conservar `yolo26s-pose-hands.pt` como localizador activo y mantener deshabilitados ambos candidatos (pose y clasificador). No se cambiaron pesos, umbrales, mapeos ni gates.

Este diagnóstico no prueba precisión clínica, generalización a ángulos no vistos, ni desempeño con Continuity Camera. El test no es independiente por cámara y las etiquetas del checkpoint de pasos siguen siendo ordinales; faltan el `data.yaml` y la rúbrica exactos. La enumeración actual de AVFoundation solo encontró FaceTime HD y `Capture screen 0`, sin Continuity Camera. El manifiesto permanece `NOT_READY` y `hospitalUseAllowed: false`.
