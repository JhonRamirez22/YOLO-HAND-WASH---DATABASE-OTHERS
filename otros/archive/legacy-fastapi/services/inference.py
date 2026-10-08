"""
2-Stage Inference Pipeline:
  Stage 1: hand_yolov8s → detects if a hand is present
  Stage 2: yolo26n (7-class) → classifies which hand wash step
"""
import numpy as np
import logging
from pathlib import Path
from typing import Optional, Tuple
import cv2

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).parent.parent / "models"

# Class mappings
HAND_DETECTOR_CLASSES = {0: "hand"}

STEP_CLASSIFIER_CLASSES = {
    0: "Paso1_Palmas",
    1: "Paso2_Dorsos",
    2: "Paso3_Interdigitales",
    3: "Paso4_Nudillos",
    4: "Paso5_Pulgar",
    5: "Paso6_PuntaDeDedos",
    6: "Paso7_Circulares",
}

# Map model output classes to backend PasoLavado enum values
STEP_CLASS_TO_PASO = {
    "Paso1_Palmas": "PASO_1_PALMAS",
    "Paso2_Dorsos": "PASO_2_DORSOS",
    "Paso3_Interdigitales": "PASO_3_INTERDIGITALES",
    "Paso4_Nudillos": "PASO_4_NUDILLOS",
    "Paso5_Pulgar": "PASO_5_PULGAR",
    "Paso6_PuntaDeDedos": "PASO_6_PUNTA_DE_DEDOS",
    "Paso7_Circulares": "PASO_7_CIRCULARES",
}


class InferencePipeline:
    """
    2-stage ONNX inference:
      1. Hand detection (YOLOv8s) → filter out frames without hands
      2. Step classification (YOLO26n) → identify the hand wash step
    """

    def __init__(self):
        self._hand_detector = None
        self._step_classifier = None
        self._initialized = False

    def initialize(self):
        """Lazy-load ONNX models on first use"""
        if self._initialized:
            return

        try:
            import onnxruntime as ort

            hand_model_path = MODELS_DIR / "hand_detector.onnx"
            step_model_path = MODELS_DIR / "step_classifier.onnx"

            if not hand_model_path.exists():
                raise FileNotFoundError(f"Hand detector not found: {hand_model_path}")
            if not step_model_path.exists():
                raise FileNotFoundError(f"Step classifier not found: {step_model_path}")

            providers = ["CPUExecutionProvider"]
            self._hand_detector = ort.InferenceSession(str(hand_model_path), providers=providers)
            self._step_classifier = ort.InferenceSession(str(step_model_path), providers=providers)

            logger.info(f"Hand detector loaded: {hand_model_path.name}")
            logger.info(f"Step classifier loaded: {step_model_path.name}")
            logger.info(f"ONNX providers: {self._hand_detector.get_providers()}")
            self._initialized = True

        except Exception as e:
            logger.error(f"Failed to initialize inference pipeline: {e}")
            raise

    def preprocess(self, image: np.ndarray, imgsz: int = 640) -> np.ndarray:
        """Preprocess image for YOLO inference"""
        img = cv2.resize(image, (imgsz, imgsz))
        img = img.astype(np.float32) / 255.0
        img = img.transpose(2, 0, 1)  # HWC → CHW
        img = np.expand_dims(img, 0)  # add batch dim
        return np.ascontiguousarray(img)

    def _postprocess_yolo(
        self, output: np.ndarray, conf_thresh: float = 0.5, iou_thresh: float = 0.45
    ) -> list:
        """Postprocess YOLO output → list of (class_id, confidence, bbox)"""
        detections = []
        # output shape: (1, 5+C, 8400) → transpose to (8400, 5+C)
        preds = output[0].T  # (8400, 5+C)

        for pred in preds:
            cx, cy, w, h = pred[:4]
            scores = pred[4:]
            class_id = int(np.argmax(scores))
            confidence = float(scores[class_id])

            if confidence < conf_thresh:
                continue

            x1 = cx - w / 2
            y1 = cy - h / 2
            x2 = cx + w / 2
            y2 = cy + h / 2
            detections.append((class_id, confidence, (x1, y1, x2, y2)))

        # NMS
        if not detections:
            return []

        boxes = np.array([d[2] for d in detections])
        scores = np.array([d[1] for d in detections])
        indices = cv2.dnn.NMSBoxes(
            [[b[0], b[1], b[2]-b[0], b[3]-b[1]] for b in boxes],
            scores.tolist(), conf_thresh, iou_thresh
        )

        if len(indices) == 0:
            return []

        return [detections[i] for i in indices.flatten()]

    def infer(self, image: np.ndarray) -> dict:
        """
        Run 2-stage pipeline on a single frame.

        Returns:
            {
                "manoDetectada": bool,
                "manoConfianza": float | None,
                "pasoDetectado": str | None,
                "pasoConfianza": float | None,
                "claseBackend": str | None,
            }
        """
        self.initialize()

        result = {
            "manoDetectada": False,
            "manoConfianza": None,
            "pasoDetectado": None,
            "pasoConfianza": None,
            "claseBackend": None,
        }

        # Stage 1: Hand detection (low threshold for sensitivity)
        input_tensor = self.preprocess(image)
        hand_output = self._hand_detector.run(None, {"images": input_tensor})[0]
        hand_detections = self._postprocess_yolo(hand_output, conf_thresh=0.25)

        if not hand_detections:
            return result

        # Take highest confidence hand detection
        best_hand = max(hand_detections, key=lambda d: d[1])
        result["manoDetectada"] = True
        result["manoConfianza"] = round(best_hand[1], 4)

        # Stage 2: Step classification (only if hand detected)
        step_output = self._step_classifier.run(None, {"images": input_tensor})[0]
        step_detections = self._postprocess_yolo(step_output, conf_thresh=0.15)

        if step_detections:
            best_step = max(step_detections, key=lambda d: d[1])
            class_name = STEP_CLASSIFIER_CLASSES.get(best_step[0], "unknown")
            result["pasoDetectado"] = class_name
            result["pasoConfianza"] = round(best_step[1], 4)
            result["claseBackend"] = STEP_CLASS_TO_PASO.get(class_name)

        return result

    def infer_from_bytes(self, image_bytes: bytes) -> dict:
        """Run inference from raw image bytes (JPEG/PNG)"""
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Could not decode image")
        return self.infer(image)


# Global singleton
pipeline = InferencePipeline()
