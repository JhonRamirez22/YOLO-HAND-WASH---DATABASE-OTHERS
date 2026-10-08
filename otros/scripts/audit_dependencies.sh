#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

for tool in go uvx npm; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "Falta la herramienta requerida para SCA: $tool" >&2
    exit 1
  fi
done

cd "$PROJECT_ROOT"
echo "== SCA Java y dependencias Python declaradas bajo backend/ (OSV-Scanner 2.6.0) =="
go run github.com/google/osv-scanner/v2/cmd/osv-scanner@v2.6.0 scan source backend

echo "== SCA del lock Python exacto de la cámara =="
uvx --python 3.14.4 --from pip-audit pip-audit -r requirements-camera-macos-arm64.lock

echo "== SCA del lock con hashes del generador SBOM (build-only) =="
uvx --python 3.14.4 --from pip-audit pip-audit -r requirements-sbom-generator-macos-arm64.lock

echo "== SCA de dependencias frontend, incluidas las herramientas de build =="
npm --prefix frontend audit --audit-level=moderate
