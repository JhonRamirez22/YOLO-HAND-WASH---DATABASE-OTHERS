#!/usr/bin/env python3
"""Create a new YOLO dataset with near-duplicate images kept in one split.

This is a conservative perceptual-similarity split, not proof of separation by
source video, scene, participant, or camera. The source dataset is read-only.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys
import tempfile

import numpy as np
import yaml

try:  # Support both `python scripts/...py` and package-based test imports.
    from .audit_yolo_split_duplicates import _resolve_dataset_root, _signature, find_duplicate_candidates
except ImportError:  # pragma: no cover - exercised by the command-line entry point
    from audit_yolo_split_duplicates import _resolve_dataset_root, _signature, find_duplicate_candidates


SPLIT_NAMES = ("train", "val", "test")
TRAINING_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp"}


@dataclass(frozen=True)
class DatasetImage:
    image_path: Path
    label_path: Path
    source_split: str
    source_relative_path: str
    class_counts: tuple[int, ...]


@dataclass(frozen=True)
class SimilarityGroup:
    group_id: str
    image_indexes: tuple[int, ...]
    class_counts: tuple[int, ...]


def _normalise_names(value: object, class_count: int) -> list[str]:
    if isinstance(value, dict):
        try:
            names = [str(value[index] if index in value else value[str(index)]) for index in range(class_count)]
        except (KeyError, TypeError) as error:
            raise ValueError("El YAML names debe incluir IDs consecutivos desde 0") from error
    elif isinstance(value, list):
        names = [str(name) for name in value]
    else:
        raise ValueError("El YAML debe declarar names como lista o mapa de IDs a nombres")
    if len(names) != class_count or any(not name.strip() for name in names):
        raise ValueError(f"nc={class_count} no coincide con la lista names")
    return names


def _resolve_path(root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def _source_dataset_roots(data_yaml: Path, config: dict[str, object]) -> set[Path]:
    dataset_root = _resolve_dataset_root(data_yaml, config)
    roots: set[Path] = set()
    for split in SPLIT_NAMES:
        split_value = config.get(split)
        if split == "val" and split_value is None:
            split_value = config.get("valid")
        if not isinstance(split_value, str):
            continue
        parts = Path(split_value).expanduser().parts
        try:
            image_segment = parts.index("images")
        except ValueError:
            continue
        relative_root = Path(*parts[:image_segment])
        roots.add(_resolve_path(dataset_root, relative_root.as_posix() or "."))
    return roots


def _read_dataset(data_yaml: Path) -> tuple[Path, list[str], list[DatasetImage]]:
    config = yaml.safe_load(data_yaml.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError(f"YAML inválido: {data_yaml}")
    class_count = config.get("nc")
    if not isinstance(class_count, int) or class_count <= 0:
        raise ValueError("El YAML debe declarar nc como entero positivo")
    names = _normalise_names(config.get("names"), class_count)

    dataset_root = _resolve_dataset_root(data_yaml, config)
    images: list[DatasetImage] = []
    seen_paths: set[Path] = set()

    for split in SPLIT_NAMES:
        split_value = config.get(split)
        if split == "val" and split_value is None:
            split_value = config.get("valid")
        if split_value is None:
            continue
        if not isinstance(split_value, str):
            raise ValueError(f"La preparación requiere una sola ruta por split; '{split}' no es una ruta string")
        image_dir = _resolve_path(dataset_root, split_value)
        if not image_dir.is_dir():
            raise FileNotFoundError(f"No existe el directorio de imágenes de {split}: {image_dir}")
        relative_parts = Path(split_value).parts
        try:
            image_position = relative_parts.index("images")
            label_relative = Path(*relative_parts[:image_position], "labels", *relative_parts[image_position + 1:])
        except ValueError as error:
            raise ValueError(f"La ruta del split debe seguir el formato images/<split>: {split_value}") from error
        label_dir = _resolve_path(dataset_root, label_relative.as_posix())
        split_images = sorted(
            path for path in image_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in TRAINING_IMAGE_SUFFIXES
        )
        if not split_images:
            raise ValueError(f"El split {split} no contiene imágenes compatibles con el entrenamiento")

        for image_path in split_images:
            resolved_image = image_path.resolve()
            if resolved_image in seen_paths:
                # Repeated paths in an input YAML are one sample, not two examples.
                continue
            seen_paths.add(resolved_image)
            relative_image = image_path.relative_to(image_dir)
            label_path = label_dir / relative_image.with_suffix(".txt")
            if not label_path.is_file():
                raise FileNotFoundError(
                    f"Falta el .txt de etiquetas para {image_path}; crea un .txt vacío solo si es un negativo anotado"
                )
            class_counts = [0] * class_count
            for line_number, line in enumerate(label_path.read_text(encoding="utf-8").splitlines(), start=1):
                fields = line.split()
                if not fields:
                    continue
                if len(fields) != 5:
                    raise ValueError(f"Etiqueta no compatible con YOLO detect en {label_path}:{line_number}")
                try:
                    class_id = int(fields[0])
                    box = [float(value) for value in fields[1:]]
                except ValueError as error:
                    raise ValueError(f"Etiqueta no numérica en {label_path}:{line_number}") from error
                if not 0 <= class_id < class_count:
                    raise ValueError(f"ID de clase {class_id} fuera de rango en {label_path}:{line_number}")
                center_x, center_y, width, height = box
                if (
                    not all(math.isfinite(value) for value in box)
                    or not 0 <= center_x <= 1
                    or not 0 <= center_y <= 1
                    or not 0 < width <= 1
                    or not 0 < height <= 1
                ):
                    raise ValueError(f"Caja YOLO fuera de rango en {label_path}:{line_number}")
                class_counts[class_id] += 1
            images.append(DatasetImage(
                image_path=image_path,
                label_path=label_path,
                source_split=split,
                source_relative_path=image_path.relative_to(dataset_root).as_posix(),
                class_counts=tuple(class_counts),
            ))

    if len(images) < len(SPLIT_NAMES):
        raise ValueError("Se necesitan al menos tres imágenes para construir train/val/test")
    return dataset_root, names, images


def build_similarity_groups(
    images: list[DatasetImage],
    max_phash_distance: int = 4,
    max_pixel_mae: float = 5.0,
) -> tuple[list[SimilarityGroup], int]:
    signatures = [_signature(image.image_path) for image in images]
    parent = list(range(len(images)))
    rank = [0] * len(images)

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        root_left = find(left)
        root_right = find(right)
        if root_left == root_right:
            return
        if rank[root_left] < rank[root_right]:
            root_left, root_right = root_right, root_left
        parent[root_right] = root_left
        if rank[root_left] == rank[root_right]:
            rank[root_left] += 1

    candidate_edges = 0
    for left in range(len(signatures)):
        left_signature = signatures[left]
        for right in range(left + 1, len(signatures)):
            right_signature = signatures[right]
            exact = left_signature.sha256 == right_signature.sha256
            distance = (left_signature.perceptual_hash ^ right_signature.perceptual_hash).bit_count()
            if not exact and distance > max_phash_distance:
                continue
            mae = float(np.abs(
                left_signature.gray_thumbnail.astype(np.int16)
                - right_signature.gray_thumbnail.astype(np.int16)
            ).mean())
            if exact or (distance <= max_phash_distance and mae <= max_pixel_mae):
                union(left, right)
                candidate_edges += 1

    components: dict[int, list[int]] = {}
    for index in range(len(images)):
        components.setdefault(find(index), []).append(index)

    groups: list[SimilarityGroup] = []
    for members in components.values():
        class_counts = [0] * len(images[0].class_counts)
        for index in members:
            for class_id, count in enumerate(images[index].class_counts):
                class_counts[class_id] += count
        stable_hashes = sorted(signatures[index].sha256 for index in members)
        group_id = hashlib.sha256("\n".join(stable_hashes).encode("ascii")).hexdigest()[:16]
        groups.append(SimilarityGroup(group_id, tuple(sorted(members)), tuple(class_counts)))
    groups.sort(key=lambda group: group.group_id)
    return groups, candidate_edges


def assign_groups_to_splits(
    groups: list[SimilarityGroup],
    class_count: int,
    ratios: dict[str, float] | None = None,
) -> dict[str, list[SimilarityGroup]]:
    ratios = ratios or {"train": 0.70, "val": 0.15, "test": 0.15}
    if set(ratios) != set(SPLIT_NAMES) or any(value <= 0 for value in ratios.values()):
        raise ValueError("Los tres ratios train/val/test deben ser positivos")
    ratio_total = sum(ratios.values())
    ratios = {name: value / ratio_total for name, value in ratios.items()}
    total_images = sum(len(group.image_indexes) for group in groups)
    total_class_counts = [0] * class_count
    for group in groups:
        for class_id, count in enumerate(group.class_counts):
            total_class_counts[class_id] += count
    if any(count == 0 for count in total_class_counts):
        missing = [str(index) for index, count in enumerate(total_class_counts) if count == 0]
        raise ValueError(f"El dataset no tiene anotaciones para las clases: {', '.join(missing)}")

    target_total = {split: ratios[split] * total_images for split in SPLIT_NAMES}
    target_classes = {
        split: [ratios[split] * total_class_counts[index] for index in range(class_count)]
        for split in SPLIT_NAMES
    }
    assignments = {split: [] for split in SPLIT_NAMES}
    current_total = {split: 0 for split in SPLIT_NAMES}
    current_classes = {split: [0] * class_count for split in SPLIT_NAMES}

    group_order = sorted(
        groups,
        key=lambda group: (
            -len(group.image_indexes),
            -max((count / total_class_counts[index] for index, count in enumerate(group.class_counts)), default=0),
            group.group_id,
        ),
    )
    remaining_group_presence = [0] * class_count
    for group in group_order:
        for class_id, count in enumerate(group.class_counts):
            if count:
                remaining_group_presence[class_id] += 1

    for group in group_order:
        for class_id, count in enumerate(group.class_counts):
            if count:
                remaining_group_presence[class_id] -= 1
        choices: list[tuple[float, str, str]] = []
        for candidate_split in SPLIT_NAMES:
            feasible = True
            for class_id, count in enumerate(group.class_counts):
                covered_splits = sum(
                    1 for split in SPLIT_NAMES
                    if current_classes[split][class_id] > 0
                    or (split == candidate_split and count > 0)
                )
                if len(SPLIT_NAMES) - covered_splits > remaining_group_presence[class_id]:
                    feasible = False
                    break
            if not feasible:
                continue
            cost = 0.0
            for split in SPLIT_NAMES:
                added_images = len(group.image_indexes) if split == candidate_split else 0
                total_after = current_total[split] + added_images
                cost += ((total_after - target_total[split]) / max(target_total[split], 1.0)) ** 2
                for class_id, group_count in enumerate(group.class_counts):
                    added_count = group_count if split == candidate_split else 0
                    target = target_classes[split][class_id]
                    after = current_classes[split][class_id] + added_count
                    cost += ((after - target) / max(target, 1.0)) ** 2
            tie_break = hashlib.sha256(f"{group.group_id}:{candidate_split}".encode("ascii")).hexdigest()
            choices.append((cost, tie_break, candidate_split))
        if not choices:
            raise ValueError(
                "No se puede mantener la cobertura de todas las clases en train/val/test "
                "sin separar grupos visualmente similares. Añade escenas anotadas independientes."
            )
        selected = min(choices)[2]
        assignments[selected].append(group)
        current_total[selected] += len(group.image_indexes)
        for class_id, count in enumerate(group.class_counts):
            current_classes[selected][class_id] += count

    missing_by_split = {
        split: [class_id for class_id, count in enumerate(current_classes[split]) if count == 0]
        for split in SPLIT_NAMES
    }
    if any(missing_by_split.values()):
        details = "; ".join(
            f"{split}: {classes}" for split, classes in missing_by_split.items() if classes
        )
        raise ValueError(
            "La agrupación no puede dejar las siete clases en todos los splits "
            f"sin romper grupos similares ({details}). Reúne más escenas/personas o cambia la fuente."
        )
    return assignments


def _split_image_paths(images: list[DatasetImage], groups_by_split: dict[str, list[SimilarityGroup]]) -> dict[str, list[int]]:
    return {
        split: sorted(index for group in groups_by_split[split] for index in group.image_indexes)
        for split in SPLIT_NAMES
    }


def plan_grouped_dataset(
    data_yaml: Path,
    max_phash_distance: int = 4,
    max_pixel_mae: float = 5.0,
    ratios: dict[str, float] | None = None,
) -> dict[str, object]:
    """Build an in-memory plan only; never creates or edits dataset files."""
    dataset_root, names, images = _read_dataset(data_yaml.resolve())
    groups, candidate_edges = build_similarity_groups(images, max_phash_distance, max_pixel_mae)
    assignments = assign_groups_to_splits(groups, len(names), ratios)
    indexes_by_split = _split_image_paths(images, assignments)
    split_counts: dict[str, dict[str, int]] = {}
    for split, indexes in indexes_by_split.items():
        split_counts[split] = {
            str(class_id): sum(images[index].class_counts[class_id] for index in indexes)
            for class_id in range(len(names))
        }
    groups_per_split = {
        split: len(groups_for_split) for split, groups_for_split in assignments.items()
    }
    similarity_groups_by_class = {
        names[class_id]: sum(
            group.class_counts[class_id] > 0 for group in groups
        )
        for class_id in range(len(names))
    }
    return {
        "datasetRoot": dataset_root,
        "names": names,
        "images": images,
        "groups": groups,
        "candidateEdges": candidate_edges,
        "assignments": assignments,
        "indexesBySplit": indexes_by_split,
        "splitCounts": {split: len(indexes) for split, indexes in indexes_by_split.items()},
        "groupsPerSplit": groups_per_split,
        "similarityGroupsByClass": similarity_groups_by_class,
        "instanceCountsByClassAndSplit": split_counts,
    }


def create_grouped_dataset(
    data_yaml: Path,
    output_dir: Path,
    max_phash_distance: int = 4,
    max_pixel_mae: float = 5.0,
    ratios: dict[str, float] | None = None,
) -> dict[str, object]:
    output_dir = output_dir.expanduser().resolve()
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(f"La salida ya existe y no se modificará: {output_dir}")
    if not 0 <= max_phash_distance <= 64 or max_pixel_mae < 0:
        raise ValueError("Umbral inválido: pHash debe estar entre 0 y 64 y MAE no puede ser negativo")

    source_yaml = data_yaml.expanduser().resolve()
    source_config = yaml.safe_load(source_yaml.read_text(encoding="utf-8"))
    if not isinstance(source_config, dict):
        raise ValueError(f"YAML inválido: {source_yaml}")
    source_roots = _source_dataset_roots(source_yaml, source_config)
    if any(
        output_dir == source_root or source_root in output_dir.parents
        for source_root in source_roots
    ):
        raise ValueError("La salida no puede estar dentro del dataset fuente; usa una carpeta derivada separada")

    plan = plan_grouped_dataset(data_yaml, max_phash_distance, max_pixel_mae, ratios)
    names = plan["names"]
    images = plan["images"]
    groups = plan["groups"]
    candidate_edges = plan["candidateEdges"]
    assignments = plan["assignments"]
    indexes_by_split = plan["indexesBySplit"]
    split_counts = plan["instanceCountsByClassAndSplit"]
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.staging-", dir=output_dir.parent))
    try:
        manifest_files: list[dict[str, object]] = []
        group_for_image = {
            image_index: group.group_id
            for split_groups in assignments.values()
            for group in split_groups
            for image_index in group.image_indexes
        }
        for split in SPLIT_NAMES:
            image_dir = staging / "images" / split
            label_dir = staging / "labels" / split
            image_dir.mkdir(parents=True, exist_ok=True)
            label_dir.mkdir(parents=True, exist_ok=True)
            for sequence, image_index in enumerate(indexes_by_split[split]):
                sample = images[image_index]
                target_stem = f"{split}_{sequence:06d}"
                target_image = image_dir / f"{target_stem}{sample.image_path.suffix.lower()}"
                target_label = label_dir / f"{target_stem}.txt"
                shutil.copy2(sample.image_path, target_image)
                shutil.copy2(sample.label_path, target_label)
                manifest_files.append({
                    "image": f"images/{split}/{target_image.name}",
                    "label": f"labels/{split}/{target_label.name}",
                    "source": sample.source_relative_path,
                    "sourceSplit": sample.source_split,
                    "similarityGroup": group_for_image[image_index],
                })

        portable_config = {
            "path": ".",
            "train": "images/train",
            "val": "images/val",
            "test": "images/test",
            "nc": len(names),
            "names": {class_id: name for class_id, name in enumerate(names)},
        }
        (staging / "data.yaml").write_text(yaml.safe_dump(portable_config, sort_keys=False), encoding="utf-8")
        manifest = {
            "schemaVersion": 1,
            "method": "connected-components over exact SHA-256 or perceptual hash plus grayscale MAE",
            "thresholds": {
                "perceptualHashMaxHammingDistance": max_phash_distance,
                "grayscaleThumbnail": "64x64",
                "meanAbsoluteErrorMaxOutOf255": max_pixel_mae,
            },
            "sourceVideoSeparationProven": False,
            "limitations": [
                "This only groups exact/near-duplicate-looking images; different frames from one source video may remain in separate groups.",
                "Connected components can over-group transitive chains of visually similar frames.",
                "No annotation semantics or clinical validity are inferred by this split tool.",
            ],
            "sourceDataYaml": data_yaml.name,
            "sourceImageCount": len(images),
            "similarityGroupCount": len(groups),
            "similarityCandidateEdgeCount": candidate_edges,
            "splitRatiosRequested": ratios or {"train": 0.70, "val": 0.15, "test": 0.15},
            "splitCounts": {split: len(indexes_by_split[split]) for split in SPLIT_NAMES},
            "similarityGroupsPerSplit": {
                split: len(assignments[split]) for split in SPLIT_NAMES
            },
            "similarityGroupsByClass": {
                names[class_id]: sum(group.class_counts[class_id] > 0 for group in groups)
                for class_id in range(len(names))
            },
            "instanceCountsByClassAndSplit": split_counts,
            "files": manifest_files,
        }
        (staging / "group_split_manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

        for left_index, left_split in enumerate(SPLIT_NAMES):
            for right_split in SPLIT_NAMES[left_index + 1:]:
                _, _, candidates = find_duplicate_candidates(
                    staging / "images" / left_split,
                    staging / "images" / right_split,
                    max_phash_distance,
                    max_pixel_mae,
                )
                if candidates:
                    raise RuntimeError(
                        f"El split generado aún cruza grupos: {left_split}/{right_split} "
                        f"tiene {len(candidates)} candidatos; no se publicará la salida."
                    )
        staging.rename(output_dir)
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise

    return {
        "output": output_dir,
        "images": {split: len(indexes_by_split[split]) for split in SPLIT_NAMES},
        "groups": len(groups),
        "candidateEdgesGrouped": candidate_edges,
        "instanceCountsByClassAndSplit": split_counts,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("datasets/handwash_public_7steps.yaml"))
    parser.add_argument("--output", type=Path, help="Nueva carpeta de salida; nunca sobrescribe")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Calcula grupos y balance sin escribir archivos; no requiere --output",
    )
    parser.add_argument("--max-phash-distance", type=int, default=4)
    parser.add_argument("--max-pixel-mae", type=float, default=5.0)
    parser.add_argument("--train-ratio", type=float, default=0.70)
    parser.add_argument("--val-ratio", type=float, default=0.15)
    parser.add_argument("--test-ratio", type=float, default=0.15)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ratios = {"train": args.train_ratio, "val": args.val_ratio, "test": args.test_ratio}
    try:
        if not math.isclose(sum(ratios.values()), 1.0, rel_tol=0.0, abs_tol=1e-6):
            raise ValueError("Los ratios train/val/test deben sumar 1.0")
        if args.dry_run:
            plan = plan_grouped_dataset(args.data, args.max_phash_distance, args.max_pixel_mae, ratios)
            report = {
                "dryRun": True,
                "sourceImages": len(plan["images"]),
                "similarityGroups": len(plan["groups"]),
                "candidateEdgesGrouped": plan["candidateEdges"],
                "splitImages": plan["splitCounts"],
                "groupsPerSplit": plan["groupsPerSplit"],
                "similarityGroupsByClass": plan["similarityGroupsByClass"],
                "instanceCountsByClassAndSplit": plan["instanceCountsByClassAndSplit"],
            }
        elif args.output is None:
            raise ValueError("Indica --output con una ruta nueva; el dataset original no se modifica")
        else:
            report = create_grouped_dataset(
                args.data,
                args.output,
                args.max_phash_distance,
                args.max_pixel_mae,
                ratios,
            )
    except (FileNotFoundError, OSError, ValueError, RuntimeError, yaml.YAMLError) as error:
        print(f"No se generó el dataset agrupado: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    print("AVISO: separación por similitud, no por video/escena/persona. No demuestra generalización clínica.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
