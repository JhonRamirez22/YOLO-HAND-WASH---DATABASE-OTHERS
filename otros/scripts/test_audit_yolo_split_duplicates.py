from pathlib import Path
import tempfile
import unittest

import cv2
import numpy as np

from audit_yolo_split_duplicates import _dataset_split_paths, find_duplicate_candidates


class YoloSplitDuplicateAuditTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.train = self.root / "images/train"
        self.val = self.root / "images/val"
        self.train.mkdir(parents=True)
        self.val.mkdir(parents=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def write_image(path: Path, image: np.ndarray) -> None:
        if not cv2.imwrite(str(path), image):
            raise AssertionError(f"No se pudo escribir fixture de prueba: {path}")

    def test_reports_exact_binary_duplicate_between_splits(self):
        generator = np.random.default_rng(19)
        image = generator.integers(0, 256, (96, 128), dtype=np.uint8)
        self.write_image(self.train / "frame_train.png", image)
        self.write_image(self.val / "frame_val.png", image)

        _, _, matches = find_duplicate_candidates(self.train, self.val)

        self.assertEqual(1, len(matches))
        self.assertTrue(matches[0].exact_bytes)
        self.assertEqual(0.0, matches[0].mean_absolute_error)

    def test_reports_reencoded_near_duplicate_and_ignores_distinct_frame(self):
        generator = np.random.default_rng(41)
        source = generator.integers(0, 256, (96, 128), dtype=np.uint8)
        near = np.clip(source.astype(np.int16) + 1, 0, 255).astype(np.uint8)
        distinct = 255 - source
        self.write_image(self.train / "source.png", source)
        self.write_image(self.val / "reencoded.png", near)
        self.write_image(self.val / "different.png", distinct)

        _, _, matches = find_duplicate_candidates(self.train, self.val)

        self.assertEqual(1, len(matches))
        self.assertEqual("reencoded.png", matches[0].validation_path.name)
        self.assertFalse(matches[0].exact_bytes)
        self.assertLessEqual(matches[0].mean_absolute_error, 5.0)

    def test_resolves_portable_yaml_paths_relative_to_yaml_directory(self):
        data_yaml = self.root / "data.yaml"
        data_yaml.write_text(
            "path: .\ntrain: images/train\nval: images/val\nnc: 1\nnames: [hand]\n",
            encoding="utf-8",
        )

        train, val = _dataset_split_paths(data_yaml)

        self.assertEqual(self.train.resolve(), train)
        self.assertEqual(self.val.resolve(), val)

    def test_resolves_repository_yaml_path_relative_to_project_root(self):
        root = Path(__file__).resolve().parents[1]
        data_yaml = root / "datasets/handwash_public_7steps.yaml"

        train, val = _dataset_split_paths(data_yaml)

        self.assertEqual(root / "datasets/handwash_public_7steps/images/train", train)
        self.assertEqual(root / "datasets/handwash_public_7steps/images/val", val)


if __name__ == "__main__":
    unittest.main()
