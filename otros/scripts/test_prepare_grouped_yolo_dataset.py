from pathlib import Path
import json
import tempfile
import unittest

import cv2
import numpy as np
import yaml

from prepare_grouped_yolo_dataset import create_grouped_dataset, plan_grouped_dataset
from audit_yolo_split_duplicates import find_duplicate_candidates


class GroupedYoloDatasetTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.source = self.root / "source"
        self.data_yaml = self.source / "data.yaml"
        self._create_source()

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def _write_image(path: Path, image: np.ndarray) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(path), image):
            raise AssertionError(f"No se pudo escribir fixture de prueba: {path}")

    def _add_sample(self, source_split: str, name: str, image: np.ndarray, class_id: int) -> Path:
        image_path = self.source / "images" / source_split / f"{name}.png"
        label_path = self.source / "labels" / source_split / f"{name}.txt"
        self._write_image(image_path, image)
        label_path.parent.mkdir(parents=True, exist_ok=True)
        label_path.write_text(f"{class_id} 0.5 0.5 0.3 0.3\n", encoding="utf-8")
        return image_path

    def _create_source(self) -> None:
        rng = np.random.default_rng(782)
        names = [
            "Paso1_Palmas", "Paso2_Dorsos", "Paso3_Interdigitales", "Paso4_Nudillos",
            "Paso5_Pulgar", "Paso6_PuntaDeDedos", "Paso7_Circulares",
        ]
        for class_id in range(len(names)):
            for variant in range(3):
                image = rng.integers(0, 256, (96, 128), dtype=np.uint8)
                split = "train" if variant != 1 else "val"
                self._add_sample(split, f"class{class_id}_variant{variant}", image, class_id)

        base = cv2.imread(
            str(self.source / "images/train/class0_variant0.png"), cv2.IMREAD_GRAYSCALE
        )
        near = np.clip(base.astype(np.int16) + 1, 0, 255).astype(np.uint8)
        self._add_sample("val", "class0_near_duplicate", near, 0)
        self.data_yaml.write_text(yaml.safe_dump({
            "path": str(self.source),
            "train": "images/train",
            "val": "images/val",
            "nc": len(names),
            "names": {index: name for index, name in enumerate(names)},
        }, sort_keys=False), encoding="utf-8")

    def test_plan_is_deterministic_and_keeps_near_duplicates_together(self):
        first = plan_grouped_dataset(self.data_yaml)
        second = plan_grouped_dataset(self.data_yaml)
        self.assertEqual(first["splitCounts"], second["splitCounts"])
        self.assertEqual(
            {split: [group.group_id for group in groups]
             for split, groups in first["assignments"].items()},
            {split: [group.group_id for group in groups]
             for split, groups in second["assignments"].items()},
        )

        near_duplicate = next(
            index for index, item in enumerate(first["images"])
            if item.image_path.name == "class0_near_duplicate.png"
        )
        source_image = next(
            index for index, item in enumerate(first["images"])
            if item.image_path.name == "class0_variant0.png"
        )
        group_by_image = {
            index: split for split, groups in first["assignments"].items()
            for group in groups for index in group.image_indexes
        }
        self.assertEqual(group_by_image[source_image], group_by_image[near_duplicate])

    def test_creates_portable_train_val_test_without_cross_split_duplicates(self):
        output = self.root / "grouped"
        report = create_grouped_dataset(self.data_yaml, output)
        self.assertEqual(22, report["images"]["train"] + report["images"]["val"] + report["images"]["test"])
        config = yaml.safe_load((output / "data.yaml").read_text(encoding="utf-8"))
        self.assertEqual(".", config["path"])
        self.assertEqual(7, config["nc"])
        manifest = json.loads((output / "group_split_manifest.json").read_text(encoding="utf-8"))
        self.assertFalse(manifest["sourceVideoSeparationProven"])
        self.assertEqual(22, len(manifest["files"]))
        self.assertEqual(22, len(list((output / "images").rglob("*.png"))))
        self.assertEqual(22, len(list((output / "labels").rglob("*.txt"))))

        for left, right in (("train", "val"), ("train", "test"), ("val", "test")):
            _, _, candidates = find_duplicate_candidates(
                output / "images" / left, output / "images" / right
            )
            self.assertEqual([], candidates, f"duplicados entre {left} y {right}")

        # The original tree remains readable and unchanged by the derived copy.
        self.assertTrue((self.source / "images/train/class0_variant0.png").is_file())
        self.assertEqual(22, len(list((self.source / "images").rglob("*.png"))))

    def test_refuses_to_overwrite_an_existing_output(self):
        output = self.root / "grouped"
        output.mkdir()
        sentinel = output / "keep.txt"
        sentinel.write_text("do not overwrite", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            create_grouped_dataset(self.data_yaml, output)
        self.assertEqual("do not overwrite", sentinel.read_text(encoding="utf-8"))

    def test_rejects_output_inside_source_without_creating_it(self):
        output = self.source / "derived"
        with self.assertRaisesRegex(ValueError, "dentro del dataset fuente"):
            create_grouped_dataset(self.data_yaml, output)
        self.assertFalse(output.exists())

    def test_missing_label_fails_before_creating_output(self):
        (self.source / "labels/train/class0_variant0.txt").unlink()
        output = self.root / "should-not-exist"
        with self.assertRaisesRegex(FileNotFoundError, "Falta el .txt"):
            create_grouped_dataset(self.data_yaml, output)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
