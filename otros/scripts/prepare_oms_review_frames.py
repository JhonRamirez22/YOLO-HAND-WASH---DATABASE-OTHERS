#!/usr/bin/env python3
"""Extract full-wash videos into a review-only YOLO image bundle.

No model-generated or inferred annotations are written. Human review must
create bounding-box labels for all visible WHO actions and soap regions before
the bundle can be passed to train_handwash_who.py.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

import cv2
import yaml

from train_handwash_who import REQUIRED_CLASSES


VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".avi"}
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
SPLITS = ("train", "valid", "test")


@dataclass(frozen=True)
class VideoEntry:
    video_id: str
    path: Path
    person: str
    split: str


def load_manifest(manifest: Path) -> list[VideoEntry]:
    entries: list[VideoEntry] = []
    seen_videos: set[str] = set()
    seen_sources: set[tuple[int, int]] = set()
    split_by_person: dict[str, str] = {}
    with manifest.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        expected = {"video_id", "video", "person", "split", "consent"}
        if not expected.issubset(reader.fieldnames or []):
            raise ValueError("El CSV necesita video_id,video,person,split,consent")
        for row in reader:
            video_id = row["video_id"].strip()
            person = row["person"].strip()
            split = row["split"].strip().lower()
            consent = row["consent"].strip().lower()
            if not SAFE_ID.fullmatch(video_id) or not SAFE_ID.fullmatch(person):
                raise ValueError(f"video_id/person deben ser identificadores seguros: {row}")
            if video_id in seen_videos:
                raise ValueError(f"video_id repetido: {video_id}")
            if split not in SPLITS:
                raise ValueError(f"Split inválido para {video_id}: {split}")
            if consent not in {"yes", "si", "sí"}:
                raise ValueError(f"Falta consentimiento confirmado para {video_id}")
            previous = split_by_person.get(person)
            if previous is not None and previous != split:
                raise ValueError(f"Participante {person} aparece en {previous} y {split}")
            raw_path = Path(row["video"].strip())
            path = (raw_path if raw_path.is_absolute() else manifest.parent / raw_path).resolve()
            if not path.is_file() or path.suffix.lower() not in VIDEO_SUFFIXES:
                raise ValueError(f"Video inexistente o formato no admitido: {path}")
            source_key = (path.stat().st_dev, path.stat().st_ino)
            if source_key in seen_sources:
                raise ValueError(f"El mismo archivo de video aparece más de una vez: {path}")
            entries.append(VideoEntry(video_id, path, person, split))
            seen_videos.add(video_id)
            seen_sources.add(source_key)
            split_by_person[person] = split
    if not entries:
        raise ValueError("El manifiesto no contiene videos")
    return entries


def extract_video(entry: VideoEntry, staging: Path, sample_fps: float,
                  long_side: int) -> list[tuple[str, str, str, str, str, int, float]]:
    capture = cv2.VideoCapture(str(entry.path))
    if not capture.isOpened():
        raise ValueError(f"No se pudo abrir el video: {entry.path}")
    source_fps = float(capture.get(cv2.CAP_PROP_FPS))
    if not math.isfinite(source_fps) or source_fps <= 0:
        capture.release()
        raise ValueError(f"El video no informa FPS válidos: {entry.path}")
    image_dir = staging / entry.split / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    rows: list[tuple[str, str, str, str, str, int, float]] = []
    frame_index = 0
    next_sample_seconds = 0.0
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            seconds = frame_index / source_fps
            if seconds + 1e-6 >= next_sample_seconds:
                height, width = frame.shape[:2]
                if max(height, width) > long_side:
                    scale = long_side / max(height, width)
                    frame = cv2.resize(frame, (round(width * scale), round(height * scale)),
                                       interpolation=cv2.INTER_AREA)
                image_name = f"{entry.video_id}_f{frame_index:08d}.jpg"
                relative_image = f"{entry.split}/images/{image_name}"
                if not cv2.imwrite(str(image_dir / image_name), frame,
                                   [cv2.IMWRITE_JPEG_QUALITY, 90]):
                    raise OSError(f"No se pudo guardar {relative_image}")
                rows.append((relative_image, entry.person, entry.video_id, entry.split,
                             str(entry.path), frame_index, round(seconds, 4)))
                next_sample_seconds += 1.0 / sample_fps
            frame_index += 1
    finally:
        capture.release()
    if not rows:
        raise ValueError(f"El video no entregó fotogramas: {entry.path}")
    return rows


def prepare(manifest: Path, output_dir: Path, sample_fps: float = 2.0,
            long_side: int = 960) -> int:
    if not math.isfinite(sample_fps) or not 0.2 <= sample_fps <= 10:
        raise ValueError("--sample-fps debe estar entre 0.2 y 10")
    if not 320 <= long_side <= 1920:
        raise ValueError("--long-side debe estar entre 320 y 1920")
    manifest = manifest.resolve()
    output_dir = output_dir.absolute()
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(f"No se sobrescribirá un paquete existente: {output_dir}")
    entries = load_manifest(manifest)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="oms-review-", dir=output_dir.parent) as temporary:
        staging = Path(temporary) / "bundle"
        staging.mkdir()
        for split in SPLITS:
            (staging / split / "images").mkdir(parents=True)
        rows = [row for entry in entries
                for row in extract_video(entry, staging, sample_fps, long_side)]

        with (staging / "group_manifest.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(("image", "person", "video", "split"))
            writer.writerows(row[:4] for row in rows)
        with (staging / "frame_provenance.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(("image", "source_video", "frame_number", "time_seconds"))
            writer.writerows((row[0], row[4], row[5], row[6]) for row in rows)
        (staging / "data.yaml").write_text(yaml.safe_dump({
            "path": str(output_dir),
            "train": "train/images",
            "val": "valid/images",
            "test": "test/images",
            "nc": len(REQUIRED_CLASSES),
            "names": REQUIRED_CLASSES,
        }, sort_keys=False), encoding="utf-8")
        if output_dir.exists() or output_dir.is_symlink():
            raise FileExistsError(f"No se sobrescribirá un paquete existente: {output_dir}")
        staging.rename(output_dir)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Extrae clips completos para anotación OMS humana")
    parser.add_argument("--manifest", type=Path, required=True,
                        help="CSV video_id,video,person,split,consent")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--sample-fps", type=float, default=2.0)
    parser.add_argument("--long-side", type=int, default=960)
    args = parser.parse_args()
    count = prepare(args.manifest, args.output_dir, args.sample_fps, args.long_side)
    print(f"Preparados {count} fotogramas en {args.output_dir} SIN etiquetas YOLO.")
    print("Anota y revisa las 36 clases antes de entrenar; no uses el paquete como dataset terminado.")


if __name__ == "__main__":
    main()
