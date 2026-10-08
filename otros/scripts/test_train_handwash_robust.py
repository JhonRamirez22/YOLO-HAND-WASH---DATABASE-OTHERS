from contextlib import redirect_stdout
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import io

import cv2
import numpy as np
import yaml

from train_handwash_robust import (
    audit_prepared_splits,
    ensure_fresh_run_paths,
    merge_split,
    normalize_label,
    prepare_dataset,
    register_candidate_model,
)


class RobustTrainingSplitGateTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        for split in ("train", "val", "test"):
            (self.root / "images" / split).mkdir(parents=True)
        self.data_yaml = self.root / "data.yaml"
        self.data_yaml.write_text(yaml.safe_dump({
            "path": str(self.root),
            "train": "images/train",
            "val": "images/val",
            "test": "images/test",
        }))

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def write_image(path: Path, image: np.ndarray) -> None:
        if not cv2.imwrite(str(path), image):
            raise AssertionError(f"No se pudo escribir fixture de prueba: {path}")

    def test_all_three_splits_pass_when_they_are_visually_distinct(self):
        for index, split in enumerate(("train", "val", "test")):
            image = np.random.default_rng(100 + index).integers(0, 256, (96, 128), dtype=np.uint8)
            self.write_image(self.root / "images" / split / f"{split}.png", image)

        with redirect_stdout(io.StringIO()):
            audit_prepared_splits(self.data_yaml)

    def test_near_duplicate_across_train_and_validation_blocks_preflight(self):
        source = np.random.default_rng(52).integers(0, 256, (96, 128), dtype=np.uint8)
        near_duplicate = np.clip(source.astype(np.int16) + 1, 0, 255).astype(np.uint8)
        distinct_test = np.random.default_rng(53).integers(0, 256, (96, 128), dtype=np.uint8)
        self.write_image(self.root / "images/train/train.png", source)
        self.write_image(self.root / "images/val/val.png", near_duplicate)
        self.write_image(self.root / "images/test/test.png", distinct_test)

        with redirect_stdout(io.StringIO()), self.assertRaisesRegex(RuntimeError, "No se inició YOLO"):
            audit_prepared_splits(self.data_yaml)

    def test_test_split_is_also_checked_against_training(self):
        training = np.random.default_rng(91).integers(0, 256, (96, 128), dtype=np.uint8)
        validation = np.random.default_rng(92).integers(0, 256, (96, 128), dtype=np.uint8)
        test_near_duplicate = np.clip(training.astype(np.int16) + 1, 0, 255).astype(np.uint8)
        self.write_image(self.root / "images/train/train.png", training)
        self.write_image(self.root / "images/val/val.png", validation)
        self.write_image(self.root / "images/test/test.png", test_near_duplicate)

        with redirect_stdout(io.StringIO()), self.assertRaisesRegex(RuntimeError, "train/test"):
            audit_prepared_splits(self.data_yaml)

    def test_install_mode_requires_nonempty_independent_test_before_training(self):
        train = np.random.default_rng(110).integers(0, 256, (96, 128), dtype=np.uint8)
        validation = np.random.default_rng(111).integers(0, 256, (96, 128), dtype=np.uint8)
        self.write_image(self.root / "images/train/train.png", train)
        self.write_image(self.root / "images/val/val.png", validation)

        with redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, "cancela antes"):
            audit_prepared_splits(self.data_yaml, require_test=True)

    def test_candidate_registration_records_hash_without_marking_it_active(self):
        artifact = self.root / "candidate.pt"
        artifact.write_bytes(b"synthetic candidate bytes")
        manifest_path = self.root / "model-manifest.json"
        manifest_path.write_text(json.dumps({
            "active": {"path": "backend/models/active.pt", "sha256": "a" * 64},
            "candidates": [{"path": "backend/models/handwash_yolo26s_robust.pt", "sha256": "old"}],
        }))

        digest = register_candidate_model(
            artifact,
            manifest_path,
            "backend/models/handwash_yolo26s_robust.pt",
        )
        manifest = json.loads(manifest_path.read_text())
        registered = [
            item for item in manifest["candidates"]
            if item["path"] == "backend/models/handwash_yolo26s_robust.pt"
        ]

        self.assertEqual(hashlib.sha256(artifact.read_bytes()).hexdigest(), digest)
        self.assertEqual(1, len(registered))
        self.assertEqual(digest, registered[0]["sha256"])
        self.assertEqual("backend/models/active.pt", manifest["active"]["path"])
        self.assertEqual("detect", registered[0]["task"])

    def test_invalid_negative_class_id_is_rejected_instead_of_mapping_to_last_class(self):
        source = self.root / "source"
        (source / "train/images").mkdir(parents=True)
        (source / "train/labels").mkdir(parents=True)
        image = np.random.default_rng(31).integers(0, 256, (32, 32), dtype=np.uint8)
        self.write_image(source / "train/images/frame.png", image)
        (source / "train/labels/frame.txt").write_text("-1 0.5 0.5 0.3 0.3\n")

        with self.assertRaisesRegex(ValueError, "fuera de rango"):
            merge_split(source, self.root / "prepared", "train", ["Step_1"])

    def test_canonical_project_labels_map_to_the_seven_backend_classes(self):
        names = [
            "Paso1_Palmas", "Paso2_Dorsos", "Paso3_Interdigitales", "Paso4_Nudillos",
            "Paso5_Pulgar", "Paso6_PuntaDeDedos", "Paso7_Circulares",
        ]
        self.assertEqual(list(range(7)), [normalize_label(name) for name in names])
        self.assertEqual(1, normalize_label("Step_2_Left"))
        self.assertIsNone(normalize_label("07_turn_off_faucet_with_paper_towel"))

    def test_grouped_yolo_layout_is_accepted_and_explicit_negative_is_preserved(self):
        source = self.root / "grouped"
        output = self.root / "prepared"
        names = [
            "Paso1_Palmas", "Paso2_Dorsos", "Paso3_Interdigitales", "Paso4_Nudillos",
            "Paso5_Pulgar", "Paso6_PuntaDeDedos", "Paso7_Circulares",
        ]
        for split in ("train", "val"):
            (source / "images" / split).mkdir(parents=True)
            (source / "labels" / split).mkdir(parents=True)
        train_image = np.random.default_rng(711).integers(0, 256, (48, 48), dtype=np.uint8)
        val_image = np.random.default_rng(712).integers(0, 256, (48, 48), dtype=np.uint8)
        self.write_image(source / "images/train/negative.png", train_image)
        self.write_image(source / "images/val/paso7.png", val_image)
        (source / "labels/train/negative.txt").write_text("", encoding="utf-8")
        (source / "labels/val/paso7.txt").write_text(
            "6 0.5 0.5 0.3 0.3\n", encoding="utf-8"
        )
        (source / "data.yaml").write_text(yaml.safe_dump({
            "path": ".", "train": "images/train", "val": "images/val",
            "nc": len(names), "names": {index: name for index, name in enumerate(names)},
        }), encoding="utf-8")

        prepared_yaml = prepare_dataset(source, output)
        self.assertTrue((output / "images/train/train_000000.png").is_file())
        self.assertEqual("", (output / "labels/train/train_000000.txt").read_text(encoding="utf-8"))
        self.assertIn("6 ", (output / "labels/val/val_000000.txt").read_text(encoding="utf-8"))
        prepared_config = yaml.safe_load(prepared_yaml.read_text(encoding="utf-8"))
        self.assertEqual(7, prepared_config["nc"])

    def test_existing_output_is_not_deleted_or_reused(self):
        output_dir = self.root / "runs/candidate"
        prepared_dir = self.root / "runs/candidate_dataset"
        prepared_dir.mkdir(parents=True)
        sentinel = prepared_dir / "preserve.txt"
        sentinel.write_text("existing user data")

        with self.assertRaisesRegex(FileExistsError, "No se reutiliza ni elimina"):
            ensure_fresh_run_paths(output_dir)

        self.assertEqual("existing user data", sentinel.read_text())


if __name__ == "__main__":
    unittest.main()
