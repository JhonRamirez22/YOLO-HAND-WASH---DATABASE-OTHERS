#!/usr/bin/env python3
"""Train a robust seven-step hand-washing detector in Colab.

Recommended source: the public Roboflow handwash-hygiene-zepmy v2 dataset.
It has left/right labels for the movements that are visually ambiguous. Those
labels are merged back to the seven labels expected by the Java state machine.

Examples:
  python scripts/train_handwash_robust.py --roboflow-api-key "$ROBOFLOW_API_KEY"
  python scripts/train_handwash_robust.py --dataset-dir /content/handwash-v2

The active model is never overwritten or activated. With --install-model, the
checkpoint is copied and hash-registered as a separate candidate only.
"""

from __future__ import annotations

import argparse
from itertools import combinations
import hashlib
import json
import math
import os
import shutil
import tempfile
from pathlib import Path

import yaml

try:  # Support both direct CLI execution and package-based integration checks.
    from .audit_yolo_split_duplicates import IMAGE_SUFFIXES, find_duplicate_candidates
except ImportError:  # pragma: no cover - exercised by the command-line entry point
    from audit_yolo_split_duplicates import IMAGE_SUFFIXES, find_duplicate_candidates


TARGET_NAMES = [
    "Paso1_Palmas",
    "Paso2_Dorsos",
    "Paso3_Interdigitales",
    "Paso4_Nudillos",
    "Paso5_Pulgar",
    "Paso6_PuntaDeDedos",
    "Paso7_Circulares",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Entrena YOLO26s robusto para lavado de manos")
    parser.add_argument("--dataset-dir", type=Path, help="Dataset exportado en formato YOLOv8")
    parser.add_argument(
        "--roboflow-api-key",
        default=os.getenv("ROBOFLOW_API_KEY"),
        help="Clave Roboflow; también se puede usar la variable ROBOFLOW_API_KEY",
    )
    parser.add_argument("--workspace", default="tutorial-7lcvi")
    parser.add_argument("--project", default="handwash-hygiene-zepmy")
    parser.add_argument("--version", type=int, default=2)
    parser.add_argument("--base-model", default="yolo26s.pt")
    parser.add_argument("--epochs", type=int, default=120)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--device", default="0")
    parser.add_argument("--output-dir", type=Path, default=Path("runs/handwash_robust"))
    parser.add_argument(
        "--install-model",
        action="store_true",
        help=(
            "Copia best.pt como detector candidato handwash_yolo26s_robust.pt y registra su SHA-256; "
            "no reemplaza ni activa el modelo de producción"
        ),
    )
    parser.add_argument(
        "--min-test-map50",
        type=float,
        default=0.75,
        help="No instala el modelo si el mAP50 de test queda por debajo de este valor",
    )
    return parser.parse_args()


def download_dataset(args: argparse.Namespace) -> Path:
    if args.dataset_dir:
        return args.dataset_dir.resolve()
    if not args.roboflow_api_key:
        raise SystemExit("Usa --dataset-dir o proporciona --roboflow-api-key en Colab")
    try:
        from roboflow import Roboflow
    except ImportError as exc:
        raise SystemExit("Instala primero: pip install roboflow") from exc
    rf = Roboflow(api_key=args.roboflow_api_key)
    dataset = rf.workspace(args.workspace).project(args.project).version(args.version).download("yolov8")
    return Path(dataset.location).resolve()


def normalize_label(name: str) -> int | None:
    key = name.lower().replace("_", "").replace("-", "").replace(" ", "")
    aliases = {
        "step1": 0,
        "paso1palmas": 0,
        "step2left": 1,
        "step2right": 1,
        "paso2dorsos": 1,
        "step3": 2,
        "paso3interdigitales": 2,
        "step4left": 3,
        "step4right": 3,
        "paso4nudillos": 3,
        "step5left": 4,
        "step5right": 4,
        "paso5pulgar": 4,
        "step6left": 5,
        "step6right": 5,
        "paso6puntadededos": 5,
        "step7left": 6,
        "step7right": 6,
        "paso7circulares": 6,
    }
    return aliases.get(key)


def read_names(dataset_dir: Path) -> list[str]:
    yaml_candidates = [dataset_dir / "data.yaml", dataset_dir / "data.yml"]
    config_path = next((path for path in yaml_candidates if path.exists()), None)
    if config_path is None:
        raise FileNotFoundError(f"No se encontró data.yaml en {dataset_dir}")
    config = yaml.safe_load(config_path.read_text())
    names = config.get("names", [])
    if isinstance(names, dict):
        return [str(names[index]) for index in sorted(names, key=lambda value: int(value))]
    return list(names)


def split_directories(dataset_dir: Path, split: str) -> tuple[Path, Path] | None:
    """Resolve Roboflow (`train/images`) and canonical YOLO (`images/train`) layouts."""
    aliases = ("valid", "val") if split == "val" else (split,)
    candidates: list[tuple[Path, Path]] = []
    for source_split in aliases:
        candidates.extend((
            (dataset_dir / source_split / "images", dataset_dir / source_split / "labels"),
            (dataset_dir / "images" / source_split, dataset_dir / "labels" / source_split),
        ))
    populated = [
        pair for pair in candidates
        if pair[0].is_dir() and any(
            path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"}
            for path in pair[0].rglob("*")
        )
    ]
    if len(populated) > 1:
        raise ValueError(
            f"Se encontraron varias carpetas con imágenes para '{split}' en {dataset_dir}; "
            "se requiere una estructura de split inequívoca."
        )
    return populated[0] if populated else None


def merge_split(dataset_dir: Path, output_dir: Path, split: str, source_names: list[str]) -> int:
    source_dirs = split_directories(dataset_dir, split)
    if source_dirs is None:
        return 0
    images_src, labels_src = source_dirs
    images_dst = output_dir / "images" / split
    labels_dst = output_dir / "labels" / split
    images_dst.mkdir(parents=True, exist_ok=True)
    labels_dst.mkdir(parents=True, exist_ok=True)
    copied = 0
    for image_path in sorted(images_src.iterdir()):
        if image_path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".bmp"}:
            continue
        label_path = labels_src / f"{image_path.stem}.txt"
        if not label_path.exists():
            raise FileNotFoundError(
                f"Falta el .txt de etiquetas para {image_path}; usa un archivo vacío explícito "
                "para representar una imagen negativa anotada."
            )
        out_label_lines = []
        for line_number, line in enumerate(label_path.read_text(encoding="utf-8").splitlines(), start=1):
            fields = line.split()
            if not fields:
                continue
            if len(fields) != 5:
                raise ValueError(f"Etiqueta no compatible con YOLO detect en {label_path}:{line_number}")
            try:
                source_id = int(fields[0])
                box = [float(value) for value in fields[1:]]
            except ValueError as error:
                raise ValueError(f"Etiqueta no numérica en {label_path}:{line_number}") from error
            if not 0 <= source_id < len(source_names):
                raise ValueError(
                    f"ID de clase {source_id} fuera de rango en {label_path}:{line_number}; "
                    f"el YAML declara {len(source_names)} clases"
                )
            center_x, center_y, width, height = box
            if (
                not all(math.isfinite(value) for value in box)
                or not 0 <= center_x <= 1
                or not 0 <= center_y <= 1
                or not 0 < width <= 1
                or not 0 < height <= 1
            ):
                raise ValueError(f"Caja YOLO fuera de rango en {label_path}:{line_number}")
            target_id = normalize_label(source_names[source_id])
            if target_id is None:
                raise ValueError(
                    f"Clase fuente sin mapeo explícito '{source_names[source_id]}' "
                    f"en {label_path}:{line_number}; no se descarta silenciosamente"
                )
            out_label_lines.append(" ".join([str(target_id), *fields[1:]]))
        destination_stem = f"{split}_{copied:06d}"
        shutil.copy2(image_path, images_dst / f"{destination_stem}{image_path.suffix.lower()}")
        label_text = "\n".join(out_label_lines)
        (labels_dst / f"{destination_stem}.txt").write_text(
            label_text + ("\n" if label_text else ""), encoding="utf-8"
        )
        copied += 1
    return copied


def prepare_dataset(source_dir: Path, output_dir: Path) -> Path:
    source_names = read_names(source_dir)
    if not source_names:
        raise ValueError(f"El YAML no declara nombres de clase: {source_dir}")
    unmapped_names = [name for name in source_names if normalize_label(name) is None]
    if unmapped_names:
        raise ValueError(f"Clases fuente sin mapeo explícito: {', '.join(unmapped_names)}")
    output_dir.mkdir(parents=True, exist_ok=False)
    train_count = merge_split(source_dir, output_dir, "train", source_names)
    val_count = merge_split(source_dir, output_dir, "val", source_names)
    test_count = merge_split(source_dir, output_dir, "test", source_names)
    if not train_count or not val_count:
        raise RuntimeError(f"Dataset incompleto: train={train_count}, val={val_count}")
    data_yaml = output_dir / "data.yaml"
    dataset_config = {
        "path": str(output_dir.resolve()),
        "train": "images/train",
        "val": "images/val",
        "nc": len(TARGET_NAMES),
        "names": {index: name for index, name in enumerate(TARGET_NAMES)},
    }
    if test_count:
        dataset_config["test"] = "images/test"
    data_yaml.write_text(yaml.safe_dump(dataset_config, sort_keys=False))
    print(f"Dataset fusionado: {train_count} train, {val_count} val, {test_count} test -> {data_yaml}")
    return data_yaml


def ensure_fresh_run_paths(output_dir: Path) -> Path:
    prepared_dir = output_dir.parent / f"{output_dir.name}_dataset"
    for path in (output_dir, prepared_dir):
        if path.exists():
            raise FileExistsError(
                f"La salida ya existe: {path}. No se reutiliza ni elimina para evitar mezclar "
                "pesos/datos viejos; elige un --output-dir nuevo."
            )
    return prepared_dir


def audit_prepared_splits(data_yaml: Path, require_test: bool = False) -> None:
    """Fail closed if train/val/test contain exact or near-identical frames."""
    config = yaml.safe_load(data_yaml.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or not config.get("train") or not config.get("val"):
        raise ValueError(f"El YAML debe definir train y val: {data_yaml}")

    configured_root = Path(str(config.get("path", data_yaml.parent)))
    root = configured_root if configured_root.is_absolute() else (data_yaml.parent / configured_root).resolve()

    split_dirs: dict[str, Path] = {}
    for split in ("train", "val", "test"):
        split_value = config.get(split)
        if split_value is None:
            continue
        if not isinstance(split_value, str):
            raise ValueError(f"El preflight requiere una ruta única para '{split}' en {data_yaml}")
        split_path = Path(split_value)
        split_dir = split_path if split_path.is_absolute() else (root / split_path).resolve()
        has_images = split_dir.is_dir() and any(
            path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
            for path in split_dir.rglob("*")
        )
        if split in {"train", "val"} and not has_images:
            raise ValueError(f"La partición obligatoria '{split}' no contiene imágenes: {split_dir}")
        if has_images:
            split_dirs[split] = split_dir

    if require_test and "test" not in split_dirs:
        raise ValueError(
            "--install-model requiere una partición test independiente y no vacía; "
            "el entrenamiento se cancela antes de invocar YOLO."
        )

    suspicious_pairs: list[str] = []
    for left_name, right_name in combinations(split_dirs, 2):
        _, _, candidates = find_duplicate_candidates(split_dirs[left_name], split_dirs[right_name])
        exact = sum(candidate.exact_bytes for candidate in candidates)
        near = len(candidates) - exact
        print(
            f"Preflight de particiones {left_name}/{right_name}: "
            f"{exact} duplicados exactos, {near} candidatos casi duplicados."
        )
        if candidates:
            suspicious_pairs.append(
                f"{left_name}/{right_name}: {len(candidates)} candidatos "
                f"({exact} exactos, {near} casi duplicados)"
            )
            for candidate in candidates[:3]:
                print(
                    f"  revisar {right_name}={candidate.validation_path} "
                    f"contra {left_name}={candidate.training_path} "
                    f"pHash={candidate.phash_distance} MAE={candidate.mean_absolute_error:.3f}/255"
                )

    if suspicious_pairs:
        details = "; ".join(suspicious_pairs)
        raise RuntimeError(
            "Preflight rechazó el dataset por posible solapamiento entre particiones: "
            f"{details}. No se inició YOLO. Rehaga train/val/test agrupando por video o escena "
            "fuente y vuelva a ejecutar el preflight; los candidatos pHash/MAE requieren "
            "revisión y no prueban por sí solos la identidad del video."
        )


def register_candidate_model(
    artifact: Path,
    manifest_path: Path,
    manifest_key: str,
) -> str:
    """Add one integrity-checked, explicitly non-active candidate to the manifest."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    candidates = manifest.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError(f"El manifiesto no contiene una lista candidates: {manifest_path}")

    digest = hashlib.sha256()
    with artifact.open("rb") as model_file:
        for chunk in iter(lambda: model_file.read(1024 * 1024), b""):
            digest.update(chunk)
    sha256 = digest.hexdigest()

    candidates[:] = [item for item in candidates if not isinstance(item, dict) or item.get("path") != manifest_key]
    candidates.append({
        "path": manifest_key,
        "task": "detect",
        "role": "unvalidated-seven-step-detector-candidate",
        "source": "scripts/train_handwash_robust.py",
        "sha256": sha256,
        "activation": "explicit-only; validate task, class taxonomy, split provenance and camera performance first",
        "limitations": "A passing split-image audit does not prove video/scene independence or clinical performance.",
    })

    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=".model-manifest-", suffix=".tmp", dir=manifest_path.parent
    )
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as temporary_file:
            json.dump(manifest, temporary_file, indent=2, ensure_ascii=False)
            temporary_file.write("\n")
        os.replace(temporary_name, manifest_path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
    return sha256


def train(args: argparse.Namespace, data_yaml: Path) -> Path:
    from ultralytics import YOLO

    model = YOLO(args.base_model)
    model.train(
        data=str(data_yaml),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        project=str(args.output_dir.parent),
        name=args.output_dir.name,
        exist_ok=False,
        patience=30,
        workers=2,
        degrees=12,
        translate=0.10,
        scale=0.50,
        shear=5,
        perspective=0.0005,
        fliplr=0.50,
        mosaic=0.80,
        mixup=0.10,
        close_mosaic=15,
        plots=True,
    )
    best = args.output_dir / "weights" / "best.pt"
    if not best.exists():
        raise FileNotFoundError(f"No se generó el peso esperado: {best}")

    test_images = data_yaml.parent / "images" / "test"
    if test_images.exists() and any(test_images.iterdir()):
        test_model = YOLO(str(best))
        metrics = test_model.val(
            data=str(data_yaml),
            split="test",
            imgsz=args.imgsz,
            batch=args.batch,
            device=args.device,
            workers=2,
            plots=True,
        )
        test_metrics = {
            "map50": float(metrics.box.map50),
            "map50_95": float(metrics.box.map),
            "precision": float(metrics.box.mp),
            "recall": float(metrics.box.mr),
            "perClassMap50_95": [float(value) for value in metrics.box.maps],
        }
        metrics_path = args.output_dir / "test_metrics.json"
        metrics_path.write_text(json.dumps(test_metrics, indent=2) + "\n")
        print(json.dumps(test_metrics, indent=2))
        if args.install_model and test_metrics["map50"] < args.min_test_map50:
            raise RuntimeError(
                f"El modelo no se instala: test mAP50={test_metrics['map50']:.3f} "
                f"< mínimo {args.min_test_map50:.3f}. Revisa ángulos/personas no vistos."
            )

    if args.install_model:
        destination = Path("backend/models/handwash_yolo26s_robust.pt")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(best, destination)
        manifest_path = Path("backend/models/model-manifest.json")
        sha256 = register_candidate_model(
            destination,
            manifest_path,
            destination.as_posix(),
        )
        print(
            f"Detector candidato copiado a {destination} y registrado en {manifest_path} "
            f"(SHA-256 {sha256}). No quedó activo: usa HANDWASH_YOLO_MODEL explícitamente "
            "solo después de validarlo. Descarga también model-manifest.json junto al .pt."
        )
    return best


def main() -> None:
    args = parse_args()
    try:
        prepared_dir = ensure_fresh_run_paths(args.output_dir)
    except FileExistsError as error:
        raise SystemExit(str(error)) from None
    source_dir = download_dataset(args)
    data_yaml = prepare_dataset(source_dir, prepared_dir)
    audit_prepared_splits(data_yaml, require_test=args.install_model)
    best = train(args, data_yaml)
    print(f"Listo: {best}")


if __name__ == "__main__":
    main()
