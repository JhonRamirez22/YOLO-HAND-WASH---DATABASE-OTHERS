#!/usr/bin/env python3
"""Train a full-procedure OMS detector candidate; never replace the active model.

The YOLO export must have the exact full action and bilateral soap-evidence
taxonomy defined in this script, plus train/valid/test splits. To copy a tested
candidate into backend/models, also provide a manifest proving no person or
source video is shared across splits.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
import tempfile
from pathlib import Path

import yaml


OMS_ACTION_CLASSES = [
    "OMS_01_MOJAR_MANOS",
    "OMS_02_APLICAR_JABON",
    "OMS_03_FROTAR_PALMAS",
    "OMS_04_FROTAR_DORSOS",
    "OMS_05_FROTAR_ENTRE_DEDOS",
    "OMS_06_FROTAR_DORSO_DE_DEDOS",
    "OMS_07_FROTAR_PULGARES",
    "OMS_08_FROTAR_PUNTAS_DE_DEDOS",
    "OMS_09_ENJUAGAR_MANOS",
    "OMS_10_SECAR_TOALLA_DESECHABLE",
    "OMS_11_CERRAR_GRIFO_CON_TOALLA",
    "OMS_CONTACTO_RIESGO",
]
SOAP_REGIONS = [
    "PALMA_IZQUIERDA", "PALMA_DERECHA", "DORSO_IZQUIERDO", "DORSO_DERECHO",
    "INTERDIGITALES_IZQUIERDA", "INTERDIGITALES_DERECHA", "DORSO_DE_DEDOS_IZQUIERDO",
    "DORSO_DE_DEDOS_DERECHO", "PULGAR_IZQUIERDO", "PULGAR_DERECHO",
    "PUNTAS_DE_DEDOS_IZQUIERDA", "PUNTAS_DE_DEDOS_DERECHA",
]
ACTION_FOR_SOAP_REGION = {
    region: OMS_ACTION_CLASSES[2 + index // 2]
    for index, region in enumerate(SOAP_REGIONS)
}
REQUIRED_CLASSES = [
    *OMS_ACTION_CLASSES,
    *[
        label
        for region in SOAP_REGIONS
        for label in (f"ESPUMA_VISIBLE_{region}", f"SIN_ESPUMA_VISIBLE_{region}")
    ],
]
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Entrena un candidato YOLO de lavado OMS completo")
    parser.add_argument("--dataset-dir", type=Path, required=True, help="Export YOLO con train/val (o valid)/test")
    parser.add_argument("--base-model", default=str(PROJECT_ROOT / "yolo26n.pt"),
                        help="Peso base local (por defecto yolo26n.pt); se puede usar un peso mayor en Colab")
    parser.add_argument("--epochs", type=int, default=150)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--device", default="0")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output-dir", type=Path, default=Path("runs/handwash_oms"))
    parser.add_argument("--group-manifest", type=Path,
                        help="CSV image,person,video,split; each person and video may occur in only one split")
    parser.add_argument("--copy-candidate", action="store_true",
                        help="Copy a metric-gated weight to handwash_oms_candidate.pt (never activates it)")
    parser.add_argument("--minimum-map50", type=float, default=0.70)
    parser.add_argument("--minimum-class-map50-95", type=float, default=0.30)
    parser.add_argument("--minimum-class-precision", type=float, default=0.60)
    parser.add_argument("--minimum-class-recall", type=float, default=0.60)
    return parser.parse_args()


def read_names(config: dict) -> list[str]:
    names = config.get("names")
    if isinstance(names, dict):
        indexed = {int(index): str(name) for index, name in names.items()}
        if sorted(indexed) != list(range(len(indexed))):
            raise ValueError("Los índices de names deben ser consecutivos desde 0")
        return [indexed[index] for index in range(len(indexed))]
    if isinstance(names, list):
        return [str(name) for name in names]
    raise ValueError("data.yaml debe definir names como lista o mapa indexado")


def split_path(config: dict, dataset_dir: Path, split: str) -> Path:
    config_key = "val" if split == "valid" and "valid" not in config else split
    value = config.get(config_key)
    if not value:
        raise ValueError(f"data.yaml debe declarar el split '{split}' (o 'val' para validación)")
    path = Path(value)
    if not path.is_absolute():
        base = Path(config.get("path", dataset_dir))
        if not base.is_absolute():
            base = dataset_dir / base
        path = base / path
    resolved = path.resolve()
    if resolved.exists():
        return resolved
    # Raw Roboflow ZIPs commonly use "../train/images" even though the
    # exported train/ directory is adjacent to data.yaml, within dataset_dir.
    if "path" not in config and str(value).startswith("../"):
        relative_parts = list(Path(value).parts)
        while relative_parts and relative_parts[0] in ("..", "."):
            relative_parts.pop(0)
        roboflow_path = dataset_dir.joinpath(*relative_parts).resolve()
        if roboflow_path.exists():
            return roboflow_path
    return resolved


def list_images(path: Path, dataset_dir: Path) -> list[Path]:
    if path.is_file():
        images = []
        for line in path.read_text().splitlines():
            raw = line.strip()
            if not raw:
                continue
            entry = Path(raw)
            candidates = [entry] if entry.is_absolute() else [path.parent / entry, dataset_dir / entry]
            resolved = next((candidate.resolve() for candidate in candidates if candidate.is_file()), None)
            if resolved is None:
                raise FileNotFoundError(f"La lista {path} referencia una imagen inexistente: {raw}")
            images.append(resolved)
        return images
    if not path.is_dir():
        raise FileNotFoundError(f"No existe ruta del split: {path}")
    return [item for item in path.rglob("*") if item.is_file() and item.suffix.lower() in IMAGE_SUFFIXES]


def label_for_image(image: Path) -> Path:
    if isinstance(image, str):
        image = Path(image)
    parts = list(image.parts)
    if "images" in parts:
        index = len(parts) - 1 - parts[::-1].index("images")
        parts[index] = "labels"
        return Path(*parts).with_suffix(".txt")
    return image.parent.parent / "labels" / f"{image.stem}.txt"


def xyxy_from_yolo(center_x: float, center_y: float,
                   width: float, height: float) -> tuple[float, float, float, float]:
    return (center_x - width / 2, center_y - height / 2,
            center_x + width / 2, center_y + height / 2)


def overlap_fraction(inner: tuple[float, float, float, float],
                     outer: tuple[float, float, float, float]) -> float:
    intersection = (max(0.0, min(inner[2], outer[2]) - max(inner[0], outer[0]))
                    * max(0.0, min(inner[3], outer[3]) - max(inner[1], outer[1])))
    return intersection / ((inner[2] - inner[0]) * (inner[3] - inner[1]))


def validate_class_distribution(config: dict, dataset_dir: Path, names: list[str]) -> dict[str, int]:
    if len(names) != len(REQUIRED_CLASSES) or len(names) != len(set(names)):
        raise ValueError("El mapa de clases debe tener 36 nombres únicos")
    missing_names = sorted(set(REQUIRED_CLASSES) - set(names))
    unexpected_names = sorted(set(names) - set(REQUIRED_CLASSES))
    if missing_names or unexpected_names:
        raise ValueError(
            f"El mapa de clases debe coincidir exactamente. Faltan={missing_names}; sobran={unexpected_names}"
        )
    class_id = {name: index for index, name in enumerate(names)}
    counts: dict[str, int] = {}
    for split in ("train", "valid", "test"):
        split_dir = split_path(config, dataset_dir, split)
        images = list_images(split_dir, dataset_dir)
        if not images:
            raise ValueError(f"El split {split} no contiene imágenes: {split_dir}")
        seen_ids: set[int] = set()
        for image in images:
            label = label_for_image(image)
            if not label.is_file():
                raise FileNotFoundError(f"Falta anotación YOLO para {image}: {label}")
            boxes_by_name: dict[str, list[tuple[float, float, float, float]]] = {}
            for line_number, line in enumerate(label.read_text().splitlines(), 1):
                fields = line.split()
                if len(fields) != 5:
                    raise ValueError(f"Etiqueta malformada {label}:{line_number}; se esperaba class x y w h")
                try:
                    category = int(fields[0])
                    coords = [float(value) for value in fields[1:]]
                except ValueError as error:
                    raise ValueError(f"Etiqueta no numérica en {label}:{line_number}") from error
                center_x, center_y, box_width, box_height = coords
                if (category < 0 or category >= len(names)
                    or not all(math.isfinite(value) for value in coords)
                    or any(value < 0 or value > 1 for value in coords)
                    or box_width <= 0 or box_height <= 0
                    or center_x - box_width / 2 < 0 or center_y - box_height / 2 < 0
                    or center_x + box_width / 2 > 1 or center_y + box_height / 2 > 1):
                    raise ValueError(f"Clase/coordenadas fuera de rango en {label}:{line_number}")
                seen_ids.add(category)
                boxes_by_name.setdefault(names[category], []).append(
                    xyxy_from_yolo(center_x, center_y, box_width, box_height)
                )
            for region, action in ACTION_FOR_SOAP_REGION.items():
                for state in ("ESPUMA_VISIBLE", "SIN_ESPUMA_VISIBLE"):
                    soap_name = f"{state}_{region}"
                    for soap_box in boxes_by_name.get(soap_name, []):
                        if not any(overlap_fraction(soap_box, action_box) >= 0.8
                                   for action_box in boxes_by_name.get(action, [])):
                            raise ValueError(
                                f"{label}: {soap_name} no pertenece a una caja {action} "
                                "que cubra al menos el 80 % de su área"
                            )
        missing_split = sorted(name for name, index in class_id.items() if index not in seen_ids)
        if missing_split:
            raise ValueError(f"El split {split} no tiene muestras para {missing_split}")
        counts[split] = len(images)
    return counts


def validate_group_manifest(path: Path, dataset_dir: Path, config: dict) -> None:
    people_by_split: dict[str, set[str]] = {"train": set(), "valid": set(), "test": set()}
    videos_by_split: dict[str, set[str]] = {"train": set(), "valid": set(), "test": set()}
    images_by_split = {
        split: {image.resolve() for image in list_images(split_path(config, dataset_dir, split), dataset_dir)}
        for split in people_by_split
    }
    split_names = list(images_by_split)
    for index, split in enumerate(split_names):
        for other in split_names[index + 1:]:
            duplicated = images_by_split[split] & images_by_split[other]
            if duplicated:
                raise ValueError(f"La misma imagen aparece en {split} y {other}: {next(iter(duplicated))}")
    manifest_images: set[Path] = set()
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if not {"image", "person", "video", "split"}.issubset(reader.fieldnames or []):
            raise ValueError("group-manifest debe tener columnas image,person,video,split")
        for row in reader:
            split = row["split"].strip().lower()
            person = row["person"].strip()
            video = row["video"].strip()
            image = row["image"].strip()
            if split not in people_by_split or not person or not video or not image:
                raise ValueError(f"Fila inválida en group-manifest: {row}")
            entry = Path(image)
            candidates = [entry] if entry.is_absolute() else [dataset_dir / entry, path.parent / entry]
            resolved = next((candidate.resolve() for candidate in candidates if candidate.is_file()), None)
            if resolved is None:
                raise ValueError(f"Imagen del group-manifest inexistente: {image}")
            if resolved not in images_by_split[split]:
                raise ValueError(f"La imagen {image} no pertenece al split declarado '{split}'")
            if resolved in manifest_images:
                raise ValueError(f"Imagen duplicada en group-manifest: {image}")
            manifest_images.add(resolved)
            people_by_split[split].add(person)
            videos_by_split[split].add(video)
    if not manifest_images:
        raise ValueError("group-manifest vacío")
    dataset_images = set().union(*images_by_split.values())
    missing = dataset_images - manifest_images
    extra = manifest_images - dataset_images
    if missing or extra:
        raise ValueError(
            f"group-manifest debe cubrir exactamente las imágenes de train/valid/test; "
            f"faltan={len(missing)}, sobran={len(extra)}"
        )
    splits = list(people_by_split)
    for index, split in enumerate(splits):
        for other in splits[index + 1:]:
            shared_people = people_by_split[split] & people_by_split[other]
            shared_videos = videos_by_split[split] & videos_by_split[other]
            if shared_people or shared_videos:
                raise ValueError(
                    f"Fuga de participantes/videos entre {split} y {other}: "
                    f"personas={sorted(shared_people)[:5]}, videos={sorted(shared_videos)[:5]}"
                )


def normalized_data_config(config: dict, dataset_dir: Path, names: list[str]) -> dict:
    """Give Ultralytics absolute split paths, including raw Roboflow ZIP exports."""
    return {
        "path": str(dataset_dir),
        "train": str(split_path(config, dataset_dir, "train")),
        "val": str(split_path(config, dataset_dir, "valid")),
        "test": str(split_path(config, dataset_dir, "test")),
        "nc": len(names),
        "names": names,
    }


def class_metrics(box_metrics: object, names: list[str]) -> dict[str, dict[str, float]]:
    """Reject partial/invalid test metrics instead of hiding them in a global mAP."""
    measured_ids = [int(class_id) for class_id in box_metrics.ap_class_index]
    if len(measured_ids) != len(names) or set(measured_ids) != set(range(len(names))):
        missing = sorted(set(range(len(names))) - set(measured_ids))
        raise ValueError(f"La evaluación de test no produjo métricas para todas las clases: {missing}")
    result: dict[str, dict[str, float]] = {}
    for position, class_id in enumerate(measured_ids):
        precision, recall, map50, map50_95 = (
            float(value) for value in box_metrics.class_result(position))
        values = (precision, recall, map50, map50_95)
        if any(not math.isfinite(value) or value < 0.0 or value > 1.0 for value in values):
            raise ValueError(f"Métricas inválidas para {names[class_id]}: {values}")
        result[names[class_id]] = {
            "precision": precision,
            "recall": recall,
            "map50": map50,
            "map50_95": map50_95,
        }
    return result


def candidate_meets_thresholds(map50: float,
                               per_class: dict[str, dict[str, float]],
                               minimum_map50: float,
                               minimum_class_map50_95: float,
                               minimum_class_precision: float,
                               minimum_class_recall: float) -> bool:
    thresholds = (minimum_map50, minimum_class_map50_95,
                  minimum_class_precision, minimum_class_recall)
    if any(not math.isfinite(value) or not 0.0 <= value <= 1.0 for value in thresholds):
        raise ValueError("Los umbrales de aceptación deben estar entre 0 y 1")
    return (math.isfinite(map50) and map50 >= minimum_map50
            and set(per_class) == set(REQUIRED_CLASSES)
            and all(item["map50_95"] >= minimum_class_map50_95
                    and item["precision"] >= minimum_class_precision
                    and item["recall"] >= minimum_class_recall
                    for item in per_class.values()))


def main() -> None:
    args = parse_args()
    dataset_dir = args.dataset_dir.resolve()
    config_path = next((path for path in (dataset_dir / "data.yaml", dataset_dir / "data.yml") if path.is_file()), None)
    if config_path is None:
        raise FileNotFoundError(f"No se encontró data.yaml dentro de {dataset_dir}")
    config = yaml.safe_load(config_path.read_text())
    names = read_names(config)
    counts = validate_class_distribution(config, dataset_dir, names)
    if args.copy_candidate:
        if args.group_manifest is None:
            raise ValueError("--copy-candidate requiere --group-manifest para probar separación por persona/video")
        validate_group_manifest(args.group_manifest.resolve(), dataset_dir, config)

    from ultralytics import YOLO

    with tempfile.TemporaryDirectory(prefix="handwash-oms-data-") as temporary_dir:
        normalized_yaml = Path(temporary_dir) / "data.yaml"
        normalized_yaml.write_text(yaml.safe_dump(
            normalized_data_config(config, dataset_dir, names), sort_keys=False))
        model = YOLO(args.base_model)
        model.train(
            data=str(normalized_yaml), epochs=args.epochs, imgsz=args.imgsz, batch=args.batch,
            device=args.device, workers=args.workers, project=str(args.output_dir.parent),
            name=args.output_dir.name, exist_ok=False, patience=25, close_mosaic=15,
            plots=True, seed=2026,
        )
        save_dir = Path(model.trainer.save_dir)
        best = save_dir / "weights" / "best.pt"
        if not best.is_file():
            raise FileNotFoundError(f"El entrenamiento no produjo {best}")
        shutil.copy2(normalized_yaml, save_dir / "data.normalized.yaml")

        tested = YOLO(str(best)).val(
            data=str(normalized_yaml), split="test", imgsz=args.imgsz,
            batch=args.batch, device=args.device, plots=True,
        )
    per_class = class_metrics(tested.box, names)
    class_map50 = [per_class[name]["map50_95"] for name in names]
    metrics = {
        "task": "detect",
        "model": str(best),
        "map50": float(tested.box.map50),
        "map50_95": float(tested.box.map),
        "precision": float(tested.box.mp),
        "recall": float(tested.box.mr),
        "classMap50_95": class_map50,
        "perClass": per_class,
        "classNames": names,
        "imagesPerSplit": counts,
        "approvalEnabled": False,
        "approvalNote": "Box metrics do not validate temporal sequences or false approvals; run full held-out video review before setting HANDWASH_OMS_MODEL_READY=true.",
    }
    metrics_path = save_dir / "test_metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n")
    print(json.dumps(metrics, indent=2))

    passed_metrics = candidate_meets_thresholds(
        metrics["map50"], per_class, args.minimum_map50,
        args.minimum_class_map50_95, args.minimum_class_precision,
        args.minimum_class_recall)
    if args.copy_candidate and passed_metrics:
        candidate = PROJECT_ROOT / "backend/models/handwash_oms_candidate.pt"
        candidate.parent.mkdir(parents=True, exist_ok=True)
        if candidate.exists():
            raise FileExistsError(f"El candidato ya existe y no se sobrescribirá: {candidate}")
        shutil.copy2(best, candidate)
        print(f"Candidato copiado a {candidate}; el detector activo y la aprobación OMS siguen desactivados.")
    elif args.copy_candidate:
        print("No se copia el candidato: no supera los umbrales globales o de precisión/recall por clase.")


if __name__ == "__main__":
    main()
