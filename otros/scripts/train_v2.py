"""
Train YOLO26s on Balanced DataSet5 - V2
=======================================
- YOLO26s (small) for better capacity
- 300 epochs, patience 50
- Aggressive augmentation for hand wash domain
- Class-balanced loss weighting
"""

import gc
import torch
import time
import os
from pathlib import Path
from ultralytics import YOLO
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
    print("  YOLO26s - Balanced DataSet5 Training (V2)")
    print("=" * 70)
    print(f"  PyTorch: {torch.__version__}")
    print(f"  CUDA: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"  GPU: {torch.cuda.get_device_name(0)}")
        props = torch.cuda.get_device_properties(0)
        print(f"  VRAM: {props.total_memory / 1e9:.1f} GB")
    print("=" * 70)

    # Load YOLO26s (small - more capacity than nano)
    model = YOLO("yolo26s.pt")

    # Train with optimized settings
    results = model.train(
        data=str(dataset_yaml),
        epochs=300,
        imgsz=640,
        batch=16,
        device=0,
        project=str(project_root / "runs" / "detect"),
        name="handwash-v2-yolo26s",
        exist_ok=False,

        # Optimization
        optimizer="AdamW",
        lr0=0.001,
        lrf=0.01,
        momentum=0.937,
        weight_decay=0.0005,
        warmup_epochs=5,
        warmup_momentum=0.8,
        warmup_bias_lr=0.1,

        # Early stopping - more patient
        patience=50,

        # Augmentation - aggressive for hand wash domain
        mosaic=1.0,
        mixup=0.2,
        copy_paste=0.15,
        erasing=0.4,
        fliplr=0.5,
        flipud=0.0,
        degrees=15.0,
        translate=0.15,
        scale=0.6,
        shear=8.0,
        perspective=0.001,
        hsv_h=0.02,
        hsv_s=0.7,
        hsv_v=0.4,

        # Close mosaic for last 20 epochs
        close_mosaic=20,

        # Performance
        amp=True,
        cache="disk",
        workers=4,
        cos_lr=True,

        # Save
        save=True,
        save_period=20,
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

    # Also export PyTorch
    print("  Exporting PyTorch...")
    # best_model.export(format="torchscript")  # Optional

    print(f"\n{'=' * 70}")
    print("  ALL DONE!")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
