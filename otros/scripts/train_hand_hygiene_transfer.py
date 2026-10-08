#!/usr/bin/env python3
"""Train an isolated seven-step detector using the Roboflow hand-hygiene set.

The Roboflow export has one generic class, so it is used only for visual-domain
pretraining. The resulting checkpoint is then fine-tuned on the project's
seven canonical step classes. No active model or Java source is overwritten.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import torch
import yaml
from ultralytics import YOLO

from run_yolo26_continuity_camera import REQUIRED_STEP_CLASSES, validate_step_model


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTEXT_DATA = Path("/Users/jhon/Downloads/Hand-Hygiene.v1i.yolo26")
DEFAULT_STEP_DATA = ROOT / "datasets/handwash_public_7steps"
DEFAULT_BASE_MODEL = ROOT / "yolo26n.pt"
DEFAULT_OUTPUT = ROOT / "runs/detect/handwash-hygiene-transfer"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}


def class_names(config: dict[str, Any]) -> list[str]:
    names = config.get("names")
    if isinstance(names, list):
        result = [str(name) for name in names]
    elif isinstance(names, dict):
        result = [str(names[key]) for key in sorted(names, key=lambda value: int(value))]
    else:
        raise ValueError("El YAML debe declarar `names` como lista o mapa ordenado.")
    if config.get("nc", len(result)) != len(result):
        raise ValueError(f"nc={config.get('nc')} pero names contiene {len(result)} clases.")
    return result


def validate_split(root: Path, image_dir: str, label_dir: str, nc: int) -> tuple[int, int, list[int]]:
    images_path = root / image_dir
    labels_path = root / label_dir
    if not images_path.is_dir() or not labels_path.is_dir():
        raise FileNotFoundError(f"Falta el split {images_path} o sus etiquetas {labels_path}.")

    images = {path.stem for path in images_path.iterdir()
              if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES}
    labels = {path.stem for path in labels_path.glob("*.txt")}
    if not images:
        raise ValueError(f"No hay imágenes en {images_path}.")
    if images != labels:
        missing_labels = sorted(images - labels)[:5]
        orphan_labels = sorted(labels - images)[:5]
        raise ValueError(
            f"Imágenes/etiquetas no coinciden en {root}: "
            f"sin etiqueta={missing_labels}, etiqueta huérfana={orphan_labels}."
        )

    class_counts = [0] * nc
    box_count = 0
    for stem in labels:
        label_path = labels_path / f"{stem}.txt"
        for line_number, line in enumerate(label_path.read_text(encoding="utf-8").splitlines(), 1):
            parts = line.split()
            if len(parts) != 5:
                raise ValueError(f"Formato YOLO inválido en {label_path}:{line_number}.")
            try:
                class_id = int(parts[0])
                x, y, width, height = map(float, parts[1:])
            except ValueError as error:
                raise ValueError(f"Valor no numérico en {label_path}:{line_number}.") from error
            if not 0 <= class_id < nc:
                raise ValueError(f"Clase {class_id} fuera de rango en {label_path}:{line_number}.")
            if not all(0.0 <= value <= 1.0 for value in (x, y, width, height)) or width <= 0 or height <= 0:
                raise ValueError(f"Caja fuera de rango en {label_path}:{line_number}.")
            class_counts[class_id] += 1
            box_count += 1
    return len(images), box_count, class_counts


def write_dataset_yaml(output_path: Path, dataset_root: Path,
                       train_images: str, val_images: str,
                       names: list[str]) -> None:
    payload = {
        "path": str(dataset_root.resolve()),
        "train": train_images,
        "val": val_images,
        "nc": len(names),
        "names": {index: name for index, name in enumerate(names)},
    }
    output_path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def choose_device(requested: str) -> int | str:
    if requested != "auto":
        return int(requested) if requested.isdigit() else requested
    if torch.cuda.is_available():
        return 0
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def validate_inputs(context_root: Path, step_root: Path, base_model: Path) -> tuple[Path, Path, list[str]]:
    context_root = context_root.expanduser().resolve()
    step_root = step_root.expanduser().resolve()
    base_model = base_model.expanduser().resolve()
    context_yaml = context_root / "data.yaml"
    step_yaml = ROOT / "datasets/handwash_public_7steps.yaml"
    if not context_yaml.is_file():
        raise FileNotFoundError(f"No existe el YAML de Roboflow: {context_yaml}")
    if not step_yaml.is_file():
        raise FileNotFoundError(f"No existe el YAML de siete pasos: {step_yaml}")
    if not base_model.is_file():
        raise FileNotFoundError(f"No existe el modelo base local: {base_model}")

    context_config = yaml.safe_load(context_yaml.read_text(encoding="utf-8")) or {}
    context_names = class_names(context_config)
    if context_names != ["Performing-Hand-Hygiene"]:
        raise ValueError(f"Se esperaba la clase genérica de Roboflow; se encontró {context_names}.")
    if context_config.get("nc") != 1:
        raise ValueError("El dataset Roboflow debe tener una única clase para esta etapa auxiliar.")

    step_config = yaml.safe_load(step_yaml.read_text(encoding="utf-8")) or {}
    step_names = class_names(step_config)
    if tuple(step_names) != tuple(REQUIRED_STEP_CLASSES):
        raise ValueError(
            "Las etiquetas del dataset de ajuste no coinciden, en orden, con las clases que Java ya acepta: "
            f"{step_names}"
        )

    for split, folder in (("train", "train"), ("val", "valid"), ("test", "test")):
        count, boxes, classes = validate_split(
            context_root, f"{folder}/images", f"{folder}/labels", 1
        )
        print(f"Roboflow {split}: {count} imágenes, {boxes} cajas, clases={classes}")
    for split in ("train", "val"):
        count, boxes, classes = validate_split(
            step_root, f"images/{split}", f"labels/{split}", len(step_names)
        )
        print(f"Pasos {split}: {count} imágenes, {boxes} cajas, distribución={classes}")
    return context_yaml, step_yaml, step_names


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context-dataset", type=Path, default=DEFAULT_CONTEXT_DATA,
                        help="Directorio del export Roboflow de una clase.")
    parser.add_argument("--step-dataset", type=Path, default=DEFAULT_STEP_DATA,
                        help="Directorio datasets/handwash_public_7steps.")
    parser.add_argument("--base-model", type=Path, default=DEFAULT_BASE_MODEL,
                        help="Checkpoint YOLO26n inicial ya presente localmente.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help="Carpeta base para candidatos aislados; nunca es backend/models.")
    parser.add_argument("--context-epochs", type=int, default=20)
    parser.add_argument("--step-epochs", type=int, default=50)
    parser.add_argument("--imgsz", type=int, default=416,
                        help="Alineado con la resolución primaria del capturador Mac.")
    parser.add_argument("--batch", type=int, default=4)
    parser.add_argument("--workers", type=int, default=0,
                        help="En macOS se recomienda 0 para evitar problemas de procesos.")
    parser.add_argument("--cpu-threads", type=int, default=3,
                        help="Límite de hilos PyTorch cuando se entrena en CPU.")
    parser.add_argument("--device", default="auto", help="auto, cpu, mps o índice CUDA.")
    parser.add_argument("--check-only", action="store_true",
                        help="Revisa los datasets y hardware sin iniciar entrenamiento.")
    args = parser.parse_args()

    context_root = args.context_dataset.expanduser().resolve()
    step_root = args.step_dataset.expanduser().resolve()
    base_model = args.base_model.expanduser().resolve()
    context_source_yaml, step_source_yaml, step_names = validate_inputs(
        context_root, step_root, base_model
    )
    device = choose_device(args.device)
    print(f"Dispositivo: {device}; MPS disponible={torch.backends.mps.is_available()}; "
          f"CUDA disponible={torch.cuda.is_available()}")
    print("El Roboflow de una clase NO se mapeará a un paso; solo preentrena el dominio visual.")
    print("Java conserva el State/Strategy y recibe únicamente las siete etiquetas canónicas.")
    if args.check_only:
        print("Preflight correcto; no se crearon archivos ni se inició entrenamiento.")
        return 0
    if (args.context_epochs < 1 or args.step_epochs < 1 or args.imgsz < 64
            or args.batch < 1 or args.cpu_threads < 1):
        raise ValueError("Épocas, batch e cpu-threads deben ser positivos (imgsz >= 64).")
    if device == "cpu":
        torch.set_num_threads(args.cpu_threads)
        try:
            torch.set_num_interop_threads(1)
        except RuntimeError:
            pass
        print(f"Entrenamiento CPU limitado a {args.cpu_threads} hilos PyTorch.")

    output_base = args.output.expanduser().resolve()
    run_root = output_base / datetime.now().strftime("%Y%m%d-%H%M%S")
    run_root.mkdir(parents=True, exist_ok=False)
    context_yaml = run_root / "context-dataset.yaml"
    step_yaml = run_root / "seven-step-dataset.yaml"
    write_dataset_yaml(context_yaml, context_root, "train/images", "valid/images",
                       ["Performing-Hand-Hygiene"])
    write_dataset_yaml(step_yaml, step_root, "images/train", "images/val", step_names)
    (run_root / "training-plan.json").write_text(json.dumps({
        "baseModel": str(base_model),
        "contextDatasetYaml": str(context_source_yaml),
        "stepDatasetYaml": str(step_source_yaml),
        "contextClasses": ["Performing-Hand-Hygiene"],
        "finalClasses": step_names,
        "contextEpochs": args.context_epochs,
        "stepEpochs": args.step_epochs,
        "imageSize": args.imgsz,
        "device": device,
        "activeModelModified": False,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    common = {
        "imgsz": args.imgsz,
        "batch": args.batch,
        "device": device,
        "workers": args.workers,
        "cache": False,
        "amp": isinstance(device, int),
        "optimizer": "AdamW",
        "patience": 10,
        "plots": True,
        "save": True,
        "save_period": -1,
        "verbose": True,
        "seed": 42,
    }
    print(f"Etapa 1/2: adaptación de dominio ({args.context_epochs} épocas) → {run_root / 'context'}")
    context_model = YOLO(str(base_model))
    context_model.train(
        data=str(context_yaml), epochs=args.context_epochs, project=str(run_root), name="context",
        exist_ok=False, close_mosaic=min(5, args.context_epochs), **common,
    )
    context_best = run_root / "context/weights/best.pt"
    if not context_best.is_file():
        raise FileNotFoundError(f"Ultralytics no produjo el checkpoint esperado: {context_best}")

    print("Etapa 2/2: transferencia y ajuste a los siete pasos canónicos. "
          "La cabeza de detección se adapta de 1 a 7 clases.")
    step_model = YOLO(str(context_best))
    step_model.train(
        data=str(step_yaml), epochs=args.step_epochs, project=str(run_root), name="seven-steps",
        exist_ok=False, close_mosaic=min(10, args.step_epochs),
        **{**common, "patience": 15},
    )
    candidate = run_root / "seven-steps/weights/best.pt"
    if not candidate.is_file():
        raise FileNotFoundError(f"Ultralytics no produjo el checkpoint final: {candidate}")

    final_model = YOLO(str(candidate))
    _, mode = validate_step_model(final_model, str(candidate))
    if mode != "FRICCION_PARCIAL":
        raise RuntimeError(f"Candidato final inesperado: {mode}.")
    metrics = final_model.val(data=str(step_yaml), imgsz=args.imgsz, device=device,
                              workers=args.workers, plots=True, verbose=False,
                              project=str(run_root), name="final-validation", exist_ok=False)
    print("\nCandidato compatible con Java; no se promovió automáticamente.")
    print(f"Pesos: {candidate}")
    print(f"Clases: {final_model.names}")
    print(f"mAP50={metrics.box.map50:.4f}; mAP50-95={metrics.box.map:.4f}; "
          f"precision={metrics.box.mp:.4f}; recall={metrics.box.mr:.4f}")
    print("La validación local es pequeña y no sustituye pruebas con sesiones nuevas de la cámara del iPhone.")
    print("Para seleccionar el candidato sin reemplazar el modelo anterior: "
          f"HANDWASH_YOLO_MODEL='{candidate}' ./scripts/start_handwash.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
