"""Shared dataset taxonomy contracts used by runtime, audits, and training preflight."""

from collections import Counter
from collections.abc import Mapping
import math
import os
from pathlib import Path
from typing import Any


DATASET5_CONTRACT_VERSION = 2
DATASET5_CLASS_NAMES = (
    "Paso1_Palmas", "Paso2_Dorsos", "Paso3_Interdigitales", "Paso4_Nudillos",
    "Paso5_Pulgar", "Paso6_PuntaDeDedos", "Paso7_Circulares", "Fondo",
)

# DataSet5 code 7 means faucet closure, not circular friction; code 0 is an
# unspecified/other movement. Neither is positive evidence for a friction step.
DATASET5_MOVEMENT_TO_CLASS = {
    0: 7, 1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 7: 7,
}

DERIVED_CLASSIFIER_NAMES: dict[int, str] = {
    0: "00_other_washing_movement",
    1: "01_palm_to_palm",
    2: "02_palm_over_dorsum_fingers_interlaced",
    3: "03_palms_fingers_interlaced",
    4: "04_backs_of_fingers_interlocked",
    5: "05_rotational_thumb_rubbing",
    6: "06_fingertips_to_palm",
    7: "07_turn_off_faucet_with_paper_towel",
    8: "08_not_washing",
}


def consensus_frame_label(votes: list[tuple[int, int]]) -> tuple[int, int] | None:
    """Return a label only when washing and movement votes each have a unique mode."""
    if not votes:
        raise ValueError("No hay votos de anotación para el frame.")

    washing_counts = Counter(washing for washing, _ in votes)
    washing_count = max(washing_counts.values())
    washing_winners = [label for label, count in washing_counts.items() if count == washing_count]
    if len(washing_winners) != 1:
        return None
    is_washing = washing_winners[0]

    movement_votes = [movement for washing, movement in votes if washing == is_washing]
    movement_counts = Counter(movement_votes)
    movement_count = max(movement_counts.values())
    movement_winners = [label for label, count in movement_counts.items()
                        if count == movement_count]
    if len(movement_winners) != 1:
        return None
    return is_washing, movement_winners[0]


def dataset5_output_dir(project_root: Path) -> Path:
    """Resolve an isolated DataSet5 output directory without touching existing data."""
    configured = os.environ.get("HANDWASH_DATASET5_OUTPUT_DIR")
    output = Path(configured).expanduser() if configured else project_root / "DataSet5_YOLO"
    if not output.is_absolute():
        output = project_root / output
    return output.resolve()


def ensure_fresh_dataset_output(output_dir: Path) -> None:
    """Refuse to mix regenerated labels with stale files from an older mapping."""
    if output_dir.exists() and (not output_dir.is_dir() or any(output_dir.iterdir())):
        raise FileExistsError(
            f"La salida {output_dir} ya existe y no está vacía; no se reutiliza ni se borra. "
            "Configura HANDWASH_DATASET5_OUTPUT_DIR con una carpeta nueva."
        )


def validate_dataset5_source_taxonomy() -> None:
    """Fail before video processing: DataSet5 has no source class for circular friction."""
    if 6 not in DATASET5_MOVEMENT_TO_CLASS.values():
        raise RuntimeError(
            "DataSet5 solo aporta seis movimientos de fricción: movement_code 7 es cerrar "
            "el grifo y se asigna a Fondo. No puede generar un detector completo de siete "
            "pasos sin anotaciones verificadas de Paso7_Circulares en train y val."
        )


def validate_dataset5_contract(config: Mapping[str, Any], config_path: Path) -> None:
    """Reject legacy/partial DataSet5 exports before any training or checkpoint load."""
    if config.get("projectDatasetContractVersion") != DATASET5_CONTRACT_VERSION:
        raise RuntimeError(
            "YAML DataSet5 histórico o sin contrato: vuelve a preparar una salida nueva; "
            "los export antiguos pueden etiquetar el cierre del grifo como Paso7_Circulares."
        )

    class_count = config.get("nc")
    raw_names = config.get("names")
    if isinstance(raw_names, Mapping):
        if set(raw_names) != set(range(len(DATASET5_CLASS_NAMES))):
            raise RuntimeError("El YAML DataSet5 debe usar IDs contiguos 0..7.")
        names = [raw_names[index] for index in range(len(DATASET5_CLASS_NAMES))]
    elif isinstance(raw_names, (list, tuple)):
        names = list(raw_names)
    else:
        raise RuntimeError("El YAML DataSet5 no declara nombres de clase válidos.")
    if class_count != len(DATASET5_CLASS_NAMES) or names != list(DATASET5_CLASS_NAMES):
        raise RuntimeError("El YAML DataSet5 no coincide con la taxonomía versionada del proyecto.")

    data_path = config.get("path", ".")
    if not isinstance(data_path, str) or not data_path.strip():
        raise RuntimeError("El YAML DataSet5 requiere una ruta de dataset válida.")
    dataset_root = (config_path.parent / data_path).resolve()
    image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
    for split in ("train", "val"):
        if config.get(split) != f"images/{split}":
            raise RuntimeError(f"El split {split} debe apuntar a images/{split}.")
        image_dir = dataset_root / "images" / split
        label_dir = dataset_root / "labels" / split
        if not image_dir.is_dir() or not label_dir.is_dir():
            raise RuntimeError(f"Faltan images/{split} o labels/{split} en el dataset DataSet5.")
        image_files = [
            path for path in image_dir.iterdir()
            if path.is_file() and path.suffix.lower() in image_extensions
        ]
        image_stems = {path.stem for path in image_files}
        label_files = list(label_dir.glob("*.txt"))
        label_stems = {path.stem for path in label_files}
        if not image_stems or len(image_stems) != len(image_files) or image_stems != label_stems:
            raise RuntimeError(
                f"El split {split} debe tener imágenes y etiquetas uno-a-uno; "
                f"imágenes={len(image_stems)}, etiquetas={len(label_stems)}."
            )

        counts: Counter[int] = Counter()
        for label_file in label_files:
            for line_number, line in enumerate(label_file.read_text(encoding="utf-8").splitlines(), 1):
                fields = line.split()
                if not fields:
                    continue
                try:
                    class_id = int(fields[0])
                except ValueError as error:
                    raise RuntimeError(
                        f"ID de clase inválido en {label_file.name}:{line_number}."
                    ) from error
                if not 0 <= class_id < len(DATASET5_CLASS_NAMES):
                    raise RuntimeError(
                        f"ID de clase fuera de rango en {label_file.name}:{line_number}."
                    )
                if len(fields) != 5:
                    raise RuntimeError(
                        f"Etiqueta YOLO debe tener 5 campos en {label_file.name}:{line_number}."
                    )
                try:
                    box = [float(value) for value in fields[1:]]
                except ValueError as error:
                    raise RuntimeError(
                        f"Coordenadas inválidas en {label_file.name}:{line_number}."
                    ) from error
                if (
                    not all(math.isfinite(value) and 0.0 <= value <= 1.0 for value in box)
                    or box[2] <= 0.0
                    or box[3] <= 0.0
                ):
                    raise RuntimeError(
                        f"Caja fuera de rango o sin área en {label_file.name}:{line_number}."
                    )
                counts[class_id] += 1
        missing = [name for class_id, name in enumerate(DATASET5_CLASS_NAMES) if counts[class_id] == 0]
        if missing:
            raise RuntimeError(
                f"El split {split} no tiene ejemplos anotados de: {', '.join(missing)}. "
                "No entrenes ni declares una validación completa con clases ausentes."
            )


def validate_dataset5_contract_file(config_path: Path) -> None:
    """Load and validate the DataSet5 contract without importing training libraries."""
    import yaml

    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise RuntimeError(f"No se pudo leer el YAML DataSet5 {config_path}: {error}") from error
    if not isinstance(config, Mapping):
        raise RuntimeError(f"El YAML DataSet5 {config_path} debe contener un objeto.")
    validate_dataset5_contract(config, config_path)
