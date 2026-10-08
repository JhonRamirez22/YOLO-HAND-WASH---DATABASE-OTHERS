"""
Aggressive Dataset Rebalancing
==============================
- Cap Fondo class to max 800 samples (from 4098)
- Oversample all step classes to 800 each
- Ensure minimum 200 val samples per class
"""

import os
import shutil
import random
from pathlib import Path
from collections import Counter, defaultdict

SEED = 42
random.seed(SEED)

PROJECT_ROOT = Path(os.environ.get("HANDWASH_PROJECT_ROOT", Path(__file__).resolve().parents[1])).resolve()
BASE = PROJECT_ROOT / "DataSet5_YOLO"
TRAIN_IMG = BASE / "images" / "train"
TRAIN_LBL = BASE / "labels" / "train"
VAL_IMG = BASE / "images" / "val"
VAL_LBL = BASE / "labels" / "val"

TARGET_COUNT = 800  # Target per class in train
VAL_TARGET = 150    # Target per class in val

CLASS_NAMES = [
    "Paso1_Palmas", "Paso2_Dorsos", "Paso3_Interdigitales",
    "Paso4_Nudillos", "Paso5_Pulgar", "Paso6_PuntaDeDedos",
    "Paso7_Circulares", "Fondo",
]


def count_classes(label_dir):
    """Count instances per class across all label files."""
    class_counts = Counter()
    class_to_files = defaultdict(list)

    for lbl_file in label_dir.glob("*.txt"):
        with open(lbl_file, "r") as f:
            classes_in_file = set()
            for line in f:
                parts = line.strip().split()
                if parts:
                    cls = int(parts[0])
                    classes_in_file.add(cls)
            for cls in classes_in_file:
                class_counts[cls] += 1
                class_to_files[cls].append(lbl_file.stem)

    return class_counts, class_to_files


def rebalance_split(img_dir, lbl_dir, target_count, prefix=""):
    """Rebalance a split (train or val) to target_count per class."""
    class_counts, class_to_files = count_classes(lbl_dir)

    print(f"\n  {prefix} Before rebalancing:")
    for cls_id in sorted(class_counts.keys()):
        name = CLASS_NAMES[cls_id] if cls_id < len(CLASS_NAMES) else f"Class_{cls_id}"
        print(f"    {name:25s}: {class_counts[cls_id]:6d} files")

    # For each class that needs more samples
    for cls_id in sorted(class_counts.keys()):
        current = class_counts[cls_id]
        if current >= target_count:
            continue

        needed = target_count - current
        source_files = class_to_files[cls_id]

        if not source_files:
            continue

        print(f"    Duplicating {CLASS_NAMES[cls_id]}: {current} -> {target_count} (+{needed})")

        for i in range(needed):
            src_name = source_files[i % len(source_files)]
            src_img = img_dir / f"{src_name}.jpg"
            src_lbl = lbl_dir / f"{src_name}.txt"

            if not src_img.exists() or not src_lbl.exists():
                continue

            # Create unique name
            suffix = f"_r{cls_id}_{i:05d}"
            dst_img = img_dir / f"{src_name}{suffix}.jpg"
            dst_lbl = lbl_dir / f"{src_name}{suffix}.txt"

            shutil.copy2(str(src_img), str(dst_img))
            shutil.copy2(str(src_lbl), str(dst_lbl))

    # Cap Fondo class
    if 7 in class_to_files and len(class_to_files[7]) > target_count:
        fondo_files = class_to_files[7]
        excess = fondo_files[target_count:]
        print(f"\n    Capping Fondo: removing {len(excess)} files (keeping {target_count})")
        for name in excess:
            img_path = img_dir / f"{name}.jpg"
            lbl_path = lbl_dir / f"{name}.txt"
            if img_path.exists():
                img_path.unlink()
            if lbl_path.exists():
                lbl_path.unlink()

    # Final count
    final_counts, _ = count_classes(lbl_dir)
    print(f"\n  {prefix} After rebalancing:")
    for cls_id in sorted(final_counts.keys()):
        name = CLASS_NAMES[cls_id] if cls_id < len(CLASS_NAMES) else f"Class_{cls_id}"
        print(f"    {name:25s}: {final_counts[cls_id]:6d}")

    return final_counts


def main():
    print("=" * 60)
    print("  AGGRESSIVE DATASET REBALANCING")
    print("=" * 60)

    # Rebalance train
    print("\n[TRAIN SET]")
    train_counts = rebalance_split(TRAIN_IMG, TRAIN_LBL, TARGET_COUNT, "Train")

    # Rebalance val
    print("\n[VAL SET]")
    val_counts = rebalance_split(VAL_IMG, VAL_LBL, VAL_TARGET, "Val")

    # Summary
    total_train = sum(train_counts.values())
    total_val = sum(val_counts.values())

    print(f"\n{'=' * 60}")
    print(f"  REBALANCING COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Train: {total_train} instances across {len(train_counts)} classes")
    print(f"  Val:   {total_val} instances across {len(val_counts)} classes")
    print(f"  Target per class train: {TARGET_COUNT}")
    print(f"  Target per class val:   {VAL_TARGET}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
