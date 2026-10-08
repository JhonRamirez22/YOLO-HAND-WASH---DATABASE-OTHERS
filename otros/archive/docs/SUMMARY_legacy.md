# PROYECTO HAND WASH YOLO — Resumen Completo

> Este archivo conserva notas históricas de versiones anteriores y no es una guía de ejecución vigente. La única arquitectura operativa actual es: iPhone como cámara de Continuidad → YOLO local en Mac → backend Java → video MJPEG y dashboard React locales. No hay app iOS en el flujo. Consultar `AGENTS.md` y `README.md` para requisitos y comandos actuales; no ejecutar comandos ni seguir diagramas iOS/WebSocket de este historial.

## 1. Objetivo del Sistema

Sistema de evaluación parcial de movimientos de lavado en tiempo real:

- **Cámara**: El iPhone se presenta a macOS como cámara de Continuidad; no ejecuta una app ni YOLO.
- **YOLO local**: El proceso Python captura e infiere en la Mac, y publica el video anotado localmente.
- **Backend Java (Spring Boot)**: Recibe detecciones REST (`POST /api/deteccion`), valida secuencia (State), valida tiempos (Strategy) y notifica por WebSocket (Observer).
- **Dashboard React**: En la Mac muestra el stream MJPEG, pasos, tiempos, infracciones y resumen.

Las siete clases disponibles representan movimientos de fricción. Sin detecciones de mojar manos, aplicar jabón, enjuagar, secar y cerrar el grifo, el resumen no certifica el procedimiento completo.

---

## 2. Arquitectura del Sistema

### 2.1 Flujo de Datos

```
Cámara iPhone → Continuity Camera → YOLO en Mac ──REST──▶ Java State/Strategy
                                   │                         │
                                   └──── video MJPEG ───────▶Dashboard React
                                                             ▲
                                              Observer/WebSocket
```

### 2.2 Agentes del Backend

| Agente | Patrón | Responsabilidad |
|--------|--------|-----------------|
| **Receptor** | Observer (Subject) | Ingesta WebSocket/REST, validación estructural, publicación de eventos |
| **Evaluador de Secuencia** | State | Máquina de estados: garantiza orden correcto de pasos |
| **Validador de Reglas** | Strategy | Acumula tiempo por paso, valida contra protocolo activo |
| **Notificador** | Observer | Consolida resultados, envía respuesta al cliente |

### 2.3 Protocolos de Validación

| Protocolo | Tiempo Total | Tiempos por Paso |
|-----------|-------------|------------------|
| **CLINICO_QUIRURGICO** | 60s | 8s por paso (excepto Paso7_Circulares: 12s) |
| **DOMESTICO** | 20s | 3s por paso (excepto Pulgar/PuntaDedos: 2s, Circulares: 4s) |

### 2.4 Los 7 Pasos OMS

| ID | Clase YOLO | Nombre | Código DataSet5 |
|----|-----------|--------|-----------------|
| 0 | Paso1_Palmas | Frotar palmas | movement_code 1 |
| 1 | Paso2_Dorsos | Dorso de manos | movement_code 2 |
| 2 | Paso3_Interdigitales | Entrelazar dedos | movement_code 3 |
| 3 | Paso4_Nudillos | Dedos entrelazados | movement_code 4 |
| 4 | Paso5_Pulgar | Pulgar rotacional | movement_code 5 |
| 5 | Paso6_PuntaDeDedos | Yemas en palma | movement_code 6 |
| 6 | Paso7_Circulares | Muñecas / Circular | movement_code 7 |
| 7 | Fondo | Movimiento genérico | movement_code 0 |

---

## 3. Estado Actual del Proyecto

### 3.1 Backend Java (COMPLETADO)

**Ubicación:** `backend/`

**Stack:**
- Java 21 + Spring Boot 3.4.1
- ONNX Runtime 1.20.0 (inferencia del modelo)
- WebSocket (comunicación en tiempo real)
- REST API (control y monitoreo)

**Archivos clave:**
```
backend/
├── pom.xml                          # Maven config
├── src/main/java/com/handwash/
│   ├── HandWashApplication.java     # Entry point
│   ├── config/
│   │   ├── WebSocketConfig.java     # Configuración WS
│   │   └── SessionConfig.java       # Configuración sesiones
│   ├── controller/
│   │   ├── DetectionController.java # Endpoint REST detecciones
│   │   ├── SessionController.java   # CRUD sesiones
│   │   └── MetricsController.java   # Métricas y estadísticas
│   ├── model/
│   │   ├── Detection.java           # DTO de detección entrante
│   │   ├── Session.java             # Modelo de sesión de lavado
│   │   ├── StepState.java           # Estados de la máquina
│   │   ├── WashProtocol.java        # Enum protocolos
│   │   └── ValidationResult.java    # Resultado de validación
│   ├── agent/
│   │   ├── ReceptorAgent.java       # Observer Subject - ingesta
│   │   ├── SequenceEvaluator.java   # State Manager - secuencia
│   │   ├── RuleValidator.java       # Strategy Executor - tiempos
│   │   └── NotificationAgent.java   # Observer - notificaciones
│   ├── strategy/
│   │   ├── ValidationStrategy.java  # Interfaz Strategy
│   │   ├── ClinicalSurgicalStrategy.java  # CLINICO_QUIRURGICO
│   │   └── DomesticStrategy.java    # DOMESTICO
│   ├── state/
│   │   ├── WashState.java           # Interfaz State
│   │   └── WashStateMachine.java    # Máquina de estados
│   ├── session/
│   │   └── SessionManager.java      # Gestión de sesiones activas
│   ├── inference/
│   │   ├── OnnxInferenceEngine.java # Motor ONNX Runtime
│   │   └── YoloDetector.java        # Post-procesamiento YOLO
│   └── websocket/
│       └── DetectionWebSocket.java  # Handler WebSocket
├── src/main/resources/
│   ├── application.yml              # Config Spring Boot
│   └── static/                      # Frontend web
│       ├── index.html               # Dashboard principal
│       └── test.html                # Test cámara iPhone
└── models/
    ├── step_classifier.pt           # Pesos PyTorch (76.7 MB)
    └── step_classifier.onnx         # Modelo ONNX (36.4 MB) [gitignored]
```

**Para compilar y ejecutar:**
```bash
cd backend
mvn clean install
mvn spring-boot:run
```

### 3.2 iOS (COMPLETADO — pendiente compilar en Mac)

**Ubicación:** `ios/HandWashCompliance/`

**Stack:**
- Swift 5.9+
- SwiftUI (UIKit para cámara)
- UltralyticsYOLO (SPM dependency)
- CoreML (inferencia en dispositivo)

**Archivos clave:**
```
ios/HandWashCompliance/
├── HandWashComplianceApp.swift      # Entry point
├── ContentView.swift                # Navegación principal
├── Models/
│   ├── HandWashStep.swift           # Enum pasos
│   ├── WashSession.swift            # Modelo sesión
│   └── ValidationResult.swift       # Resultado validación
├── Views/
│   ├── CameraView.swift             # Captura cámara trasera
│   ├── SessionView.swift            # UI durante lavado
│   └── ResultsView.swift            # Resumen post-lavado
├── Services/
│   ├── YOLODetector.swift           # Inferencia CoreML
│   ├── WebSocketService.swift       # Comunicación backend
│   └── SessionManager.swift         # Estado de sesión
├── Utils/
│   └── Extensions.swift             # Utilidades
├── HandWashCompliance.xcodeproj/    # Proyecto Xcode
└── Package.swift                    # SPM dependencies
```

**Para compilar en Mac:**
```bash
cd ios/HandWashCompliance
open HandWashCompliance.xcodeproj
# En Xcode: Product → Build (Cmd+B)
# Seleccionar dispositivo iOS真机 para CoreML
```

**Nota importante:** El modelo YOLO se exporta a CoreML en Mac:
```bash
cd /ruta/al/proyecto
yolo export model=runs/detect/handwash-v2-yolo26s/weights/best.pt format=coreml imgsz=640
```

### 3.3 Modelo YOLO (ENTRENAMIENTO COMPLETADO)

**Dataset:** `DataSet5_YOLO/`

**Pipeline de preparación:**
1. 324 videos MP4 (30fps, 2.48GB total, cámaras hospitalarias)
2. 4 anotadores temporales (frame_time, is_washing, movement_code)
3. Consenso por votación mayoritaria entre anotadores
4. Extracción a 1fps → 5,114 frames con movimiento de lavado
5. Auto-anotación de bounding boxes con `hand_yolov8s.pt`
6. Combinación con 567 imágenes manuales existentes
7. Re-balanceo agresivo: Fondo limitado a 800, pasos ~2,000 cada uno

**Dataset final:**
- Train: 14,845 imágenes (8 clases balanceadas)
- Val: 1,200 imágenes (150/clase)
- Config: `DataSet5_YOLO/dataset5_combined.yaml`

**Modelo entrenado:**
- Arquitectura: YOLO26s (small, 9.5M parámetros, 20.8 GFLOPs)
- Épocas: 34 (early stop en epoch 26)
- Pesos: `runs/detect/handwash-v2-yolo26s/weights/best.pt`

**Métricas (mejor época):**
| Métrica | Valor |
|---------|-------|
| mAP50 | 0.299 |
| mAP50-95 | 0.200 |
| Precision | 0.358 |
| Recall | 0.433 |

**Exportar a CoreML (en Mac):**
```bash
pip install ultralytics
yolo export model=runs/detect/handwash-v2-yolo26s/weights/best.pt format=coreml imgsz=640
```

### 3.4 Frontend Web (COMPLETADO)

**Archivos:**
- `frontend/index.html` — Dashboard de monitoreo en tiempo real
- `frontend/test.html` — Test de cámara iPhone (acceso a cámara local)

**Para servir:**
```bash
cd frontend
python -m http.server 8080
# O usar el backend Spring Boot que sirve /static/
```

---

## 4. Estructura Completa del Repo

```
PROYECTO-HAND-WASH-YOLO/
├── AGENTS.md                        # Arquitectura del sistema (docs)
├── README.md                        # Instrucciones generales
├── .gitignore                       # Reglas de exclusión
│
├── backend/                         # Java Spring Boot
│   ├── pom.xml
│   ├── src/
│   └── models/
│       └── step_classifier.pt       # Pesos YOLO26s (76.7 MB)
│
├── ios/HandWashCompliance/          # App iOS (Swift)
│   ├── HandWashCompliance.xcodeproj
│   ├── Package.swift
│   └── Sources/
│
├── frontend/                        # Dashboard web
│   ├── index.html
│   └── test.html
│
├── scripts/                         # Pipeline de entrenamiento
│   ├── prepare_dataset5.py          # Extracción + auto-anotación
│   ├── rebalance_dataset.py         # Re-balanceo de clases
│   ├── train_dataset5.py            # Entrenamiento V1 (nano)
│   └── train_v2.py                  # Entrenamiento V2 (small)
│
├── DataSet5_YOLO/                   # Dataset preparado
│   ├── dataset5_combined.yaml       # Config YOLO (8 clases)
│   ├── images/train/                # 14,845 imágenes train
│   ├── images/val/                  # 1,200 imágenes val
│   ├── labels/train/
│   └── labels/val/
│
├── runs/detect/                     # Resultados de entrenamiento
│   ├── handwash-dataset5/           # V1 (nano, 46 epochs)
│   │   └── weights/
│   └── handwash-v2-yolo26s/         # V2 (small, 34 epochs) ← MEJOR
│       ├── args.yaml
│       ├── results.csv
│       └── weights/
│           ├── best.pt              # Mejor modelo
│           ├── last.pt              # Último checkpoint
│           ├── epoch0.pt
│           └── epoch20.pt
│
├── ENTRENAMIENTO/                   # Datos crudos (gitignored)
│   ├── DataSet5/                    # 324 videos + anotaciones
│   │   ├── Videos/                  # MP4s de cámaras
│   │   ├── Annotations/             # 4 anotadores (CSV+JSON)
│   │   ├── summary.csv
│   │   └── statistics.csv
│   └── hand_yolov8s.pt             # Modelo detector de manos
│
└── hand-wash-compliance-yolo/       # Proyecto训练 antiguo (gitignored)
    ├── hand-wash-dataset.yaml       # Config 7 clases (dataset viejo)
    └── HandWashDataset_yoloFormat/  # 567 imágenes manuales
```

---

## 5. Git History

```
1d632d4  feat: DataSet5 YOLO26s model - balanced training, 34 epochs
4e3fe61  feat: Full Java backend + iOS project + frontend
```

**Commiteado:**
- Backend Java completo
- iOS project (Xcode-ready)
- Frontend dashboard
- Scripts de entrenamiento
- Pesos YOLO26s (best.pt, last.pt, epoch0.pt, epoch20.pt)
- Dataset YAML config

**NO commiteado (gitignored):**
- ONNX models (*.onnx)
- Dataset images/labels (DataSet5_YOLO/images/, labels/)
- Videos crudos (ENTRENAMIENTO/)
- Modelos .pt del repo hand-wash-compliance-yolo/

---

## 6. Próximos Pasos en Mac

### 6.1 Instalar dependencias
```bash
# Python (para inferencia ONNX y exportar CoreML)
pip install ultralytics onnxruntime opencv-python

# Java (para backend)
brew install openjdk@21
brew install maven
```

### 6.2 Exportar modelo a CoreML
```bash
cd /ruta/al/proyecto
python -c "
from ultralytics import YOLO
model = YOLO('runs/detect/handwash-v2-yolo26s/weights/best.pt')
model.export(format='coreml', imgsz=640)
"
# Genera: runs/detect/handwash-v2-yolo26s/weights/best.mlpackage
```

### 6.3 Integrar en iOS
1. Copiar `best.mlpackage` al proyecto Xcode
2. Arrastrar al proyecto → "Copy items if needed"
3. En `YOLODetector.swift`, apuntar al modelo CoreML
4. Configurar `Package.swift` con UltralyticsYOLO
5. Build y run en iPhone真机

### 6.4 Ejecutar backend
```bash
cd backend
mvn clean install
mvn spring-boot:run
# Backend en http://localhost:8080
# WebSocket en ws://localhost:8080/ws/deteccion
```

### 6.5 Ejecutar frontend
```bash
cd frontend
python -m http.server 8080
# Dashboard en http://localhost:8080
```

---

## 7. Variables de Entorno y Configuración

### Backend (application.yml)
```yaml
server:
  port: 8080

spring:
  websocket:
    endpoint: /ws/deteccion

handwash:
  model:
    path: models/step_classifier.onnx
  validation:
    protocol: CLINICO_QUIRURGICO  # o DOMESTICO
    confidence-threshold: 0.3
  session:
    timeout-seconds: 300
```

### iOS (Configuración)
- `BackendURL`: URL del servidor WebSocket (ej. `ws://192.168.1.100:8080/ws/deteccion`)
- `ModelName`: Nombre del modelo CoreML (ej. `best`)
- `ProtocolType`: `clinical` o `domestic`

---

## 8. Solución de Problemas Comunes

| Problema | Solución |
|----------|----------|
| ONNX Runtime CUDA error | Usar CPUExecutionProvider (cuDNN 9.* incompatible con CUDA 12.6) |
| CoreML export falla | Ejecutar en Mac (requiere Xcode) |
| iOS no detecta manos | Bajar `confidence-threshold` en el modelo o en el backend |
| Backend no arranca | Verificar Java 21 y Maven instalados |
| Modelo predice solo "Fondo" | Re-entrenar con más epochs o dataset más grande |
| WebSocket no conecta | Verificar CORS y puerto en backend |

---

## 9. Métricas de Rendimiento

### Inferencia ONNX (CPU, i7-13700K)
- Velocidad: ~64ms/frame (2-stage: hand detect + step classify)
- Suficiente para 15-20 FPS en tiempo real

### Inferencia CoreML (iPhone, esperado)
- Velocidad estimada: ~30-50ms/frame (GPU Neural Engine)
- Suficiente para 20-30 FPS en tiempo real

---

## 10. Decisiones de Diseño

1. **YOLO26s sobre nano**: 9.5M params vs 2.4M — mejor precisión a costa de más compute
2. **8 clases**: 7 pasos OMS + Fondo (movimiento genérico sin paso específico)
3. **Auto-anotación**: hand_yolov8s detecta manos, movement_code asigna clase temporal
4. **Re-balanceo agresivo**: Fondo limitado a 800 para evitar bias
5. **Two-stage pipeline**: Detector de manos → Clasificador de paso (más preciso que end-to-end)
6. **Consenso de anotadores**: Votación mayoritaria entre 4 anotadores humanos
