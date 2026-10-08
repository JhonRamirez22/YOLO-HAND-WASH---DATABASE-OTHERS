#!/usr/bin/env python3
"""Train a YOLO26 segmentation model from a YOLO segmentation dataset.

The current DataSet5 is a detection dataset (boxes), so it cannot produce
accurate hand masks by itself. Provide a YAML whose labels contain polygons.
"""

import os
from pathlib import Path

from ultralytics import YOLO


if __name__ == "__main__":
    root = Path(os.environ.get("HANDWASH_PROJECT_ROOT", Path(__file__).resolve().parents[1]))
    data = os.environ.get("HANDWASH_SEG_DATA", str(root / "DataSet5_YOLO" / "segmentation.yaml"))
    model = YOLO(os.environ.get("HANDWASH_SEG_BASE", "yolo26n-seg.pt"))
    model.train(
        data=data,
        epochs=int(os.environ.get("HANDWASH_SEG_EPOCHS", "100")),
        imgsz=int(os.environ.get("HANDWASH_SEG_IMGSZ", "640")),
        project=str(root / "runs" / "segment"),
        name="handwash-yolo26n-seg",
        exist_ok=True,
    )
