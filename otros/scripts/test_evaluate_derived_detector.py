import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from evaluate_derived_detector import (
    camera_id_from_path,
    matches_expected_class,
    recover_pose_for_diagnostic,
    sample_class_paths,
)


class DerivedDetectorEvaluationTest(unittest.TestCase):
    def test_camera_id_parser_marks_unlabeled_files_explicitly(self):
        self.assertEqual("102", camera_id_from_path(Path("VIDEOS5_camera102_f000120.jpg")))
        self.assertEqual("unknown", camera_id_from_path(Path("frame.jpg")))

    def test_camera_sampling_is_deterministic_and_balanced(self):
        paths = [
            Path("VIDEOS_camera102_f000001.jpg"),
            Path("VIDEOS_camera100_f000003.jpg"),
            Path("VIDEOS_camera100_f000001.jpg"),
            Path("VIDEOS_camera102_f000000.jpg"),
            Path("VIDEOS_camera100_f000002.jpg"),
            Path("VIDEOS_camera100_f000000.jpg"),
        ]

        sampled = sample_class_paths(paths, per_class=20, per_camera=2)
        sampled_reversed = sample_class_paths(list(reversed(paths)), 20, 2)

        self.assertEqual(sampled, sampled_reversed)
        self.assertEqual(Counter({"100": 2, "102": 2}),
                         Counter(camera_id_from_path(path) for path in sampled))

    def test_global_sampling_and_empty_inputs_are_safe(self):
        paths = [Path(f"frame_{index}.jpg") for index in range(5)]

        self.assertEqual([paths[0], paths[2], paths[4]],
                         sample_class_paths(paths, per_class=3))
        self.assertEqual([], sample_class_paths([], per_class=3))

    def test_negative_and_positive_class_match_semantics(self):
        self.assertTrue(matches_expected_class(None, None))
        self.assertFalse(matches_expected_class(None, "Paso1_Palmas"))
        self.assertTrue(matches_expected_class("Paso1_", "Paso1_Palmas"))
        self.assertFalse(matches_expected_class("Paso1_", None))

    def test_missing_hand_uses_runtime_recovery_and_keeps_best_evidence(self):
        model, frame, primary_result, recovered_result = (object() for _ in range(4))
        primary_pose = {"manosVisibles": 1}
        recovered_pose = {"manosVisibles": 2}
        primary_crops = ["primary"]
        recovered_crops = ["recovered-left", "recovered-right"]
        options = {"imgsz": 640, "save": False}

        with (
            patch("evaluate_derived_detector.recover_hand_pose",
                  return_value=(recovered_result, 2)) as recover,
            patch("evaluate_derived_detector.HandMotionEstimator") as estimator,
            patch("evaluate_derived_detector.partial_crop_guidance_hands",
                  return_value=recovered_crops),
            patch("evaluate_derived_detector.prefer_recovered_motion", return_value=True),
            patch("evaluate_derived_detector.prefer_recovered_localization", return_value=True),
        ):
            estimator.return_value.update.return_value = recovered_pose
            result, pose, crops, inference_count = recover_pose_for_diagnostic(
                model, frame, primary_result, primary_pose, primary_crops, options, 0.1
            )

        recover.assert_called_once_with(model, frame, options, 0.1)
        self.assertIs(recovered_result, result)
        self.assertIs(recovered_pose, pose)
        self.assertEqual(recovered_crops, crops)
        self.assertEqual(3, inference_count)  # high-res frame plus two tiles

    def test_bilateral_primary_pose_skips_unneeded_recovery(self):
        model, frame, primary_result = object(), object(), object()
        primary_pose = {"manosVisibles": 2}
        primary_crops = ["primary"]

        with patch("evaluate_derived_detector.recover_hand_pose") as recover:
            result, pose, crops, inference_count = recover_pose_for_diagnostic(
                model, frame, primary_result, primary_pose, primary_crops,
                {"imgsz": 640}, 0.1,
            )

        recover.assert_not_called()
        self.assertIs(primary_result, result)
        self.assertIs(primary_pose, pose)
        self.assertIs(primary_crops, crops)
        self.assertEqual(0, inference_count)


if __name__ == "__main__":
    unittest.main()
