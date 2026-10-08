import csv
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from train_handwash_who import (
    ACTION_FOR_SOAP_REGION,
    REQUIRED_CLASSES,
    class_metrics,
    candidate_meets_thresholds,
    list_images,
    normalized_data_config,
    read_names,
    split_path,
    validate_class_distribution,
    validate_group_manifest,
)


class TrainHandwashWhoValidationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dataset = Path(self.temp.name).resolve()
        self.config = {"path": str(self.dataset), "train": "train/images", "val": "valid/images", "test": "test/images"}
        for split in ("train", "valid", "test"):
            images = self.dataset / split / "images"
            labels = self.dataset / split / "labels"
            images.mkdir(parents=True)
            labels.mkdir(parents=True)
            for class_id in range(len(REQUIRED_CLASSES)):
                image = images / f"{class_id}.jpg"
                image.write_bytes(b"test")
                lines = [f"{class_id} 0.5 0.5 0.25 0.25"]
                name = REQUIRED_CLASSES[class_id]
                region = next((region for region in ACTION_FOR_SOAP_REGION
                               if name.endswith("_" + region)), None)
                if region is not None:
                    action_id = REQUIRED_CLASSES.index(ACTION_FOR_SOAP_REGION[region])
                    lines.append(f"{action_id} 0.5 0.5 0.75 0.75")
                (labels / f"{class_id}.txt").write_text("\n".join(lines) + "\n")

    def tearDown(self):
        self.temp.cleanup()

    def test_accepts_roboflow_val_alias_and_validates_all_classes(self):
        self.assertEqual(self.dataset / "valid/images", split_path(self.config, self.dataset, "valid"))
        counts = validate_class_distribution(self.config, self.dataset, REQUIRED_CLASSES)
        self.assertEqual(len(REQUIRED_CLASSES), counts["valid"])

    def test_resolves_paths_inside_yolo_image_list(self):
        image_list = self.dataset / "train.txt"
        image_list.write_text("train/images/0.jpg\n")
        self.assertEqual(
            [self.dataset / "train/images/0.jpg"],
            list_images(image_list, self.dataset),
        )

    def test_normalizes_raw_roboflow_zip_split_paths(self):
        config = {
            "train": "../train/images",
            "val": "../valid/images",
            "test": "../test/images",
        }
        self.assertEqual(self.dataset / "train/images", split_path(config, self.dataset, "train"))
        normalized = normalized_data_config(config, self.dataset, REQUIRED_CLASSES)
        self.assertEqual(str(self.dataset / "valid/images"), normalized["val"])
        self.assertEqual(len(REQUIRED_CLASSES), normalized["nc"])

    def test_group_manifest_must_cover_images_and_keep_groups_disjoint(self):
        manifest = self.dataset / "groups.csv"
        with manifest.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=("image", "person", "video", "split"))
            writer.writeheader()
            for split in ("train", "valid", "test"):
                for class_id in range(len(REQUIRED_CLASSES)):
                    writer.writerow({
                        "image": f"{split}/images/{class_id}.jpg",
                        "person": f"participant-{split}",
                        "video": f"video-{split}",
                        "split": split,
                    })
        validate_group_manifest(manifest, self.dataset, self.config)

        (self.dataset / "valid/images/extra.jpg").write_bytes(b"test")
        with manifest.open("a", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=("image", "person", "video", "split"))
            writer.writerow({
                "image": "valid/images/extra.jpg", "person": "participant-train",
                "video": "video-valid-extra", "split": "valid",
            })
        with self.assertRaisesRegex(ValueError, "Fuga de participantes/videos"):
            validate_group_manifest(manifest, self.dataset, self.config)

    def test_rejects_non_finite_boxes_and_duplicate_class_names(self):
        with self.assertRaisesRegex(ValueError, "nombres únicos"):
            validate_class_distribution(self.config, self.dataset, [*REQUIRED_CLASSES, REQUIRED_CLASSES[0]])
        (self.dataset / "train/labels/0.txt").write_text("0 nan 0.5 0.25 0.25\n")
        with self.assertRaisesRegex(ValueError, "fuera de rango"):
            validate_class_distribution(self.config, self.dataset, REQUIRED_CLASSES)

    def test_rejects_soap_region_without_matching_spatial_action(self):
        soap_name = "ESPUMA_VISIBLE_PALMA_IZQUIERDA"
        soap_id = REQUIRED_CLASSES.index(soap_name)
        label = self.dataset / f"train/labels/{soap_id}.txt"
        label.write_text(f"{soap_id} 0.5 0.5 0.25 0.25\n")
        with self.assertRaisesRegex(ValueError, "no pertenece a una caja"):
            validate_class_distribution(self.config, self.dataset, REQUIRED_CLASSES)

        action_id = REQUIRED_CLASSES.index("OMS_03_FROTAR_PALMAS")
        label.write_text(
            f"{soap_id} 0.2 0.2 0.2 0.2\n"
            f"{action_id} 0.8 0.8 0.2 0.2\n"
        )
        with self.assertRaisesRegex(ValueError, "no pertenece a una caja"):
            validate_class_distribution(self.config, self.dataset, REQUIRED_CLASSES)

    def test_rejects_non_consecutive_class_ids(self):
        with self.assertRaisesRegex(ValueError, "consecutivos"):
            read_names({"names": {"0": REQUIRED_CLASSES[0], "2": REQUIRED_CLASSES[1]}})

    def test_class_metrics_reject_missing_or_non_finite_results(self):
        complete = SimpleNamespace(
            ap_class_index=list(range(len(REQUIRED_CLASSES))),
            class_result=lambda position: (0.90, 0.80, 0.75, 0.50),
        )
        metrics = class_metrics(complete, REQUIRED_CLASSES)
        self.assertEqual(len(REQUIRED_CLASSES), len(metrics))
        self.assertEqual(0.80, metrics[REQUIRED_CLASSES[0]]["recall"])

        incomplete = SimpleNamespace(
            ap_class_index=list(range(len(REQUIRED_CLASSES) - 1)),
            class_result=complete.class_result,
        )
        with self.assertRaisesRegex(ValueError, "no produjo métricas"):
            class_metrics(incomplete, REQUIRED_CLASSES)

        invalid = SimpleNamespace(
            ap_class_index=complete.ap_class_index,
            class_result=lambda position: (float("nan"), 0.80, 0.75, 0.50),
        )
        with self.assertRaisesRegex(ValueError, "Métricas inválidas"):
            class_metrics(invalid, REQUIRED_CLASSES)

    def test_candidate_gate_rejects_one_weak_soap_region(self):
        box = SimpleNamespace(
            ap_class_index=list(range(len(REQUIRED_CLASSES))),
            class_result=lambda position: (0.90, 0.80, 0.75, 0.50),
        )
        metrics = class_metrics(box, REQUIRED_CLASSES)
        def accepted():
            return candidate_meets_thresholds(0.80, metrics, 0.70, 0.30, 0.60, 0.60)

        self.assertTrue(accepted())
        metrics["ESPUMA_VISIBLE_PALMA_DERECHA"]["recall"] = 0.20
        self.assertFalse(accepted())
        with self.assertRaisesRegex(ValueError, "entre 0 y 1"):
            candidate_meets_thresholds(0.80, metrics, -1.0, 0.30, 0.60, 0.60)


if __name__ == "__main__":
    unittest.main()
