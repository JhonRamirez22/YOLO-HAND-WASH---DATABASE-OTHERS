"""
Train YOLO26n on DataSet5 Combined Dataset
==========================================
Optimized for RTX 4070 Ti SUPER (16GB VRAM).
Uses mixed precision, disk caching, and class-balanced augmentation.
"""

import gc
import torch
import time
import os
from ultralytics import YOLO
from pathlib import Path
from dataset_contracts import dataset5_output_dir, validate_dataset5_contract_file


def main():
    project_root = Path(os.environ.get("HANDWASH_PROJECT_ROOT", Path(__file__).resolve().parents[1])).resolve()
    dataset_yaml = dataset5_output_dir(project_root) / "dataset5_combined.yaml"
    if not dataset_yaml.exists():
        raise FileNotFoundError(f"Dataset config not found: {dataset_yaml}")
    validate_dataset5_contract_file(dataset_yaml)

    start = time.time()

    gc.collect()
    torch.cuda.empty_cache()

    print("=" * 70)
    print("  YOLO26n - DataSet5 Combined Training")
    print("=" * 70)
    print(f"  PyTorch: {torch.__version__}")
    print(f"  CUDA: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"  GPU: {torch.cuda.get_device_name(0)}")
        props = torch.cuda.get_device_properties(0)
        print(f"  VRAM: {props.total_memory / 1e9:.1f} GB")
    print("=" * 70)

    # Load pretrained YOLO26n
    model = YOLO("yolo26n.pt")

    # Train
    results = model.train(
        data=str(dataset_yaml),
        epochs=100,
        imgsz=640,
        batch=16,
        device=0,
        project=str(project_root / "runs" / "detect"),
        name="handwash-dataset5",
        exist_ok=False,

        # Optimization
        optimizer="AdamW",
        lr0=0.001,
        lrf=0.01,
        momentum=0.937,
        weight_decay=0.0005,

        # Early stopping
        patience=20,

        # Augmentation
        mosaic=1.0,
        mixup=0.15,
        copy_paste=0.1,
        erasing=0.4,
        fliplr=0.5,
        flipud=0.0,
        degrees=10.0,
        translate=0.1,
        scale=0.5,
        shear=5.0,
        perspective=0.0,
        hsv_h=0.015,
        hsv_s=0.7,
        hsv_v=0.4,

        # Performance
        amp=True,
        cache="disk",
        workers=4,
        cos_lr=True,

        # Save
        save=True,
        save_period=10,
        plots=True,
        verbose=True,
    )

    trainer = getattr(model, "trainer", None)
    run_dir = Path(trainer.save_dir) if trainer is not None else None
    if run_dir is None:
        raise RuntimeError("Ultralytics no informó la carpeta real del entrenamiento; no se exporta.")

    elapsed = time.time() - start
    print(f"\n{'=' * 70}")
    print(f"  TRAINING COMPLETE in {elapsed / 60:.1f} minutes")
    print(f"  Best weights: {run_dir / 'weights' / 'best.pt'}")
    print(f"  Last weights: {run_dir / 'weights' / 'last.pt'}")
    print(f"{'=' * 70}")

    # Validate best model
    print("\n  Validating best model...")
    best_model = YOLO(str(run_dir / "weights" / "best.pt"))
    metrics = best_model.val(data=str(dataset_yaml))

    print(f"\n  Validation Results:")
    print(f"  mAP50:     {metrics.box.map50:.4f}")
    print(f"  mAP50-95:  {metrics.box.map:.4f}")
    print(f"  Precision: {metrics.box.mp:.4f}")
    print(f"  Recall:    {metrics.box.mr:.4f}")

    # Per-class results
    if hasattr(metrics, "names") and metrics.names:
        print(f"\n  Per-class results:")
        for i, name in metrics.names.items():
            if i < len(metrics.box.ap):
                print(f"    {name:25s}: mAP50={metrics.box.ap50[i]:.4f}  mAP50-95={metrics.box.ap[i]:.4f}")

    # Export ONNX
    print("\n  Exporting to ONNX...")
    exported = best_model.export(format="onnx", imgsz=640)
    print(f"  ONNX candidate saved at {exported}; not installed into backend/models.")
    print("  Requiere revisión de taxonomía, métricas, hash y registro antes de activarlo.")

    print(f"\n{'=' * 70}")
    print("  ALL DONE!")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
