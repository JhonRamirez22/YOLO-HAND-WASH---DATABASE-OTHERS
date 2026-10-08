import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dataset_contracts import (
    DATASET5_CLASS_NAMES,
    DATASET5_MOVEMENT_TO_CLASS,
    consensus_frame_label,
    ensure_fresh_dataset_output,
    validate_dataset5_contract,
    validate_dataset5_contract_file,
    validate_dataset5_source_taxonomy,
)
from prepare_dataset5 import consensus_annotation


class Dataset5ContractTests(unittest.TestCase):
    def make_valid_dataset(self, root: Path) -> tuple[dict, Path]:
        for split in ("train", "val"):
            images = root / "images" / split
            labels = root / "labels" / split
            images.mkdir(parents=True)
            labels.mkdir(parents=True)
            for class_id in range(len(DATASET5_CLASS_NAMES)):
                stem = f"{split}_{class_id}"
                (images / f"{stem}.jpg").write_bytes(b"synthetic test image")
                (labels / f"{stem}.txt").write_text(
                    f"{class_id} 0.5 0.5 0.2 0.2\n", encoding="utf-8"
                )
        config = {
            "projectDatasetContractVersion": 2,
            "path": ".",
            "train": "images/train",
            "val": "images/val",
            "nc": len(DATASET5_CLASS_NAMES),
            "names": dict(enumerate(DATASET5_CLASS_NAMES)),
        }
        return config, root / "dataset5_combined.yaml"

    def test_faucet_closure_is_never_circular_friction(self):
        self.assertEqual(DATASET5_MOVEMENT_TO_CLASS[0], 7)
        self.assertEqual(DATASET5_MOVEMENT_TO_CLASS[7], 7)
        self.assertNotIn(6, DATASET5_MOVEMENT_TO_CLASS.values())
        with self.assertRaisesRegex(RuntimeError, "seis movimientos"):
            validate_dataset5_source_taxonomy()

    def test_output_guard_preserves_nonempty_dataset(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "existing"
            output.mkdir()
            marker = output / "keep.txt"
            marker.write_text("user data", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                ensure_fresh_dataset_output(output)
            self.assertEqual(marker.read_text(encoding="utf-8"), "user data")

    def test_movement_consensus_ignores_votes_from_nonwashing_frames(self):
        votes = [(1, 2), (1, 3), (1, 2), (1, 3), (1, 2), (0, 1), (0, 1), (0, 1)]
        self.assertEqual(consensus_frame_label(votes), (1, 2))

    def test_tied_washing_votes_abstain_independent_of_input_order(self):
        votes = [(1, 1), (0, 7)]
        self.assertIsNone(consensus_frame_label(votes))
        self.assertIsNone(consensus_frame_label(list(reversed(votes))))

    def test_tied_movement_votes_abstain_instead_of_using_file_order(self):
        votes = [(1, 1), (1, 2), (0, 7)]
        self.assertIsNone(consensus_frame_label(votes))
        self.assertIsNone(consensus_frame_label(list(reversed(votes))))

    def test_consensus_annotation_retains_ambiguous_frame_as_abstention(self):
        annotators = [
            ("annotator-a", {12: (1, 1)}),
            ("annotator-b", {12: (0, 7)}),
        ]
        self.assertEqual(consensus_annotation(annotators), {12: None})

    def test_empty_or_missing_output_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "new"
            ensure_fresh_dataset_output(missing)
            missing.mkdir()
            ensure_fresh_dataset_output(missing)

    def test_versioned_dataset_requires_all_classes_in_both_splits(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, config_path = self.make_valid_dataset(root)
            validate_dataset5_contract(config, config_path)

            missing_label = root / "labels" / "val" / "val_6.txt"
            missing_label.write_text("", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "Paso7_Circulares"):
                validate_dataset5_contract(config, config_path)

    def test_legacy_yaml_is_rejected_before_training(self):
        with tempfile.TemporaryDirectory() as directory:
            config, config_path = self.make_valid_dataset(Path(directory))
            del config["projectDatasetContractVersion"]
            with self.assertRaisesRegex(RuntimeError, "histórico o sin contrato"):
                validate_dataset5_contract(config, config_path)

    def test_checked_in_historical_yaml_is_rejected_by_training_preflight(self):
        project_root = Path(__file__).resolve().parents[1]
        historical_yaml = project_root / "DataSet5_YOLO" / "dataset5_combined.yaml"
        with self.assertRaisesRegex(RuntimeError, "histórico o sin contrato"):
            validate_dataset5_contract_file(historical_yaml)

    def test_unpaired_images_and_labels_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, config_path = self.make_valid_dataset(root)
            (root / "labels" / "train" / "train_0.txt").unlink()
            with self.assertRaisesRegex(RuntimeError, "uno-a-uno"):
                validate_dataset5_contract(config, config_path)

    def test_duplicate_image_stems_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, config_path = self.make_valid_dataset(root)
            (root / "images" / "train" / "train_0.png").write_bytes(b"duplicate stem")
            with self.assertRaisesRegex(RuntimeError, "uno-a-uno"):
                validate_dataset5_contract(config, config_path)

    def test_invalid_yolo_box_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, config_path = self.make_valid_dataset(root)
            (root / "labels" / "train" / "train_0.txt").write_text(
                "0 1.2 0.5 0.2 0.2\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(RuntimeError, "Caja fuera de rango"):
                validate_dataset5_contract(config, config_path)


if __name__ == "__main__":
    unittest.main()
