import csv
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np
import yaml

from prepare_oms_review_frames import load_manifest, prepare
from train_handwash_who import REQUIRED_CLASSES, validate_class_distribution


class PrepareOmsReviewFramesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.video = self.root / "complete_wash.avi"
        writer = cv2.VideoWriter(str(self.video), cv2.VideoWriter_fourcc(*"MJPG"), 6.0, (640, 480))
        self.assertTrue(writer.isOpened())
        for index in range(12):
            writer.write(np.full((480, 640, 3), index * 10, dtype=np.uint8))
        writer.release()
        self.manifest = self.root / "videos.csv"

    def tearDown(self):
        self.temp.cleanup()

    def write_manifest(self, rows):
        with self.manifest.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=(
                "video_id", "video", "person", "split", "consent"))
            writer.writeheader()
            writer.writerows(rows)

    def row(self, **overrides):
        return {"video_id": "wash01", "video": self.video.name,
                "person": "person01", "split": "train", "consent": "yes", **overrides}

    def test_extracts_provenance_and_exact_taxonomy_without_fake_labels(self):
        self.write_manifest([self.row()])
        output = self.root / "review_bundle"
        count = prepare(self.manifest, output, sample_fps=2.0, long_side=320)
        self.assertEqual(4, count)
        self.assertEqual(4, len(list((output / "train/images").glob("*.jpg"))))
        self.assertFalse((output / "train/labels").exists())
        config = yaml.safe_load((output / "data.yaml").read_text())
        self.assertEqual(REQUIRED_CLASSES, config["names"])
        self.assertEqual(str(output.absolute()), config["path"])
        with (output / "group_manifest.csv").open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(4, len(rows))
        self.assertEqual({"person01"}, {row["person"] for row in rows})
        self.assertEqual({"wash01"}, {row["video"] for row in rows})
        image = cv2.imread(str(output / rows[0]["image"]))
        self.assertEqual((240, 320), image.shape[:2])
        with self.assertRaisesRegex(FileNotFoundError, "Falta anotación YOLO"):
            validate_class_distribution(config, output, REQUIRED_CLASSES)
        with self.assertRaises(FileExistsError):
            prepare(self.manifest, output)

    def test_rejects_missing_consent_and_split_leakage(self):
        self.write_manifest([self.row(consent="no")])
        with self.assertRaisesRegex(ValueError, "consentimiento"):
            load_manifest(self.manifest)

        second_video = self.root / "second_wash.avi"
        second_video.write_bytes(self.video.read_bytes())
        self.write_manifest([
            self.row(),
            self.row(video_id="wash02", video=second_video.name, split="test"),
        ])
        with self.assertRaisesRegex(ValueError, "aparece en train y test"):
            load_manifest(self.manifest)

        self.write_manifest([
            self.row(),
            self.row(video_id="wash02", person="person02", split="test"),
        ])
        with self.assertRaisesRegex(ValueError, "mismo archivo de video"):
            load_manifest(self.manifest)


if __name__ == "__main__":
    unittest.main()
