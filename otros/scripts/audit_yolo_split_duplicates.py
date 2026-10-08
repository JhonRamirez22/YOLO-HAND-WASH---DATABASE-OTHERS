#!/usr/bin/env python3
"""Screen YOLO train/validation splits for exact and near-duplicate frames.

Read-only: does not move images, edit labels, persist frames, or train a model.
Near matches are review candidates, not proof of source-video identity.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
from pathlib import Path
import sys

import cv2
import numpy as np
import yaml


ROOT = Path(__file__).resolve().parents[1]
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}


@dataclass(frozen=True)
class ImageSignature:
    path: Path
    sha256: str
    perceptual_hash: int
    gray_thumbnail: np.ndarray


@dataclass(frozen=True)
class DuplicateCandidate:
    validation_path: Path
    training_path: Path
    exact_bytes: bool
    phash_distance: int
    mean_absolute_error: float


def _image_paths(directory: Path) -> list[Path]:
    if not directory.is_dir():
        raise FileNotFoundError(f"No existe la partición de imágenes: {directory}")
    return sorted(
        path for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )


def _signature(path: Path) -> ImageSignature:
    encoded = path.read_bytes()
    image = cv2.imdecode(np.frombuffer(encoded, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None or image.size == 0:
        raise ValueError(f"No se pudo leer la imagen: {path}")

    thumb = cv2.resize(image, (64, 64), interpolation=cv2.INTER_AREA)
    dct = cv2.dct(cv2.resize(image, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32))
    coefficients = dct[:8, :8].flatten()[1:]
    median = float(np.median(coefficients))
    perceptual_hash = 0
    for coefficient in coefficients:
        perceptual_hash = (perceptual_hash << 1) | int(coefficient > median)

    return ImageSignature(
        path=path,
        sha256=hashlib.sha256(encoded).hexdigest(),
        perceptual_hash=perceptual_hash,
        gray_thumbnail=thumb,
    )


def find_duplicate_candidates(
    train_dir: Path,
    val_dir: Path,
    max_phash_distance: int = 4,
    max_pixel_mae: float = 5.0,
) -> tuple[list[Path], list[Path], list[DuplicateCandidate]]:
    train_paths = _image_paths(train_dir)
    val_paths = _image_paths(val_dir)
    if not train_paths or not val_paths:
        raise ValueError("Train y validation deben contener imágenes para comparar")

    train_signatures = [_signature(path) for path in train_paths]
    val_signatures = [_signature(path) for path in val_paths]
    train_by_sha: dict[str, ImageSignature] = {}
    for signature in train_signatures:
        train_by_sha.setdefault(signature.sha256, signature)

    candidates: list[DuplicateCandidate] = []
    for validation in val_signatures:
        exact = train_by_sha.get(validation.sha256)
        if exact is not None:
            candidates.append(DuplicateCandidate(
                validation.path,
                exact.path,
                True,
                (validation.perceptual_hash ^ exact.perceptual_hash).bit_count(),
                0.0,
            ))
            continue

        ranked = sorted(
            (
                ((validation.perceptual_hash ^ training.perceptual_hash).bit_count(), training)
                for training in train_signatures
            ),
            key=lambda item: (item[0], str(item[1].path)),
        )
        best: tuple[float, int, ImageSignature] | None = None
        for distance, training in ranked:
            if distance > max_phash_distance:
                break
            mae = float(np.abs(
                validation.gray_thumbnail.astype(np.int16)
                - training.gray_thumbnail.astype(np.int16)
            ).mean())
            item = (mae, distance, training)
            if best is None or (mae, distance, str(training.path)) < (
                best[0], best[1], str(best[2].path)
            ):
                best = item

        if best is not None and best[0] <= max_pixel_mae:
            candidates.append(DuplicateCandidate(
                validation.path, best[2].path, False, best[1], best[0]
            ))

    return train_paths, val_paths, candidates


def _resolve_split(root: Path, path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else (root / path).resolve()


def _resolve_dataset_root(data_yaml: Path, config: dict[str, object]) -> Path:
    configured = Path(str(config.get("path", ".")).strip()).expanduser()
    if configured.is_absolute():
        return configured.resolve()
    candidates: list[Path] = []
    for base in (data_yaml.parent, Path.cwd(), ROOT):
        candidate = (base / configured).resolve()
        if candidate not in candidates:
            candidates.append(candidate)
    for candidate in candidates:
        if any(
            isinstance(config.get(split), str)
            and _resolve_split(candidate, str(config[split])).is_dir()
            for split in ("train", "val", "test")
        ) or (
            isinstance(config.get("valid"), str)
            and _resolve_split(candidate, str(config["valid"])).is_dir()
        ):
            return candidate
    return candidates[0]


def _dataset_split_paths(data_yaml: Path) -> tuple[Path, Path]:
    config = yaml.safe_load(data_yaml.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or not config.get("train") or not (config.get("val") or config.get("valid")):
        raise ValueError(f"El YAML debe declarar las rutas train y val: {data_yaml}")
    root = _resolve_dataset_root(data_yaml.resolve(), config)
    val_value = config.get("val", config.get("valid"))
    return _resolve_split(root, str(config["train"])), _resolve_split(root, str(val_value))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data", type=Path, default=ROOT / "datasets/handwash_public_7steps.yaml",
        help="YAML del dataset YOLO con path, train y val",
    )
    parser.add_argument("--max-phash-distance", type=int, default=4)
    parser.add_argument("--max-pixel-mae", type=float, default=5.0)
    parser.add_argument(
        "--report-only", action="store_true",
        help="Devuelve código 0 aun si hay candidatos para revisión",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not 0 <= args.max_phash_distance <= 64 or args.max_pixel_mae < 0:
        print("Umbral fuera de rango: pHash debe estar entre 0 y 64; MAE no puede ser negativo.", file=sys.stderr)
        return 2

    try:
        train_dir, val_dir = _dataset_split_paths(args.data.resolve())
        train_paths, val_paths, candidates = find_duplicate_candidates(
            train_dir, val_dir, args.max_phash_distance, args.max_pixel_mae
        )
    except (FileNotFoundError, OSError, ValueError, yaml.YAMLError) as error:
        print(f"Error auditando dataset: {error}", file=sys.stderr)
        return 2

    exact_count = sum(candidate.exact_bytes for candidate in candidates)
    near_count = len(candidates) - exact_count
    print(f"Imágenes train: {len(train_paths)} | validation: {len(val_paths)}")
    print(f"Coincidencias binarias exactas: {exact_count}")
    print(
        f"Candidatos casi duplicados: {near_count} "
        f"(pHash <= {args.max_phash_distance}, MAE <= {args.max_pixel_mae:g}/255)"
    )
    if candidates:
        print("REVISAR: los candidatos pueden inflar la métrica de validación; no prueban por sí solos el video de origen.")
        for candidate in candidates:
            kind = "exacto" if candidate.exact_bytes else "casi duplicado"
            print(
                f"{kind}\tval={candidate.validation_path}\ttrain={candidate.training_path}"
                f"\tphash={candidate.phash_distance}\tmae={candidate.mean_absolute_error:.3f}"
            )
        return 0 if args.report_only else 1

    print("PASS: no se encontraron pares sospechosos con estos umbrales.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
