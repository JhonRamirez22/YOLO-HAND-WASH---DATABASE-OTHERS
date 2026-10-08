#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"
RUNTIME_DIR="$ROOT_DIR/.runtime"
mkdir -p "$RUNTIME_DIR"

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Falta el comando requerido: $1" >&2
    exit 1
  fi
}

require_command java
require_command mvn
require_command npm
require_command lsof
require_command curl
require_command ffmpeg

if ! ffmpeg -hide_banner -devices 2>&1 | grep -q avfoundation; then
  echo "FFmpeg no tiene el dispositivo AVFoundation requerido para Continuity Camera." >&2
  exit 1
fi

if [[ ! -x "$ROOT_DIR/.venv/bin/python" ]]; then
  echo "No existe el entorno Python del proyecto: $ROOT_DIR/.venv/bin/python" >&2
  exit 1
fi
if [[ ! -d "$ROOT_DIR/frontend/node_modules" ]]; then
  echo "Faltan las dependencias del dashboard. Ejecuta: npm --prefix frontend ci" >&2
  exit 1
fi
MODEL_PATH="${HANDWASH_YOLO_MODEL:-$ROOT_DIR/backend/models/handwash_yolo26n_7pasos.pt}"
if [[ ! -f "$MODEL_PATH" ]]; then
  echo "No existe el modelo YOLO: $MODEL_PATH" >&2
  exit 1
fi
HAND_MODEL_PATH="${HANDWASH_YOLO_HAND_MODEL:-$ROOT_DIR/backend/models/yolo26s-pose-hands.pt}"
if [[ ! -f "$HAND_MODEL_PATH" ]]; then
  echo "No existe el modelo preentrenado de manos requerido: $HAND_MODEL_PATH" >&2
  exit 1
fi
CLASSIFIER_MODEL_PATH="${HANDWASH_YOLO_CLASSIFIER_MODEL:-$ROOT_DIR/backend/models/handwash_who_yolo26m_cls.pt}"
CLASSIFIER_ARGS=(--classifier-model "$CLASSIFIER_MODEL_PATH")
MODEL_CHECK_ARGS=(--check-model --check-hand-model)
if [[ "${HANDWASH_CLASSIFIER_FALLBACK:-1}" == "1" ]]; then
  CLASSIFIER_ARGS+=(--classifier-fallback)
  MODEL_CHECK_ARGS+=(--check-classifier-model)
else
  CLASSIFIER_ARGS+=(--no-classifier-fallback)
fi
if ! "$ROOT_DIR/.venv/bin/python" -c 'import cv2, numpy, requests, torch, ultralytics' >/dev/null 2>&1; then
  echo "El entorno .venv no tiene las dependencias de cámara e inferencia YOLO." >&2
  echo "Instálalas con: $ROOT_DIR/.venv/bin/python -m pip install -r $ROOT_DIR/requirements-camera.txt" >&2
  exit 1
fi
if ! "$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/scripts/run_yolo26_continuity_camera.py" \
  --check-camera "${MODEL_CHECK_ARGS[@]}" --model "$MODEL_PATH" \
  --hand-model "$HAND_MODEL_PATH" "${CLASSIFIER_ARGS[@]}"; then
  echo "No se inició ningún servicio: revisa la cámara del iPhone y los pesos YOLO activos." >&2
  exit 1
fi

JAVA_PID=""
DASHBOARD_PID=""

cleanup() {
  local status=$?
  trap - EXIT INT TERM
  if [[ -n "$DASHBOARD_PID" ]]; then
    kill "$DASHBOARD_PID" 2>/dev/null || true
    wait "$DASHBOARD_PID" 2>/dev/null || true
  fi
  if [[ -n "$JAVA_PID" ]]; then
    kill "$JAVA_PID" 2>/dev/null || true
    wait "$JAVA_PID" 2>/dev/null || true
  fi
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT TERM

start_if_missing() {
  local port="$1"
  local name="$2"
  shift 2
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "[activo] $name :$port"
    return
  fi
  echo "[iniciando] $name :$port"
  "$@" >"$RUNTIME_DIR/$name.log" 2>&1 </dev/null &
  case "$name" in
    java) JAVA_PID=$! ;;
    dashboard) DASHBOARD_PID=$! ;;
  esac
}

wait_for_http() {
  local url="$1"
  local name="$2"
  local expected_marker="${3:-}"
  for _ in {1..60}; do
    local response=""
    if response="$(curl --silent --fail --max-time 2 "$url" 2>/dev/null)"; then
      if [[ -n "$expected_marker" && "$response" != *"$expected_marker"* ]]; then
        local port="${url#http://127.0.0.1:}"
        port="${port%%/*}"
        echo "El puerto de $name responde, pero no pertenece a este proyecto: $url" >&2
        echo "No usaré ni cerraré ese servicio. Proceso que escucha:" >&2
        lsof -nP -iTCP:"$port" -sTCP:LISTEN >&2 || true
        return 1
      fi
      echo "[listo] $name"
      return
    fi
    sleep 1
  done
  echo "No inició $name. Revisa $RUNTIME_DIR/$name.log" >&2
  exit 1
}

HANDWASH_JAVA_PROFILES="${SPRING_PROFILES_ACTIVE:-local}"
start_if_missing 8080 java env SPRING_PROFILES_ACTIVE="$HANDWASH_JAVA_PROFILES" mvn -f backend/pom.xml clean spring-boot:run
wait_for_http "http://127.0.0.1:8080/api/v1/protocols" java '"DOMESTICO"'

cd "$ROOT_DIR/frontend"
start_if_missing 5173 dashboard env \
  VITE_API_URL="http://127.0.0.1:8080" \
  VITE_WS_URL="ws://127.0.0.1:8080" \
  VITE_CAMERA_STREAM_URL="http://127.0.0.1:8091/video.mjpg" \
  "$ROOT_DIR/frontend/node_modules/.bin/vite" --host 127.0.0.1 --port 5173 --strictPort
wait_for_http "http://127.0.0.1:5173/" dashboard 'name="handwash-dashboard" content="handwash-monitor-v1"'
cd "$ROOT_DIR"

echo
echo "Dashboard: http://127.0.0.1:5173/"
echo "YOLO usa la cámara de Continuidad del iPhone y transmite video al dashboard."
echo "Modelo YOLO: $MODEL_PATH"
if [[ "${HANDWASH_CLASSIFIER_FALLBACK:-1}" == "1" ]]; then
  echo "Clasificador auxiliar: $CLASSIFIER_MODEL_PATH"
else
  echo "Clasificador auxiliar: desactivado por HANDWASH_CLASSIFIER_FALLBACK=0"
fi
if [[ -n "${HANDWASH_PAIRING_CODE:-}" ]]; then
  echo "El visor se vinculará a la sesión ya creada en el dashboard."
else
  echo "El visor creará una sesión y mostrará su código aquí; vincúlala en el dashboard."
fi
echo "Mantén esta terminal abierta. Ctrl+C detiene la cámara y los servicios que inició este script."
echo

CAMERA_ARGS=(--java-url http://127.0.0.1:8080 --model "$MODEL_PATH" --hand-model "$HAND_MODEL_PATH" "${CLASSIFIER_ARGS[@]}")
if [[ -n "${HANDWASH_PAIRING_CODE:-}" ]]; then
  CAMERA_ARGS+=(--pairing-code "$HANDWASH_PAIRING_CODE")
fi
"$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/scripts/run_yolo26_continuity_camera.py" "${CAMERA_ARGS[@]}"
