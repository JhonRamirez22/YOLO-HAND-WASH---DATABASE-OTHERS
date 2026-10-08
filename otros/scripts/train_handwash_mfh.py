#!/usr/bin/env python3
"""Train a multi-view hand-washing step classifier from the MFH dataset.

MFH is an image classification dataset (not a YOLO bounding-box dataset), so
this produces an optional Ultralytics classification checkpoint.  The gateway
can use it as a second opinion when the seven-step detector is uncertain.

Typical Colab usage:
  python scripts/train_handwash_mfh.py \
      --dataset-dir /content/SceneCategory_Frame_final_7classes_6scenes \
      --epochs 40 --device 0 --install-model
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
from pathlib import Path


TARGET_NAMES = [
    "Paso1_Palmas",
    "Paso2_Dorsos",
    "Paso3_Interdigitales",
    "Paso4_Nudillos",
    "Paso5_Pulgar",
    "Paso6_PuntaDeDedos",
    "Paso7_Circulares",
]
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Entrena un clasificador MFH de siete pasos")
    parser.add_argument("--dataset-dir", type=Path, required=True)
    parser.add_argument("--base-model", default="yolo26s-cls.pt")
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--imgsz", type=int, default=224)
    parser.add_argument("--batch", type=int, default=64)
    parser.add_argument("--device", default="0")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output-dir", type=Path, default=Path("runs/handwash_mfh"))
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=None,
        help="Copia best.pt/last.pt y resultados a esta carpeta después de cada checkpoint",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reanuda desde backup-dir/last.pt si existe",
    )
    parser.add_argument(
        "--install-model",
        action="store_true",
        help="Copia best.pt a backend/models/handwash_multiview.pt",
    )
    return parser.parse_args()


def label_for_path(path: Path) -> int | None:
    """Find Step1..Step7 in any ancestor; tolerate left/right suffixes."""
    for part in reversed(path.parts):
        normalized = part.lower().replace(" ", "").replace("_", "").replace("-", "")
        match = re.search(r"step(\d+)", normalized)
        if match:
            value = int(match.group(1))
            return value - 1 if 1 <= value <= 7 else None
        if normalized.isdigit() and 1 <= int(normalized) <= 7:
            return int(normalized) - 1
    return None


def split_for_path(path: Path) -> str:
    """Prefer the dataset's explicit split; otherwise hold out scenes 5 and 6."""
    parts = {part.lower() for part in path.parts}
    if parts.intersection({"test", "testing", "val", "valid", "validation"}):
        return "val"
    if parts.intersection({"train", "training"}):
        return "train"
    for part in path.parts:
        match = re.search(r"scene[_ -]?(\d+)", part.lower())
        if match:
            return "val" if int(match.group(1)) >= 5 else "train"
    # A source without scene names has no defensible cross-view split. Keep a
    # deterministic 80/20 split based on the relative parent path.
    digest = hashlib.sha1(str(path.parent).encode("utf-8")).digest()
    return "val" if digest[0] % 5 == 0 else "train"


def link_or_copy(source: Path, destination: Path) -> None:
    source_resolved = source.resolve()
    if destination.is_symlink():
        try:
            if destination.resolve() == source_resolved:
                return
        except OSError:
            pass
        destination.unlink(missing_ok=True)
    elif destination.exists():
        try:
            if destination.samefile(source):
                return
        except OSError:
            pass
        destination.unlink()
    try:
        destination.symlink_to(source_resolved)
    except FileExistsError:
        if destination.is_symlink() and destination.resolve() == source_resolved:
            return
        raise
    except OSError:
        shutil.copy2(source, destination)


def prepare_dataset(source_dir: Path, output_dir: Path) -> tuple[int, int]:
    if not source_dir.exists():
        raise FileNotFoundError(source_dir)
    counts = {"train": 0, "val": 0}
    for image_path in sorted(source_dir.rglob("*")):
        if not image_path.is_file() or image_path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        class_id = label_for_path(image_path)
        if class_id is None:
            continue
        split = split_for_path(image_path)
        class_dir = output_dir / split / TARGET_NAMES[class_id]
        class_dir.mkdir(parents=True, exist_ok=True)
        destination = class_dir / f"{counts[split]:09d}_{image_path.name}"
        link_or_copy(image_path, destination)
        counts[split] += 1
    if min(counts.values()) == 0:
        raise RuntimeError(
            "No se pudieron detectar imágenes con carpetas Step1..Step7. "
            f"Revisa la estructura de {source_dir}."
        )
    print(f"MFH preparado: {counts['train']} train, {counts['val']} val -> {output_dir}")
    return counts["train"], counts["val"]


def train(args: argparse.Namespace, prepared_dir: Path) -> Path:
    from ultralytics import YOLO

    backup_dir = args.backup_dir.resolve() if args.backup_dir else None
    resume_checkpoint = backup_dir / "last.pt" if backup_dir else None
    if args.resume and resume_checkpoint and resume_checkpoint.exists():
        model = YOLO(str(resume_checkpoint))
    else:
        model = YOLO(args.base_model)

    if backup_dir:
        backup_dir.mkdir(parents=True, exist_ok=True)

        def backup_checkpoint(trainer) -> None:
            weights_dir = Path(trainer.save_dir) / "weights"
            for filename in ("best.pt", "last.pt"):
                source = weights_dir / filename
                if source.exists():
                    shutil.copy2(source, backup_dir / filename)
            for filename in ("results.csv", "args.yaml"):
                source = Path(trainer.save_dir) / filename
                if source.exists():
                    shutil.copy2(source, backup_dir / filename)

        model.add_callback("on_model_save", backup_checkpoint)

    model.train(
        data=str(prepared_dir),
        task="classify",
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        workers=args.workers,
        project=str(args.output_dir.parent),
        name=args.output_dir.name,
        exist_ok=True,
        patience=8,
        degrees=18,
        translate=0.12,
        scale=0.45,
        shear=6,
        perspective=0.0008,
        fliplr=0.50,
        plots=True,
        resume=bool(args.resume and resume_checkpoint and resume_checkpoint.exists()),
    )
    save_dir = Path(model.trainer.save_dir)
    best = save_dir / "weights" / "best.pt"
    if backup_dir and (backup_dir / "best.pt").exists():
        best = backup_dir / "best.pt"
    if not best.exists():
        raise FileNotFoundError(best)
    metrics = YOLO(str(best)).val(data=str(prepared_dir), imgsz=args.imgsz, batch=args.batch, device=args.device)
    print(f"Validación MFH: top1={float(metrics.top1):.4f}, top5={float(metrics.top5):.4f}")
    if args.install_model:
        destination = Path("backend/models/handwash_multiview.pt")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(best, destination)
        print(f"Clasificador multivista instalado en {destination}; el detector principal no fue reemplazado.")
    return best


def main() -> None:
    args = parse_args()
    prepared_dir = args.output_dir.parent / f"{args.output_dir.name}_dataset"
    prepare_dataset(args.dataset_dir.resolve(), prepared_dir)
    print(f"Listo: {train(args, prepared_dir)}")


if __name__ == "__main__":
    main()
