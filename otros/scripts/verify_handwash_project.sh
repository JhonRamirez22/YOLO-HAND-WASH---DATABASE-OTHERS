#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$PROJECT_ROOT/.venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
  echo "Falta el Python del proyecto: $PYTHON" >&2
  exit 1
fi
if ! command -v mvn >/dev/null 2>&1; then
  echo "No se encontró Maven (mvn) en PATH." >&2
  exit 1
fi
if ! command -v npm >/dev/null 2>&1; then
  echo "No se encontró npm en PATH." >&2
  exit 1
fi
if ! command -v go >/dev/null 2>&1; then
  echo "No se encontró Go en PATH (requerido por scripts/audit_dependencies.sh)." >&2
  exit 1
fi
if ! command -v uvx >/dev/null 2>&1; then
  echo "No se encontró uvx en PATH (requerido por scripts/audit_dependencies.sh)." >&2
  exit 1
fi
if [[ ! -d "$PROJECT_ROOT/frontend/node_modules" ]]; then
  echo "Faltan dependencias locales de frontend/node_modules." >&2
  exit 1
fi

cd "$PROJECT_ROOT"
echo "== Escaneo de vulnerabilidades de dependencias =="
"$PROJECT_ROOT/scripts/audit_dependencies.sh"

echo "== Backend Java/Spring Boot =="
mvn -f backend/pom.xml test

echo "== Pruebas Python offline (sin entrenamiento ni cámara física) =="
cd "$PROJECT_ROOT/scripts"
"$PYTHON" -m unittest \
  test_run_yolo26_continuity_camera \
  test_run_handwash_station \
  test_evaluate_derived_detector \
  test_evaluate_derived_sequence \
  test_handwash_motion \
  test_dataset_contracts \
  test_audit_yolo_split_duplicates \
  test_prepare_oms_review_frames \
  test_prepare_grouped_yolo_dataset

echo "== Preflight de modelos activos (hash, rol y taxonomía; sin cámara ni entrenamiento) =="
cd "$PROJECT_ROOT"
"$PYTHON" "$PROJECT_ROOT/scripts/run_yolo26_continuity_camera.py" \
  --check-model --check-hand-model --check-classifier-model

echo "== Frontend TypeScript/React =="
cd "$PROJECT_ROOT/frontend"
npm test -- --run
npm run build
npm run lint

echo "Verificación técnica completada; no certifica precisión clínica ni autoriza uso hospitalario."
echo "No se entrenaron modelos ni se accedió a una cámara física."
