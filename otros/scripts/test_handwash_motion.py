"""Synthetic keypoint checks only; no camera access or image recording."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
import run_yolo26_continuity_camera as camera


class Tensor:
    def __init__(self, value): self.value = value
    def cpu(self): return self
    def numpy(self): return self.value
    def __getitem__(self, key): return self.value[key]


def poses(points, confidence=0.9):
    boxes = []
    for hand in points:
        xy = hand[:, :2]
        bounds = [*xy.min(axis=0) - 4, *xy.max(axis=0) + 4]
        boxes.append(SimpleNamespace(
            xyxy=np.array([bounds]), conf=SimpleNamespace(item=lambda value=confidence: value)
        ))
    return SimpleNamespace(boxes=boxes, keypoints=SimpleNamespace(data=Tensor(points)))


class MotionTest(unittest.TestCase):
    def setUp(self):
        xy = np.array([[100 + i % 5 * 10, 100 + i // 5 * 10, .95] for i in range(21)], dtype=float)
        self.points = np.stack((xy, xy + [65, 0, 0]))
        self.estimator = camera.HandMotionEstimator()
        self.estimator.update(poses(self.points), 1, 10.)

    def test_static_hands_have_no_motion(self):
        result = self.estimator.update(poses(self.points), 2, 10.2)
        self.assertTrue(result["medicionValida"])
        self.assertLess(result["movimientoNormalizado"], 1e-8)

    def test_camera_translation_rotation_scale_not_friction(self):
        moved = self.points.copy()
        angle = .2
        rotation = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
        moved[:, :, :2] = (moved[:, :, :2] @ rotation) * 1.2 + [30, 25]
        result = self.estimator.update(poses(moved), 2, 10.2)
        self.assertTrue(result["medicionValida"])
        self.assertLess(result["movimientoNormalizado"], 1e-8)

    def test_detector_order_swap_not_friction(self):
        result = self.estimator.update(poses(self.points[::-1]), 2, 10.2)
        self.assertTrue(result["medicionValida"])
        self.assertLess(result["movimientoNormalizado"], 1e-8)

    def test_relative_hand_movement_is_measured(self):
        moved = self.points.copy()
        moved[0, :, 1] += 15
        result = self.estimator.update(poses(moved), 2, 10.2)
        self.assertTrue(result["medicionValida"])
        self.assertGreater(result["movimientoNormalizado"], .06)

    def test_relative_hand_translation_is_not_normalized_away(self):
        moved = self.points.copy()
        moved[0, :, 0] += 12
        result = self.estimator.update(poses(moved), 2, 10.2)
        self.assertTrue(result["medicionValida"])
        self.assertGreater(result["movimientoNormalizado"], .06)

    def test_touching_bilateral_poses_are_not_collapsed_as_one_hand(self):
        for offset, expected_hands in ((5, 1), (10, 2)):
            with self.subTest(offset=offset):
                close_hands = self.points.copy()
                close_hands[1, :, :2] = self.points[0, :, :2] + [offset, 0]
                result = camera.HandMotionEstimator().update(
                    poses(close_hands), 1, 10.0
                )
                self.assertEqual(expected_hands, result["manosVisibles"])

    def test_low_confidence_pose_proposals_can_still_measure_two_hands(self):
        moved = self.points.copy()
        moved[0, :, 1] += 15
        weak_poses = poses(moved, confidence=.02)
        self.assertEqual(0, len(camera.detected_hand_boxes(weak_poses, min_confidence=.15)))
        self.assertEqual(2, len(camera.detected_hands(weak_poses, min_confidence=.01)))
        result = self.estimator.update(weak_poses, 2, 10.2, min_confidence=.01)
        self.assertEqual(2, result["manosVisibles"])
        self.assertTrue(result["medicionValida"])
        self.assertGreater(result["movimientoNormalizado"], .06)

    def test_recovery_can_compare_after_weak_primary(self):
        self.estimator.update(poses(self.points[:1]), 2, 10.1)
        moved = self.points.copy()
        moved[0, :, 1] += 15
        result = self.estimator.update(poses(moved), 3, 10.3)
        self.assertTrue(result["medicionValida"])

    def test_same_frame_recovery_compares_against_previous_frame_not_primary_retry(self):
        estimator = camera.HandMotionEstimator()
        estimator.update(poses(self.points), 10, 10.0)

        separated_primary = self.points.copy()
        separated_primary[1, :, 0] += 500
        primary = estimator.update(poses(separated_primary), 11, 10.2)
        self.assertFalse(primary["medicionValida"])

        recovered = self.points.copy()
        recovered[0, :, 1] += 15
        recovery = estimator.update(poses(recovered), 11, 10.2)
        self.assertTrue(recovery["medicionValida"])
        self.assertGreater(recovery["movimientoNormalizado"], .06)

    def test_out_of_order_sequence_and_duplicate_id_with_new_time_are_rejected(self):
        estimator = camera.HandMotionEstimator()
        estimator.update(poses(self.points), 10, 10.0)
        moved = self.points.copy()
        moved[0, :, 1] += 15
        self.assertTrue(estimator.update(poses(moved), 12, 10.2)["medicionValida"])

        old_sequence = estimator.update(poses(self.points), 11, 10.4)
        duplicate_with_new_time = estimator.update(poses(self.points), 12, 10.4)
        self.assertFalse(old_sequence["medicionValida"])
        self.assertFalse(duplicate_with_new_time["medicionValida"])

        next_frame = estimator.update(poses(self.points), 13, 10.4)
        self.assertTrue(next_frame["medicionValida"])

    def test_old_or_same_capture_does_not_measure_motion(self):
        self.assertFalse(self.estimator.update(poses(self.points), 1, 10.)["medicionValida"])
        self.assertFalse(self.estimator.update(poses(self.points), 2, 12.)["medicionValida"])

    def test_motion_evidence_must_match_the_classified_frame(self):
        evidence = {"secuencia": 11, "_captured_at": 10.2}
        self.assertTrue(camera.motion_evidence_matches_frame(evidence, 11, 10.2, .5))
        self.assertFalse(camera.motion_evidence_matches_frame(evidence, 12, 10.3, .5))
        self.assertFalse(camera.motion_evidence_matches_frame(evidence, 10, 10.2, .5))
        self.assertFalse(camera.motion_evidence_matches_frame(evidence, 12, 10.8, .5))
        self.assertFalse(camera.motion_evidence_matches_frame(None, 12, 10.3, .5))

    def test_occluded_keypoints_fail_closed(self):
        occluded = self.points.copy()
        occluded[0, 6:, 2] = 0
        result = self.estimator.update(poses(occluded), 2, 10.2)
        self.assertFalse(result["medicionValida"])
        self.assertEqual(1, result["manosVisibles"])

    def test_sender_includes_time_waiting_in_queue(self):
        evidence = self.estimator.update(poses(self.points), 2, 10.2,
                                         frame_shape=(540, 960, 3))
        response = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"accepted": True})
        with patch.object(camera.time, "monotonic", return_value=11.2), patch.object(
            camera.HTTP_SESSION, "post", return_value=response
        ) as post:
            self.assertTrue(camera.send_detection("http://localhost:8080", "fake-session", "fake-token",
                                                   "Paso1_Palmas", .9, {}, evidence))
        payload = post.call_args.kwargs["json"]["evidenciaMovimiento"]
        self.assertGreaterEqual(payload["antiguedadMs"], 999)
        self.assertNotIn("_captured_at", payload)
        self.assertEqual(960, payload["frameWidth"])
        self.assertEqual(540, payload["frameHeight"])
        self.assertEqual((2, 21, 3), np.asarray(payload["poseKeypoints"]).shape)
        self.assertEqual((2, 4), np.asarray(payload["handBoxes"]).shape)


if __name__ == "__main__":
    unittest.main()
