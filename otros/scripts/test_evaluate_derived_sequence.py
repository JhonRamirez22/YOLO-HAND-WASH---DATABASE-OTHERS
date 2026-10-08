"""Tests for replay timebase and one-vote-per-source-frame guarantees."""
from contextlib import redirect_stderr
import csv
import io
import tempfile
import unittest
from pathlib import Path
import sys
from unittest.mock import patch

from evaluate_derived_sequence import (
    DERIVED_CLASSIFIER_NAMES,
    load_test_sequence,
    main,
    source_frame_time_seconds,
    validate_unique_source_frames,
)


class DerivedSequenceEvaluationTest(unittest.TestCase):
    def test_source_frame_time_uses_declared_fps(self):
        self.assertEqual(8.0, source_frame_time_seconds(240, 30.0))
        self.assertEqual(12.0, source_frame_time_seconds(240, 20.0))

    def test_invalid_source_fps_is_rejected(self):
        for fps in (0.0, -30.0, float("nan"), float("inf")):
            with self.subTest(fps=fps), self.assertRaises(ValueError):
                source_frame_time_seconds(240, fps)
        with self.assertRaisesRegex(ValueError, "non-negative integer"):
            source_frame_time_seconds(-1, 30.0)

    @staticmethod
    def _write_manifest(root: Path, rows: list[dict[str, str]],
                        *, create_test_images: bool = True) -> None:
        fields = [
            "split", "relative_image", "class_id", "class_name",
            "video", "source_frame_index",
        ]
        manifest = root / "manifest.csv"
        with manifest.open("w", newline="", encoding="utf-8") as output:
            writer = csv.DictWriter(output, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        if create_test_images:
            for row in rows:
                if row["split"] == "test":
                    image = root / row["relative_image"]
                    image.parent.mkdir(parents=True, exist_ok=True)
                    image.write_bytes(b"test-frame-placeholder")

    @staticmethod
    def _row(split: str, video: str, frame: int, class_id: int = 1,
             relative_image: str | None = None) -> dict[str, str]:
        class_name = DERIVED_CLASSIFIER_NAMES[class_id]
        return {
            "split": split,
            "relative_image": relative_image or f"{split}/{class_name}/{video}_f{frame:06d}.jpg",
            "class_id": str(class_id),
            "class_name": class_name,
            "video": video,
            "source_frame_index": str(frame),
        }

    def test_manifest_must_keep_each_source_video_in_one_split(self):
        with tempfile.TemporaryDirectory(prefix="handwash-eval-manifest-") as directory:
            root = Path(directory)
            rows = [
                self._row("train", "video-a", 15),
                self._row("test", "video-a", 30),
            ]
            self._write_manifest(root, rows)
            with self.assertRaisesRegex(ValueError, "más de un split"):
                load_test_sequence("video-a", root)

    def test_manifest_rejects_duplicate_column_names(self):
        with tempfile.TemporaryDirectory(prefix="handwash-eval-manifest-") as directory:
            root = Path(directory)
            (root / "manifest.csv").write_text(
                "split,split,relative_image,class_id,class_name,video,source_frame_index\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "nombres de columna duplicados"):
                load_test_sequence("video-a", root)

    def test_manifest_missing_test_frame_is_not_silently_omitted(self):
        with tempfile.TemporaryDirectory(prefix="handwash-eval-manifest-") as directory:
            root = Path(directory)
            self._write_manifest(
                root, [self._row("test", "video-a", 15)], create_test_images=False
            )
            with self.assertRaisesRegex(ValueError, "falta una imagen declarada"):
                load_test_sequence("video-a", root)

    def test_manifest_rejects_wrong_class_name_and_path_escape(self):
        with tempfile.TemporaryDirectory(prefix="handwash-eval-manifest-") as directory:
            root = Path(directory)
            bad_label = self._row("test", "video-a", 15)
            bad_label["class_name"] = DERIVED_CLASSIFIER_NAMES[2]
            self._write_manifest(root, [bad_label])
            with self.assertRaisesRegex(ValueError, "class_id y class_name"):
                load_test_sequence("video-a", root)

        with tempfile.TemporaryDirectory(prefix="handwash-eval-manifest-") as directory:
            root = Path(directory)
            escaped = self._row("test", "video-a", 15, relative_image="../outside.jpg")
            self._write_manifest(root, [escaped], create_test_images=False)
            with self.assertRaisesRegex(ValueError, "ruta de imagen no canónica"):
                load_test_sequence("video-a", root)

    def test_valid_manifest_loads_every_held_out_frame(self):
        with tempfile.TemporaryDirectory(prefix="handwash-eval-manifest-") as directory:
            root = Path(directory)
            rows = [
                self._row("train", "train-video", 30),
                self._row("test", "video-a", 30),
                self._row("test", "video-a", 15),
            ]
            self._write_manifest(root, rows)
            sequence = load_test_sequence("video-a", root)
            self.assertEqual([15, 30], [frame_index for frame_index, _, _ in sequence])
            self.assertTrue(all(path.is_file() for _, _, path in sequence))

    def test_replay_requires_source_fps_instead_of_assuming_thirty(self):
        with patch.object(sys, "argv", ["evaluate_derived_sequence.py"]):
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                main()
        self.assertEqual(2, error.exception.code)

    def test_each_source_frame_contributes_at_most_one_annotation_vote(self):
        validate_unique_source_frames([
            (15, 1, Path("frame-a")),
            (30, 2, Path("frame-b")),
        ])
        with self.assertRaisesRegex(ValueError, "Duplicate source_frame_index 15"):
            validate_unique_source_frames([
                (15, 1, Path("frame-a")),
                (15, 2, Path("frame-a-conflicting-label")),
            ])


if __name__ == "__main__":
    unittest.main()
