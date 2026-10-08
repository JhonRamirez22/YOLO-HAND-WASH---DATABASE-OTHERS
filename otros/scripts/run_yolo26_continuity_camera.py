#!/usr/bin/env python3
"""Run native YOLO26 on a macOS camera, including Apple's Continuity Camera.

The iPhone is selected by macOS as a normal AVFoundation camera. No AirDrop,
browser, web deployment, or iPhone application is used by this path.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import math
import os
from queue import Empty, Full, Queue
import re
import subprocess
import threading
import time
from collections import deque
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import parse_qs, urlsplit

import cv2
import numpy as np
import requests
import torch
from ultralytics import YOLO

if __package__:  # Support both direct script execution and package-based tests.
    from .dataset_contracts import DERIVED_CLASSIFIER_NAMES
else:  # pragma: no cover - exercised by the command-line entry point
    from dataset_contracts import DERIVED_CLASSIFIER_NAMES


ROOT = Path(__file__).resolve().parents[1]
MODEL_MANIFEST_PATH = ROOT / "backend/models/model-manifest.json"
DEFAULT_MJPEG_MAX_CLIENTS = 2
DEFAULT_MJPEG_CLIENT_TIMEOUT_SECONDS = 2.0
DEFAULT_HAND_POSE_IMAGE_SIZE = 320
DEFAULT_HAND_POSE_CONFIDENCE = 0.001
DEFAULT_HAND_PRESENCE_MAX_GAP_MS = 500
HTTP_SESSION = requests.Session()


def _reject_duplicate_manifest_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for key, value in pairs:
        if key in parsed:
            raise ValueError(f"El manifiesto contiene una clave JSON duplicada: {key}.")
        parsed[key] = value
    return parsed


STEP_TO_BACKEND = {
    "Paso1_Palmas": "PASO_1_PALMAS",
    "Paso2_Dorsos": "PASO_2_DORSOS",
    "Paso3_Interdigitales": "PASO_3_INTERDIGITALES",
    "Paso4_Nudillos": "PASO_4_NUDILLOS",
    "Paso5_Pulgar": "PASO_5_PULGAR",
    "Paso6_PuntaDeDedos": "PASO_6_PUNTA_DE_DEDOS",
    "Paso7_Circulares": "PASO_7_CIRCULARES",
}


def is_local_dashboard_origin(origin: str | None) -> bool:
    if not origin:
        return False
    try:
        parsed = urlsplit(origin)
        host = parsed.hostname
        return (
            parsed.scheme in {"http", "https"}
            and host is not None
            and MjpegFrameServer._is_loopback_host(host)
            and parsed.username is None
            and parsed.password is None
            and parsed.path in {"", "/"}
            and not parsed.query
            and not parsed.fragment
        )
    except ValueError:
        return False
REQUIRED_STEP_CLASSES = tuple(STEP_TO_BACKEND)
CLASSIFIER_TO_STEP = {index: REQUIRED_STEP_CLASSES[index - 1] for index in range(1, 7)}
STEP_INDEX_ALIASES = {
    f"paso_{index}": canonical
    for index, canonical in enumerate(REQUIRED_STEP_CLASSES, start=1)
}
OMS_ACTION_CLASSES = (
    "OMS_01_MOJAR_MANOS", "OMS_02_APLICAR_JABON", "OMS_03_FROTAR_PALMAS",
    "OMS_04_FROTAR_DORSOS", "OMS_05_FROTAR_ENTRE_DEDOS", "OMS_06_FROTAR_DORSO_DE_DEDOS",
    "OMS_07_FROTAR_PULGARES", "OMS_08_FROTAR_PUNTAS_DE_DEDOS", "OMS_09_ENJUAGAR_MANOS",
    "OMS_10_SECAR_TOALLA_DESECHABLE", "OMS_11_CERRAR_GRIFO_CON_TOALLA", "OMS_CONTACTO_RIESGO",
)
OMS_SPATIAL_EVIDENCE_MAX_AGE_SECONDS = 0.5
SOAP_REGIONS = (
    "PALMA_IZQUIERDA", "PALMA_DERECHA", "DORSO_IZQUIERDO", "DORSO_DERECHO",
    "INTERDIGITALES_IZQUIERDA", "INTERDIGITALES_DERECHA", "DORSO_DE_DEDOS_IZQUIERDO",
    "DORSO_DE_DEDOS_DERECHO", "PULGAR_IZQUIERDO", "PULGAR_DERECHO",
    "PUNTAS_DE_DEDOS_IZQUIERDA", "PUNTAS_DE_DEDOS_DERECHA",
)
SOAP_REGIONS_BY_ACTION = {
    "OMS_03_FROTAR_PALMAS": frozenset(SOAP_REGIONS[0:2]),
    "OMS_04_FROTAR_DORSOS": frozenset(SOAP_REGIONS[2:4]),
    "OMS_05_FROTAR_ENTRE_DEDOS": frozenset(SOAP_REGIONS[4:6]),
    "OMS_06_FROTAR_DORSO_DE_DEDOS": frozenset(SOAP_REGIONS[6:8]),
    "OMS_07_FROTAR_PULGARES": frozenset(SOAP_REGIONS[8:10]),
    "OMS_08_FROTAR_PUNTAS_DE_DEDOS": frozenset(SOAP_REGIONS[10:12]),
}
SOAP_CLASSES = {
    label: (region, state)
    for region in SOAP_REGIONS
    for label, state in (
        (f"ESPUMA_VISIBLE_{region}", "ESPUMA_VISIBLE"),
        (f"SIN_ESPUMA_VISIBLE_{region}", "SIN_ESPUMA_VISIBLE"),
    )
}
REQUIRED_OMS_CLASSES = (*OMS_ACTION_CLASSES, *SOAP_CLASSES)
RETRYABLE_HTTP_STATUSES = {408, 425, 429}
SESSION_UNAVAILABLE_TIMEOUT_SECONDS = 15.0
MIN_HAND_KEYPOINTS = 7
POSE_KEYPOINT_CONFIDENCE = 0.1
INTENTION_KEYPOINT_CONFIDENCE = 0.3
HAND_POSE_DEDUP_MIN_BOX_IOU = 0.45
HAND_POSE_DEDUP_MAX_CENTER_SHIFT_DIAGONALS = 0.12
HAND_POSE_DEDUP_MAX_MEDIAN_KEYPOINT_SHIFT_DIAGONALS = 0.075
HAND_RECOVERY_TILE_OVERLAP = 0.15


class PermanentDetectionRejection(Exception):
    """The Java API rejected a request that retrying cannot repair."""


def normalized_confidence(value: Any) -> float | None:
    """Return only finite model scores in the JSON/API confidence domain."""
    if isinstance(value, bool):
        return None
    try:
        confidence = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return confidence if math.isfinite(confidence) and 0.0 <= confidence <= 1.0 else None


def hand_presence_freshness_window(max_hand_age_seconds: float) -> float:
    """Keep producer/UI presence freshness no looser than Java's 500 ms gate."""
    if (isinstance(max_hand_age_seconds, bool)
        or not isinstance(max_hand_age_seconds, (int, float))
        or not math.isfinite(max_hand_age_seconds)
        or max_hand_age_seconds <= 0):
        return 0.0
    return min(max_hand_age_seconds, DEFAULT_HAND_PRESENCE_MAX_GAP_MS / 1000.0)


class ProducerEpochStream:
    """Process-lifetime transport identity; FFmpeg restarts do not replace it."""

    def __init__(self, producer_epoch: str):
        if not isinstance(producer_epoch, str) or not producer_epoch:
            raise ValueError("Java no devolvió un producerEpoch válido")
        self.producer_epoch = producer_epoch
        self.last_frame_sequence = -1
        self.last_control_sequence = -1
        self.last_presence_sequence = -1
        self._lock = threading.Lock()

    def reserve_frame(self, sequence: int) -> bool:
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
            return False
        with self._lock:
            if sequence <= self.last_frame_sequence or sequence < self.last_presence_sequence:
                return False
            self.last_frame_sequence = sequence
            return True

    def reserve_control(self, frame_watermark: int) -> int | None:
        if isinstance(frame_watermark, bool) or not isinstance(frame_watermark, int):
            return None
        with self._lock:
            if (frame_watermark < max(self.last_frame_sequence, self.last_presence_sequence)
                or frame_watermark < 0):
                return None
            self.last_frame_sequence = max(self.last_frame_sequence, frame_watermark)
            self.last_control_sequence += 1
            return self.last_control_sequence

    def reserve_presence(self, frame_watermark: int) -> int | None:
        """Sequence a presence pulse without consuming the detector frame."""
        if isinstance(frame_watermark, bool) or not isinstance(frame_watermark, int):
            return None
        with self._lock:
            if (frame_watermark < self.last_frame_sequence
                or frame_watermark <= self.last_presence_sequence or frame_watermark < 0):
                return None
            self.last_presence_sequence = frame_watermark
            self.last_control_sequence += 1
            return self.last_control_sequence


class CameraFrameSequence:
    """Monotonic within one Python process, including its FFmpeg reconnects."""

    def __init__(self):
        self.value = 0

    def next(self) -> int:
        self.value += 1
        return self.value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="YOLO26 + Cámara de Continuidad + backend Java")
    parser.add_argument("--check-camera", action="store_true",
                        help="Comprueba que el iPhone aparece en AVFoundation sin iniciar YOLO ni servicios")
    parser.add_argument("--check-model", action="store_true",
                        help="Valida las clases del peso YOLO sin iniciar cámara ni servicios")
    parser.add_argument("--check-hand-model", action="store_true",
                        help="Valida que el peso auxiliar sea pose de una mano con 21 puntos clave")
    parser.add_argument("--check-classifier-model", action="store_true",
                        help="Valida el clasificador auxiliar de nueve clases sin iniciar cámara ni servicios")
    parser.add_argument("--camera-index", type=int, default=None, help="Índice AVFoundation de la cámara del iPhone")
    parser.add_argument("--model", default=str(ROOT / "backend/models/handwash_yolo26n_7pasos.pt"))
    parser.add_argument("--hand-model", default=str(ROOT / "backend/models/yolo26s-pose-hands.pt"))
    parser.add_argument("--classifier-model", default=(
        os.getenv("HANDWASH_YOLO_CLASSIFIER_MODEL")
        or str(ROOT / "backend/models/handwash_who_yolo26m_cls.pt")))
    parser.add_argument("--classifier-fallback", dest="classifier_fallback", action="store_true",
                        help="Activa el respaldo experimental de pasos 1–6 basado en el clasificador derivado")
    parser.add_argument("--no-classifier-fallback", dest="classifier_fallback", action="store_false",
                        help=argparse.SUPPRESS)
    parser.add_argument("--classifier-confidence", type=float, default=0.75,
                        help="Confianza mínima del clasificador auxiliar (por defecto 0,75)")
    parser.add_argument("--classifier-challenge-below", type=float, default=0.80,
                        help="Consulta el clasificador si el detector da una clase por debajo de este umbral")
    parser.add_argument("--classifier-margin", type=float, default=0.10,
                        help="Ventaja mínima del clasificador para corregir/vetar un candidato débil")
    classifier_policy = parser.add_mutually_exclusive_group()
    classifier_policy.add_argument("--classifier-authoritative", dest="classifier_authoritative",
                                   action="store_true",
                                   help="Con dos poses frescas, prioriza clases fiables del clasificador de video")
    classifier_policy.add_argument("--classifier-guarded", dest="classifier_authoritative",
                                   action="store_false",
                                   help="Solo permite que el clasificador corrija candidatos débiles")
    hand_group = parser.add_mutually_exclusive_group()
    hand_group.add_argument("--hand-pose", dest="hand_pose", action="store_true",
                            help="Activa la detección YOLO de manos (activada por defecto)")
    hand_group.add_argument("--no-hand-pose", dest="hand_pose", action="store_false",
                            help="Desactiva la detección y analiza el cuadro completo (no recomendado)")
    classifier_fallback_env = os.getenv("HANDWASH_CLASSIFIER_FALLBACK")
    if classifier_fallback_env is None:
        classifier_fallback_default = True
    else:
        normalized_fallback = classifier_fallback_env.strip().casefold()
        if normalized_fallback in {"1", "true", "yes", "on"}:
            classifier_fallback_default = True
        elif normalized_fallback in {"0", "false", "no", "off"}:
            classifier_fallback_default = False
        else:
            parser.error(
                "HANDWASH_CLASSIFIER_FALLBACK debe ser 0/1, true/false, yes/no u on/off"
            )
    parser.set_defaults(
        hand_pose=True,
        classifier_fallback=classifier_fallback_default,
        classifier_authoritative=True,
    )
    parser.add_argument("--java-url", default="http://127.0.0.1:8080")
    parser.add_argument("--session-id", default=None)
    parser.add_argument("--pairing-code", default=os.getenv("HANDWASH_PAIRING_CODE"),
                        help="Código del dashboard para vincularse a su sesión")
    parser.add_argument("--protocol", default=os.getenv("HANDWASH_PROTOCOL", "CLINICO_QUIRURGICO"),
                        choices=("DOMESTICO", "CLINICO_QUIRURGICO"))
    parser.add_argument("--confidence", type=float, default=0.35,
                        help="Piso de confianza; el filtro temporal y Java confirman la fase")
    parser.add_argument("--imgsz", type=int, default=416, help="Tamaño de inferencia; 416 reduce carga sin perder la mano")
    parser.add_argument("--fallback-imgsz", type=int, default=640,
                        help="Resolución alta para recuperar un recorte; no infiere sin ambas manos")
    parser.add_argument("--step-recovery-interval", type=float, default=0.8,
                        help="Intervalo mínimo entre recuperaciones de pasos a alta resolución")
    parser.add_argument("--device", default="auto", help="auto, cpu, mps o cuda")
    parser.add_argument("--precision", choices=("fp16", "fp32"), default="fp16")
    parser.add_argument("--inference-fps", type=float, default=8.0,
                        help="FPS máximos del detector de pasos; reserva tiempo al localizador de manos")
    parser.add_argument("--event-heartbeat-ms", type=int,
                        default=int(os.getenv("HANDWASH_DETECTION_HEARTBEAT_MS", "200")),
                        help="Frecuencia de estados Java para el mismo paso (100–1500 ms); los cambios se envían inmediatamente")
    parser.add_argument("--hand-imgsz", type=int, default=DEFAULT_HAND_POSE_IMAGE_SIZE,
                        help="Resolución YOLO del detector de manos; 320 mantiene buena velocidad en CPU")
    parser.add_argument("--hand-recovery-imgsz", type=int, default=640,
                        help="Resolución alta de recuperación cuando la pasada principal no encuentra manos")
    parser.add_argument("--hand-recovery-interval", type=float, default=0.5,
                        help="Intervalo mínimo entre recuperaciones de manos a alta resolución")
    parser.add_argument("--hand-confidence", type=float, default=DEFAULT_HAND_POSE_CONFIDENCE,
                        help="Confianza de caja; se combina con al menos 7 keypoints visibles para conservar manos ocluidas")
    parser.add_argument("--hand-iou", type=float, default=0.90,
                        help="IoU NMS del pose de manos; alto conserva propuestas de manos que se solapan")
    parser.add_argument("--hand-max-det", type=int, default=16,
                        help="Propuestas máximas del pose antes de deduplicar manos geométricamente")
    parser.add_argument("--hand-crop-confidence", type=float,
                        default=float(os.getenv("HANDWASH_YOLO_HAND_CROP_CONFIDENCE", "0.15")),
                        help="Confianza mínima de caja para recortar pasos parciales cuando faltan keypoints visibles")
    parser.add_argument("--missing-detection-grace", type=float, default=0.9,
                        help="Segundos sin una fase estable antes de enviar Fondo y reiniciar el intento")
    parser.add_argument("--hand-inference-fps", type=float, default=6.0,
                        help="Frecuencia del detector de manos; la imagen y el paso siguen actualizándose entre detecciones")
    parser.add_argument("--hand-max-age", type=float, default=0.5,
                        help="Edad máxima desde la captura para aceptar una localización o un resultado de pasos")
    parser.add_argument("--hand-presence-warmup-ms", type=int, default=3000,
                        help="Milisegundos continuos con dos manos antes de inferir pasos; 0 solo para depuración")
    parser.add_argument("--hand-padding", type=float, default=0.45,
                        help="Margen alrededor de las manos para conservar el contexto del movimiento")
    parser.add_argument("--temporal-history", type=int, default=3, help="Fotogramas usados para estabilizar el paso")
    parser.add_argument("--temporal-min-votes", type=int, default=2, help="Votos necesarios para cambiar de paso")
    parser.add_argument("--stream-host", default=os.getenv("HANDWASH_CAMERA_STREAM_HOST", "127.0.0.1"))
    parser.add_argument("--stream-port", type=int, default=int(os.getenv("HANDWASH_CAMERA_STREAM_PORT", "8091")))
    parser.add_argument("--stream-width", type=int, default=720,
                        help="Ancho del MJPEG del dashboard; no reduce la resolución de captura ni de YOLO")
    parser.add_argument("--stream-fps", type=float, default=24.0,
                        help="Límite de publicación MJPEG (5–30); no altera la cadencia de inferencia")
    parser.add_argument("--stream-jpeg-quality", type=int, default=78,
                        help="Calidad JPEG del video del dashboard (50–95)")
    parser.add_argument("--camera-reconnect-timeout", type=float, default=45.0,
                        help="Segundos máximos para recuperar el iPhone tras un corte de video")
    parser.add_argument("--camera-retry-interval", type=float, default=2.0,
                        help="Espera entre reintentos de abrir la cámara de Continuidad")
    parser.add_argument("--native-preview", action="store_true",
                        help="Abre además una ventana ffplay; el dashboard muestra el video por defecto")
    args = parser.parse_args()
    if not 0 <= args.hand_presence_warmup_ms <= 10_000:
        parser.error("--hand-presence-warmup-ms debe estar entre 0 y 10000")
    # An explicit emergency-off environment setting cannot be undone by a CLI flag.
    if classifier_fallback_env is not None and not classifier_fallback_default:
        args.classifier_fallback = False
    return args


class MjpegFrameServer:
    """Serve the most recent annotated frame to the local dashboard."""

    def __init__(self, host: str, port: int, output_width: int = 720,
                 jpeg_quality: int = 78, max_clients: int = DEFAULT_MJPEG_MAX_CLIENTS,
                 client_write_timeout_seconds: float = DEFAULT_MJPEG_CLIENT_TIMEOUT_SECONDS):
        if output_width < 320 or not 50 <= jpeg_quality <= 95:
            raise ValueError("La salida MJPEG requiere ancho >=320 y calidad JPEG entre 50 y 95")
        if not 1 <= max_clients <= 8:
            raise ValueError("El stream MJPEG permite entre 1 y 8 clientes simultáneos")
        if (not math.isfinite(client_write_timeout_seconds)
            or not 0.1 <= client_write_timeout_seconds <= 30.0):
            raise ValueError("El timeout de escritura MJPEG debe estar entre 0.1 y 30 segundos")
        if not self._is_loopback_host(host):
            raise ValueError("El stream MJPEG solo puede enlazarse a loopback en esta estación local")
        self._output_width = output_width
        self._jpeg_quality = jpeg_quality
        self._max_clients = max_clients
        self._client_write_timeout_seconds = client_write_timeout_seconds
        self._condition = threading.Condition()
        self._jpeg: bytes | None = None
        self._sequence = 0
        self._clients = 0
        self._camera_connected = False
        self._session_id: str | None = None
        self._hand_presence: dict[str, Any] | None = None
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def setup(self) -> None:
                # Bound both slow header readers and blocked MJPEG socket writes.
                self.request.settimeout(owner._client_write_timeout_seconds)
                super().setup()

            def do_GET(self) -> None:
                request_url = urlsplit(self.path)
                path = request_url.path
                if path == "/health":
                    origin = self.headers.get("Origin")
                    with owner._condition:
                        health = {
                            "status": "ok",
                            "camera": "connected" if owner._camera_connected else "reconnecting",
                            "sessionId": owner._session_id,
                            "stream": "/video.mjpg",
                            "handPresence": owner._current_hand_presence_locked(),
                        }
                    body = json.dumps(health).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", str(len(body)))
                    if is_local_dashboard_origin(origin):
                        self.send_header("Access-Control-Allow-Origin", origin)
                        self.send_header("Vary", "Origin")
                    self.end_headers()
                    self.wfile.write(body)
                    return
                if path != "/video.mjpg":
                    self.send_error(404)
                    return

                requested_sessions = parse_qs(request_url.query).get("sessionId", [])
                with owner._condition:
                    session_id = owner._session_id
                if (session_id is None or len(requested_sessions) != 1
                    or requested_sessions[0] != session_id):
                    body = json.dumps({"error": "SESSION_MISMATCH"}).encode("utf-8")
                    self.send_response(409)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return

                with owner._condition:
                    at_capacity = owner._clients >= owner._max_clients
                    if not at_capacity:
                        owner._clients += 1
                if at_capacity:
                    body = json.dumps({"error": "STREAM_CAPACITY_REACHED"}).encode("utf-8")
                    try:
                        self.send_response(503)
                        self.send_header("Retry-After", "2")
                        self.send_header("Content-Type", "application/json")
                        self.send_header("Cache-Control", "no-store")
                        self.send_header("Content-Length", str(len(body)))
                        self.end_headers()
                        self.wfile.write(body)
                    except OSError:
                        pass
                    return
                try:
                    self.send_response(200)
                    self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
                    self.send_header("Pragma", "no-cache")
                    self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                    self.end_headers()
                    last_sequence = -1
                    while True:
                        with owner._condition:
                            owner._condition.wait_for(
                                lambda: owner._sequence != last_sequence,
                                timeout=2.0,
                            )
                            if owner._sequence == last_sequence or owner._jpeg is None:
                                continue
                            jpeg = owner._jpeg
                            last_sequence = owner._sequence
                        self.wfile.write(
                            b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                            + str(len(jpeg)).encode("ascii")
                            + b"\r\n\r\n"
                            + jpeg
                            + b"\r\n"
                        )
                        self.wfile.flush()
                except OSError:
                    return
                finally:
                    with owner._condition:
                        owner._clients = max(0, owner._clients - 1)
                        if owner._clients == 0:
                            owner._jpeg = None

            def log_message(self, _format: str, *_args: object) -> None:
                return

        self._server = ThreadingHTTPServer((host, port), Handler)
        self._server.daemon_threads = True
        self._thread = threading.Thread(target=self._server.serve_forever,
                                        name="dashboard-mjpeg", daemon=True)
        self._started = False

    @staticmethod
    def _is_loopback_host(host: str) -> bool:
        if host.lower() == "localhost":
            return True
        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            return False

    @property
    def address(self) -> tuple[str, int]:
        host, port = self._server.server_address[:2]
        return str(host), int(port)

    def start(self) -> None:
        self._thread.start()
        self._started = True

    def set_camera_connected(self, connected: bool) -> None:
        with self._condition:
            self._camera_connected = connected

    def set_hand_presence(self, presence: dict[str, Any] | None) -> None:
        if presence is None:
            snapshot = None
        else:
            hands = presence.get("handsVisible")
            elapsed = presence.get("warmupElapsedMs")
            required = presence.get("warmupRequiredMs")
            if (type(hands) is not int or not 0 <= hands <= 2
                or type(elapsed) is not int or elapsed < 0
                or type(required) is not int or not 0 <= required <= 10_000
                or type(presence.get("warmupComplete")) is not bool
                or type(presence.get("stepsEnabled")) is not bool):
                raise ValueError("Estado de presencia de manos inválido")
            snapshot = {
                "handsVisible": hands,
                "warmupElapsedMs": min(elapsed, required),
                "warmupRequiredMs": required,
                "warmupComplete": presence["warmupComplete"],
                "stepsEnabled": presence["stepsEnabled"],
                "_updatedAt": time.monotonic(),
            }
        with self._condition:
            self._hand_presence = snapshot

    def _current_hand_presence_locked(self) -> dict[str, Any] | None:
        presence = self._hand_presence
        if presence is None:
            return None
        age = time.monotonic() - presence["_updatedAt"]
        if (not self._camera_connected or age < 0
            or age > DEFAULT_HAND_PRESENCE_MAX_GAP_MS / 1000.0):
            return {
                "handsVisible": 0,
                "warmupElapsedMs": 0,
                "warmupRequiredMs": presence["warmupRequiredMs"],
                "warmupComplete": presence["warmupComplete"],
                "stepsEnabled": False,
            }
        return {key: value for key, value in presence.items() if not key.startswith("_")}

    def set_session_id(self, session_id: str) -> None:
        """Bind this single-camera MJPEG process to exactly one Java session."""
        if not session_id or not session_id.strip():
            raise ValueError("El stream requiere un sessionId no vacío")
        with self._condition:
            if self._session_id not in (None, session_id):
                raise RuntimeError("El stream MJPEG ya está vinculado a otra sesión")
            self._session_id = session_id

    @property
    def camera_status(self) -> str:
        with self._condition:
            return "connected" if self._camera_connected else "reconnecting"

    def publish(self, frame: np.ndarray) -> bool:
        with self._condition:
            if self._clients == 0:
                return True
        height, width = frame.shape[:2]
        output_width = min(self._output_width, width)
        if output_width < width:
            output_height = max(1, round(height * output_width / width))
            frame = cv2.resize(frame, (output_width, output_height),
                               interpolation=cv2.INTER_AREA)
        encoded, buffer = cv2.imencode(
            ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self._jpeg_quality]
        )
        if not encoded:
            return False
        with self._condition:
            if self._clients == 0:
                return True
            self._jpeg = buffer.tobytes()
            self._sequence += 1
            self._condition.notify_all()
        return True

    def close(self) -> None:
        if self._started:
            self._server.shutdown()
        self._server.server_close()


def avfoundation_listing() -> str:
    try:
        return subprocess.run(
            ["ffmpeg", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
            capture_output=True,
            text=True,
            timeout=5,
        ).stderr
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("AVFoundation tardó demasiado en enumerar las cámaras") from error


def continuity_camera_index() -> int:
    listing = avfoundation_listing()
    video_listing = listing.split("AVFoundation video devices:", 1)[-1].split(
        "AVFoundation audio devices:", 1
    )[0]
    devices = re.findall(r"\[(\d+)\]\s+(.+)", video_listing)
    for index, name in devices:
        if re.search(r"iphone|continuity|continuidad", name, re.IGNORECASE):
            return int(index)
    available = ", ".join(f"{index}: {name}" for index, name in devices)
    raise RuntimeError(
        "Cámara de Continuidad no está disponible. Cámaras detectadas: "
        f"{available or 'ninguna'}. Activa Cámara de Continuidad en el iPhone."
    )


def camera_name(camera_index: int) -> str:
    listing = avfoundation_listing()
    video_listing = listing.split("AVFoundation video devices:", 1)[-1].split(
        "AVFoundation audio devices:", 1
    )[0]
    devices = dict((int(index), name) for index, name in re.findall(r"\[(\d+)\]\s+(.+)", video_listing))
    return devices.get(camera_index, "")


def select_iphone_camera(camera_index: int | None) -> tuple[int, str]:
    selected_index = camera_index if camera_index is not None else continuity_camera_index()
    selected_name = camera_name(selected_index)
    if not re.search(r"iphone|continuity|continuidad", selected_name, re.IGNORECASE):
        raise RuntimeError(
            f"El índice {selected_index} corresponde a '{selected_name or 'desconocido'}', no al iPhone. "
            "Activa Cámara de Continuidad y vuelve a ejecutar el visor."
        )
    return selected_index, selected_name


def start_camera_process(camera_index: int, width: int, height: int) -> subprocess.Popen:
    """Open the currently enumerated iPhone only; no desktop/webcam fallback."""
    return subprocess.Popen(
        [
            "ffmpeg", "-loglevel", "error", "-f", "avfoundation", "-framerate", "30",
            "-video_size", "1280x720", "-pixel_format", "uyvy422", "-i", str(camera_index),
            "-vf", f"scale={width}:{height}",
            "-f", "rawvideo", "-pix_fmt", "bgr24", "pipe:1",
        ],
        stdout=subprocess.PIPE,
        stderr=None,
    )


def reopen_iphone_camera(width: int, height: int) -> tuple[int, str, subprocess.Popen]:
    """Re-enumerate Continuity Camera; its AVFoundation index may change on reconnect."""
    camera_index, camera_name = select_iphone_camera(None)
    return camera_index, camera_name, start_camera_process(camera_index, width, height)


def stop_camera_process(process: subprocess.Popen | None) -> None:
    if process is None:
        return
    if process.poll() is None:
        process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
    if process.stdout is not None:
        process.stdout.close()


def create_session(java_url: str, protocol: str) -> tuple[str, str]:
    response = HTTP_SESSION.post(
        f"{java_url}/api/v1/session",
        json={"protocolo": protocol, "producerProtocolVersion": "2"}, timeout=5
    )
    response.raise_for_status()
    created = response.json()
    print(f"Código para vincular el dashboard: {created['pairingCode']}", flush=True)
    return created["sessionId"], created["accessToken"]


def pair_session(java_url: str, code: str) -> tuple[str, str]:
    response = HTTP_SESSION.post(
        f"{java_url}/api/v1/auth/login",
        json={"code": code, "producerProtocolVersion": "2"}, timeout=5
    )
    response.raise_for_status()
    paired = response.json()
    return paired["sessionId"], paired["accessToken"]


def register_producer_epoch(java_url: str, session_id: str, access_token: str) -> str:
    response = HTTP_SESSION.post(
        f"{java_url}/api/v1/session/{session_id}/producer-epoch",
        json={},
        headers={"X-Session-Token": access_token},
        timeout=5,
    )
    response.raise_for_status()
    registered = response.json()
    if not isinstance(registered, dict):
        raise RuntimeError("Java devolvió una respuesta de registro de productor inválida")
    epoch = registered.get("producerEpoch")
    if registered.get("protocolVersion") != 2 or not isinstance(epoch, str) or not epoch:
        raise RuntimeError("Java no confirmó el registro del productor v2")
    return epoch


def monitor_session(
    java_url: str,
    session_id: str,
    access_token: str,
    stop: threading.Event,
    session_ended: threading.Event,
    session_started: threading.Event,
) -> None:
    """Mirror Java's accepted-start state and stop capture for terminal sessions."""
    last_warning_at = 0.0
    unavailable_since: float | None = None

    def backend_unavailable(reason: str) -> bool:
        nonlocal last_warning_at, unavailable_since
        now = time.monotonic()
        if unavailable_since is None:
            unavailable_since = now
        if now - last_warning_at >= 30.0 or last_warning_at == 0.0:
            print(f"Aviso: no se pudo comprobar la sesión Java ({reason}); se reintentará.", flush=True)
            last_warning_at = now
        if now - unavailable_since >= SESSION_UNAVAILABLE_TIMEOUT_SECONDS:
            print(
                f"Java lleva {SESSION_UNAVAILABLE_TIMEOUT_SECONDS:g} segundos inaccesible; "
                "se cierra la cámara por seguridad.",
                flush=True,
            )
            session_ended.set()
            return True
        return False

    while not stop.wait(2.0):
        try:
            response = requests.get(
                f"{java_url}/api/v1/session/{session_id}",
                headers={"X-Session-Token": access_token},
                timeout=(0.5, 1.5),
            )
        except requests.RequestException as exc:
            if backend_unavailable(str(exc)):
                return
            continue

        if response.status_code in {401, 404} or (
            400 <= response.status_code < 500
            and response.status_code not in RETRYABLE_HTTP_STATUSES
        ):
            print(
                f"Java rechazó la sesión con HTTP {response.status_code}; se cierra la cámara local.",
                flush=True,
            )
            session_ended.set()
            return
        if not response.ok:
            if backend_unavailable(f"HTTP {response.status_code}"):
                return
            continue

        try:
            payload = response.json()
        except ValueError:
            if backend_unavailable("respuesta JSON inválida"):
                return
            continue
        if not isinstance(payload, dict) or not isinstance(payload.get("estado"), str):
            if backend_unavailable("respuesta de sesión incompleta"):
                return
            continue
        unavailable_since = None
        last_warning_at = 0.0
        state = payload["estado"]
        if state == "EN_PROGRESO":
            session_started.set()
        if state in {"COMPLETADA", "EXPIRADA"}:
            print(f"La sesión Java terminó ({state}); se cierra la cámara local.", flush=True)
            session_ended.set()
            return


def send_detection(java_url: str, session_id: str, access_token: str,
                   class_name: str, confidence: float,
                   soap_evidence: dict[str, dict[str, Any]] | None = None,
                   motion_evidence: dict[str, Any] | None = None,
                   producer_epoch: str | None = None,
                   frame_sequence: int | None = None,
                   frame_captured_at: float | None = None,
                   event_type: str = "DETECTION",
                   control_sequence: int | None = None,
                   frame_watermark: int | None = None,
                   presence_hands_visible: int | None = None,
                   require_accepted_ack: bool = True) -> bool:
    confidence = normalized_confidence(confidence)
    if confidence is None:
        # Never let NaN/Infinity or an out-of-range model score become invalid
        # JSON that Java treats as a permanent producer failure.
        return False
    if motion_evidence is not None and (
        not isinstance(motion_evidence, dict)
        or type(motion_evidence.get("secuencia")) is not int
        or motion_evidence["secuencia"] < 0
        or (frame_sequence is not None and (
            type(frame_sequence) is not int
            or motion_evidence["secuencia"] != frame_sequence
        ))
    ):
        # bool is an int subclass in Python, but Jackson cannot deserialize it
        # as the Java Long sequence. Reject locally instead of killing the
        # camera sender on a permanent HTTP 400.
        return False

    if event_type == "PRESENCE":
        if (producer_epoch is None or class_name != "PRESENCIA_MANOS"
            or frame_sequence is not None or type(control_sequence) is not int
            or control_sequence < 0 or type(frame_watermark) is not int
            or frame_watermark < 0 or motion_evidence is not None or soap_evidence
            or isinstance(presence_hands_visible, bool)
            or not isinstance(presence_hands_visible, int)
            or presence_hands_visible not in (0, 1, 2)):
            return False
        detected_class = "PRESENCIA_MANOS"
    else:
        step = STEP_TO_BACKEND.get(class_name)
        if class_name == "Fondo":
            detected_class = "FONDO"
        elif class_name == "OMS_SIN_EVIDENCIA":
            detected_class = class_name
        elif step is not None:
            detected_class = step
        elif class_name in OMS_ACTION_CLASSES:
            detected_class = class_name
        else:
            return False

    # A detected contamination-contact event is a fail-closed safety signal,
    # not a wash phase. Preserve it even when occlusion prevents bilateral pose;
    # Java records the risk and restarts the OMS attempt without requiring pose.
    requires_spatial_evidence = (
        class_name in OMS_ACTION_CLASSES and class_name != "OMS_CONTACTO_RIESGO"
    )
    if requires_spatial_evidence and not oms_spatial_evidence_is_valid(
        motion_evidence, frame_sequence, frame_captured_at,
        OMS_SPATIAL_EVIDENCE_MAX_AGE_SECONDS,
    ):
        # Do not enqueue a model label that Java must reject as non-accreditable.
        # The camera loop will publish OMS_SIN_EVIDENCIA after its normal grace period.
        return False

    movement = None
    if motion_evidence is not None:
        if (frame_sequence is not None
            and motion_evidence.get("secuencia") != frame_sequence):
            return False
        movement = {key: value for key, value in motion_evidence.items() if not key.startswith("_")}
        # Include time spent in the bounded sender queue and retries. A stale
        # observation must never regain freshness when HTTP recovers.
        movement["antiguedadMs"] = min(60_000, max(0, int(
            (time.monotonic() - motion_evidence["_captured_at"]) * 1000)))
    soap_evidence = soap_evidence or {}
    soap_sequence = None
    if soap_evidence:
        # frameSequence is serialized only in the v2 envelope. A legacy caller
        # must instead bind the foam result to the sequence on its movement pose.
        soap_sequence = frame_sequence if producer_epoch is not None else None
        if soap_sequence is None and motion_evidence is not None:
            soap_sequence = motion_evidence.get("secuencia")
        if (isinstance(soap_sequence, bool) or not isinstance(soap_sequence, int)
            or soap_sequence < 0):
            return False
    payload = {
        "sessionId": session_id,
        "claseDetectada": detected_class,
        "confianza": confidence,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "evidenciaJabon": soap_evidence,
        "evidenciaMovimiento": movement,
    }
    if soap_sequence is not None:
        payload["evidenciaJabonSecuencia"] = soap_sequence
    if producer_epoch is not None:
        if not isinstance(producer_epoch, str) or not producer_epoch:
            raise ValueError("producer_epoch debe ser un identificador no vacío")
        captured_at = frame_captured_at
        if motion_evidence is not None:
            captured_at = motion_evidence.get("_captured_at", captured_at)
        capture_age_ms = None
        if isinstance(captured_at, (int, float)) and math.isfinite(captured_at):
            capture_age_ms = max(0, int((time.monotonic() - float(captured_at)) * 1000))
        payload.update({"producerEpoch": producer_epoch, "captureAgeMs": capture_age_ms})
        if event_type == "CONTROL":
            if (control_sequence is None or frame_watermark is None or movement is not None
                or soap_evidence or presence_hands_visible is not None):
                raise ValueError("Un evento CONTROL requiere controlSequence y frameWatermark, sin evidencia de frame")
            payload.update({
                "eventType": "CONTROL",
                "controlSequence": control_sequence,
                "frameWatermark": frame_watermark,
            })
        elif event_type == "PRESENCE":
            if (control_sequence is None or frame_watermark is None
                or frame_sequence is not None or movement is not None or soap_evidence
                or presence_hands_visible not in (0, 1, 2)
                or isinstance(presence_hands_visible, bool)):
                raise ValueError("Un evento PRESENCE requiere secuencia, watermark y 0–2 manos, sin evidencia de paso")
            if not isinstance(frame_captured_at, (int, float)) or not math.isfinite(frame_captured_at):
                return False
            payload.update({
                "eventType": "PRESENCE",
                "controlSequence": control_sequence,
                "frameWatermark": frame_watermark,
                "presenceHandsVisible": presence_hands_visible,
            })
        else:
            if event_type != "DETECTION" or frame_sequence is None or presence_hands_visible is not None:
                raise ValueError("Una detección v2 requiere eventType DETECTION y frameSequence")
            if isinstance(frame_sequence, bool) or not isinstance(frame_sequence, int) or frame_sequence < 0:
                raise ValueError("frameSequence debe ser un entero no negativo")
            payload.update({"eventType": "DETECTION", "frameSequence": frame_sequence})

    try:
        response = HTTP_SESSION.post(
            f"{java_url}/api/v1/deteccion",
            json=payload,
            headers={"X-Session-Token": access_token},
            timeout=(0.25, 0.5),
        )
        response.raise_for_status()
        rejection_reason = getattr(response, "headers", {}).get(
            "X-Producer-Rejection-Reason")
        if rejection_reason in {
            "VERSIONED_FIELDS_ON_LEGACY_SESSION",
            "EPOCH_REQUIRED",
            "EPOCH_NOT_REGISTERED",
            "EPOCH_MISMATCH",
            "NON_CANONICAL_CLASS",
        }:
            print("Java rechazó la identidad o taxonomía del productor; se detiene la publicación.", flush=True)
            raise PermanentDetectionRejection(rejection_reason)
        # HTTP 200 also covers detections filtered by Java's confidence gate.
        # The default helper result remains acceptance-aware for existing callers.
        # The retry worker asks only whether HTTP delivered the envelope: a 200
        # filtered ACK (notably a duplicate after a lost response) is terminal.
        result = response.json()
        if not require_accepted_ack:
            return True
        return not (isinstance(result, dict) and result.get("accepted") is False)
    except requests.HTTPError as exc:
        response = exc.response
        status = response.status_code if response is not None else None
        if (status is not None and 400 <= status < 500
            and status not in RETRYABLE_HTTP_STATUSES):
            print(
                f"Java rechazó la detección con HTTP {status}; se detiene el envío de esta sesión.",
                flush=True,
            )
            raise PermanentDetectionRejection(status) from exc
        print(f"Aviso: backend Java temporalmente no disponible ({exc})", flush=True)
        return False
    except requests.RequestException as exc:
        # The camera/UI must remain real-time if Java briefly restarts.
        print(f"Aviso: backend Java no disponible ({exc})", flush=True)
        return False


def motion_evidence_matches_frame(evidence: dict[str, Any] | None,
                                 frame_sequence: int, frame_captured_at: float,
                                 max_age: float) -> bool:
    """Only pair movement metadata with its exact classified camera observation."""
    if (not isinstance(evidence, dict)
        or type(evidence.get("secuencia")) is not int
        or type(frame_sequence) is not int):
        return False
    if evidence["secuencia"] != frame_sequence:
        return False
    captured_at = evidence.get("_captured_at")
    if not isinstance(captured_at, (int, float)) or not math.isfinite(captured_at):
        return False
    age = frame_captured_at - float(captured_at)
    return -0.02 <= age <= max_age


def oms_spatial_evidence_is_valid(evidence: dict[str, Any] | None,
                                  frame_sequence: int | None,
                                  frame_captured_at: float | None,
                                  max_age: float,
                                  now: float | None = None) -> bool:
    """Require fresh, measured bilateral pose for every OMS model action."""
    if (not isinstance(frame_sequence, int) or isinstance(frame_sequence, bool)
        or not isinstance(frame_captured_at, (int, float))
        or not math.isfinite(frame_captured_at)
        or not isinstance(evidence, dict)
        or evidence.get("manosVisibles") != 2
        or evidence.get("medicionValida") is not True):
        return False
    effective_max_age = min(max_age, OMS_SPATIAL_EVIDENCE_MAX_AGE_SECONDS)
    if not motion_evidence_matches_frame(
        evidence, frame_sequence, float(frame_captured_at), effective_max_age
    ):
        return False
    captured_at = evidence.get("_captured_at")
    current_time = time.monotonic() if now is None else now
    age = current_time - float(captured_at)
    return 0 <= age <= effective_max_age


def detection_sender(
    pending: Queue,
    stop: threading.Event,
    java_url: str,
    session_id: str,
    access_token: str,
    session_ended: threading.Event | None = None,
    producer_stream: ProducerEpochStream | None = None,
) -> None:
    """Send detections off the video thread; bounded queue favors fresh state."""
    invalid_confidence_reported = False
    while not stop.is_set():
        try:
            detection = pending.get(timeout=0.2)
        except Empty:
            continue
        try:
            if detection is None:
                return
            if len(detection) < 2 or normalized_confidence(detection[1]) is None:
                if not invalid_confidence_reported:
                    print("Aviso: se descartó una salida YOLO con confianza inválida.", flush=True)
                    invalid_confidence_reported = True
                continue
            is_presence = len(detection) >= 10 and detection[6] == "PRESENCE"
            presence_age = None
            if is_presence:
                captured_at = detection[5]
                if (isinstance(captured_at, bool)
                    or not isinstance(captured_at, (int, float))
                    or not math.isfinite(captured_at)):
                    continue
                presence_age = time.monotonic() - captured_at
                if not 0 <= presence_age <= DEFAULT_HAND_PRESENCE_MAX_GAP_MS / 1000.0:
                    # Never refresh a queued pose by sending it after its freshness window.
                    continue
            presence_loss = (
                is_presence and type(detection[9]) is int and detection[9] < 2
                and presence_age is not None
            )
            critical = detection[0] in {
                "OMS_CONTACTO_RIESGO", "OMS_SIN_EVIDENCIA", "Fondo"
            } or presence_loss
            retry_delay = 0.5
            while not stop.is_set():
                try:
                    if producer_stream is None:
                        delivered = send_detection(java_url, session_id, access_token, *detection)
                    elif len(detection) >= 9 and detection[6] == "CONTROL":
                        delivered = send_detection(
                            java_url, session_id, access_token,
                            detection[0], detection[1], detection[2], detection[3],
                            producer_epoch=producer_stream.producer_epoch,
                            frame_captured_at=detection[5],
                            event_type="CONTROL",
                            control_sequence=detection[7],
                            frame_watermark=detection[8],
                            require_accepted_ack=False,
                        )
                    elif len(detection) >= 10 and detection[6] == "PRESENCE":
                        delivered = send_detection(
                            java_url, session_id, access_token,
                            detection[0], detection[1], detection[2], detection[3],
                            producer_epoch=producer_stream.producer_epoch,
                            frame_captured_at=detection[5],
                            event_type="PRESENCE",
                            control_sequence=detection[7],
                            frame_watermark=detection[8],
                            presence_hands_visible=detection[9],
                            require_accepted_ack=False,
                        )
                    else:
                        delivered = send_detection(
                            java_url, session_id, access_token,
                            detection[0], detection[1], detection[2], detection[3],
                            producer_epoch=producer_stream.producer_epoch,
                            frame_sequence=detection[4],
                            frame_captured_at=detection[5],
                            event_type="DETECTION",
                            require_accepted_ack=False,
                        )
                except PermanentDetectionRejection:
                    if session_ended is not None:
                        session_ended.set()
                    return
                if delivered:
                    break
                # A delayed hand-loss pulse is no longer useful and must not
                # keep the sender busy retrying an observation Java will reject.
                if not critical or (presence_loss
                    and (time.monotonic() - detection[5]) > 0.5):
                    break
                # Never silently discard a reset/risk event after a transient
                # Java outage. Backoff caps log/network pressure while keeping
                # the signal until Java recovers; a duplicate reset is safe.
                stop.wait(retry_delay)
                retry_delay = min(retry_delay * 2.0, 5.0)
        finally:
            pending.task_done()


def enqueue_latest_detection(
    pending: Queue,
    detection: tuple,
) -> None:
    with _PENDING_ENQUEUE_LOCK:
        buffered = []
        while True:
            try:
                buffered.append(pending.get_nowait())
                pending.task_done()
            except Empty:
                break
        buffered.append(detection)

        def priority(item: tuple) -> int:
            event_type = item[6] if len(item) > 6 else "DETECTION"
            if item[0] == "OMS_CONTACTO_RIESGO":
                return 4
            if item[0] in {"OMS_SIN_EVIDENCIA", "Fondo"} and event_type == "CONTROL":
                return 3
            if (event_type == "PRESENCE" and len(item) >= 10
                and type(item[9]) is int and item[9] < 2):
                return 2
            if event_type == "DETECTION":
                return 1
            if event_type == "PRESENCE":
                return 0
            return 3 if item[0] in {"OMS_SIN_EVIDENCIA", "Fondo"} else 1

        # Coalesce independently by event class. A hand-presence pulse cannot
        # evict a step, while risk/loss signals remain higher priority.
        newest_by_priority = {}
        for item in buffered:
            newest_by_priority[priority(item)] = item
        selected = [newest_by_priority[key]
                    for key in sorted(newest_by_priority, reverse=True)[:pending.maxsize]]

        def source_sequence(item: tuple) -> int:
            event_type = item[6] if len(item) > 6 else "DETECTION"
            if event_type in {"CONTROL", "PRESENCE"}:
                return item[8]
            return item[4]

        def source_order(item: tuple) -> int:
            event_type = item[6] if len(item) > 6 else "DETECTION"
            return {"CONTROL": 0, "PRESENCE": 1, "DETECTION": 2}.get(event_type, 3)

        if selected and all(len(item) >= 7 for item in selected):
            selected.sort(key=lambda item: (source_sequence(item), source_order(item)))
        for item in selected:
            try:
                pending.put_nowait(item)
            except Full:
                break


_PENDING_ENQUEUE_LOCK = threading.Lock()


def enqueue_presence_observation(
    pending: Queue,
    producer_stream: ProducerEpochStream,
    hands_visible: int,
    frame_sequence: int,
    frame_captured_at: float,
) -> bool:
    if type(hands_visible) is not int or hands_visible not in (0, 1, 2):
        return False
    control_sequence = producer_stream.reserve_presence(frame_sequence)
    if control_sequence is None:
        return False
    enqueue_latest_detection(pending, (
        "PRESENCIA_MANOS", 1.0, {}, None, None, frame_captured_at,
        "PRESENCE", control_sequence, frame_sequence, hands_visible,
    ))
    return True


def should_publish_visibility_loss(
    last_sent_class: str | None, last_stable_observed_at: float,
    now: float, grace_seconds: float,
) -> bool:
    return (last_sent_class is not None
            and now - last_stable_observed_at >= grace_seconds)


def validate_step_model(model: YOLO, model_path: str) -> tuple[list[int], str]:
    """Accept canonical/known seven-step detector labels or a fully labeled OMS detector."""
    if model.task != "detect":
        raise RuntimeError(
            f"El peso de pasos '{model_path}' es tarea '{model.task}', pero se requiere 'detect'. "
            "No uses un peso OBB, pose o segmentación como clasificador de pasos."
        )
    raw_names = model.names or {}
    if isinstance(raw_names, dict):
        names = raw_names
    elif isinstance(raw_names, (list, tuple)):
        names = dict(enumerate(raw_names))
    else:
        raise RuntimeError(f"El peso '{model_path}' no declara un catálogo de clases válido.")
    class_ids = list(names)
    if (not names or any(type(class_id) is not int for class_id in class_ids)
        or sorted(class_ids) != list(range(len(class_ids)))):
        raise RuntimeError(
            f"El peso '{model_path}' debe tener IDs de clase enteros, únicos y contiguos desde cero."
        )
    labels = list(names.values())
    if (any(not isinstance(name, str) or not name.strip() for name in labels)
        or len({name.strip().casefold() for name in labels}) != len(labels)):
        raise RuntimeError(f"El peso '{model_path}' declara nombres de clase vacíos o duplicados.")
    available_names = set(names.values())
    canonical_names = {
        canonical_step_name(str(name))
        for name in available_names
    } - {None}
    oms_missing = [name for name in REQUIRED_OMS_CLASSES if name not in available_names]
    legacy_missing = [name for name in REQUIRED_STEP_CLASSES if name not in canonical_names]
    has_oms_labels = any(name.startswith("OMS_") or name.startswith("ESPUMA_VISIBLE_")
                         or name.startswith("SIN_ESPUMA_VISIBLE_") for name in available_names)
    if not oms_missing:
        if (len(names) != len(REQUIRED_OMS_CLASSES)
            or available_names != set(REQUIRED_OMS_CLASSES)
            or labels != list(REQUIRED_OMS_CLASSES)):
            raise RuntimeError(
                f"El peso OMS '{model_path}' debe contener exactamente las {len(REQUIRED_OMS_CLASSES)} "
                "clases aprobadas en el orden canónico del checkpoint; no se aceptan cambios de orden "
                "ni etiquetas adicionales."
            )
        selected_names = set(REQUIRED_OMS_CLASSES)
        mode = "PROTOCOLO_OMS"
    elif not legacy_missing and not has_oms_labels:
        mapped_steps = [canonical_step_name(str(name)) for name in available_names]
        mapped_steps = [step for step in mapped_steps if step is not None]
        unexpected_names = sorted(
            str(name) for name in available_names
            if canonical_step_name(str(name)) is None
            and str(name).strip().casefold() != "fondo"
        )
        duplicate_steps = sorted(
            step for step in set(mapped_steps) if mapped_steps.count(step) > 1
        )
        if (len(mapped_steps) != len(REQUIRED_STEP_CLASSES)
            or set(mapped_steps) != set(REQUIRED_STEP_CLASSES)
            or unexpected_names):
            raise RuntimeError(
                f"El detector parcial '{model_path}' debe contener exactamente una etiqueta "
                "por cada uno de los siete pasos y, opcionalmente, una clase Fondo; "
                f"no se aceptan alias duplicados ni clases extra. "
                f"Pasos duplicados: {duplicate_steps}; clases extra: {unexpected_names}."
            )
        selected_names = {
            name for name in available_names
            if canonical_step_name(str(name)) is not None
        }
        mode = "FRICCION_PARCIAL"
    else:
        missing = oms_missing if has_oms_labels else legacy_missing
        available = ", ".join(str(value) for value in names.values()) or "ninguna"
        raise RuntimeError(
            f"El peso '{model_path}' no corresponde a un modelo OMS completo ni al detector parcial: {missing}. "
            f"Etiquetas encontradas: {available}. Usa un detector con las siete etiquetas canónicas "
            "(o el alias secuencial paso_1...paso_7) o un detector con todas las clases de "
            "docs/REQUISITOS_MODELO_OMS.md."
        )
    return ([class_id for class_id, name in names.items() if name in selected_names], mode)


def verify_model_artifact(model_path: str | Path,
                          manifest_path: str | Path | None = None) -> str:
    """Fail closed when a runtime weight is missing or differs from its recorded SHA-256."""
    artifact = Path(model_path).expanduser().resolve()
    try:
        manifest_key = artifact.relative_to(ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise RuntimeError(
            f"El peso '{artifact}' está fuera del proyecto y no tiene procedencia verificable; "
            "regístralo en model-manifest.json antes de habilitarlo."
        ) from exc

    if not artifact.is_file():
        raise RuntimeError(f"No existe el peso YOLO requerido: {artifact}")

    manifest_file = Path(manifest_path or MODEL_MANIFEST_PATH).expanduser().resolve()
    try:
        if manifest_file.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("el manifiesto supera 2 MiB")
        manifest_bytes = manifest_file.read_bytes()
        if len(manifest_bytes) > 2 * 1024 * 1024:
            raise ValueError("el manifiesto supera 2 MiB")
        manifest = json.loads(
            manifest_bytes.decode("utf-8"), object_pairs_hook=_reject_duplicate_manifest_keys)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise RuntimeError(f"No se pudo leer el manifiesto de modelos '{manifest_file}': {exc}") from exc

    expected_hashes: list[str] = []
    pending = [manifest]
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            if value.get("path") == manifest_key and isinstance(value.get("sha256"), str):
                expected_hashes.append(value["sha256"].lower())
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)

    if len(expected_hashes) != 1:
        raise RuntimeError(
            f"El peso '{manifest_key}' debe tener exactamente una huella SHA-256 en "
            f"'{manifest_file.name}'; encontradas: {len(expected_hashes)}."
        )

    expected = expected_hashes[0]
    if re.fullmatch(r"[0-9a-f]{64}", expected) is None:
        raise RuntimeError(f"El SHA-256 registrado para '{manifest_key}' no tiene formato válido.")

    digest = hashlib.sha256()
    try:
        with artifact.open("rb") as model_file:
            for chunk in iter(lambda: model_file.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise RuntimeError(f"No se pudo leer el peso YOLO '{artifact}': {exc}") from exc

    actual = digest.hexdigest()
    if actual != expected:
        raise RuntimeError(
            f"La huella SHA-256 de '{manifest_key}' no coincide con model-manifest.json "
            f"(esperada {expected}, encontrada {actual}); no se iniciará YOLO."
        )
    return actual


def validate_active_step_manifest(
    model: YOLO, model_path: str | Path,
    manifest_path: str | Path | None = None,
) -> None:
    """Keep the active checkpoint's real class-ID order aligned with its signed mapping."""
    artifact = Path(model_path).expanduser().resolve()
    try:
        manifest_key = artifact.relative_to(Path(ROOT).resolve()).as_posix()
    except ValueError as exc:
        raise RuntimeError(
            f"El detector '{artifact}' está fuera del proyecto y no puede compararse "
            "con la taxonomía activa del manifiesto."
        ) from exc

    manifest_file = Path(manifest_path or MODEL_MANIFEST_PATH).expanduser().resolve()
    try:
        if manifest_file.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("el manifiesto supera 2 MiB")
        manifest_bytes = manifest_file.read_bytes()
        if len(manifest_bytes) > 2 * 1024 * 1024:
            raise ValueError("el manifiesto supera 2 MiB")
        manifest = json.loads(
            manifest_bytes.decode("utf-8"), object_pairs_hook=_reject_duplicate_manifest_keys)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise RuntimeError(f"No se pudo leer el manifiesto de modelos '{manifest_file}': {exc}") from exc

    active = manifest.get("active") if isinstance(manifest, dict) else None
    if not isinstance(active, dict) or active.get("path") != manifest_key:
        return

    raw_names = model.names or {}
    names = raw_names if isinstance(raw_names, dict) else dict(enumerate(raw_names))
    actual_names = [names[index] for index in range(len(names)) if index in names]
    declared_names = active.get("modelClassNames")
    if not isinstance(declared_names, list) or actual_names != declared_names:
        raise RuntimeError(
            f"Las clases/IDs cargados desde '{manifest_key}' no coinciden exactamente con "
            "active.modelClassNames; se cancela el arranque para evitar traducir un ID "
            "a un paso incorrecto."
        )

    declared_mapping = active.get("classNameMapping")
    canonical_mapping = {name: canonical_step_name(name) for name in actual_names}
    uses_aliases = any(
        canonical is not None and canonical.casefold() != name.casefold()
        for name, canonical in canonical_mapping.items()
    )
    if uses_aliases and not isinstance(declared_mapping, dict):
        raise RuntimeError(
            f"El detector '{manifest_key}' usa etiquetas ordinales pero no declara "
            "active.classNameMapping; no se puede validar su traducción a pasos."
        )
    if declared_mapping is not None and declared_mapping != canonical_mapping:
        raise RuntimeError(
            f"active.classNameMapping no coincide con la traducción canónica del productor "
            f"para '{manifest_key}'; se cancela el arranque."
        )
    backend_steps = [STEP_TO_BACKEND.get(canonical) for canonical in canonical_mapping.values()]
    if uses_aliases and (any(step is None for step in backend_steps)
                         or len(set(backend_steps)) != len(backend_steps)):
        raise RuntimeError(
            "La traducción activa no corresponde uno-a-uno con las clases que acepta Java."
        )


def canonical_step_name(name: str) -> str | None:
    """Normalize only the explicitly supported canonical and paso_1..paso_7 labels."""
    normalized = name.strip().casefold()
    for canonical in REQUIRED_STEP_CLASSES:
        if normalized == canonical.casefold():
            return canonical
    return STEP_INDEX_ALIASES.get(normalized)


def sequential_label_taxonomy_warning(model_names: Any) -> str | None:
    """Explain that generic ordinal labels are structural aliases, not verified semantics."""
    names = model_names if isinstance(model_names, dict) else dict(enumerate(model_names or []))
    if not any(str(name).strip().casefold() in STEP_INDEX_ALIASES for name in names.values()):
        return None
    return (
        "paso_1…paso_7 se mapean por orden a las clases del proyecto; "
        "este proceso no contrasta el data.yaml ni la rúbrica del entrenamiento, "
        "y no acredita el significado de las clases ni la precisión del detector."
    )


def validate_derived_classifier(model: YOLO, model_path: str) -> None:
    """Never confuse WHO faucet closure with the project's seventh friction step."""
    raw_names = model.names or {}
    names = raw_names if isinstance(raw_names, dict) else dict(enumerate(raw_names))
    if model.task != "classify" or names != DERIVED_CLASSIFIER_NAMES:
        raise RuntimeError(
            f"El clasificador auxiliar '{model_path}' debe ser 'classify' "
            "con las nueve clases derivadas de videos, en el orden esperado."
        )


def compatible_classifier_step(result, minimum_confidence: float = 0.75) -> tuple[str | None, float | None]:
    """Only six semantically matching motions can support the partial state machine."""
    if result is None or result.probs is None:
        return None, None
    class_id = int(result.probs.top1)
    confidence = float(result.probs.top1conf)
    if not math.isfinite(confidence) or confidence < minimum_confidence:
        return None, None
    return CLASSIFIER_TO_STEP.get(class_id), confidence if class_id in CLASSIFIER_TO_STEP else None


def derived_classifier_decision(result, minimum_confidence: float = 0.75) -> tuple[str, str | None, float | None]:
    """Separate six compatible motions, explicit negatives, and uncertain output."""
    if result is None or result.probs is None:
        return "ABSTAIN", None, None
    class_id = int(result.probs.top1)
    confidence = float(result.probs.top1conf)
    if not math.isfinite(confidence) or confidence < minimum_confidence:
        return "ABSTAIN", None, None
    if class_id in CLASSIFIER_TO_STEP:
        return "STEP", CLASSIFIER_TO_STEP[class_id], confidence
    if class_id in (0, 7, 8):
        return "NEGATIVE", None, confidence
    return "ABSTAIN", None, None


def arbitrate_uncertain_detection(
    raw_class: str | None,
    raw_confidence: float | None,
    classification,
    classifier_minimum: float = 0.75,
    detector_challenge_below: float = 0.80,
    classifier_margin: float = 0.10,
    classifier_authoritative: bool = False,
) -> tuple[str | None, float | None, str]:
    """Let the video-trained classifier challenge only weak partial-mode detections.

    Faucet closure and other non-step classes stay negative and never map to
    Paso7. The caller checks the final candidate against Fondo confidence.
    """
    decision, proposed_step, proposed_confidence = derived_classifier_decision(
        classification, classifier_minimum
    )
    if classifier_authoritative:
        if decision == "STEP" and proposed_step is not None and proposed_confidence is not None:
            return proposed_step, proposed_confidence, "classifier"
        if decision == "NEGATIVE":
            return None, None, "classifier_veto"
        return raw_class, raw_confidence, "detector"
    if raw_class is not None and (
        raw_confidence is None or raw_confidence >= detector_challenge_below
    ):
        return raw_class, raw_confidence, "detector"
    if decision == "STEP" and proposed_step is not None and proposed_confidence is not None:
        if raw_class == proposed_step:
            return proposed_step, max(raw_confidence or 0.0, proposed_confidence), "detector"
        if (raw_class is None
            or proposed_confidence >= (raw_confidence or 0.0) + classifier_margin):
            return proposed_step, proposed_confidence, "classifier"
    if (decision == "NEGATIVE" and raw_class is not None
        and proposed_confidence is not None
        and proposed_confidence >= (raw_confidence or 0.0) + classifier_margin):
        return None, None, "classifier_veto"
    return raw_class, raw_confidence, "detector"


def background_vetoes_detection(result, step_confidence: float | None) -> bool:
    """Veto a candidate only when Fondo is at least as confident as that step."""
    if result is None or result.boxes is None:
        return False
    background_scores = [
        score
        for box in result.boxes
        if str(result.names[int(box.cls.item())]).casefold() == "fondo"
        and (score := normalized_confidence(box.conf.item())) is not None
    ]
    if not background_scores:
        return False
    candidate_score = normalized_confidence(step_confidence)
    return candidate_score is not None and max(background_scores) >= candidate_score


def classifier_fallback_allowed(raw_class: str | None, mode: str,
                                spatial: dict[str, Any] | None,
                                frame_age: float, max_age: float,
                                hand_inference_queued: bool) -> bool:
    """Require fresh bilateral pose; Java separately guards measured start intent."""
    return (
        mode == "FRICCION_PARCIAL" and raw_class is None
        and spatial is not None and spatial.get("manosVisibles", 0) >= 2
        and 0 <= frame_age <= max_age and not hand_inference_queued
    )


def classifier_challenge_allowed(raw_class: str | None, raw_confidence: float | None,
                                 mode: str, spatial: dict[str, Any] | None,
                                 frame_age: float, max_age: float,
                                 hand_inference_queued: bool,
                                 challenge_below: float = 0.80,
                                 challenge_all: bool = False) -> bool:
    """Challenge an abstention or weak class only with fresh bilateral evidence."""
    uncertain = (challenge_all or raw_class is None or raw_confidence is None
                 or raw_confidence < challenge_below)
    return (
        uncertain and mode == "FRICCION_PARCIAL"
        and spatial is not None and spatial.get("manosVisibles", 0) >= 2
        and 0 <= frame_age <= max_age and not hand_inference_queued
    )


def validate_hand_model(model: YOLO, model_path: str) -> None:
    """Fail early if the auxiliary weight is not a 21-keypoint hand pose model."""
    if model.task != "pose":
        raise RuntimeError(
            f"El peso auxiliar de manos '{model_path}' es tarea '{model.task}', no 'pose'."
        )
    raw_names = model.names or {}
    names = raw_names if isinstance(raw_names, dict) else dict(enumerate(raw_names))
    if len(names) != 1 or next(iter(names.values()), "").lower() != "hand":
        raise RuntimeError(
            f"El peso auxiliar '{model_path}' debe tener la única clase 'hand'; "
            f"clases encontradas: {list(names.values())}."
        )
    model_config = getattr(getattr(model, "model", None), "yaml", {})
    keypoint_shape = model_config.get("kpt_shape") if isinstance(model_config, dict) else None
    if (not keypoint_shape or len(keypoint_shape) != 2
        or tuple(map(int, keypoint_shape)) != (21, 3)):
        raise RuntimeError(
            f"El peso auxiliar '{model_path}' debe exponer keypoints con forma [21, 3] "
            "(x, y y confianza); el detector de manos necesita el canal de visibilidad."
        )


def hand_pose_proposal_count(result) -> int:
    """Count raw pose boxes before keypoint validation and duplicate suppression."""
    boxes = getattr(result, "boxes", None) if result is not None else None
    return len(boxes) if boxes is not None else 0


def hand_pose_candidates(result, min_confidence: float,
                         keypoint_confidence: float,
                         max_hands: int = 2) -> list[tuple[float, tuple, np.ndarray]]:
    """Return distinct hand poses; overlapping duplicate predictions are not two hands."""
    if result is None or result.boxes is None or result.keypoints is None:
        return []
    keypoints = result.keypoints.data
    if hasattr(keypoints, "cpu"):
        keypoints = keypoints.cpu().numpy()
    candidates = []
    for index, box in enumerate(result.boxes):
        coordinates = box_coordinates(box)
        confidence = float(box.conf.item())
        pose = keypoints[index]
        if (coordinates is None or not math.isfinite(confidence)
            or confidence < min_confidence or not np.isfinite(pose).all()
            or int((pose[:, 2] >= keypoint_confidence).sum()) < MIN_HAND_KEYPOINTS):
            continue
        candidates.append((confidence, coordinates, pose.copy()))
    candidates.sort(key=lambda candidate: candidate[0], reverse=True)

    distinct = []
    for candidate in candidates:
        x1, y1, x2, y2 = candidate[1]
        candidate_area = max(0.0, x2 - x1) * max(0.0, y2 - y1)
        candidate_center = np.array([(x1 + x2) / 2.0, (y1 + y2) / 2.0])
        is_duplicate = False
        for accepted in distinct:
            ax1, ay1, ax2, ay2 = accepted[1]
            accepted_area = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
            intersection_width = max(0.0, min(x2, ax2) - max(x1, ax1))
            intersection_height = max(0.0, min(y2, ay2) - max(y1, ay1))
            intersection = intersection_width * intersection_height
            union = candidate_area + accepted_area - intersection
            overlap = intersection / union if union > 0 else 0.0
            accepted_center = np.array([(ax1 + ax2) / 2.0, (ay1 + ay2) / 2.0])
            diagonal = (
                math.hypot(x2 - x1, y2 - y1)
                + math.hypot(ax2 - ax1, ay2 - ay1)
            ) / 2.0
            if overlap < HAND_POSE_DEDUP_MIN_BOX_IOU or diagonal <= 0:
                continue
            shared = ((candidate[2][:, 2] >= keypoint_confidence)
                      & (accepted[2][:, 2] >= keypoint_confidence))
            if int(shared.sum()) < MIN_HAND_KEYPOINTS:
                continue
            joint_shift = np.linalg.norm(
                candidate[2][shared, :2] - accepted[2][shared, :2], axis=1
            )
            if (np.linalg.norm(candidate_center - accepted_center)
                <= HAND_POSE_DEDUP_MAX_CENTER_SHIFT_DIAGONALS * diagonal
                and float(np.median(joint_shift))
                <= HAND_POSE_DEDUP_MAX_MEDIAN_KEYPOINT_SHIFT_DIAGONALS * diagonal):
                is_duplicate = True
                break
        if not is_duplicate:
            distinct.append(candidate)
            if len(distinct) >= max(1, max_hands):
                break
    return distinct


def prefer_recovered_motion(recovered: dict[str, Any], primary: dict[str, Any]) -> bool:
    """Use a recovery only when its evidence quality improves the primary pose."""
    recovered_quality = (
        bool(recovered.get("medicionValida")),
        int(recovered.get("manosVisibles", 0)),
        int(recovered.get("_manosParaInicio", 0)),
    )
    primary_quality = (
        bool(primary.get("medicionValida")),
        int(primary.get("manosVisibles", 0)),
        int(primary.get("_manosParaInicio", 0)),
    )
    return recovered_quality > primary_quality


def prefer_recovered_localization(
    recovered: list[tuple[tuple[float, float, float, float], float]],
    primary: list[tuple[tuple[float, float, float, float], float]],
) -> bool:
    """Keep the primary boxes on ties; replace only when count/score improves."""
    recovered_quality = (len(recovered), sum(confidence for _, confidence in recovered))
    primary_quality = (len(primary), sum(confidence for _, confidence in primary))
    return recovered_quality > primary_quality


class HandMotionEstimator:
    """Compare adjacent usable hand snapshots without re-counting frame retries.

    Similarity alignment removes common translation/rotation/scale (camera
    motion). Residual articulation and relative hand motion remain. Matching
    both permutations avoids treating detection-order swaps as movement. A
    recovery inference for the same camera sequence is compared against the
    preceding sequence, not against the primary inference of its own frame.
    """
    def __init__(self):
        self.previous = None
        self.previous_at = 0.0
        self.previous_sequence = -1
        self.current = None
        self.current_quality = None
        self.current_at = 0.0
        self.current_sequence = -1

    def update(self, result, sequence: int, captured_at: float,
               min_confidence: float = 0.15,
               frame_shape: tuple[int, ...] | None = None) -> dict[str, Any]:
        visible_hands = hand_pose_candidates(
            result, min_confidence, POSE_KEYPOINT_CONFIDENCE
        )
        candidates = [
            candidate for candidate in visible_hands
            if int((candidate[2][:, 2] >= INTENTION_KEYPOINT_CONFIDENCE).sum())
            >= MIN_HAND_KEYPOINTS
        ]
        evidence = {"secuencia": sequence, "manosVisibles": len(visible_hands),
                    "_manosParaInicio": len(candidates),
                    "movimientoNormalizado": 0.0, "medicionValida": False,
                    "_captured_at": captured_at}
        if len(candidates) == 2 and frame_shape is not None and len(frame_shape) >= 2:
            frame_height, frame_width = int(frame_shape[0]), int(frame_shape[1])
            if frame_width > 0 and frame_height > 0:
                evidence["poseKeypoints"] = [
                    [[float(point[0]), float(point[1]), float(point[2])] for point in pose]
                    for _, _, pose in candidates
                ]
                evidence["handBoxes"] = [
                    [float(value) for value in box]
                    for _, box, _ in candidates
                ]
                evidence["frameWidth"] = frame_width
                evidence["frameHeight"] = frame_height
        if (type(sequence) is not int or sequence < 0
            or not isinstance(captured_at, (int, float))
            or not math.isfinite(captured_at)):
            return evidence

        if sequence < self.current_sequence:
            # Out-of-order inference must not replace the latest valid sample.
            return evidence
        if sequence == self.current_sequence and captured_at != self.current_at:
            # A camera sequence has exactly one capture timestamp. Refuse a
            # duplicated identifier paired with fabricated/newer time.
            return evidence
        if sequence > self.current_sequence:
            if self.current is not None:
                self.previous = self.current
                self.previous_at = self.current_at
                self.previous_sequence = self.current_sequence
            self.current_sequence = sequence
            self.current_at = float(captured_at)
            self.current = None
            self.current_quality = None

        current = np.stack([item[2] for item in candidates]) if len(candidates) == 2 else None
        if current is None:
            return evidence
        previous, previous_at = self.previous, self.previous_at
        elapsed = float(captured_at) - previous_at
        if previous is None or self.previous_sequence >= sequence:
            self._retain_current(current, evidence)
            return evidence
        if elapsed > 0.65:
            self.previous = None
            self.previous_at = 0.0
            self.previous_sequence = -1
            self._retain_current(current, evidence)
            return evidence
        if not 0.04 <= elapsed <= 0.65:
            self._retain_current(current, evidence)
            return evidence
        a, b = candidates[0][1], candidates[1][1]
        gap = math.hypot(max(0, a[0] - b[2], b[0] - a[2]), max(0, a[1] - b[3], b[1] - a[3]))
        hand_size = (math.hypot(a[2] - a[0], a[3] - a[1])
                     + math.hypot(b[2] - b[0], b[3] - b[1])) / 2
        if hand_size < 10 or gap > hand_size:
            return evidence
        residuals = []
        for matched in (current, current[::-1]):
            visible = ((previous[:, :, 2] >= INTENTION_KEYPOINT_CONFIDENCE)
                       & (matched[:, :, 2] >= INTENTION_KEYPOINT_CONFIDENCE))
            if np.any(visible.sum(axis=1) < MIN_HAND_KEYPOINTS):
                continue
            # Estimate one camera transform for both hands together. Fitting
            # each hand independently cancels the relative translation that
            # makes palm rubbing visible to the intent gate.
            first, second = previous[:, :, :2][visible], matched[:, :, :2][visible]
            first = first - first.mean(axis=0)
            second = second - second.mean(axis=0)
            first_scale = float(np.sqrt(np.mean(np.sum(first * first, axis=1))))
            second_scale = float(np.sqrt(np.mean(np.sum(second * second, axis=1))))
            if min(first_scale, second_scale) < 10:
                continue
            first, second = first / first_scale, second / second_scale
            left, _, right = np.linalg.svd(first.T @ second)
            correction = np.eye(2)
            correction[-1, -1] = np.linalg.det(left @ right)
            aligned = first @ (left @ correction @ right)
            residuals.append(float(np.sqrt(np.mean(np.sum((aligned - second) ** 2, axis=1)))))
        if residuals:
            speed = min(residuals) / elapsed
            if math.isfinite(speed):
                evidence["movimientoNormalizado"] = min(1.0, max(0.0, speed))
                evidence["medicionValida"] = True
        self._retain_current(current, evidence)
        return evidence

    def _retain_current(self, current: np.ndarray, evidence: dict[str, Any]) -> None:
        """Keep the best keypoint result for this capture, without retaining frames."""
        quality = (
            bool(evidence["medicionValida"]),
            int(evidence["manosVisibles"]),
            int(evidence["_manosParaInicio"]),
        )
        if self.current_quality is None or quality > self.current_quality:
            self.current = current.copy()
            self.current_quality = quality


class HandPresenceWarmup:
    """Require consecutive fresh bilateral poses before partial-step inference."""

    def __init__(self, required_ms: int, max_gap_ms: int):
        if type(required_ms) is not int or not 0 <= required_ms <= 10_000:
            raise ValueError("hand-presence warmup debe estar entre 0 y 10000 ms")
        if type(max_gap_ms) is not int or max_gap_ms <= 0:
            raise ValueError("el hueco máximo de presencia debe ser positivo")
        self.required_ms = required_ms
        self.max_gap_ms = max_gap_ms
        self.started_at: float | None = None
        self.last_seen_at: float | None = None
        self.last_sequence = -1
        self.elapsed_ms = 0
        self.hands_visible = 0
        self.ready = required_ms == 0

    def update(
        self,
        hands_visible: int,
        sequence: int,
        captured_at: float,
        session_started: bool,
    ) -> dict[str, Any]:
        if (type(sequence) is not int or sequence < 0
            or not isinstance(captured_at, (int, float)) or not math.isfinite(captured_at)):
            self.hands_visible = 0
            self._reset_interval(force=not session_started)
            return self.snapshot()
        if sequence <= self.last_sequence:
            return self.snapshot()
        self.last_sequence = sequence
        self.hands_visible = max(0, min(2, int(hands_visible)))
        now = float(captured_at)
        if session_started:
            # Java already enforced the initial dwell. Its accepted start may
            # arrive after polling while this local mirror saw a brief hand loss.
            self.ready = True
            self.last_seen_at = now
            return self.snapshot()
        if self.ready and not session_started:
            gap_ms = (now - self.last_seen_at) * 1000 if self.last_seen_at is not None else None
            if (self.hands_visible != 2 or gap_ms is None or gap_ms <= 0
                or gap_ms > self.max_gap_ms):
                self._reset_interval(force=True)
        if self.ready:
            self.last_seen_at = now
            return self.snapshot()
        if self.hands_visible != 2:
            self._reset_interval()
            return self.snapshot()

        gap_ms = (now - self.last_seen_at) * 1000 if self.last_seen_at is not None else None
        if (self.started_at is None or gap_ms is None or gap_ms <= 0
            or gap_ms > self.max_gap_ms):
            self.started_at = now
            self.elapsed_ms = 0
        else:
            self.elapsed_ms = max(0, int(round((now - self.started_at) * 1000)))
        self.last_seen_at = now
        self.ready = self.elapsed_ms >= self.required_ms
        return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "elapsed_ms": min(self.elapsed_ms, self.required_ms),
            "required_ms": self.required_ms,
            "observed_at": self.last_seen_at or 0.0,
            "hands_visible": self.hands_visible,
        }

    def _reset_interval(self, force: bool = False) -> None:
        if self.ready and not force:
            return
        self.started_at = None
        self.last_seen_at = None
        self.elapsed_ms = 0
        self.ready = False


def bilateral_presence_is_fresh(
    presence: dict[str, Any], now: float, max_age_seconds: float
) -> bool:
    observed_at = presence.get("observed_at")
    return bool(
        presence.get("ready") is True
        and presence.get("hands_visible") == 2
        and isinstance(observed_at, (int, float))
        and math.isfinite(observed_at)
        and observed_at > 0
        and math.isfinite(now)
        and math.isfinite(max_age_seconds)
        and 0 <= now - observed_at <= max_age_seconds
    )


def fresh_hand_presence_progress_ms(
    presence: dict[str, Any], now: float, max_age_seconds: float
) -> int:
    observed_at = presence.get("observed_at")
    elapsed_ms = presence.get("elapsed_ms")
    required_ms = presence.get("required_ms")
    if (presence.get("hands_visible") != 2
        or type(elapsed_ms) is not int or elapsed_ms < 0
        or type(required_ms) is not int or required_ms < 0
        or not isinstance(observed_at, (int, float))
        or not math.isfinite(observed_at)
        or not math.isfinite(now)
        or not math.isfinite(max_age_seconds)):
        return 0
    age = now - observed_at
    if age < 0 or age > max_age_seconds:
        return 0
    return min(elapsed_ms, required_ms)


def should_block_step_inference_for_hands(
    model_mode: str,
    hand_model_enabled: bool,
    presence: dict[str, Any],
    fresh_hand_count: int,
    now: float,
    max_age_seconds: float,
) -> bool:
    if not hand_model_enabled:
        return False
    if model_mode == "PROTOCOLO_OMS":
        # OMS keeps a full-frame risk-only inference path while bilateral
        # evidence is absent or the initial presence warmup is incomplete.
        return False
    if fresh_hand_count < 2:
        return True
    return not bilateral_presence_is_fresh(
        presence, now, max_age_seconds
    )


def step_classes_for_presence(
    model_mode: str,
    all_class_ids: list[int],
    oms_risk_class_id: int | None,
    presence_ready: bool,
) -> list[int]:
    """During OMS warmup, preserve only the risk class; release phases when ready."""
    if model_mode == "PROTOCOLO_OMS" and not presence_ready:
        if oms_risk_class_id is None or oms_risk_class_id not in all_class_ids:
            raise ValueError("El detector OMS no tiene una clase única de contacto de riesgo")
        return [oms_risk_class_id]
    return all_class_ids


def detected_hands(result, min_confidence: float = 0.005,
                   max_hands: int = 2) -> list[tuple[tuple[float, float, float, float], float]]:
    """Return distinct confident hand boxes with enough visible keypoints."""
    return [(coordinates, confidence) for confidence, coordinates, _pose
            in hand_pose_candidates(result, min_confidence, POSE_KEYPOINT_CONFIDENCE, max_hands)]


def detected_hand_boxes(result, min_confidence: float = 0.01,
                        max_hands: int = 2) -> list[tuple[tuple[float, float, float, float], float]]:
    """Return drawable hand boxes; partial mode may use stronger boxes as ROI."""
    if result is None or result.boxes is None:
        return []
    boxes = []
    for box in result.boxes:
        coordinates = box_coordinates(box)
        confidence = float(box.conf.item())
        if coordinates is None or not math.isfinite(confidence) or confidence < min_confidence:
            continue
        boxes.append((coordinates, confidence))
    boxes.sort(key=lambda item: item[1], reverse=True)
    return boxes[:max(1, max_hands)]


def _same_crop_hand(
    first: tuple[tuple[float, float, float, float], float],
    second: tuple[tuple[float, float, float, float], float],
) -> bool:
    """Geometrically deduplicate pose-valid and box-only views of one hand."""
    x1, y1, x2, y2 = first[0]
    ax1, ay1, ax2, ay2 = second[0]
    area_a = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_b = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    intersection = (max(0.0, min(x2, ax2) - max(x1, ax1))
                    * max(0.0, min(y2, ay2) - max(y1, ay1)))
    union = area_a + area_b - intersection
    overlap = intersection / union if union > 0 else 0.0
    diagonal = (math.hypot(x2 - x1, y2 - y1)
                + math.hypot(ax2 - ax1, ay2 - ay1)) / 2.0
    if overlap < 0.45 or diagonal <= 0:
        return False
    center_a = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
    center_b = ((ax1 + ax2) / 2.0, (ay1 + ay2) / 2.0)
    return math.dist(center_a, center_b) <= 0.22 * diagonal


def partial_crop_guidance_hands(
    result,
    pose_min_confidence: float = 0.001,
    box_min_confidence: float = 0.15,
    max_hands: int = 2,
) -> list[tuple[tuple[float, float, float, float], float]]:
    """Use valid poses or stronger box-only proposals to locate a partial-mode ROI.

    Pose-valid boxes can guide crops below the visible/box-only threshold. A
    box-only proposal still cannot become pose evidence, be drawn as a reliable
    hand box, or pass Java's bilateral evidence gate.
    """
    limit = max(1, max_hands)
    guided = detected_hands(result, min_confidence=pose_min_confidence, max_hands=limit)
    for candidate in detected_hand_boxes(
        result, min_confidence=box_min_confidence, max_hands=16
    ):
        if any(_same_crop_hand(candidate, existing) for existing in guided):
            continue
        guided.append(candidate)
        if len(guided) >= limit:
            break
    return guided[:limit]


def hand_crop_bounds(
    hands: list[tuple[tuple[float, float, float, float], float]],
    frame_shape: tuple[int, ...],
    padding: float = 0.45,
    minimum_fraction: float = 0.4,
) -> tuple[int, int, int, int] | None:
    """Build one context-preserving ROI around the one or two best hand boxes."""
    if not hands:
        return None
    frame_height, frame_width = frame_shape[:2]
    if frame_width <= 0 or frame_height <= 0:
        return None
    x1 = min(item[0][0] for item in hands)
    y1 = min(item[0][1] for item in hands)
    x2 = max(item[0][2] for item in hands)
    y2 = max(item[0][3] for item in hands)
    box_width = x2 - x1
    box_height = y2 - y1
    # Keep the ROI tight on each axis. Using the larger extent for both
    # margins made two hands side-by-side produce an unnecessarily tall crop
    # (and hands stacked vertically produce an unnecessarily wide crop).
    margin_x = box_width * padding
    margin_y = box_height * padding
    center_x, center_y = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    crop_width = min(
        frame_width, max(box_width + 2 * margin_x, frame_width * minimum_fraction)
    )
    crop_height = min(
        frame_height, max(box_height + 2 * margin_y, frame_height * minimum_fraction)
    )
    left = max(0, min(frame_width - int(math.ceil(crop_width)),
                      int(math.floor(center_x - crop_width / 2.0))))
    top = max(0, min(frame_height - int(math.ceil(crop_height)),
                     int(math.floor(center_y - crop_height / 2.0))))
    right = min(frame_width, max(left + 1, int(math.ceil(left + crop_width))))
    bottom = min(frame_height, max(top + 1, int(math.ceil(top + crop_height))))
    return left, top, right, bottom


def draw_hand_boxes(frame: np.ndarray,
                    hands: list[tuple[tuple[float, float, float, float], float]]) -> np.ndarray:
    """Overlay the pre-trained hand detector boxes without retaining video."""
    for index, (coordinates, confidence) in enumerate(hands, start=1):
        x1, y1, x2, y2 = (int(round(value)) for value in coordinates)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (70, 235, 120), 2)
        cv2.putText(frame, f"mano {index} {confidence:.2f}", (x1, max(18, y1 - 7)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (70, 235, 120), 2)
    return frame


def hand_framing_hint(hands: list[tuple[tuple[float, float, float, float], float]],
                      width: int, height: int) -> str:
    """Give positioning feedback; this is not a calibrated hand-detection score."""
    if len(hands) < 2:
        return ("Centra ambas manos completas dentro del encuadre" if not hands
                else "Acerca la segunda mano al centro")
    if any(
        coordinates[0] < width * 0.08 or coordinates[1] < height * 0.08
        or coordinates[2] > width * 0.92 or coordinates[3] > height * 0.92
        for coordinates, _confidence in hands
    ):
        return "Aleja las manos del borde de la imagen"
    return "Ambas manos encuadradas"


def draw_hand_focus_inset(
    frame: np.ndarray,
    hands: list[tuple[tuple[float, float, float, float], float]],
    valid_pose_count: int,
    padding: float = 0.45,
    bounds: tuple[int, int, int, int] | None = None,
) -> np.ndarray:
    """Show the live hand-focused crop; the main-frame border marks the last analyzed ROI."""
    if bounds is None:
        bounds = hand_crop_bounds(hands, frame.shape, padding=padding)
    if bounds is None:
        return frame
    left, top, right, bottom = bounds
    crop = frame[top:bottom, left:right]
    if crop.size == 0:
        return frame

    max_width = max(1, int(frame.shape[1] * 0.40))
    max_height = max(1, int(frame.shape[0] * 0.40))
    scale = min(max_width / crop.shape[1], max_height / crop.shape[0])
    inset_width = max(1, int(round(crop.shape[1] * scale)))
    inset_height = max(1, int(round(crop.shape[0] * scale)))
    interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR
    inset = cv2.resize(crop, (inset_width, inset_height), interpolation=interpolation)

    margin = 12
    x = max(margin, frame.shape[1] - inset_width - margin)
    y = min(76, max(margin + 24, frame.shape[0] - inset_height - margin - 24))
    panel_left, panel_top = x - 4, y - 25
    panel_right, panel_bottom = x + inset_width + 4, y + inset_height + 4
    cv2.rectangle(frame, (panel_left, panel_top), (panel_right, panel_bottom), (5, 18, 25), -1)
    frame[y:y + inset_height, x:x + inset_width] = inset
    cv2.rectangle(frame, (x, y), (x + inset_width, y + inset_height), (70, 235, 120), 2)
    pose_label = (
        f"POSES {valid_pose_count}/2" if valid_pose_count
        else "CAJA YOLO | KEYPOINTS INCOMPLETOS"
    )
    cv2.putText(frame, f"ENCUADRE ACTUAL | {pose_label}", (x, y - 7),
                cv2.FONT_HERSHEY_SIMPLEX, 0.43, (255, 255, 255), 1, cv2.LINE_AA)
    return frame


def draw_step_boxes(frame: np.ndarray, result, origin: tuple[int, int] = (0, 0)) -> np.ndarray:
    """Draw step-model boxes in full-frame coordinates, including cropped inference."""
    if result is None or result.boxes is None:
        return frame
    offset_x, offset_y = origin
    for box in result.boxes:
        coordinates = box_coordinates(box)
        if coordinates is None:
            continue
        x1, y1, x2, y2 = coordinates
        first = (int(round(x1 + offset_x)), int(round(y1 + offset_y)))
        second = (int(round(x2 + offset_x)), int(round(y2 + offset_y)))
        class_id = int(box.cls.item())
        confidence = float(box.conf.item())
        label = f"{result.names[class_id]} {confidence:.2f}"
        cv2.rectangle(frame, first, second, (40, 185, 255), 2)
        cv2.putText(frame, label, (first[0], max(18, first[1] - 7)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (40, 185, 255), 2)
    return frame


def box_coordinates(box) -> tuple[float, float, float, float] | None:
    """Read a YOLO xyxy box without assuming CPU inference."""
    if not hasattr(box, "xyxy"):
        return None
    coordinates = box.xyxy[0]
    if hasattr(coordinates, "cpu"):
        coordinates = coordinates.cpu()
    values = coordinates.tolist()
    if len(values) != 4 or not all(math.isfinite(value) for value in values):
        return None
    x1, y1, x2, y2 = map(float, values)
    return (x1, y1, x2, y2) if x1 < x2 and y1 < y2 else None


def translate_pose_result(result, offset_x: int, offset_y: int):
    """Return tile-local pose boxes/keypoints in the source-frame coordinate system."""
    if result is None or result.boxes is None or result.keypoints is None:
        return SimpleNamespace(boxes=[], keypoints=SimpleNamespace(data=np.empty((0, 21, 3))))
    points = result.keypoints.data
    if hasattr(points, "cpu"):
        points = points.cpu().numpy()
    points = np.asarray(points, dtype=float).copy()
    if points.ndim != 3 or points.shape[1:] != (21, 3):
        raise ValueError("El resultado de pose recortado no tiene keypoints [N,21,3]")
    points[:, :, 0] += offset_x
    points[:, :, 1] += offset_y
    boxes = []
    retained_points = []
    for index, box in enumerate(result.boxes):
        coordinates = box_coordinates(box)
        if coordinates is None:
            continue
        x1, y1, x2, y2 = coordinates
        boxes.append(SimpleNamespace(
            xyxy=np.array([[x1 + offset_x, y1 + offset_y,
                            x2 + offset_x, y2 + offset_y]], dtype=float),
            conf=box.conf,
        ))
        retained_points.append(points[index])
    points = np.stack(retained_points) if retained_points else np.empty((0, 21, 3))
    return SimpleNamespace(boxes=boxes, keypoints=SimpleNamespace(data=points))


def hand_recovery_tiles(frame: np.ndarray):
    """Split a failed full-frame hand search into two overlapping long-axis tiles."""
    if not isinstance(frame, np.ndarray) or frame.ndim < 2:
        return []
    height, width = frame.shape[:2]
    axis = 0 if width >= height else 1
    length = width if axis == 0 else height
    if length < 4:
        return []

    split = length / 2.0
    overlap = max(1, int(round(length * HAND_RECOVERY_TILE_OVERLAP)))
    tile_length = min(length - 1, int(math.ceil((length + overlap) / 2.0)))
    first_end = tile_length
    second_start = length - tile_length
    if first_end >= length or second_start <= 0 or first_end <= second_start:
        return []

    if axis == 0:
        return [
            (frame[:, :first_end], 0, 0, axis, 0, split),
            (frame[:, second_start:], second_start, 0, axis, 1, split),
        ]
    return [
        (frame[:first_end, :], 0, 0, axis, 0, split),
        (frame[second_start:, :], 0, second_start, axis, 1, split),
    ]


def merge_hand_pose_tiles(results, tile_specs):
    """Map tile detections to full-frame coordinates and keep each hand's owner tile."""
    if len(results) != len(tile_specs):
        raise ValueError("La recuperación debe devolver un resultado por cada recorte")
    boxes = []
    poses = []
    for result, spec in zip(results, tile_specs):
        _tile, offset_x, offset_y, axis, owner, split = spec
        translated = translate_pose_result(result, offset_x, offset_y)
        points = translated.keypoints.data
        for index, box in enumerate(translated.boxes):
            coordinates = box_coordinates(box)
            if coordinates is None:
                continue
            center = (coordinates[axis] + coordinates[axis + 2]) / 2.0
            if (owner == 0 and center >= split) or (owner == 1 and center < split):
                continue
            boxes.append(box)
            poses.append(points[index])
    keypoints = np.stack(poses) if poses else np.empty((0, 21, 3))
    return SimpleNamespace(boxes=boxes, keypoints=SimpleNamespace(data=keypoints))


def recover_hand_pose(model, frame: np.ndarray, predict_options: dict[str, Any],
                      min_confidence: float) -> tuple[Any, int]:
    """Try overlapped tiles only if the ordinary high-resolution pass misses a hand."""
    safe_options = {**predict_options, "save": False}
    result = model.predict(frame, **safe_options)[0]
    visible_hands = len(detected_hands(result, min_confidence))
    if visible_hands >= 2:
        return result, 0
    tile_specs = hand_recovery_tiles(frame)
    if not tile_specs:
        return result, 0
    tile_results = model.predict([spec[0] for spec in tile_specs], **safe_options)
    tiled_result = merge_hand_pose_tiles(tile_results, tile_specs)
    improved = len(detected_hands(tiled_result, min_confidence)) > visible_hands
    return (tiled_result if improved else result), len(tile_specs)


def overlap_fraction(inner: tuple[float, float, float, float],
                     outer: tuple[float, float, float, float]) -> float:
    """Fraction of inner box covered by outer box, independent of box size."""
    x1 = max(inner[0], outer[0])
    y1 = max(inner[1], outer[1])
    x2 = min(inner[2], outer[2])
    y2 = min(inner[3], outer[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area = (inner[2] - inner[0]) * (inner[3] - inner[1])
    return intersection / area if area > 0 else 0.0


def best_detection(result, mode: str) -> tuple[str | None, float | None, dict[str, dict[str, Any]]]:
    if result.boxes is None or len(result.boxes) == 0:
        return None, None, {}
    candidates: list[tuple[float, str, tuple[float, float, float, float] | None]] = []
    risk: tuple[float, str] | None = None
    background_confidence: float | None = None
    soap: dict[str, list[tuple[float, str, tuple[float, float, float, float] | None]]] = {}
    for box in result.boxes:
        class_id = int(box.cls.item())
        confidence = normalized_confidence(box.conf.item())
        if confidence is None:
            continue
        name = result.names[class_id]
        if mode == "PROTOCOLO_OMS" and name == "OMS_CONTACTO_RIESGO":
            if risk is None or confidence > risk[0]:
                risk = (confidence, name)
        elif mode == "PROTOCOLO_OMS" and name in SOAP_CLASSES:
            region, state = SOAP_CLASSES[name]
            soap.setdefault(region, []).append((confidence, state, box_coordinates(box)))
        elif mode == "PROTOCOLO_OMS" and name in OMS_ACTION_CLASSES:
            candidates.append((confidence, name, box_coordinates(box)))
        elif mode == "FRICCION_PARCIAL":
            if name.strip().casefold() == "fondo":
                background_confidence = max(background_confidence or 0.0, confidence)
            else:
                canonical_name = canonical_step_name(name)
                if canonical_name is not None:
                    candidates.append((confidence, canonical_name, None))
    if risk is not None:
        return risk[1], risk[0], {}
    if not candidates:
        return None, None, {}

    confidence, name, action_box = max(candidates, key=lambda item: item[0])
    if mode != "PROTOCOLO_OMS":
        if background_confidence is not None and background_confidence >= confidence:
            return None, None, {}
        return name, confidence, {}
    # Every OMS action box must enclose the same two hands. Two disjoint action
    # boxes suggest multiple people or incompatible regions: abstain entirely.
    if action_box is None or any(
        other_box is None or overlap_fraction(other_box, action_box) < 0.5
        for _, _, other_box in candidates if other_box != action_box
    ):
        return None, None, {}

    evidence: dict[str, dict[str, Any]] = {}
    for region in SOAP_REGIONS_BY_ACTION.get(name, frozenset()):
        associated = [
            (score, state) for score, state, soap_box in soap.get(region, [])
            if soap_box is not None and overlap_fraction(soap_box, action_box) >= 0.8
        ]
        if not associated:
            continue
        states = {state for _, state in associated}
        # Opposing predictions for one anatomical region are not evidence of foam.
        state = next(iter(states)) if len(states) == 1 else "NO_VERIFICABLE"
        evidence[region] = {
            "estado": state,
            "confianza": max(score for score, _ in associated),
        }
    return name, confidence, evidence


class TemporalStepFilter:
    """Stabilize the spatial detector against one-frame class flips."""

    def __init__(self, history_size: int = 3, min_votes: int = 2):
        self.history_size = max(1, history_size)
        self.min_votes = max(1, min(min_votes, self.history_size))
        self.history: deque[tuple[str, float] | None] = deque(maxlen=self.history_size)
        self.stable: tuple[str, float] | None = None

    def reset(self) -> None:
        self.history.clear()
        self.stable = None

    def votes_for(self, name: str | None) -> int:
        if name is None:
            return 0
        return sum(1 for item in self.history if item is not None and item[0] == name)

    def update(self, name: str | None, confidence: float | None) -> tuple[str | None, float | None]:
        confidence = normalized_confidence(confidence)
        if name is None or confidence is None:
            self.history.append(None)
            if self.stable is not None:
                stable_votes = sum(
                    1 for item in self.history
                    if item is not None and item[0] == self.stable[0]
                )
                if stable_votes < self.min_votes:
                    self.stable = None
            return None, None
        current = (name, confidence)
        self.history.append(current)
        if self.stable is not None:
            stable_votes = sum(
                1 for item in self.history
                if item is not None and item[0] == self.stable[0]
            )
            if stable_votes < self.min_votes:
                self.stable = None
        if self.stable is None:
            votes: dict[str, int] = {}
            for item in self.history:
                if item is None:
                    continue
                item_name, _ = item
                votes[item_name] = votes.get(item_name, 0) + 1
            if votes.get(name, 0) < self.min_votes:
                return None, None
            self.stable = current
            return self.stable
        if name == self.stable[0]:
            # Never retain an old high score as if it were the current frame.
            self.stable = (name, confidence)
            return self.stable
        votes: dict[str, int] = {}
        for item in self.history:
            if item is None:
                continue
            item_name, _ = item
            votes[item_name] = votes.get(item_name, 0) + 1
        winner = max(votes, key=votes.get, default=self.stable[0])
        if winner == name and winner != self.stable[0] and votes[winner] >= self.min_votes:
            self.stable = current
            return self.stable
        # A conflicting observation is not evidence for the previous action.
        return None, None


def temporal_gap_exceeded(previous_observed_at: float, current_observed_at: float,
                          maximum_gap_seconds: float) -> bool:
    """Only retain temporal votes across a bounded interval of real camera time."""
    return (
        math.isfinite(previous_observed_at)
        and math.isfinite(current_observed_at)
        and math.isfinite(maximum_gap_seconds)
        and previous_observed_at > 0
        and current_observed_at >= previous_observed_at
        and current_observed_at - previous_observed_at >= maximum_gap_seconds
    )


def stabilize_detection(temporal_filter: TemporalStepFilter, mode: str,
                        name: str | None, confidence: float | None) -> tuple[str | None, float | None]:
    """Debounce ordinary phases, but never delay a possible contamination event."""
    confidence = normalized_confidence(confidence)
    if name is None or confidence is None:
        return temporal_filter.update(None, None)
    if mode == "PROTOCOLO_OMS" and name == "OMS_CONTACTO_RIESGO":
        temporal_filter.reset()
        return name, confidence
    return temporal_filter.update(name, confidence)


def should_send_step_detection(name: str | None, confidence: float | None,
                               previous_name: str | None, elapsed_seconds: float,
                               heartbeat_ms: int) -> bool:
    """Publish transitions immediately; keep same-step traffic bounded."""
    return name is not None and confidence is not None and (
        name != previous_name or elapsed_seconds >= heartbeat_ms / 1000.0
    )


def run() -> None:
    args = parse_args()
    check_hand_model = getattr(args, "check_hand_model", False)
    check_classifier_model = getattr(args, "check_classifier_model", False)
    if args.check_camera or args.check_model or check_hand_model or check_classifier_model:
        try:
            if args.check_camera:
                camera_index, selected_name = select_iphone_camera(args.camera_index)
                print(f"Cámara de Continuidad disponible: [{camera_index}] {selected_name}", flush=True)
            if args.check_model:
                verify_model_artifact(args.model)
                checked_model = YOLO(args.model)
                _, checked_mode = validate_step_model(checked_model, args.model)
                validate_active_step_manifest(checked_model, args.model)
                print(f"Compatibilidad estructural YOLO: {checked_mode} ({args.model})", flush=True)
                warning = sequential_label_taxonomy_warning(checked_model.names)
                if warning:
                    print(f"ADVERTENCIA DE TAXONOMÍA: {warning}", flush=True)
                print("Este preflight no demuestra precisión ni validación clínica.", flush=True)
            if check_hand_model:
                verify_model_artifact(args.hand_model)
                checked_hand_model = YOLO(args.hand_model)
                validate_hand_model(checked_hand_model, args.hand_model)
                print(f"Modelo YOLO de manos compatible: {args.hand_model}", flush=True)
            if check_classifier_model:
                verify_model_artifact(args.classifier_model)
                checked_classifier = YOLO(args.classifier_model)
                validate_derived_classifier(checked_classifier, args.classifier_model)
                print(f"Clasificador auxiliar compatible: {args.classifier_model}", flush=True)
        except RuntimeError as exc:
            raise SystemExit(str(exc)) from None
        return
    if not 100 <= args.event_heartbeat_ms <= 1_500:
        raise ValueError("--event-heartbeat-ms debe estar entre 100 y 1500")
    if args.camera_reconnect_timeout < 5 or args.camera_retry_interval < 0.5:
        raise ValueError("La reconexión requiere al menos 5 s y reintentos separados por 0,5 s")
    if (args.stream_width < 320 or not 5 <= args.stream_fps <= 30
        or not 50 <= args.stream_jpeg_quality <= 95):
        raise ValueError(
            "La salida MJPEG requiere --stream-width >=320, --stream-fps entre 5 y 30 "
            "y --stream-jpeg-quality entre 50 y 95"
        )
    device = args.device
    if device == "auto":
        device = "mps" if torch.backends.mps.is_available() else "cpu"
    # Ultralytics currently leaves precision unchanged on MPS/ARM64; only request
    # FP16 on CUDA so the on-screen badge never claims an optimization that did
    # not happen. CUDA accepts numeric device IDs as well as cuda:N.
    is_cuda = device == "cuda" or device.startswith("cuda:") or device.isdigit()
    use_fp16 = args.precision == "fp16" and is_cuda
    verify_model_artifact(args.model)
    model = YOLO(args.model)
    step_classes, model_mode = validate_step_model(model, args.model)
    validate_active_step_manifest(model, args.model)
    classifier_model = None
    if model_mode == "FRICCION_PARCIAL" and args.classifier_fallback:
        if not Path(args.classifier_model).is_file():
            raise RuntimeError(
                f"Falta el clasificador auxiliar '{args.classifier_model}'. "
                "Restáuralo o usa --no-classifier-fallback."
            )
        verify_model_artifact(args.classifier_model)
        classifier_model = YOLO(args.classifier_model)
        validate_derived_classifier(classifier_model, args.classifier_model)
        if not 0 <= args.classifier_confidence <= 1:
            raise ValueError("--classifier-confidence debe estar entre 0 y 1")
        if not 0 <= args.classifier_challenge_below <= 1:
            raise ValueError("--classifier-challenge-below debe estar entre 0 y 1")
        if not 0 <= args.classifier_margin <= 1:
            raise ValueError("--classifier-margin debe estar entre 0 y 1")
    step_inference_classes = list(step_classes)
    raw_step_names = model.names or {}
    step_name_map = (
        raw_step_names if isinstance(raw_step_names, dict)
        else dict(enumerate(raw_step_names))
    )
    oms_risk_class_ids = [
        class_id for class_id, name in step_name_map.items()
        if name == "OMS_CONTACTO_RIESGO"
    ]
    if model_mode == "PROTOCOLO_OMS" and len(oms_risk_class_ids) != 1:
        raise RuntimeError("El detector OMS debe tener una clase OMS_CONTACTO_RIESGO única.")
    oms_risk_class_id = oms_risk_class_ids[0] if oms_risk_class_ids else None
    if model_mode == "FRICCION_PARCIAL":
        step_inference_classes.extend(
            class_id for class_id, name in step_name_map.items()
            if str(name).strip().casefold() == "fondo"
            and class_id not in step_inference_classes
        )
    # Hand localization is part of the canonical flow. The detector runs at a
    # smaller input size and lower cadence than step inference to limit heat.
    if args.hand_pose:
        verify_model_artifact(args.hand_model)
        hand_model = YOLO(args.hand_model)
    else:
        hand_model = None
    if hand_model is not None:
        validate_hand_model(hand_model, args.hand_model)
    elif model_mode == "PROTOCOLO_OMS":
        raise RuntimeError("El modo OMS requiere el localizador de manos; quita --no-hand-pose.")
    elif args.hand_presence_warmup_ms > 0:
        raise RuntimeError(
            "El calentamiento bilateral requiere el localizador YOLO de manos; "
            "desactívalo solo para depuración explícita."
        )
    if args.confidence < 0 or args.confidence > 1:
        raise ValueError("--confidence debe estar entre 0 y 1")
    if not 0 <= args.hand_confidence <= 1:
        raise ValueError("--hand-confidence debe estar entre 0 y 1")
    if not 0.1 <= args.hand_iou <= 0.95:
        raise ValueError("--hand-iou debe estar entre 0.1 y 0.95")
    if not 2 <= args.hand_max_det <= 64:
        raise ValueError("--hand-max-det debe estar entre 2 y 64")
    if not 0 <= args.hand_crop_confidence <= 1:
        raise ValueError("--hand-crop-confidence debe estar entre 0 y 1")
    if args.missing_detection_grace <= 0:
        raise ValueError("--missing-detection-grace debe ser positivo")
    configured_detection_gap = int(os.getenv("HANDWASH_MAX_DETECTION_GAP_MS", "1500")) / 1000.0
    if args.missing_detection_grace >= configured_detection_gap:
        raise ValueError(
            "--missing-detection-grace debe ser menor que "
            "HANDWASH_MAX_DETECTION_GAP_MS para no ocultar una pausa al backend"
        )
    if args.hand_imgsz < 160 or args.hand_imgsz % 32 != 0:
        raise ValueError("--hand-imgsz debe ser múltiplo de 32 y no menor que 160")
    if args.hand_recovery_imgsz < args.hand_imgsz or args.hand_recovery_imgsz % 32 != 0:
        raise ValueError("--hand-recovery-imgsz debe ser múltiplo de 32 y no menor que --hand-imgsz")
    if args.hand_recovery_interval <= 0:
        raise ValueError("--hand-recovery-interval debe ser positivo")
    if args.fallback_imgsz < args.imgsz or args.fallback_imgsz % 32 != 0:
        raise ValueError("--fallback-imgsz debe ser múltiplo de 32 y no menor que --imgsz")
    if args.step_recovery_interval <= 0:
        raise ValueError("--step-recovery-interval debe ser positivo")
    if args.hand_max_age <= 0 or not 0.1 <= args.hand_padding <= 1.5:
        raise ValueError("--hand-max-age debe ser positivo y --hand-padding estar entre 0.1 y 1.5")
    presence_max_age_seconds = hand_presence_freshness_window(args.hand_max_age)
    if args.inference_fps <= 0 or args.hand_inference_fps <= 0:
        raise ValueError("Las frecuencias de inferencia deben ser positivas")
    warmup_message = (
        f"pasos bloqueados hasta {args.hand_presence_warmup_ms / 1000:.1f} s "
        "de dos manos continuas"
        if hand_model is not None and args.hand_presence_warmup_ms > 0
        else "sin bloqueo previo de presencia bilateral"
    )
    print(
        f"Calentando detector de pasos ({args.imgsz}px; {warmup_message}); "
        "la primera inferencia se prepara antes de abrir la cámara...",
        flush=True,
    )
    step_warmup_options = {
        "imgsz": args.imgsz,
        "conf": args.confidence,
        "device": device,
        "verbose": False,
        "classes": step_inference_classes,
        "max_det": 24 if model_mode == "PROTOCOLO_OMS" else 10,
    }
    if use_fp16:
        step_warmup_options["quantize"] = 16
    model.predict(
        np.zeros((args.imgsz, args.imgsz, 3), dtype=np.uint8),
        **step_warmup_options,
    )
    if args.fallback_imgsz > args.imgsz:
        print(
            f"Preparando recuperación del recorte de pasos a {args.fallback_imgsz}px...",
            flush=True,
        )
        recovery_warmup_options = dict(step_warmup_options)
        recovery_warmup_options.update({
            "imgsz": args.fallback_imgsz,
            "max_det": 24 if model_mode == "PROTOCOLO_OMS" else 10,
        })
        model.predict(
            np.zeros((args.fallback_imgsz, args.fallback_imgsz, 3), dtype=np.uint8),
            **recovery_warmup_options,
        )
    if hand_model is not None:
        print(
            f"Calentando detector de manos ({args.hand_imgsz}px); "
            "la primera inferencia en CPU puede tardar más que las siguientes...",
            flush=True,
        )
        hand_warmup_options = {
            "imgsz": args.hand_imgsz,
            "conf": args.hand_confidence,
            "device": device,
            "verbose": False,
            # Preserve overlapping hand proposals through NMS. The pose-level
            # geometric deduplicator below rejects duplicate views of one hand.
            "iou": args.hand_iou,
            "max_det": args.hand_max_det,
        }
        if use_fp16:
            hand_warmup_options["quantize"] = 16
        hand_model.predict(
            np.zeros((args.hand_imgsz, args.hand_imgsz, 3), dtype=np.uint8),
            **hand_warmup_options,
        )
        if args.hand_recovery_imgsz > args.hand_imgsz:
            print(
                f"Preparando recuperación de manos ({args.hand_recovery_imgsz}px)...",
                flush=True,
            )
            recovery_warmup_options = dict(hand_warmup_options)
            recovery_warmup_options["imgsz"] = args.hand_recovery_imgsz
            hand_model.predict(
                np.zeros((args.hand_recovery_imgsz, args.hand_recovery_imgsz, 3), dtype=np.uint8),
                **recovery_warmup_options,
            )
    if classifier_model is not None:
        print("Calentando clasificador auxiliar a 320 px en CPU...", flush=True)
        classifier_model.predict(
            np.zeros((320, 320, 3), dtype=np.uint8),
            imgsz=320, device="cpu", verbose=False, save=False,
        )
    camera_index, selected_name = select_iphone_camera(args.camera_index)
    print(f"Cámara activa: [{camera_index}] {selected_name}", flush=True)
    print(f"Modelo de manos: {args.hand_model}", flush=True)
    print(f"Modelo de pasos: {args.model} ({model_mode})", flush=True)
    if classifier_model is not None:
        print(f"Clasificador auxiliar pasos 1–6: {args.classifier_model} "
              f"({'prioritario' if args.classifier_authoritative else 'challenge débil'}; "
              f"umbral detector {args.classifier_challenge_below:.2f}, "
              f"requiere pose bilateral fresca; Java protege secuencia e inicio)", flush=True)
    enabled_step_names = [
        str(step_name_map[class_id]) for class_id in step_inference_classes
        if class_id in step_name_map
    ]
    print(f"Clases YOLO activas: {', '.join(enabled_step_names)}", flush=True)
    taxonomy_warning = sequential_label_taxonomy_warning(model.names)
    if model_mode == "FRICCION_PARCIAL" and taxonomy_warning:
        print(f"ADVERTENCIA DE TAXONOMÍA: {taxonomy_warning}", flush=True)
    # Capture at 720p but hand a smaller frame to Python/ffplay. This keeps the
    # Continuity Camera sharp enough for hands while reducing memory bandwidth.
    width, height = 960, 540
    frame_bytes = width * height * 3
    camera = start_camera_process(camera_index, width, height)
    camera_started_at = time.monotonic()
    if camera.stdout is None:
        raise RuntimeError("FFmpeg no pudo abrir el flujo de la cámara del iPhone")

    display = None
    if args.native_preview:
        display = subprocess.Popen(
            [
                "ffplay", "-loglevel", "error", "-f", "rawvideo", "-pixel_format", "bgr24",
                "-video_size", f"{width}x{height}", "-framerate", "30", "-alwaysontop",
                "-window_title", "HandWash - YOLO26 / iPhone", "-i", "pipe:0",
            ],
            stdin=subprocess.PIPE,
        )

    predict_options = {
        "imgsz": args.imgsz,
        "conf": args.confidence,
        "device": device,
        "verbose": False,
        "classes": step_inference_classes,  # conserva Fondo como veto; excluye clases auxiliares
        "max_det": 24 if model_mode == "PROTOCOLO_OMS" else 10,
    }
    if use_fp16:
        predict_options["quantize"] = 16
    crop_recovery_options = dict(predict_options)
    crop_recovery_options["imgsz"] = args.fallback_imgsz
    crop_recovery_options["max_det"] = 24 if model_mode == "PROTOCOLO_OMS" else 10
    hand_predict_options = {
        "imgsz": args.hand_imgsz,
        "conf": args.hand_confidence,
        "device": device,
        "verbose": False,
        "iou": args.hand_iou,
        "max_det": args.hand_max_det,
    }
    if use_fp16:
        hand_predict_options["quantize"] = 16
    hand_recovery_options = dict(hand_predict_options)
    hand_recovery_options["imgsz"] = args.hand_recovery_imgsz

    latest_frame = None
    latest_sequence = 0
    capture_sequence = CameraFrameSequence()
    last_capture_at = time.monotonic()
    frame_lock = threading.Lock()
    inference_lock = threading.Lock()
    hand_inference_pending = threading.Event()
    stop_capture = threading.Event()
    camera_online = threading.Event()
    capture_restart_requested = threading.Event()
    capture_failure: list[str] = []
    disconnected_since: float | None = None

    def acquire_step_inference_slot() -> bool:
        """Acquire the shared accelerator only when hand inference is not queued."""
        if hand_inference_pending.is_set() or not inference_lock.acquire(blocking=False):
            return False
        # Close the check/acquire race: the hand thread may have queued itself
        # immediately after the first event check.
        if hand_inference_pending.is_set():
            inference_lock.release()
            return False
        return True

    def capture_frames() -> None:
        nonlocal camera, camera_started_at, latest_frame, latest_sequence
        nonlocal last_capture_at, disconnected_since
        while not stop_capture.is_set():
            with frame_lock:
                active = camera
            try:
                raw_frame = active.stdout.read(frame_bytes) if active and active.stdout else b""
            except (OSError, ValueError):
                raw_frame = b""
            if len(raw_frame) == frame_bytes:
                frame = np.frombuffer(raw_frame, dtype=np.uint8).reshape((height, width, 3))
                with frame_lock:
                    # The view keeps raw_frame alive; downstream snapshots are read-only.
                    first_frame = latest_sequence == 0
                    latest_frame = frame
                    latest_sequence = capture_sequence.next()
                    last_capture_at = time.monotonic()
                    recovered = disconnected_since is not None
                    disconnected_since = None
                capture_restart_requested.clear()
                camera_online.set()
                if first_frame:
                    print("Primer frame recibido desde la cámara de Continuidad.", flush=True)
                if recovered:
                    print("Cámara del iPhone recuperada; reanudando video.", flush=True)
                continue
            if stop_capture.is_set():
                stop_camera_process(active)
                return
            camera_online.clear()
            with frame_lock:
                latest_frame = None
                if disconnected_since is None:
                    disconnected_since = time.monotonic()
                    print("Cámara desconectada; intentando reconectar sin cerrar la sesión.", flush=True)
                started = disconnected_since
                camera = None
            stop_camera_process(active)
            if stop_capture.is_set():
                break
            while not stop_capture.is_set():
                if time.monotonic() - started >= args.camera_reconnect_timeout:
                    capture_failure.append("No se recuperó la cámara del iPhone dentro del plazo de reconexión.")
                    stop_capture.set()
                    return
                if stop_capture.wait(args.camera_retry_interval):
                    break
                try:
                    next_index, next_name, reopened = reopen_iphone_camera(width, height)
                except (RuntimeError, OSError) as error:
                    print(f"Reintento de cámara: {error}", flush=True)
                    continue
                with frame_lock:
                    camera = reopened
                    camera_started_at = time.monotonic()
                    last_capture_at = time.monotonic()
                capture_restart_requested.clear()
                print(f"Reabriendo cámara: [{next_index}] {next_name}", flush=True)
                break

    capture_thread = threading.Thread(target=capture_frames, name="iphone-capture", daemon=True)
    capture_thread.start()
    hand_state_lock = threading.Lock()
    stop_hand_inference = threading.Event()
    hand_presence_gate = HandPresenceWarmup(
        args.hand_presence_warmup_ms,
        max(1, int(presence_max_age_seconds * 1000)),
    )
    hand_state: dict[str, Any] = {
        "boxes": [], "observed_at": 0.0, "pose_sequence": -1,
        "pose_proposals": 0, "pose_proposals_observed_at": 0.0,
        "pose_frame": None,
        "crop_boxes": [], "crop_observed_at": 0.0, "crop_sequence": -1,
        "crop_frame": None,
        "display_boxes": [], "display_observed_at": 0.0, "display_sequence": -1,
        "motion": None, "motion_sequence": -1,
        "presence": hand_presence_gate.snapshot(),
        "inferences": 0, "error": None,
    }

    def detect_hands_continuously() -> None:
        """Localize hands off-thread and reserve accelerator slots before step inference."""
        motion_estimator = HandMotionEstimator()
        if hand_model is None:
            return
        interval = 1.0 / max(args.hand_inference_fps, 0.1)
        recovery_interval = args.hand_recovery_interval
        last_sequence = -1
        next_inference_at = 0.0
        next_recovery_at = 0.0
        recovery_error_logged: str | None = None
        inference_error_logged: str | None = None
        consecutive_inference_errors = 0
        last_presence_enqueued_at = float("-inf")
        last_presence_hands = None
        while not stop_hand_inference.is_set():
            with frame_lock:
                # Only inspect availability here. Copy once the accelerator is
                # acquired, rather than copying on every scheduler poll.
                current = latest_frame
                sequence = latest_sequence
                captured_at = last_capture_at
            now = time.monotonic()
            if current is None or sequence == last_sequence or now < next_inference_at:
                wait_for = max(0.005, min(0.03, next_inference_at - now))
                stop_hand_inference.wait(wait_for)
                continue
            hand_inference_pending.set()
            if not inference_lock.acquire(timeout=0.2):
                hand_inference_pending.clear()
                stop_hand_inference.wait(0.01)
                continue
            inference_count = 1
            try:
                # Inference may have waited behind the step detector; always use
                # the freshest frame after acquiring the shared accelerator lock.
                with frame_lock:
                    current = latest_frame.copy() if latest_frame is not None else None
                    sequence = latest_sequence
                    captured_at = last_capture_at
                if current is None or sequence == last_sequence:
                    continue
                started_at = time.monotonic()
                result = hand_model.predict(current, **hand_predict_options)[0]
                pose_proposals = hand_pose_proposal_count(result)
                pose_proposals_captured_at = captured_at
                # Match pose localization's box threshold. The estimator then
                # applies its stricter per-hand keypoint-visibility requirement;
                # using the crop-box threshold here can hide a valid second hand.
                motion = motion_estimator.update(
                    result, sequence, captured_at, args.hand_confidence, current.shape)
                consecutive_inference_errors = 0
                inference_error_logged = None
                with hand_state_lock:
                    hand_state["error"] = None
                    hand_state["motion"] = motion
                    hand_state["motion_sequence"] = sequence
                    hand_state["pose_proposals"] = pose_proposals
                    hand_state["pose_proposals_observed_at"] = captured_at
                # The permissive pose proposal threshold is not sufficient to
                # label an object as a hand in the live preview.
                display_hands = detected_hand_boxes(
                    result, max(args.hand_confidence, args.hand_crop_confidence)
                )
                display_captured_at = captured_at if display_hands else 0.0
                display_sequence = sequence if display_hands else -1
                hands = detected_hands(result, args.hand_confidence)
                hands_captured_at = captured_at if hands else 0.0
                pose_sequence = sequence if hands else -1
                pose_frame = current if hands else None
                crop_hands = (
                    partial_crop_guidance_hands(
                        result, args.hand_confidence, args.hand_crop_confidence
                    )
                    if model_mode == "FRICCION_PARCIAL" else hands
                )
                crop_hands_captured_at = captured_at if crop_hands else 0.0
                crop_sequence = sequence if crop_hands else -1
                crop_frame = current if crop_hands else None
                if len(hands) >= 2:
                    next_recovery_at = 0.0
                    recovery_error_logged = None
            except Exception as exc:
                error_message = str(exc)
                with hand_state_lock:
                    hand_state["error"] = error_message
                if error_message != inference_error_logged:
                    print(
                        f"Aviso: falló la inferencia de manos; se mantiene el video y "
                        f"se reintentará ({error_message})",
                        flush=True,
                    )
                    inference_error_logged = error_message
                consecutive_inference_errors += 1
                retry_delay = min(0.5 * (2 ** min(consecutive_inference_errors - 1, 4)), 8.0)
                last_sequence = sequence
                next_inference_at = time.monotonic() + retry_delay
                continue
            finally:
                hand_inference_pending.clear()
                inference_lock.release()

            completed_at = time.monotonic()
            # Publish the primary result before the slower recovery pass. A
            # useful 320px localization must not wait until a 640px retry ends.
            with hand_state_lock:
                if display_hands:
                    hand_state["display_boxes"] = display_hands
                    hand_state["display_observed_at"] = display_captured_at
                    hand_state["display_sequence"] = display_sequence
                if hands or display_hands:
                    hand_state["boxes"] = hands
                    hand_state["observed_at"] = hands_captured_at
                    hand_state["pose_sequence"] = pose_sequence
                    hand_state["pose_frame"] = pose_frame
                if crop_hands or display_hands:
                    hand_state["crop_boxes"] = crop_hands
                    hand_state["crop_observed_at"] = crop_hands_captured_at
                    hand_state["crop_sequence"] = crop_sequence
                    hand_state["crop_frame"] = crop_frame
                hand_state["inferences"] += 1
            # Washing movements normally involve both hands. A single valid
            # pose can still drive a contextual crop, but periodically retry at
            # higher resolution to recover the second hand when it is small or
            # partially occluded. Never discard the primary pose on a miss.
            if len(hands) < 2 and completed_at >= next_recovery_at:
                # Don't hold the accelerator lock through the expensive recovery
                # pass; reserve only its next slot after the primary pass.
                next_recovery_at = completed_at + recovery_interval
                hand_inference_pending.set()
                if inference_lock.acquire(timeout=0.2):
                    inference_count += 1
                    try:
                        # Recovery is deliberately lower-frequency and may wait
                        # behind step inference. Refresh its input after acquiring
                        # the shared lock so the expensive 640px pass localizes
                        # the current hands, not a frame that has already moved.
                        with frame_lock:
                            recovery_frame = (
                                latest_frame.copy() if latest_frame is not None else None
                            )
                            recovery_sequence = latest_sequence
                            recovery_captured_at = last_capture_at
                        if recovery_frame is not None:
                            current = recovery_frame
                            sequence = recovery_sequence
                            captured_at = recovery_captured_at
                        recovery_input_frame = current
                        recovery_input_sequence = sequence
                        recovery_input_captured_at = captured_at
                        result, tile_inferences = recover_hand_pose(
                            hand_model, current, hand_recovery_options,
                            args.hand_confidence,
                        )
                        inference_count += tile_inferences
                        recovered_motion = motion_estimator.update(
                            result, sequence, captured_at, args.hand_confidence, current.shape)
                        recovery_improves_pose = prefer_recovered_motion(recovered_motion, motion)
                        if recovery_improves_pose:
                            pose_proposals = hand_pose_proposal_count(result)
                            pose_proposals_captured_at = recovery_input_captured_at
                            motion = recovered_motion
                            with hand_state_lock:
                                hand_state["motion"] = motion
                                hand_state["motion_sequence"] = sequence
                        recovered_hands = detected_hands(result, args.hand_confidence)
                        recovered_display_hands = detected_hand_boxes(
                            result, max(args.hand_confidence, args.hand_crop_confidence)
                        )
                        if prefer_recovered_localization(recovered_display_hands, display_hands):
                            display_hands = recovered_display_hands
                            display_captured_at = (
                                recovery_input_captured_at if recovered_display_hands else 0.0
                            )
                            display_sequence = recovery_input_sequence if recovered_display_hands else -1
                        if recovery_improves_pose:
                            hands = recovered_hands
                            hands_captured_at = (
                                recovery_input_captured_at if recovered_hands else 0.0
                            )
                            pose_sequence = recovery_input_sequence if recovered_hands else -1
                            pose_frame = recovery_input_frame if recovered_hands else None
                        recovered_crop_hands = (
                            partial_crop_guidance_hands(
                                result, args.hand_confidence, args.hand_crop_confidence
                            )
                            if model_mode == "FRICCION_PARCIAL" else recovered_hands
                        )
                        if prefer_recovered_localization(recovered_crop_hands, crop_hands):
                            crop_hands = recovered_crop_hands
                            crop_hands_captured_at = (
                                recovery_input_captured_at if recovered_crop_hands else 0.0
                            )
                            crop_sequence = recovery_input_sequence if recovered_crop_hands else -1
                            crop_frame = recovery_input_frame if recovered_crop_hands else None
                        recovery_error_logged = None
                    except Exception as recovery_error:
                        recovery_message = str(recovery_error)
                        if recovery_message != recovery_error_logged:
                            print(
                                f"Aviso: recuperación YOLO de manos a "
                                f"{args.hand_recovery_imgsz}px falló: {recovery_message}",
                                flush=True,
                            )
                            recovery_error_logged = recovery_message
                    finally:
                        hand_inference_pending.clear()
                        inference_lock.release()
                        next_recovery_at = (
                            0.0 if len(hands) >= 2
                            else time.monotonic() + recovery_interval
                        )
                else:
                    hand_inference_pending.clear()
            last_sequence = sequence
            completed_at = time.monotonic()
            presence_state = hand_presence_gate.update(
                len(hands), sequence, captured_at, session_started.is_set()
            )
            presence_hands = presence_state["hands_visible"]
            if (producer_stream is not None
                and (presence_hands != last_presence_hands
                     or completed_at - last_presence_enqueued_at >= 0.25)):
                if enqueue_presence_observation(
                    pending_detections, producer_stream, presence_hands,
                    sequence, captured_at,
                ):
                    last_presence_enqueued_at = completed_at
                    last_presence_hands = presence_hands
            with hand_state_lock:
                hand_state["presence"] = presence_state
                hand_state["pose_proposals"] = pose_proposals
                hand_state["pose_proposals_observed_at"] = pose_proposals_captured_at
                # The overlay may show incomplete poses. Partial friction can
                # crop from stronger boxes when keypoints are occluded; the OMS
                # path still uses only poses with enough visible keypoints. A
                # single negative inference does not erase a recent positive;
                # every retained box remains paired with its own image.
                if display_hands:
                    hand_state["display_boxes"] = display_hands
                    hand_state["display_observed_at"] = display_captured_at
                    hand_state["display_sequence"] = display_sequence
                elif (hand_state["display_observed_at"] <= 0.0
                      or completed_at - hand_state["display_observed_at"] > args.hand_max_age):
                    hand_state["display_boxes"] = []
                    hand_state["display_observed_at"] = 0.0
                    hand_state["display_sequence"] = -1
                if hands:
                    hand_state["boxes"] = hands
                    hand_state["observed_at"] = hands_captured_at
                    hand_state["pose_sequence"] = pose_sequence
                    hand_state["pose_frame"] = pose_frame
                elif display_hands:
                    hand_state["boxes"] = []
                    hand_state["observed_at"] = 0.0
                    hand_state["pose_sequence"] = -1
                    hand_state["pose_frame"] = None
                elif (hand_state["observed_at"] <= 0.0
                      or completed_at - hand_state["observed_at"] > args.hand_max_age):
                    hand_state["boxes"] = []
                    hand_state["observed_at"] = 0.0
                    hand_state["pose_sequence"] = -1
                    hand_state["pose_frame"] = None
                if crop_hands:
                    hand_state["crop_boxes"] = crop_hands
                    hand_state["crop_observed_at"] = crop_hands_captured_at
                    hand_state["crop_sequence"] = crop_sequence
                    hand_state["crop_frame"] = crop_frame
                elif display_hands:
                    hand_state["crop_boxes"] = []
                    hand_state["crop_observed_at"] = 0.0
                    hand_state["crop_sequence"] = -1
                    hand_state["crop_frame"] = None
                elif (hand_state["crop_observed_at"] <= 0.0
                      or completed_at - hand_state["crop_observed_at"] > args.hand_max_age):
                    hand_state["crop_boxes"] = []
                    hand_state["crop_observed_at"] = 0.0
                    hand_state["crop_sequence"] = -1
                    hand_state["crop_frame"] = None
                hand_state["inferences"] += inference_count - 1
            # On slow devices the primary/recovery pair can exceed its cadence.
            # Leave at least one camera tick for step inference rather than
            # immediately taking the accelerator again on every iteration.
            next_inference_at = max(started_at + interval, completed_at + 0.05)

    stream = None
    try:
        # Start the dashboard and session before the first camera frame. That
        # keeps the reconnect indicator visible and lets capture_frames use
        # its full configured retry window even when AVFoundation opens slowly.
        stream = MjpegFrameServer(
            args.stream_host, args.stream_port,
            output_width=args.stream_width, jpeg_quality=args.stream_jpeg_quality,
        )
        stream.start()
        if args.pairing_code:
            session_id, access_token = pair_session(args.java_url, args.pairing_code)
        elif args.session_id:
            session_id = args.session_id
            access_token = os.getenv("HANDWASH_SESSION_TOKEN", "")
            if not access_token:
                raise RuntimeError("Con --session-id, define HANDWASH_SESSION_TOKEN o usa --pairing-code")
        else:
            session_id, access_token = create_session(args.java_url, args.protocol)
        producer_stream = ProducerEpochStream(
            register_producer_epoch(args.java_url, session_id, access_token)
        )
        stream.set_session_id(session_id)
    except Exception:
        stop_capture.set()
        if stream is not None:
            stream.close()
        with frame_lock:
            active = camera
        if active is not None and active.poll() is None:
            active.terminate()
        capture_thread.join(timeout=4.0)
        if display is not None:
            display.terminate()
        raise
    stream_host, stream_port = stream.address
    print(f"Video del dashboard: http://{stream_host}:{stream_port}/video.mjpg", flush=True)
    pending_detections: Queue = Queue(maxsize=2)
    stop_sender = threading.Event()
    session_ended = threading.Event()
    session_started = threading.Event()
    sender_thread = threading.Thread(
        target=detection_sender,
        args=(pending_detections, stop_sender, args.java_url, session_id, access_token,
              session_ended, producer_stream),
        name="java-detection-sender",
        daemon=True,
    )
    sender_thread.start()

    hand_thread = None
    if hand_model is not None:
        hand_thread = threading.Thread(
            target=detect_hands_continuously,
            name="yolo-hand-localization",
            daemon=True,
        )
        hand_thread.start()

    last_sent_class = None
    last_sent_at = 0.0
    last_infer_at = 0.0
    last_step_recovery_at = 0.0
    step_recovery_error_logged: str | None = None
    last_step_result = None
    last_step_origin = (0, 0)
    last_step_region: tuple[int, int, int, int] | None = None
    last_step_observed_at = 0.0
    last_step_input_sequence = -1
    last_stable_observed_at = 0.0
    last_temporal_observation_at = 0.0
    last_step_class = None
    last_step_confidence = None
    classifier_error_logged: str | None = None
    last_soap_evidence: dict[str, dict[str, Any]] = {}
    temporal_filter = TemporalStepFilter(args.temporal_history, args.temporal_min_votes)
    last_inference_source = "BUSCANDO_MANOS" if hand_model is not None else "CUADRO_COMPLETO"

    def current_motion_evidence(frame_sequence: int | None = None,
                                frame_captured_at: float | None = None) -> dict[str, Any] | None:
        with hand_state_lock:
            motion = hand_state.get("motion")
            snapshot = dict(motion) if motion is not None else None
        if snapshot is None:
            return None
        if frame_sequence is not None and frame_captured_at is not None:
            if not motion_evidence_matches_frame(
                snapshot, frame_sequence, frame_captured_at, args.hand_max_age
            ):
                return None
        return snapshot

    def enqueue_frame_detection(class_name: str, confidence: float,
                                soap_evidence: dict[str, dict[str, Any]] | None,
                                motion_evidence: dict[str, Any] | None,
                                frame_sequence: int,
                                frame_captured_at: float) -> bool:
        if (motion_evidence is not None
            and motion_evidence.get("secuencia") != frame_sequence):
            return False
        if not producer_stream.reserve_frame(frame_sequence):
            return False
        enqueue_latest_detection(pending_detections, (
            class_name, confidence, soap_evidence or {}, motion_evidence,
            frame_sequence, frame_captured_at, "DETECTION",
        ))
        return True

    def enqueue_control_signal(class_name: str, confidence: float,
                               frame_watermark: int,
                               frame_captured_at: float) -> bool:
        control_sequence = producer_stream.reserve_control(frame_watermark)
        if control_sequence is None:
            return False
        enqueue_latest_detection(pending_detections, (
            class_name, confidence, {}, None, None, frame_captured_at,
            "CONTROL", control_sequence, frame_watermark,
        ))
        return True

    def expire_step_observation(now: float) -> None:
        """Invalidate evidence by elapsed capture time, even when inference skips a slot."""
        nonlocal last_sent_class
        nonlocal last_step_class, last_step_confidence, last_soap_evidence
        if not should_publish_visibility_loss(
            last_sent_class, last_stable_observed_at, now, args.missing_detection_grace
        ):
            return
        gap_signal = "OMS_SIN_EVIDENCIA" if model_mode == "PROTOCOLO_OMS" else "Fondo"
        # Controls have their own per-epoch idempotency sequence and carry the
        # current camera watermark, never an old pose/frame identity.
        with frame_lock:
            control_watermark = latest_sequence
            control_captured_at = last_capture_at
        enqueue_control_signal(gap_signal, 1.0, control_watermark, control_captured_at)
        last_sent_class = None
        last_step_class, last_step_confidence, last_soap_evidence = None, None, {}
        temporal_filter.reset()

    last_processed_sequence = -1
    step_inferences = 0
    step_preview_lock = threading.Lock()
    step_preview: dict[str, Any] = {
        "result": None, "origin": (0, 0), "region": None,
        "observed_at": 0.0, "phase": None, "confidence": None,
        "candidate": None, "candidate_confidence": None, "candidate_votes": 0,
        "candidate_required_votes": args.temporal_min_votes,
        "source": last_inference_source, "candidate_model": "detector",
        "step_inference_blocked": True, "inferences": 0,
    }
    stop_video = threading.Event()
    video_errors: list[Exception] = []

    def render_camera_video() -> None:
        """Publish the latest camera image independently of step-model latency."""
        next_display_at = 0.0
        previous_sequence = -1
        previous_capture_sequence = 0
        fps_started_at = time.monotonic()
        frames_seen = 0
        previous_step_inferences = 0
        previous_hand_inferences = 0
        fps = capture_fps = step_fps = hand_fps = 0.0
        try:
            while not stop_video.is_set() and not stop_capture.is_set() and not session_ended.is_set():
                now = time.monotonic()
                if now < next_display_at:
                    stop_video.wait(min(0.02, next_display_at - now))
                    continue
                with step_preview_lock:
                    view = dict(step_preview)
                with hand_state_lock:
                    display_hands = list(hand_state["display_boxes"])
                    display_observed_at = float(hand_state["display_observed_at"])
                    display_sequence = int(hand_state["display_sequence"])
                    pose_hands = list(hand_state["boxes"])
                    pose_observed_at = float(hand_state["observed_at"])
                    pose_proposals = int(hand_state["pose_proposals"])
                    pose_proposals_observed_at = float(
                        hand_state["pose_proposals_observed_at"]
                    )
                    hand_error = hand_state["error"]
                    hand_total = int(hand_state["inferences"])
                    motion_state = hand_state.get("motion")
                    presence_state = dict(hand_state["presence"])
                with frame_lock:
                    render_frame = latest_frame
                    render_sequence = latest_sequence
                if not camera_online.is_set() or render_frame is None:
                    stream.set_camera_connected(False)
                    if hand_model is not None:
                        stream.set_hand_presence({
                            "handsVisible": 0,
                            "warmupElapsedMs": 0,
                            "warmupRequiredMs": args.hand_presence_warmup_ms,
                            "warmupComplete": bool(presence_state.get("ready")),
                            "stepsEnabled": False,
                        })
                    else:
                        stream.set_hand_presence(None)
                    placeholder = np.zeros((height, width, 3), dtype=np.uint8)
                    cv2.putText(placeholder, "CAMARA DESCONECTADA", (75, height // 2 - 20),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 185, 255), 2)
                    cv2.putText(placeholder, "Reconectando iPhone...", (75, height // 2 + 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (230, 230, 230), 2)
                    stream.publish(placeholder)
                    next_display_at = now + 0.25
                    continue
                stream.set_camera_connected(True)
                if render_sequence == previous_sequence:
                    stop_video.wait(0.005)
                    continue
                previous_sequence = render_sequence
                next_display_at = now + 1.0 / args.stream_fps
                hand_presence_gate_active = hand_model is not None
                presence_warmup_complete = bool(presence_state.get("ready"))
                presence_elapsed_ms = fresh_hand_presence_progress_ms(
                    presence_state, now, presence_max_age_seconds
                )
                presence_ready = bilateral_presence_is_fresh(
                    presence_state, now, presence_max_age_seconds
                )
                current_step_result = (
                    view["observed_at"] > 0 and 0 <= now - view["observed_at"] <= 0.5
                    and not view.get("step_inference_blocked", False)
                )
                risk_alert_fresh = bool(
                    model_mode == "PROTOCOLO_OMS"
                    and view.get("phase") == "OMS_CONTACTO_RIESGO"
                    and current_step_result
                )
                step_result_fresh = current_step_result and (
                    not hand_presence_gate_active or presence_ready or risk_alert_fresh
                )
                hand_count = (
                    len(display_hands)
                    if (display_observed_at > 0
                        and 0 <= now - display_observed_at <= args.hand_max_age
                        and display_sequence <= render_sequence) else 0
                )
                pose_count = (
                    len(pose_hands)
                    if pose_observed_at > 0 and 0 <= now - pose_observed_at <= args.hand_max_age else 0
                )
                step_gate_open = (
                    not view.get("step_inference_blocked", False)
                    and (not hand_presence_gate_active or presence_ready)
                )
                if hand_presence_gate_active:
                    stream.set_hand_presence({
                        "handsVisible": pose_count,
                        "warmupElapsedMs": presence_elapsed_ms,
                        "warmupRequiredMs": args.hand_presence_warmup_ms,
                        "warmupComplete": presence_warmup_complete,
                        "stepsEnabled": step_gate_open,
                    })
                else:
                    stream.set_hand_presence(None)
                if not (pose_proposals_observed_at > 0
                        and 0 <= now - pose_proposals_observed_at <= args.hand_max_age):
                    pose_proposals = 0
                motion_fresh = bool(
                    motion_state
                    and 0 <= now - float(motion_state.get("_captured_at", 0.0)) <= args.hand_max_age
                    and int(motion_state.get("secuencia", -1)) <= render_sequence
                )
                intent_hands = int(motion_state.get("_manosParaInicio", 0)) if motion_fresh else 0
                movement_valid = bool(motion_state.get("medicionValida")) if motion_fresh else False
                movement_score = float(motion_state.get("movimientoNormalizado", 0.0)) if motion_fresh else 0.0
                rendered = render_frame.copy()
                if hand_model is not None and hand_count:
                    draw_hand_boxes(rendered, display_hands)
                    draw_hand_focus_inset(rendered, display_hands, pose_count, padding=args.hand_padding)
                if view["region"] is not None and step_result_fresh:
                    left, top, right, bottom = view["region"]
                    cv2.rectangle(rendered, (left, top), (right, bottom), (255, 105, 80), 1)
                if view["result"] is not None and step_result_fresh:
                    draw_step_boxes(rendered, view["result"], view["origin"])
                frames_seen += 1
                elapsed = now - fps_started_at
                if elapsed >= 1.0:
                    fps = frames_seen / elapsed
                    capture_fps = max(0, render_sequence - previous_capture_sequence) / elapsed
                    step_fps = (view["inferences"] - previous_step_inferences) / elapsed
                    hand_fps = (hand_total - previous_hand_inferences) / elapsed
                    previous_capture_sequence = render_sequence
                    previous_step_inferences = view["inferences"]
                    previous_hand_inferences = hand_total
                    frames_seen, fps_started_at = 0, now
                hand_status = (
                    ("pose reintentando | " if hand_error else "")
                    + f"propuestas pose: {pose_proposals} | "
                    + f"cajas ≥{args.hand_crop_confidence:.2f}: {hand_count} | "
                    + f"pose7kp≥{POSE_KEYPOINT_CONFIDENCE:.2f}: {pose_count} | "
                    + f"intención7kp≥{INTENTION_KEYPOINT_CONFIDENCE:.2f}: {intent_hands}/2 "
                    + f"| mov. rel. {movement_score:.2f} (diag.) "
                    + f"| pose {'medible' if movement_valid else 'no medible'}"
                    if hand_model is not None else "manos apagadas"
                )
                phase = view["phase"] if step_result_fresh else None
                if phase and view["confidence"] is not None:
                    phase = f"{phase} {view['confidence']:.2f}"
                if phase is None:
                    if model_mode == "PROTOCOLO_OMS" and hand_count and not pose_count:
                        phase = "esperando pose OMS"
                    elif hand_model is not None and hand_count:
                        phase = "estabilizando paso" if step_result_fresh else "actualizando paso"
                    else:
                        phase = "buscando manos" if hand_model is not None else "sin fase"
                if risk_alert_fresh:
                    phase = "ALERTA: contacto de riesgo"
                elif hand_presence_gate_active and not presence_ready:
                    phase = (
                        f"esperando manos {presence_elapsed_ms / 1000:.1f}/"
                        f"{args.hand_presence_warmup_ms / 1000:.0f}s"
                        if not presence_warmup_complete else "esperando dos manos actuales"
                    )
                line_one = f"YOLO26 {device}{'/FP16' if use_fp16 else ''} | {model_mode} | {phase}"
                source_status = {
                    "RECORTE_MANOS": "ROI manos",
                    "BUSCANDO_MANOS": "buscando",
                    "ESPERANDO_DOS_MANOS": "esperando 2 manos",
                    "CUADRO_COMPLETO": "cuadro completo",
                    "ALERTA_OMS": "alerta OMS",
                }.get(view["source"], view["source"].lower())
                if not step_result_fresh and view["observed_at"] > 0:
                    source_status = "detección desactualizada"
                line_two = (
                    f"{hand_status} | {source_status} | captura {capture_fps:.0f} fps"
                    f" | stream {fps:.0f} fps | paso {step_fps:.1f} fps"
                    + (f" | manos {hand_fps:.1f} fps" if hand_model is not None else "")
                )
                status_color = (70, 235, 120) if pose_count else (0, 185, 255)
                cv2.putText(rendered, line_one, (20, 32), cv2.FONT_HERSHEY_SIMPLEX,
                            0.65, status_color, 2)
                cv2.putText(rendered, line_two, (20, 60), cv2.FONT_HERSHEY_SIMPLEX,
                            0.55, status_color, 2)
                if taxonomy_warning:
                    cv2.putText(rendered, "TAXONOMIA DE PASOS NO VALIDADA", (20, 91),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 80, 255), 2)
                candidate_name = view["candidate"]
                candidate_confidence = view["candidate_confidence"]
                if risk_alert_fresh:
                    candidate_line = "ALERTA OMS: contacto de riesgo; intento reiniciado por seguridad"
                elif hand_presence_gate_active and not step_gate_open:
                    candidate_line = (
                        f"Pasos bloqueados: dos manos estables "
                        f"{presence_elapsed_ms / 1000:.1f}/"
                        f"{args.hand_presence_warmup_ms / 1000:.1f} s"
                        if not presence_warmup_complete
                        else (
                            "Pasos bloqueados: esperando dos manos actuales"
                            if not presence_ready
                            else "Pasos bloqueados: encuadre bilateral incompleto"
                        )
                    )
                elif not step_result_fresh:
                    candidate_line = "YOLO: esperando una observación reciente"
                elif candidate_name and candidate_confidence is not None:
                    candidate_model = "Clasificador" if view["candidate_model"] == "classifier" else "Detector"
                    candidate_line = (
                        f"{candidate_model} candidato: {candidate_name} {candidate_confidence:.2f} | "
                        f"estabilidad {view['candidate_votes']}/{view['candidate_required_votes']} | "
                        f"confirmado: {view['phase'] or 'todavía no'}"
                    )
                else:
                    candidate_line = "YOLO: sin clase de paso candidata en el frame actual"
                cv2.rectangle(rendered, (0, height - 76), (width, height - 38), (20, 20, 20), -1)
                cv2.putText(rendered, candidate_line[:120], (20, height - 51),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.43, (245, 245, 245), 1)
                if hand_model is not None:
                    framing_hands = display_hands[:hand_count]
                    if pose_count:
                        framing_hands = pose_hands[:pose_count]
                    framing = hand_framing_hint(framing_hands, width, height)
                    cv2.rectangle(rendered, (0, height - 38), (width, height), (20, 20, 20), -1)
                    cv2.putText(rendered, framing, (20, height - 13), cv2.FONT_HERSHEY_SIMPLEX,
                                0.62, (245, 245, 245), 2)
                stream.publish(rendered)
                if display is not None:
                    if display.poll() is not None:
                        return
                    try:
                        display.stdin.write(np.ascontiguousarray(rendered).tobytes())
                    except (BrokenPipeError, AttributeError):
                        return
        except Exception as error:
            video_errors.append(error)
        finally:
            stop_video.set()

    video_thread = threading.Thread(target=render_camera_video, name="camera-video-render", daemon=True)
    monitor_stop = threading.Event()
    monitor_thread = threading.Thread(
        target=monitor_session,
        args=(args.java_url, session_id, access_token, monitor_stop,
              session_ended, session_started),
        name="java-session-monitor",
        daemon=True,
    )
    monitor_thread.start()
    restart_requested_at = 0.0
    try:
        video_thread.start()
        while True:
            if session_ended.is_set():
                break
            if stop_capture.is_set():
                raise RuntimeError(capture_failure[0] if capture_failure else
                                   "El flujo de cámara se interrumpió.")
            if stop_video.is_set():
                if video_errors:
                    raise RuntimeError("Falló la publicación del video de cámara") from video_errors[0]
                break
            with frame_lock:
                frame = latest_frame
                sequence = latest_sequence
                captured_at = last_capture_at
                opened_at = camera_started_at
                active = camera
            now = time.monotonic()
            # AVFoundation can take several seconds to produce its first frame,
            # especially while the YOLO models are warming up. Do not kill a
            # newly opened process using the ordinary stale-frame watchdog.
            startup_grace_elapsed = now - opened_at > 5.0
            if active is not None and now - captured_at > 2.0 and startup_grace_elapsed:
                if not capture_restart_requested.is_set():
                    capture_restart_requested.set()
                    restart_requested_at = now
                    camera_online.clear()
                    if active.poll() is None:
                        active.terminate()
                elif (restart_requested_at > 0 and now - restart_requested_at > 3.0
                      and active.poll() is None):
                    active.kill()
            if now - captured_at > 2.0:
                frame = None
            expire_step_observation(now)
            if frame is None or sequence == last_processed_sequence:
                time.sleep(0.02 if frame is None else 0.001)
                continue
            last_processed_sequence = sequence
            if now - last_infer_at >= 1.0 / max(args.inference_fps, 1.0):
                inference_region = (0, 0, frame.shape[1], frame.shape[0])
                inference_frame = frame
                inference_sequence = sequence
                inference_captured_at = captured_at
                fresh_hands = []
                hand_age = float("inf")
                if hand_model is not None:
                    with hand_state_lock:
                        pose_hands = list(hand_state["boxes"])
                        pose_observed_at = float(hand_state["observed_at"])
                        pose_sequence = int(hand_state["pose_sequence"])
                        pose_frame = hand_state["pose_frame"]
                        crop_hands = list(hand_state["crop_boxes"])
                        crop_observed_at = float(hand_state["crop_observed_at"])
                        crop_sequence = int(hand_state["crop_sequence"])
                        crop_frame = hand_state["crop_frame"]
                        presence_state = dict(hand_state["presence"])
                    if model_mode == "PROTOCOLO_OMS":
                        fresh_hands = pose_hands
                        observed_at = pose_observed_at
                        hand_sequence = pose_sequence
                        localized_frame = pose_frame
                    else:
                        fresh_hands = crop_hands
                        observed_at = crop_observed_at
                        hand_sequence = crop_sequence
                        localized_frame = crop_frame
                    now = time.monotonic()
                    hand_age = now - observed_at if observed_at > 0 else float("inf")
                    if (0 <= hand_age <= args.hand_max_age and fresh_hands
                        and localized_frame is not None):
                        crop_bounds = hand_crop_bounds(
                            fresh_hands, localized_frame.shape, padding=args.hand_padding
                        )
                        if crop_bounds is not None:
                            inference_region = crop_bounds
                            # Keep the dashboard frame independent of the exact
                            # image paired with the hand-model boxes.
                            inference_frame = localized_frame
                            inference_sequence = hand_sequence
                            inference_captured_at = observed_at
                        else:
                            fresh_hands = []
                    else:
                        fresh_hands = []
                    if fresh_hands and hand_sequence <= last_step_input_sequence:
                        # A retained localization must never count twice.
                        fresh_hands = []

                detection_processed = False
                presence_gate_waiting = (
                    hand_model is not None
                    and not bilateral_presence_is_fresh(
                        presence_state, now, presence_max_age_seconds
                    )
                )
                risk_only_oms = model_mode == "PROTOCOLO_OMS" and presence_gate_waiting
                if risk_only_oms:
                    # Keep the independent contamination alert available during
                    # startup/occlusion; normal OMS phases remain gated.
                    inference_region = (0, 0, frame.shape[1], frame.shape[0])
                    inference_frame = frame
                    inference_sequence = sequence
                    inference_captured_at = captured_at
                inference_blocked = should_block_step_inference_for_hands(
                    model_mode, hand_model is not None, presence_state,
                    len(fresh_hands), now, presence_max_age_seconds,
                )
                raw_class = raw_confidence = None
                candidate_class = candidate_confidence = None
                candidate_model = "detector"
                classifier_vetoed_detection = False
                raw_soap_evidence: dict[str, dict[str, Any]] = {}
                if inference_blocked:
                    # Never infer a step from a stale, unilateral, or unlocalized frame.
                    last_infer_at = now
                    last_step_result = None
                    last_step_origin = (0, 0)
                    last_step_region = None
                    detection_processed = True
                elif (inference_sequence > last_step_input_sequence
                      and acquire_step_inference_slot()):
                    try:
                        # A failed lock attempt must not consume the 8fps slot;
                        # retry on the next camera frame so steps can use the
                        # window yielded by the hand worker.
                        left, top, right, bottom = inference_region
                        step_frame = inference_frame[top:bottom, left:right].copy()
                        if step_frame.size == 0:
                            raise RuntimeError("El recorte de manos quedó vacío; no se analiza el paso.")
                        frame_classes = step_classes_for_presence(
                            model_mode, step_inference_classes, oms_risk_class_id,
                            not presence_gate_waiting,
                        )
                        frame_predict_options = (
                            predict_options if frame_classes == step_inference_classes
                            else {**predict_options, "classes": frame_classes}
                        )
                        last_step_result = model.predict(step_frame, **frame_predict_options)[0]
                        last_step_input_sequence = inference_sequence
                        last_step_origin = (left, top)
                        last_step_region = inference_region if hand_model is not None and fresh_hands else None
                        raw_class, raw_confidence, raw_soap_evidence = best_detection(
                            last_step_result, model_mode
                        )
                        candidate_class, candidate_confidence = raw_class, raw_confidence
                        detection_processed = True
                        step_inferences += 1
                        if classifier_model is not None:
                            spatial = current_motion_evidence(
                                inference_sequence, inference_captured_at
                            )
                            if classifier_challenge_allowed(
                                raw_class, raw_confidence, model_mode, spatial,
                                time.monotonic() - inference_captured_at,
                                args.hand_max_age, hand_inference_pending.is_set(),
                                args.classifier_challenge_below,
                                args.classifier_authoritative,
                            ):
                                try:
                                    classification = classifier_model.predict(
                                        inference_frame, imgsz=320, device="cpu",
                                        verbose=False, save=False,
                                    )[0]
                                    resolved_class, resolved_confidence, resolution_source = (
                                        arbitrate_uncertain_detection(
                                            raw_class, raw_confidence, classification,
                                            args.classifier_confidence,
                                            args.classifier_challenge_below,
                                            args.classifier_margin,
                                            args.classifier_authoritative,
                                        )
                                    )
                                    if (resolution_source in ("detector", "classifier")
                                        and background_vetoes_detection(
                                            last_step_result, resolved_confidence
                                        )):
                                        resolved_class, resolved_confidence = None, None
                                        resolution_source = "background_veto"
                                    if resolution_source == "classifier":
                                        raw_class, raw_confidence = resolved_class, resolved_confidence
                                        candidate_class, candidate_confidence = resolved_class, resolved_confidence
                                        candidate_model = "classifier"
                                    elif resolution_source in ("classifier_veto", "background_veto"):
                                        # An explicit high-confidence negative may abstain on a
                                        # weak detector class; Fondo also vetoes only when its
                                        # score is at least the final candidate's score.
                                        raw_class, raw_confidence = None, None
                                        candidate_class, candidate_confidence = None, None
                                        classifier_vetoed_detection = True
                                except Exception as classifier_error:
                                    classifier_message = str(classifier_error)
                                    if classifier_message != classifier_error_logged:
                                        print(f"Respaldo de clasificador desactivado: {classifier_message}",
                                              flush=True)
                                        classifier_error_logged = classifier_message
                                    classifier_model = None
                        if (fresh_hands and not presence_gate_waiting and raw_class is None
                            and not classifier_vetoed_detection
                            and time.monotonic() - inference_captured_at <= args.hand_max_age
                            and now - last_step_recovery_at >= args.step_recovery_interval
                            and not hand_inference_pending.is_set()):
                            try:
                                recovered_result = model.predict(
                                    step_frame, **crop_recovery_options
                                )[0]
                                step_inferences += 1
                                recovered_class, recovered_confidence, recovered_evidence = best_detection(
                                    recovered_result, model_mode
                                )
                                step_recovery_error_logged = None
                                if recovered_class is not None:
                                    last_step_result = recovered_result
                                    raw_class = recovered_class
                                    raw_confidence = recovered_confidence
                                    raw_soap_evidence = recovered_evidence
                                    candidate_class = recovered_class
                                    candidate_confidence = recovered_confidence
                            except Exception as recovery_error:
                                recovery_message = str(recovery_error)
                                if recovery_message != step_recovery_error_logged:
                                    print(
                                        f"Aviso: recuperación YOLO de pasos a "
                                        f"{args.fallback_imgsz}px falló: {recovery_message}",
                                        flush=True,
                                    )
                                    step_recovery_error_logged = recovery_message
                            finally:
                                last_step_recovery_at = time.monotonic()
                    finally:
                        # Rate-limit from completion: a slow prediction must not
                        # immediately trigger another pass and saturate the Mac.
                        last_infer_at = time.monotonic()
                        inference_lock.release()

                if detection_processed:
                    # Keep an observation time for the overlay as well as the
                    # backend heartbeat; skipped accelerator slots must not
                    # leave old boxes looking like current predictions.
                    last_step_observed_at = inference_captured_at
                    now = time.monotonic()
                    expire_step_observation(now)
                    if temporal_gap_exceeded(
                        last_temporal_observation_at, inference_captured_at,
                        args.missing_detection_grace,
                    ):
                        temporal_filter.reset()
                    last_temporal_observation_at = inference_captured_at
                    if now - inference_captured_at > args.hand_max_age:
                        # A slow inference cannot refresh the age of its input
                        # or become new evidence for the Java state machine.
                        raw_class, raw_confidence, raw_soap_evidence = None, None, {}
                        candidate_class, candidate_confidence = None, None
                        last_step_result = None
                        last_step_region = None
                    risk_alert = (
                        model_mode == "PROTOCOLO_OMS"
                        and raw_class == "OMS_CONTACTO_RIESGO"
                    )
                    if risk_alert:
                        last_step_class, last_step_confidence = stabilize_detection(
                            temporal_filter, model_mode, raw_class, raw_confidence)
                        last_inference_source = "ALERTA_OMS"
                    elif hand_model is None:
                        last_step_class, last_step_confidence = stabilize_detection(
                            temporal_filter, model_mode, raw_class, raw_confidence)
                        last_inference_source = "CUADRO_COMPLETO"
                    elif len(fresh_hands) >= 2 and not presence_gate_waiting:
                        if last_inference_source != "RECORTE_MANOS":
                            temporal_filter.reset()
                        last_step_class, last_step_confidence = stabilize_detection(
                            temporal_filter, model_mode, raw_class, raw_confidence)
                        last_inference_source = "RECORTE_MANOS"
                    else:
                        temporal_filter.reset()
                        last_step_class, last_step_confidence = None, None
                        last_inference_source = (
                            "ESPERANDO_DOS_MANOS" if hand_model is not None else "BUSCANDO_MANOS"
                        )
                    if presence_gate_waiting and not risk_alert:
                        temporal_filter.reset()
                        last_step_class, last_step_confidence = None, None
                        last_inference_source = "ESPERANDO_DOS_MANOS"
                    last_soap_evidence = raw_soap_evidence if raw_class == last_step_class else {}
                    candidate_votes = temporal_filter.votes_for(candidate_class)
                    if (last_step_class is not None
                        and (model_mode != "PROTOCOLO_OMS"
                             or oms_spatial_evidence_is_valid(
                                 current_motion_evidence(inference_sequence, inference_captured_at),
                                 inference_sequence, inference_captured_at,
                                 args.hand_max_age,
                             ))):
                        last_stable_observed_at = inference_captured_at
                if detection_processed and should_send_step_detection(
                    last_step_class, last_step_confidence, last_sent_class,
                    now - last_sent_at, args.event_heartbeat_ms
                ):
                    movement = current_motion_evidence(inference_sequence, inference_captured_at)
                    if enqueue_frame_detection(
                        last_step_class, last_step_confidence, last_soap_evidence,
                        movement, inference_sequence, inference_captured_at,
                    ):
                        last_sent_class, last_sent_at = last_step_class, now

                if detection_processed:
                    # Publish one coherent preview snapshot. CPU tensors keep
                    # the renderer from waiting on the inference accelerator.
                    preview_result = last_step_result.cpu() if last_step_result is not None else None
                    with step_preview_lock:
                        step_preview.update({
                            "result": preview_result,
                            "origin": last_step_origin,
                            "region": last_step_region,
                            "observed_at": last_step_observed_at,
                            "phase": last_step_class,
                            "confidence": last_step_confidence,
                            "candidate": candidate_class,
                            "candidate_confidence": candidate_confidence,
                            "candidate_model": candidate_model,
                            "candidate_votes": candidate_votes,
                            "candidate_required_votes": temporal_filter.min_votes,
                            "source": last_inference_source,
                            "step_inference_blocked": inference_blocked,
                            "inferences": step_inferences,
                        })
    finally:
        stop_video.set()
        if display is not None and display.poll() is None:
            # Unblock an optional ffplay pipe write before joining its producer.
            display.terminate()
        if video_thread.ident is not None:
            video_thread.join(timeout=2.0)
        monitor_stop.set()
        monitor_thread.join(timeout=2.0)
        stop_hand_inference.set()
        if hand_thread is not None:
            hand_thread.join(timeout=2.0)
        stop_sender.set()
        sender_thread.join(timeout=2.0)
        if last_sent_class is not None and not session_ended.is_set():
            # Stop invalidates continuous observation for both model modes.
            gap_signal = "OMS_SIN_EVIDENCIA" if model_mode == "PROTOCOLO_OMS" else "Fondo"
            with frame_lock:
                control_watermark = latest_sequence
                control_captured_at = last_capture_at
            control_sequence = producer_stream.reserve_control(control_watermark)
            if control_sequence is not None:
                try:
                    send_detection(
                        args.java_url, session_id, access_token, gap_signal, 1.0, {},
                        producer_epoch=producer_stream.producer_epoch,
                        frame_captured_at=control_captured_at,
                        event_type="CONTROL",
                        control_sequence=control_sequence,
                        frame_watermark=control_watermark,
                        require_accepted_ack=False,
                    )
                except PermanentDetectionRejection:
                    pass
        stop_capture.set()
        stream.close()
        if display is not None:
            if display.stdin:
                try:
                    display.stdin.close()
                except (BrokenPipeError, OSError):
                    pass
            display.terminate()
            try:
                display.wait(timeout=3)
            except subprocess.TimeoutExpired:
                display.kill()
                display.wait()
        with frame_lock:
            active = camera
        if active is not None and active.poll() is None:
            active.terminate()
        capture_thread.join(timeout=4.0)
        cv2.destroyAllWindows()


if __name__ == "__main__":
    run()
