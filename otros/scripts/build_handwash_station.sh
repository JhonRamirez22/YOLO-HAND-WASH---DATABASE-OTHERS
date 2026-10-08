#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

for command_name in node npm java mvn jar shasum uvx; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Falta el comando requerido para compilar la estación: $command_name" >&2
    exit 1
  fi
done

npm --prefix frontend run build
mvn -f backend/pom.xml -Pstation-ui clean package

uvx --with-requirements requirements-sbom-generator-macos-arm64.lock \
  --from cyclonedx-bom==7.5.0 --python 3.14.4 cyclonedx-py requirements \
  requirements-camera-macos-arm64.lock \
  --spec-version 1.6 \
  --output-reproducible \
  --output-format JSON \
  --output-file backend/target/handwash-camera-python-sbom.json

JAR_PATH="$ROOT_DIR/backend/target/hand-wash-compliance-1.0.0.jar"
SBOM_PATH="$ROOT_DIR/backend/target/handwash-java-sbom.json"
CAMERA_SBOM_PATH="$ROOT_DIR/backend/target/handwash-camera-python-sbom.json"
if [[ ! -f "$JAR_PATH" ]]; then
  echo "Maven terminó, pero no se generó el JAR esperado: $JAR_PATH" >&2
  exit 1
fi
if [[ ! -s "$SBOM_PATH" ]]; then
  echo "Maven terminó, pero no se generó el SBOM Java esperado: $SBOM_PATH" >&2
  exit 1
fi
if [[ ! -s "$CAMERA_SBOM_PATH" ]]; then
  echo "No se generó el SBOM Python de cámara esperado: $CAMERA_SBOM_PATH" >&2
  exit 1
fi
if ! jar tf "$JAR_PATH" | grep -Fxq 'BOOT-INF/classes/static/index.html'; then
  echo "El JAR no contiene el dashboard compilado en static/index.html." >&2
  exit 1
fi
EXPECTED_STATIC_FILES="$(find "$ROOT_DIR/frontend/dist" -type f -print \
  | sed "s#^$ROOT_DIR/frontend/dist/##" | LC_ALL=C sort)"
PACKAGED_STATIC_FILES="$(jar tf "$JAR_PATH" \
  | awk '/^BOOT-INF\/classes\/static\// && !/\/$/ {sub("^BOOT-INF/classes/static/", ""); print}' \
  | LC_ALL=C sort)"
if [[ "$EXPECTED_STATIC_FILES" != "$PACKAGED_STATIC_FILES" ]]; then
  echo "Los recursos estáticos del JAR no coinciden con frontend/dist; puede haber assets obsoletos." >&2
  exit 1
fi

echo "Paquete local de estación listo: $JAR_PATH"
echo "SBOM CycloneDX Java: $SBOM_PATH"
echo "SBOM CycloneDX de las dependencias Python exactas del lock de cámara: $CAMERA_SBOM_PATH"
echo "Huellas candidatas para revisar y firmar externamente:"
shasum -a 256 "$JAR_PATH" \
  "$SBOM_PATH" \
  "$CAMERA_SBOM_PATH" \
  "$ROOT_DIR/scripts/run_handwash_station.py" \
  "$ROOT_DIR/scripts/run_yolo26_continuity_camera.py" \
  "$ROOT_DIR/requirements-camera-macos-arm64.lock" \
  "$ROOT_DIR/requirements-sbom-generator-macos-arm64.lock"
echo "El manifiesto firmado debe registrar las huellas SBOM/lock bajo stationArtifacts.javaSbomSha256, cameraPythonSbomSha256 y sbomGeneratorLockSha256."
echo "Demostración técnica no clínica (Java + YOLO + dashboard):"
echo "  .venv/bin/python scripts/run_handwash_station.py --unvalidated-demo"
echo "Hospital: requiere evidencia revisada, stationArtifacts firmados y una firma Ed25519 externa."
