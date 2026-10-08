"""
DataSet5 Dataset Preparation Pipeline
=====================================
Extracts frames from 324 videos, reads temporal annotations from 4 annotators,
auto-annotates hand bounding boxes with hand_yolov8s, creates YOLO format dataset.
Combines with existing 567-image manually-annotated dataset.

Output structure:
  DataSet5_YOLO/
    images/train/  images/val/
    labels/train/  labels/val/
"""

import os
import csv
import json
import cv2
import numpy as np
from pathlib import Path
from collections import Counter, defaultdict
from ultralytics import YOLO
import shutil
import time
from dataset_contracts import (
    DATASET5_CLASS_NAMES,
    DATASET5_MOVEMENT_TO_CLASS,
    consensus_frame_label,
    dataset5_output_dir,
    ensure_fresh_dataset_output,
    validate_dataset5_contract,
    validate_dataset5_source_taxonomy,
)

# ============================================================
# CONFIG
# ============================================================
BASE_DIR = Path(os.environ.get("HANDWASH_PROJECT_ROOT", str(Path(__file__).resolve().parents[1]))).resolve()
VIDEOS_DIR = BASE_DIR / "ENTRENAMIENTO" / "DataSet5" / "Videos"
ANNOTATIONS_DIR = BASE_DIR / "ENTRENAMIENTO" / "DataSet5" / "Annotations"
EXISTING_TRAIN_DIR = BASE_DIR / "hand-wash-compliance-yolo" / "HandWashDataset_yoloFormat" / "TrainingData"
HAND_DETECTOR_PATH = BASE_DIR / "ENTRENAMIENTO" / "hand_yolov8s.pt"
OUTPUT_DIR = dataset5_output_dir(BASE_DIR)

FPS = 30
EXTRACT_FPS = 1  # Extract 1 frame per second
FRAME_INTERVAL = FPS // EXTRACT_FPS  # Every 30th frame
CONF_THRESHOLD = 0.3  # Hand detection confidence
VAL_SPLIT = 0.15  # 15% for validation
SEED = 42

MOVEMENT_TO_CLASS = DATASET5_MOVEMENT_TO_CLASS
CLASS_NAMES = list(DATASET5_CLASS_NAMES)


# ============================================================
# STEP 1: Read all annotations
# ============================================================
def load_annotations():
    """
    Load all annotator CSVs and build per-video, per-frame annotations.
    Returns: dict[video_name] -> list of (frame_index, movement_code) from each annotator.
    """
    print("[1/5] Loading annotations from all annotators...")
    video_annotations = defaultdict(list)  # video_name -> [(annotator, {frame_idx: movement_code})]

    annotator_dirs = sorted(ANNOTATIONS_DIR.iterdir())
    for annotator_dir in annotator_dirs:
        if not annotator_dir.is_dir():
            continue
        annotator_name = annotator_dir.name
        csv_files = list(annotator_dir.glob("*.csv"))
        print(f"  {annotator_name}: {len(csv_files)} annotation files")

        for csv_file in csv_files:
            video_name = csv_file.stem  # e.g. "2020-06-26_18-22-07_camera104"
            frame_labels = {}

            with open(csv_file, "r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    frame_time_ms = float(row["frame_time"])
                    is_washing = int(row["is_washing"])
                    movement_code = int(row["movement_code"])
                    frame_idx = round(frame_time_ms / (1000.0 / FPS))
                    frame_labels[frame_idx] = (is_washing, movement_code)

            video_annotations[video_name].append((annotator_name, frame_labels))

    print(f"  Total videos with annotations: {len(video_annotations)}")
    return video_annotations


def consensus_annotation(annotators_data):
    """
    For each frame, take majority vote across annotators.
    If is_washing disagree, majority wins.
    The movement vote is limited to annotators matching the winning washing label.
    Returns: dict[frame_idx] -> (is_washing, movement_code) or None for a tie.
    """
    # Collect all frame indices
    all_frames = set()
    for _, frame_labels in annotators_data:
        all_frames.update(frame_labels.keys())

    consensus = {}
    for frame_idx in sorted(all_frames):
        frame_votes = []
        for _, frame_labels in annotators_data:
            if frame_idx in frame_labels:
                frame_votes.append(frame_labels[frame_idx])

        if not frame_votes:
            continue

        consensus[frame_idx] = consensus_frame_label(frame_votes)

    return consensus


# ============================================================
# STEP 2: Extract frames and create labels
# ============================================================
def extract_frames_and_annotate(video_annotations):
    """
    Extract frames at 1fps, detect hands, create YOLO labels.
    """
    print("\n[2/5] Extracting frames and auto-annotating...")

    # Create output directories
    for split in ["train", "val"]:
        (OUTPUT_DIR / "images" / split).mkdir(parents=True, exist_ok=True)
        (OUTPUT_DIR / "labels" / split).mkdir(parents=True, exist_ok=True)

    # Load hand detector
    print("  Loading hand detector (hand_yolov8s)...")
    hand_model = YOLO(str(HAND_DETECTOR_PATH))

    # Get all video files
    video_files = {v.stem: v for v in VIDEOS_DIR.glob("*.mp4")}
    print(f"  Total videos found: {len(video_files)}")

    all_image_paths = []
    all_label_paths = []
    class_counts = Counter()
    stats = {"total_frames": 0, "hands_detected": 0, "no_hands": 0}

    processed = 0
    skipped = 0

    for video_name, video_path in video_files.items():
        processed += 1

        if video_name not in video_annotations:
            skipped += 1
            continue

        # Get consensus annotations
        annotators_data = video_annotations[video_name]
        consensus = consensus_annotation(annotators_data)

        if not consensus:
            skipped += 1
            continue

        # Open video
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            skipped += 1
            continue

        total_frames_video = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # Determine split for this video
        stable_bucket = int.from_bytes(__import__("hashlib").sha256(video_name.encode("utf-8")).digest()[:4], "big") % 100
        is_val = stable_bucket < int(VAL_SPLIT * 100)
        split = "val" if is_val else "train"

        video_label_count = 0

        for frame_idx in range(0, total_frames_video, FRAME_INTERVAL):
            # Check if we have annotation for this frame (or nearest)
            # Find closest annotated frame
            target_time_ms = frame_idx * (1000.0 / FPS)
            closest_frame = None
            min_dist = float("inf")

            for ann_frame in consensus.keys():
                ann_time_ms = ann_frame * (1000.0 / FPS)
                dist = abs(target_time_ms - ann_time_ms)
                if dist < min_dist:
                    min_dist = dist
                    closest_frame = ann_frame

            if closest_frame is None or min_dist > 2000:  # >2s gap
                continue

            annotation = consensus[closest_frame]
            if annotation is None:
                continue
            is_washing, movement_code = annotation

            # Skip non-washing frames
            if not is_washing:
                continue

            # Map movement code to our class
            if movement_code not in MOVEMENT_TO_CLASS:
                continue

            class_id = MOVEMENT_TO_CLASS[movement_code]

            # Read frame
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret:
                continue

            h, w = frame.shape[:2]

            # Detect hands
            results = hand_model(frame, conf=CONF_THRESHOLD, verbose=False)

            boxes = []
            for r in results:
                if r.boxes is not None:
                    for box in r.boxes:
                        cls = int(box.cls[0])
                        # class 0 is "hand" in hand_yolov8s
                        if cls == 0:
                            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                            # Convert to YOLO format (normalized center x, y, width, height)
                            cx = ((x1 + x2) / 2) / w
                            cy = ((y1 + y2) / 2) / h
                            bw = (x2 - x1) / w
                            bh = (y2 - y1) / h
                            # Clamp to [0, 1]
                            cx = max(0, min(1, cx))
                            cy = max(0, min(1, cy))
                            bw = max(0, min(1, bw))
                            bh = max(0, min(1, bh))
                            boxes.append((class_id, cx, cy, bw, bh))
                            stats["hands_detected"] += 1

            if not boxes:
                stats["no_hands"] += 1
                continue

            # Save image
            img_name = f"{video_name}_f{frame_idx:06d}.jpg"
            img_path = OUTPUT_DIR / "images" / split / img_name
            cv2.imwrite(str(img_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])

            # Save label
            label_name = f"{video_name}_f{frame_idx:06d}.txt"
            label_path = OUTPUT_DIR / "labels" / split / label_name
            with open(label_path, "w") as f:
                for cls_id, cx, cy, bw, bh in boxes:
                    f.write(f"{cls_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")

            all_image_paths.append(img_path)
            all_label_paths.append(label_path)
            class_counts[class_id] += 1
            stats["total_frames"] += 1
            video_label_count += 1

        cap.release()

        if processed % 20 == 0 or processed == len(video_files):
            print(f"  Processed {processed}/{len(video_files)} videos "
                  f"({skipped} skipped), "
                  f"{stats['total_frames']} frames so far")

    print(f"\n  === DataSet5 Extraction Complete ===")
    print(f"  Total frames extracted: {stats['total_frames']}")
    print(f"  Hands detected: {stats['hands_detected']}")
    print(f"  No hands detected: {stats['no_hands']}")
    print(f"  Class distribution:")
    for cls_id in sorted(class_counts.keys()):
        print(f"    {CLASS_NAMES[cls_id]:25s}: {class_counts[cls_id]:6d}")

    return all_image_paths, all_label_paths, class_counts


# ============================================================
# STEP 3: Copy existing dataset
# ============================================================
def copy_existing_dataset():
    """
    Copy the existing 567 manually-annotated images into the combined dataset.
    """
    print("\n[3/5] Copying existing manually-annotated dataset (567 images)...")

    existing_images = EXISTING_TRAIN_DIR / "images" / "train"
    existing_labels = EXISTING_TRAIN_DIR / "labels" / "train"

    if not existing_images.exists():
        print(f"  WARNING: Existing images not found at {existing_images}")
        return 0

    images = list(existing_images.glob("*.jpg"))
    count = 0

    for img_path in images:
        label_name = img_path.stem + ".txt"
        label_path = existing_labels / label_name

        if not label_path.exists():
            continue

        # All existing images go to train
        new_img = OUTPUT_DIR / "images" / "train" / f"existing_{img_path.name}"
        new_lbl = OUTPUT_DIR / "labels" / "train" / f"existing_{label_path.name}"

        shutil.copy2(str(img_path), str(new_img))
        shutil.copy2(str(label_path), str(new_lbl))
        count += 1

    print(f"  Copied {count} images + labels from existing dataset")
    return count


# ============================================================
# STEP 4: Balance classes
# ============================================================
def balance_classes(class_counts):
    """
    Apply oversampling to underrepresented classes by duplicating images.
    """
    print("\n[4/5] Balancing classes...")

    max_count = max(class_counts.values()) if class_counts else 1
    target_count = int(max_count * 0.5)  # Target 50% of majority class

    train_dir = OUTPUT_DIR / "labels" / "train"
    train_images = OUTPUT_DIR / "images" / "train"

    # Count current class distribution in train
    current_counts = Counter()
    class_to_files = defaultdict(list)

    for label_file in train_dir.glob("*.txt"):
        with open(label_file, "r") as f:
            for line in f:
                cls = int(line.strip().split()[0])
                current_counts[cls] += 1
                class_to_files[cls].append(label_file.stem)

    print(f"  Current train class distribution:")
    for cls_id in sorted(current_counts.keys()):
        print(f"    {CLASS_NAMES[cls_id]:25s}: {current_counts[cls_id]:6d}")

    # Oversample underrepresented classes
    duplications = 0
    for cls_id, count in current_counts.items():
        if count < target_count and count > 0:
            needed = target_count - count
            files = class_to_files[cls_id]
            # Duplicate files
            for i in range(needed):
                src_name = files[i % len(files)]
                src_img = train_images / f"{src_name}.jpg"
                src_lbl = train_dir / f"{src_name}.txt"

                if not src_img.exists() or not src_lbl.exists():
                    continue

                suffix = f"_bal{cls_id}_{i}"
                dst_img = train_images / f"{src_name}{suffix}.jpg"
                dst_lbl = train_dir / f"{src_name}{suffix}.txt"

                shutil.copy2(str(src_img), str(dst_img))
                shutil.copy2(str(src_lbl), str(dst_lbl))
                duplications += 1

    print(f"  Duplicated {duplications} images for class balancing")


# ============================================================
# STEP 5: Create YAML config
# ============================================================
def create_yaml():
    """Create dataset YAML configuration file."""
    print("\n[5/5] Creating dataset YAML...")

    yaml_path = OUTPUT_DIR / "dataset5_combined.yaml"
    config = {
        "projectDatasetContractVersion": 2,
        "path": ".",
        "train": "images/train",
        "val": "images/val",
        "nc": len(CLASS_NAMES),
        "names": dict(enumerate(CLASS_NAMES)),
    }
    validate_dataset5_contract(config, yaml_path)

    yaml_content = f"""# DataSet5 Combined Dataset - YOLO26 Format
# Auto-annotated from 324 videos + 567 manually-annotated images
# Project friction labels; this is not a complete WHO procedure.
# movement_code 7 means faucet closure and maps to Fondo, never Paso7_Circulares.
# A verified Paso7_Circulares class must exist in both train and val.

projectDatasetContractVersion: 2

path: .
train: images/train
val: images/val

nc: 8
names:
  0: Paso1_Palmas
  1: Paso2_Dorsos
  2: Paso3_Interdigitales
  3: Paso4_Nudillos
  4: Paso5_Pulgar
  5: Paso6_PuntaDeDedos
  6: Paso7_Circulares
  7: Fondo
"""

    with open(yaml_path, "w") as f:
        f.write(yaml_content)

    print(f"  Created: {yaml_path}")
    return yaml_path


# ============================================================
# MAIN
# ============================================================
def main():
    validate_dataset5_source_taxonomy()
    ensure_fresh_dataset_output(OUTPUT_DIR)
    start_time = time.time()

    print("=" * 70)
    print("  DataSet5 Dataset Preparation Pipeline")
    print("=" * 70)
    print(f"  Videos: {VIDEOS_DIR}")
    print(f"  Annotations: {ANNOTATIONS_DIR}")
    print(f"  Hand detector: {HAND_DETECTOR_PATH}")
    print(f"  Output: {OUTPUT_DIR}")
    print(f"  Extract FPS: {EXTRACT_FPS}")
    print(f"  Confidence threshold: {CONF_THRESHOLD}")
    print("=" * 70)

    # Step 1: Load annotations
    video_annotations = load_annotations()

    # Step 2: Extract frames and auto-annotate
    images, labels, class_counts = extract_frames_and_annotate(video_annotations)

    # Step 3: Copy existing dataset
    existing_count = copy_existing_dataset()

    # Step 4: Balance classes
    # Recount after copying existing
    final_counts = Counter()
    for label_file in (OUTPUT_DIR / "labels" / "train").glob("*.txt"):
        with open(label_file, "r") as f:
            for line in f:
                cls = int(line.strip().split()[0])
                final_counts[cls] += 1
    balance_classes(final_counts)

    # Step 5: Create YAML
    yaml_path = create_yaml()

    # Final stats
    elapsed = time.time() - start_time
    total_train = len(list((OUTPUT_DIR / "images" / "train").glob("*.jpg")))
    total_val = len(list((OUTPUT_DIR / "images" / "val").glob("*.jpg")))

    print("\n" + "=" * 70)
    print("  PREPARATION COMPLETE!")
    print("=" * 70)
    print(f"  Time: {elapsed / 60:.1f} minutes")
    print(f"  Train images: {total_train}")
    print(f"  Val images: {total_val}")
    print(f"  Total: {total_train + total_val}")
    print(f"  YAML config: {yaml_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
