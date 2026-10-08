"""YOLO26 native camera gateway.

The phone is only a camera. This process runs the trained Ultralytics YOLO26
weights on the PC/Mac and forwards normalized detections to the Java backend,
which owns the State/Strategy/Observer validation pipeline.
"""

import io
import os
import threading
from collections import OrderedDict, deque
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import requests
import torch
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from starlette.concurrency import run_in_threadpool
from ultralytics import YOLO


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_PATH = ROOT / "backend/models/handwash_yolo26n_7pasos.pt"
# New checkpoints are candidates, never implicit promotions. Select one only
# with HANDWASH_YOLO_MODEL after the manifest and structural checks pass.
MODEL_PATH = Path(os.getenv("HANDWASH_YOLO_MODEL", DEFAULT_MODEL_PATH))
FALLBACK_CLASSIFIER_PATH = Path(
    os.getenv("HANDWASH_YOLO_FALLBACK_CLASSIFIER", ROOT / "backend/models/handwash_stage_classifier.pt")
)
JAVA_BACKEND_URL = os.getenv("HANDWASH_JAVA_BACKEND_URL", "http://127.0.0.1:8080")
ALLOWED_ORIGINS = [origin.strip() for origin in os.getenv(
    "HANDWASH_CORS_ALLOWED_ORIGINS",
    "http://127.0.0.1:5173,http://localhost:5173",
).split(",") if origin.strip()]
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_IMAGE_PIXELS = 16_000_000
CONFIDENCE = float(os.getenv("HANDWASH_YOLO_CONFIDENCE", "0.35"))
FALLBACK_ENABLED = os.getenv("HANDWASH_YOLO_FALLBACK_ENABLED", "0").lower() in {"1", "true", "yes"}
FALLBACK_CONFIDENCE = float(os.getenv("HANDWASH_YOLO_FALLBACK_CONFIDENCE", "0.80"))
FALLBACK_DETECTOR_CONFIDENCE = float(os.getenv("HANDWASH_YOLO_FALLBACK_WHEN_BELOW", "0.55"))
MULTIVIEW_CLASSIFIER_PATH = Path(
    os.getenv("HANDWASH_YOLO_MULTIVIEW_CLASSIFIER", ROOT / "backend/models/handwash_multiview.pt")
)
MULTIVIEW_REQUESTED = os.getenv("HANDWASH_YOLO_MULTIVIEW_ENABLED", "0").lower() in {"1", "true", "yes"}
MULTIVIEW_WHEN_BELOW = float(os.getenv("HANDWASH_YOLO_MULTIVIEW_WHEN_BELOW", "0.65"))
TTA_ENABLED = os.getenv("HANDWASH_YOLO_TTA_ENABLED", "1").lower() in {"1", "true", "yes"}
TTA_WHEN_BELOW = float(os.getenv("HANDWASH_YOLO_TTA_WHEN_BELOW", "0.55"))
# Difficult frames get one higher-resolution pass only after the normal pass
# and the mirrored TTA are inconclusive. This preserves the low thermal cost
# of the live path while recovering small/partially occluded hands.
MULTISCALE_ENABLED = os.getenv("HANDWASH_YOLO_MULTISCALE_ENABLED", "1").lower() in {"1", "true", "yes"}
HIGH_RES_IMGSZ = int(os.getenv("HANDWASH_YOLO_HIGH_RES_IMGSZ", "640"))
HIGH_RES_CONFIDENCE = float(os.getenv("HANDWASH_YOLO_HIGH_RES_CONFIDENCE", "0.25"))
# 512 is a better CPU default for the live iPhone path. Override with 640 when
# the host has enough GPU/thermal headroom.
IMGSZ = int(os.getenv("HANDWASH_YOLO_IMGSZ", "512"))
DEVICE = os.getenv(
    "HANDWASH_YOLO_DEVICE",
    "mps" if torch.backends.mps.is_available() else "cpu",
)
INFERENCE_LOCK = threading.Lock()
TEMPORAL_HISTORY = int(os.getenv("HANDWASH_YOLO_TEMPORAL_HISTORY", "3"))
TEMPORAL_MIN_VOTES = int(os.getenv("HANDWASH_YOLO_TEMPORAL_MIN_VOTES", "2"))
REQUIRED_STEP_CLASSES = {
    "Paso1_Palmas",
    "Paso2_Dorsos",
    "Paso3_Interdigitales",
    "Paso4_Nudillos",
    "Paso5_Pulgar",
    "Paso6_PuntaDeDedos",
    "Paso7_Circulares",
}

FALLBACK_STEP_CLASSES = {
    "Step_1": "Paso1_Palmas",
    "Step_2_Left": "Paso2_Dorsos",
    "Step_2_Right": "Paso2_Dorsos",
    "Step_3": "Paso3_Interdigitales",
    "Step_4_Left": "Paso4_Nudillos",
    "Step_4_Right": "Paso4_Nudillos",
    "Step_5_Left": "Paso5_Pulgar",
    "Step_5_Right": "Paso5_Pulgar",
    "Step_6_Left": "Paso6_PuntaDeDedos",
    "Step_6_Right": "Paso6_PuntaDeDedos",
    "Step_7_Left": "Paso7_Circulares",
    "Step_7_Right": "Paso7_Circulares",
}


def classifier_step_name(class_name: str) -> str | None:
    """Map canonical names and common public-dataset names to project steps."""
    if class_name in REQUIRED_STEP_CLASSES:
        return class_name
    normalized = class_name.lower().replace("_", "").replace("-", "").replace(" ", "")
    canonical = [
        "Paso1_Palmas",
        "Paso2_Dorsos",
        "Paso3_Interdigitales",
        "Paso4_Nudillos",
        "Paso5_Pulgar",
        "Paso6_PuntaDeDedos",
        "Paso7_Circulares",
    ]
    for index, target in enumerate(canonical, start=1):
        if normalized in {f"step{index}", f"paso{index}", target.lower().replace("_", "")}:
            return target
    return FALLBACK_STEP_CLASSES.get(class_name)


if not MODEL_PATH.exists():
    raise RuntimeError(f"No se encontró el modelo YOLO26: {MODEL_PATH}")

model = YOLO(str(MODEL_PATH))
if model.task != "detect":
    raise RuntimeError(
        f"El modelo {MODEL_PATH} es tarea '{model.task}'. Se requiere un detector 'detect' de pasos."
    )
model_names = model.names if isinstance(model.names, dict) else dict(enumerate(model.names))
canonical_names = {
    class_id: classifier_step_name(class_name)
    for class_id, class_name in model_names.items()
}
missing = REQUIRED_STEP_CLASSES.difference(name for name in canonical_names.values() if name)
if missing:
    raise RuntimeError(
        f"El modelo {MODEL_PATH} no contiene las siete clases de lavado requeridas: {sorted(missing)}"
    )
STEP_CLASS_IDS = [class_id for class_id, name in canonical_names.items() if name]


fallback_model = None
if FALLBACK_ENABLED:
    if not FALLBACK_CLASSIFIER_PATH.exists():
        raise RuntimeError(
            f"El clasificador de respaldo está activado pero no existe: {FALLBACK_CLASSIFIER_PATH}"
        )
    fallback_model = YOLO(str(FALLBACK_CLASSIFIER_PATH))
    if fallback_model.task != "classify":
        raise RuntimeError(
            f"El modelo de respaldo {FALLBACK_CLASSIFIER_PATH} es tarea '{fallback_model.task}', "
            "pero se requiere 'classify'."
        )
multiview_model = None
if MULTIVIEW_REQUESTED:
    if not MULTIVIEW_CLASSIFIER_PATH.exists():
        raise RuntimeError(
            f"El clasificador multivista está activado pero no existe: {MULTIVIEW_CLASSIFIER_PATH}"
        )
    multiview_model = YOLO(str(MULTIVIEW_CLASSIFIER_PATH))
    if multiview_model.task != "classify":
        raise RuntimeError(
            f"El modelo multivista {MULTIVIEW_CLASSIFIER_PATH} es tarea '{multiview_model.task}', "
            "pero se requiere 'classify'."
        )
PREDICT_OPTIONS = {
    "imgsz": IMGSZ,
    "conf": CONFIDENCE,
    "device": DEVICE,
    "verbose": False,
    "classes": STEP_CLASS_IDS,
    "max_det": 10,
}
HIGH_RES_OPTIONS = {
    **PREDICT_OPTIONS,
    "imgsz": max(IMGSZ, HIGH_RES_IMGSZ),
    "conf": min(CONFIDENCE, HIGH_RES_CONFIDENCE),
}
if DEVICE == "mps":
    PREDICT_OPTIONS["quantize"] = 16
app = FastAPI(title="HandWash YOLO26 Native Inference")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class TemporalStepFilter:
    """Reject one-frame class flips without hiding a real step transition.

    The model is spatial (one image at a time), while the task is temporal.
    A short majority window makes the output usable when JPEG compression,
    blur, or a hand crossing the frame causes an occasional wrong class.
    """

    def __init__(self, history_size: int = 3, min_votes: int = 2, max_sessions: int = 256):
        self.history_size = max(1, history_size)
        self.min_votes = max(1, min(min_votes, self.history_size))
        self.max_sessions = max(1, max_sessions)
        self._history: OrderedDict[str, deque[tuple[str, float] | None]] = OrderedDict()
        self._stable: dict[str, tuple[str, float]] = {}

    def update(self, session_id: str | None, best: dict | None) -> dict | None:
        key = session_id or "__anonymous__"
        if key not in self._history and len(self._history) >= self.max_sessions:
            oldest, _ = self._history.popitem(last=False)
            self._stable.pop(oldest, None)
        history = self._history.setdefault(key, deque(maxlen=self.history_size))
        self._history.move_to_end(key)
        if best is None:
            # Never replay an old detection to Java while the hand is absent.
            history.append(None)
            self._stable.pop(key, None)
            return None

        current = (str(best["className"]), float(best["confidence"]))
        history.append(current)
        previous = self._stable.get(key)
        if previous is None:
            if sum(item is not None and item[0] == current[0] for item in history) < self.min_votes:
                return None
            self._stable[key] = current
            return best

        if current[0] == previous[0]:
            stable = current
            self._stable[key] = stable
            return {**best, "className": stable[0], "confidence": stable[1]}

        votes: dict[str, int] = {}
        for item in history:
            if item is None:
                continue
            name, _ = item
            votes[name] = votes.get(name, 0) + 1

        winner = max(votes, key=votes.get, default=previous[0])
        # A class switch needs repeated evidence; one confident false box is
        # not enough to advance Java's sequence machine.
        repeated = votes.get(winner, 0) >= self.min_votes
        if winner == current[0] and winner != previous[0] and repeated:
            stable = current
            self._stable[key] = stable
            return {**best, "className": stable[0], "confidence": stable[1]}

        # An ambiguous frame is not evidence that the old movement continued.
        return None


TEMPORAL_FILTER = TemporalStepFilter(TEMPORAL_HISTORY, TEMPORAL_MIN_VOTES)


def infer_latest_frame(payload: bytes, session_id: str) -> dict:
    """Drop overlapping uploads rather than queue stale camera frames."""
    if not INFERENCE_LOCK.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="Inferencia ocupada; envía un fotograma reciente")
    try:
        return infer_frame(payload, session_id=session_id)
    finally:
        INFERENCE_LOCK.release()


def infer_frame(payload: bytes, session_id: str | None = None) -> dict:
    try:
        with Image.open(io.BytesIO(payload)) as source:
            if source.width * source.height > MAX_IMAGE_PIXELS:
                raise HTTPException(status_code=413, detail="La imagen supera el límite de 16 MP")
            image = source.convert("RGB")
    except HTTPException:
        raise
    except Image.DecompressionBombError as exc:
        raise HTTPException(status_code=413, detail="La imagen supera el límite de resolución") from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Imagen inválida: {exc}") from exc

    # Ultralytics treats ndarray input as OpenCV/BGR. PIL decodes RGB, so swap
    # channels explicitly; otherwise some hand poses produce no detections.
    frame_bgr = np.asarray(image)[:, :, ::-1].copy()
    def parse_detections(result, mirrored: bool = False) -> list[dict]:
        names = result.names
        parsed = []
        image_width = frame_bgr.shape[1]
        if result.boxes is None:
            return parsed
        for box in result.boxes:
            class_id = int(box.cls.item())
            confidence = float(box.conf.item())
            x1, y1, x2, y2 = [float(value) for value in box.xyxy[0].tolist()]
            if mirrored:
                x1, x2 = image_width - x2, image_width - x1
            model_class_name = names[class_id] if isinstance(names, dict) else names[class_id]
            name = classifier_step_name(model_class_name)
            if name is None:
                continue
            parsed.append({
                "classId": class_id,
                "className": name,
                "confidence": round(confidence, 4),
                "bbox": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
            })
        return parsed

    result = model.predict(frame_bgr, **PREDICT_OPTIONS)[0]
    detections = parse_detections(result)

    detections.sort(key=lambda item: item["confidence"], reverse=True)
    detector_best = next((item for item in detections if item["className"].lower() != "fondo"), None)
    tta_used = False
    if TTA_ENABLED and (detector_best is None or detector_best["confidence"] < TTA_WHEN_BELOW):
        mirrored_result = model.predict(frame_bgr[:, ::-1].copy(), **PREDICT_OPTIONS)[0]
        mirrored_detections = parse_detections(mirrored_result, mirrored=True)
        detections.extend(mirrored_detections)
        detections.sort(key=lambda item: item["confidence"], reverse=True)
        detector_best = next((item for item in detections if item["className"].lower() != "fondo"), None)
        tta_used = True
    multiscale_used = False
    if MULTISCALE_ENABLED and (detector_best is None or detector_best["confidence"] < TTA_WHEN_BELOW):
        # A single 640px pass is reserved for hard frames. Running it on every
        # frame makes the iPhone path unnecessarily hot on CPU-only Macs.
        high_res_result = model.predict(frame_bgr, **HIGH_RES_OPTIONS)[0]
        high_res_detections = parse_detections(high_res_result)
        detections.extend(high_res_detections)
        detections.sort(key=lambda item: item["confidence"], reverse=True)
        detector_best = next((item for item in detections if item["className"].lower() != "fondo"), None)
        multiscale_used = True
    multiview_best = None
    if multiview_model is not None and (
        detector_best is None or detector_best["confidence"] < MULTIVIEW_WHEN_BELOW
    ):
        classification = multiview_model.predict(
            frame_bgr, imgsz=224, device=DEVICE, verbose=False
        )[0]
        if classification.probs is not None:
            class_id = int(classification.probs.top1)
            class_name = classification.names[class_id]
            step_name = classifier_step_name(class_name)
            confidence = float(classification.probs.top1conf)
            if step_name:
                multiview_best = {
                    "classId": class_id,
                    "className": step_name,
                    "confidence": round(confidence, 4),
                    "bbox": None,
                    "source": "multiview_classifier",
                }

    classifier_best = None
    selected_best = detector_best
    if multiview_best and (
        detector_best is None or multiview_best["confidence"] > detector_best["confidence"] + 0.05
    ):
        selected_best = multiview_best
    if fallback_model is not None and (
        selected_best is None or selected_best["confidence"] < FALLBACK_DETECTOR_CONFIDENCE
    ):
        classification = fallback_model.predict(
            frame_bgr, imgsz=256, conf=FALLBACK_CONFIDENCE, device=DEVICE, verbose=False
        )[0]
        if classification.probs is not None:
            class_id = int(classification.probs.top1)
            class_name = classification.names[class_id]
            step_name = classifier_step_name(class_name)
            confidence = float(classification.probs.top1conf)
            if step_name and confidence >= FALLBACK_CONFIDENCE:
                classifier_best = {
                    "classId": class_id,
                    "className": step_name,
                    "confidence": round(confidence, 4),
                    "bbox": None,
                    "source": "classifier_fallback",
                }
                if detector_best is None or confidence > detector_best["confidence"] + 0.10:
                    selected_best = classifier_best

    best = TEMPORAL_FILTER.update(session_id, selected_best)
    return {
        "model": "YOLO26",
        "modelPath": str(MODEL_PATH),
        "detections": detections,
        "rawBest": detector_best,
        "classifierBest": classifier_best,
        "multiviewBest": multiview_best,
        "best": best,
        "temporalFilter": {
            "history": TEMPORAL_HISTORY,
            "minVotes": TEMPORAL_MIN_VOTES,
            "enabled": True,
        },
        "fallbackClassifier": {
            "enabled": fallback_model is not None,
            "modelPath": str(FALLBACK_CLASSIFIER_PATH) if fallback_model is not None else None,
        },
        "multiviewClassifier": {
            "enabled": multiview_model is not None,
            "modelPath": str(MULTIVIEW_CLASSIFIER_PATH) if multiview_model is not None else None,
            "threshold": MULTIVIEW_WHEN_BELOW,
        },
        "tta": {"enabled": TTA_ENABLED, "used": tta_used, "threshold": TTA_WHEN_BELOW},
        "multiscale": {
            "enabled": MULTISCALE_ENABLED,
            "used": multiscale_used,
            "imgsz": HIGH_RES_OPTIONS["imgsz"],
            "threshold": TTA_WHEN_BELOW,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "engine": "ultralytics-yolo26",
        "model": str(MODEL_PATH),
        "device": DEVICE,
        "stepClasses": STEP_CLASS_IDS,
        "fallbackClassifier": {
            "enabled": fallback_model is not None,
            "model": str(FALLBACK_CLASSIFIER_PATH) if fallback_model is not None else None,
        },
        "multiviewClassifier": {
            "enabled": multiview_model is not None,
            "model": str(MULTIVIEW_CLASSIFIER_PATH) if multiview_model is not None else None,
            "threshold": MULTIVIEW_WHEN_BELOW,
        },
        "tta": {"enabled": TTA_ENABLED, "threshold": TTA_WHEN_BELOW},
        "multiscale": {
            "enabled": MULTISCALE_ENABLED,
            "imgsz": HIGH_RES_OPTIONS["imgsz"],
            "threshold": TTA_WHEN_BELOW,
        },
    }


@app.post("/infer")
async def infer(
    file: UploadFile = File(...),
    session_id: str = Form(...),
    access_token: str | None = Form(default=None),
):
    if not session_id.strip():
        raise HTTPException(status_code=400, detail="session_id es obligatorio")
    headers = {"X-Session-Token": access_token} if access_token else {}
    try:
        authorization = await run_in_threadpool(
            requests.get, f"{JAVA_BACKEND_URL}/api/v1/session/{session_id}",
            headers=headers, timeout=2)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail="Java backend no disponible") from exc
    if authorization.status_code != 200:
        raise HTTPException(status_code=authorization.status_code,
                            detail="Sesión no disponible o acceso no autorizado")
    if authorization.json().get("estado") in {"COMPLETADA", "EXPIRADA"}:
        raise HTTPException(status_code=409, detail="Sesión terminada")
    payload = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="La imagen supera el límite de 8 MB")
    # Keep heavy inference off the ASGI event loop. Never queue stale frames.
    result = await run_in_threadpool(infer_latest_frame, payload, session_id)
    best = result["best"]
    if best:
        class_to_step = {
            "Paso1_Palmas": "PASO_1_PALMAS",
            "Paso2_Dorsos": "PASO_2_DORSOS",
            "Paso3_Interdigitales": "PASO_3_INTERDIGITALES",
            "Paso4_Nudillos": "PASO_4_NUDILLOS",
            "Paso5_Pulgar": "PASO_5_PULGAR",
            "Paso6_PuntaDeDedos": "PASO_6_PUNTA_DE_DEDOS",
            "Paso7_Circulares": "PASO_7_CIRCULARES",
        }
        paso = class_to_step.get(best["className"])
        if paso:
            event = {
                "sessionId": session_id,
                "claseDetectada": paso,
                "confianza": best["confidence"],
                "timestamp": result["timestamp"],
            }
            try:
                response = await run_in_threadpool(
                    requests.post, f"{JAVA_BACKEND_URL}/api/v1/deteccion",
                    json=event, headers=headers, timeout=2)
                response.raise_for_status()
                result["backend"] = response.json()
            except requests.RequestException as exc:
                raise HTTPException(status_code=502, detail=f"Java backend no disponible: {exc}") from exc
    return result
