#!/usr/bin/env python3
"""Validate model roles before a weight is enabled in the live pipeline.

Usage:
    python scripts/validate_handwash_models.py
    python scripts/validate_handwash_models.py --model backend/models/handwash_yolo26s_robust.pt

This intentionally does not promote a model. It only checks task/class
compatibility so a classifier or pose model cannot enter the Java State flow.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from run_yolo26_continuity_camera import (
    sequential_label_taxonomy_warning,
    verify_model_artifact,
    validate_step_model,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model",
        type=Path,
        default=Path("backend/models/handwash_yolo26n_7pasos.pt"),
    )
    args = parser.parse_args()

    if not args.model.exists():
        raise SystemExit(f"No existe el modelo: {args.model}")

    try:
        sha256 = verify_model_artifact(args.model)
    except RuntimeError as exc:
        raise SystemExit(f"PROCEDENCIA RECHAZADA: {exc}") from None

    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit("Instala ultralytics para validar el peso") from exc

    model = YOLO(str(args.model))
    names = model.names if isinstance(model.names, dict) else dict(enumerate(model.names))
    print(f"model={args.model}")
    print(f"sha256={sha256}")
    print(f"task={model.task}")
    print(f"classes={names}")
    try:
        _, mode = validate_step_model(model, str(args.model))
    except RuntimeError as exc:
        raise SystemExit(f"RECHAZADO: {exc}") from None
    print(f"COMPATIBILIDAD ESTRUCTURAL: {mode}; tarea y nombres de clase aceptados por el pipeline Java.")
    warning = sequential_label_taxonomy_warning(names)
    if mode == "FRICCION_PARCIAL" and warning:
        print(f"ADVERTENCIA DE TAXONOMÍA: {warning}")
    print("Este resultado no valida una sesión real ni certifica el procedimiento OMS.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
