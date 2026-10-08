#!/usr/bin/env python3
"""Compare a supplied WHO classifier with labeled step crops, without saving frames.

This is a compatibility check, not a clinical or independent validation. The
public reference set is small and may overlap with training sources.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
from pathlib import Path

import cv2
from ultralytics import YOLO


ROOT = Path(__file__).resolve().parents[1]
VAL = ROOT / "datasets/handwash_public_7steps"
WEIGHTS = ROOT / "backend/models/handwash_who_yolo26m_cls.pt"

# The supplied classifier has no class corresponding to canonical step 7.
# IDs 1..6 are compared only where the described hand motion corresponds.
STEP_TO_CLASSIFIER = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6}
EXPECTED_NAMES = {
    0: "00_otro_movimiento",
    1: "01_palmas_con_palmas",
    2: "02_palmas_sobre_dorso_dedos_intercalados",
    3: "03_palmas_con_palmas_dedos_intercalados",
    4: "04_dorso_de_dedos_contra_palma",
    5: "05_frotacion_rotacional_de_pulgares",
    6: "06_puntas_de_dedos_en_palma",
    7: "07_cerrar_grifo_con_toalla",
}
DERIVED_EXPECTED_NAMES = {
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", type=Path, default=WEIGHTS,
                        help="Clasificador YOLO ya entrenado que se desea evaluar")
    parser.add_argument("--val", type=Path, default=VAL,
                        help="Dataset de referencia con images/val y labels/val")
    return parser.parse_args()


def labeled_crop(image_path: Path, val_dir: Path):
    labels = (val_dir / "labels/val" / f"{image_path.stem}.txt").read_text().splitlines()
    if len(labels) != 1:
        raise ValueError(f"Expected one labeled movement in {image_path.name}, got {len(labels)}")
    label = labels[0].split()
    if len(label) != 5:
        raise ValueError(f"Invalid bounding box in {image_path.name}")
    step = int(label[0])
    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f"Could not read {image_path.name}")
    height, width = image.shape[:2]
    cx, cy, bw, bh = map(float, label[1:])
    x1 = max(0, round((cx - bw / 2) * width))
    x2 = min(width, round((cx + bw / 2) * width))
    y1 = max(0, round((cy - bh / 2) * height))
    y2 = min(height, round((cy + bh / 2) * height))
    if x2 <= x1 or y2 <= y1:
        raise ValueError(f"Empty bounding box in {image_path.name}")
    return step, image, image[y1:y2, x1:x2]


def main() -> None:
    args = parse_args()
    if not args.weights.is_file():
        raise SystemExit(f"Missing candidate weights: {args.weights}")
    if not args.val.is_dir():
        raise SystemExit(f"Missing validation dataset: {args.val}")
    paths = sorted((args.val / "images/val").glob("*.jpg"))
    if not paths:
        raise SystemExit(f"No validation images found in {args.val / 'images/val'}")
    model = YOLO(str(args.weights))
    if model.task != "classify" or model.names not in (EXPECTED_NAMES, DERIVED_EXPECTED_NAMES):
        raise SystemExit("Candidate checkpoint does not have the expected eight or nine classifier classes")
    input_size = 320 if model.names == DERIVED_EXPECTED_NAMES else 224
    correct = defaultdict(Counter)
    total = defaultdict(Counter)
    predicted = defaultdict(lambda: defaultdict(Counter))
    skipped = Counter()
    batches = {"full": [], "crop": []}
    steps = []

    def flush() -> None:
        if not steps:
            return
        for view, batch in batches.items():
            for expected, result in zip(steps, model.predict(batch, imgsz=input_size, batch=len(batch),
                                                             device="cpu", verbose=False, save=False)):
                found = int(result.probs.top1)
                total[view][expected] += 1
                correct[view][expected] += found == STEP_TO_CLASSIFIER[expected]
                predicted[view][expected][found] += 1
            batch.clear()
        steps.clear()

    for path in paths:
        step, full, crop = labeled_crop(path, args.val)
        if step not in STEP_TO_CLASSIFIER:
            skipped[step] += 1
            continue
        batches["full"].append(full)
        batches["crop"].append(crop)
        steps.append(step)
        if len(steps) >= 8:
            flush()
    flush()
    weights_path = args.weights.resolve()
    try:
        display_path = weights_path.relative_to(ROOT)
    except ValueError:
        display_path = weights_path
    digest = hashlib.sha256(args.weights.read_bytes()).hexdigest()
    print(f"Candidate: {display_path}; sha256: {digest}; reference images: {len(paths)}")
    for view in batches:
        for step in sorted(total[view]):
            print(f"{view} step {step + 1}: {correct[view][step]}/{total[view][step]} correct; "
                  f"classifier predictions {dict(sorted(predicted[view][step].items()))}")
        overall = sum(correct[view].values()) / max(sum(total[view].values()), 1)
        print(f"compatible-step {view} accuracy: {overall:.3f} "
              f"({sum(correct[view].values())}/{sum(total[view].values())})")
    print(f"unmapped step-7 images omitted: {skipped[6]}")
    print("Warning: this small set is not an independent clinical validation.")


if __name__ == "__main__":
    main()
