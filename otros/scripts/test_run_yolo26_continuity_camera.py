import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
from queue import Queue
from threading import Event
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch
import numpy as np
import yaml

import run_yolo26_continuity_camera as camera_runner
from run_yolo26_continuity_camera import (
    DEFAULT_HAND_POSE_CONFIDENCE,
    DEFAULT_HAND_POSE_IMAGE_SIZE,
    REQUIRED_OMS_CLASSES,
    best_detection,
    detected_hands,
    detection_sender,
    enqueue_latest_detection,
    HandMotionEstimator,
    hand_pose_proposal_count,
    hand_crop_bounds,
    hand_framing_hint,
    compatible_classifier_step,
    derived_classifier_decision,
    arbitrate_uncertain_detection,
    classifier_challenge_allowed,
    classifier_fallback_allowed,
    translate_pose_result,
    hand_recovery_tiles,
    merge_hand_pose_tiles,
    recover_hand_pose,
    background_vetoes_detection,
    prefer_recovered_motion,
    TemporalStepFilter,
    validate_derived_classifier,
    validate_hand_model,
    validate_step_model,
    validate_active_step_manifest,
    should_send_step_detection,
    should_publish_visibility_loss,
    sequential_label_taxonomy_warning,
    verify_model_artifact,
)


class Scalar:
    def __init__(self, value):
        self.value = value

    def item(self):
        return self.value


def frame(*detections):
    names = {index: detection[0] for index, detection in enumerate(detections)}
    boxes = [SimpleNamespace(
        cls=Scalar(index), conf=Scalar(detection[1]),
        xyxy=np.array([detection[2] if len(detection) > 2 else (0, 0, 100, 100)], dtype=float),
    ) for index, detection in enumerate(detections)]
    return SimpleNamespace(names=names, boxes=boxes)


def hand_pose_result(*coordinates):
    boxes, points = [], []
    for x1, y1, x2, y2 in coordinates:
        boxes.append(SimpleNamespace(
            xyxy=np.array([[x1, y1, x2, y2]], dtype=float), conf=Scalar(0.9),
        ))
        pose = np.zeros((21, 3), dtype=float)
        pose[:, 0] = np.linspace(x1 + 2, x2 - 2, 21)
        pose[:, 1] = np.linspace(y1 + 2, y2 - 2, 21)
        pose[:, 2] = 0.9
        points.append(pose)
    return SimpleNamespace(
        boxes=boxes,
        keypoints=SimpleNamespace(data=np.stack(points) if points else np.empty((0, 21, 3))),
    )


class ContinuityCameraDetectionTest(unittest.TestCase):
    def test_runtime_pose_defaults_are_shared_with_offline_evaluator(self):
        self.assertEqual(0.001, DEFAULT_HAND_POSE_CONFIDENCE)
        self.assertEqual(320, DEFAULT_HAND_POSE_IMAGE_SIZE)

    def test_model_manifest_accepts_matching_artifact_hash(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            artifact = directory / "backend/models/model.pt"
            artifact.parent.mkdir(parents=True)
            artifact.write_bytes(b"verified test weight")
            expected = hashlib.sha256(artifact.read_bytes()).hexdigest()
            manifest = directory / "manifest.json"
            manifest.write_text(json.dumps({
                "active": {"path": "backend/models/model.pt", "sha256": expected}
            }), encoding="utf-8")
            with patch.object(camera_runner, "ROOT", directory):
                actual = verify_model_artifact(artifact, manifest)
        self.assertEqual(expected, actual)

    def test_model_manifest_rejects_weight_replaced_after_registration(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            artifact = directory / "backend/models/model.pt"
            artifact.parent.mkdir(parents=True)
            artifact.write_bytes(b"changed test weight")
            manifest = directory / "manifest.json"
            manifest.write_text(json.dumps({
                "active": {"path": "backend/models/model.pt", "sha256": "0" * 64}
            }), encoding="utf-8")
            with patch.object(camera_runner, "ROOT", directory), self.assertRaisesRegex(
                RuntimeError, "no coincide"
            ):
                verify_model_artifact(artifact, manifest)

    def test_model_manifest_rejects_unregistered_weight(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            artifact = directory / "backend/models/model.pt"
            artifact.parent.mkdir(parents=True)
            artifact.write_bytes(b"unregistered test weight")
            manifest = directory / "manifest.json"
            manifest.write_text(json.dumps({"active": {}}), encoding="utf-8")
            with patch.object(camera_runner, "ROOT", directory), self.assertRaisesRegex(
                RuntimeError, "exactamente una huella"
            ):
                verify_model_artifact(artifact, manifest)

    def test_model_manifest_rejects_duplicate_weight_registration(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            artifact = directory / "backend/models/model.pt"
            artifact.parent.mkdir(parents=True)
            artifact.write_bytes(b"ambiguous test weight")
            sha256 = hashlib.sha256(artifact.read_bytes()).hexdigest()
            manifest = directory / "manifest.json"
            manifest.write_text(json.dumps({
                "active": {"path": "backend/models/model.pt", "sha256": sha256},
                "candidate": {"path": "backend/models/model.pt", "sha256": sha256},
            }), encoding="utf-8")
            with patch.object(camera_runner, "ROOT", directory), self.assertRaisesRegex(
                RuntimeError, "encontradas: 2"
            ):
                verify_model_artifact(artifact, manifest)

    def test_model_manifest_rejects_duplicate_json_keys(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            artifact = directory / "backend/models/model.pt"
            artifact.parent.mkdir(parents=True)
            artifact.write_bytes(b"test weight")
            manifest = directory / "manifest.json"
            manifest.write_text(
                '{"active":{"path":"backend/models/model.pt",'
                '"sha256":"' + hashlib.sha256(artifact.read_bytes()).hexdigest()
                + '"},"active":{}}',
                encoding="utf-8",
            )
            with patch.object(camera_runner, "ROOT", directory), self.assertRaisesRegex(
                RuntimeError, "clave JSON duplicada"
            ):
                verify_model_artifact(artifact, manifest)

    def test_active_step_manifest_matches_real_class_order_and_alias_mapping(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest = json.loads(
                (camera_runner.ROOT / "backend/models/model-manifest.json").read_text(
                    encoding="utf-8"))
            manifest["active"]["path"] = "backend/models/model.pt"
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            model = SimpleNamespace(names=dict(enumerate(manifest["active"]["modelClassNames"])))

            with patch.object(camera_runner, "ROOT", root):
                validate_active_step_manifest(
                    model, root / "backend/models/model.pt", manifest_path)

    def test_active_step_manifest_rejects_class_id_order_drift(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest = json.loads(
                (camera_runner.ROOT / "backend/models/model-manifest.json").read_text(
                    encoding="utf-8"))
            manifest["active"]["path"] = "backend/models/model.pt"
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            actual_names = list(manifest["active"]["modelClassNames"])
            actual_names[0], actual_names[1] = actual_names[1], actual_names[0]
            model = SimpleNamespace(names=dict(enumerate(actual_names)))

            with patch.object(camera_runner, "ROOT", root), self.assertRaisesRegex(
                RuntimeError, "modelClassNames"
            ):
                validate_active_step_manifest(
                    model, root / "backend/models/model.pt", manifest_path)

    def test_active_step_manifest_rejects_incorrect_alias_to_step_mapping(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest = json.loads(
                (camera_runner.ROOT / "backend/models/model-manifest.json").read_text(
                    encoding="utf-8"))
            manifest["active"]["path"] = "backend/models/model.pt"
            manifest["active"]["classNameMapping"]["paso_7"] = "Paso6_PuntaDeDedos"
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            model = SimpleNamespace(names=dict(enumerate(manifest["active"]["modelClassNames"])))

            with patch.object(camera_runner, "ROOT", root), self.assertRaisesRegex(
                RuntimeError, "classNameMapping"
            ):
                validate_active_step_manifest(
                    model, root / "backend/models/model.pt", manifest_path)

    def test_generic_detector_labels_warn_about_unverified_taxonomy(self):
        warning = sequential_label_taxonomy_warning({
            index: f"paso_{index + 1}" for index in range(7)
        })

        self.assertIsNotNone(warning)
        self.assertIn("data.yaml", warning)
        self.assertIn("precisión", warning)

    def test_explicit_canonical_labels_need_no_generic_mapping_warning(self):
        self.assertIsNone(sequential_label_taxonomy_warning({
            0: "Paso1_Palmas",
            1: "Paso2_Dorsos",
        }))

    def test_stream_health_reports_camera_reconnection_without_closing_port(self):
        with patch.object(camera_runner, "ThreadingHTTPServer"):
            stream = camera_runner.MjpegFrameServer("127.0.0.1", 0)
        self.assertEqual("reconnecting", stream.camera_status)
        stream.set_camera_connected(True)
        self.assertEqual("connected", stream.camera_status)
        stream.set_camera_connected(False)
        self.assertEqual("reconnecting", stream.camera_status)

    def test_stream_health_rejects_invalid_hand_presence_counts(self):
        with patch.object(camera_runner, "ThreadingHTTPServer"):
            stream = camera_runner.MjpegFrameServer("127.0.0.1", 0)
        with self.assertRaisesRegex(ValueError, "presencia"):
            stream.set_hand_presence({
                "handsVisible": True,
                "warmupElapsedMs": 0,
                "warmupRequiredMs": 3000,
                "warmupComplete": False,
                "stepsEnabled": False,
            })

    def test_stream_health_disables_steps_after_backend_presence_window_expires(self):
        with patch.object(camera_runner, "ThreadingHTTPServer"):
            stream = camera_runner.MjpegFrameServer("127.0.0.1", 0)
        presence = {
            "handsVisible": 2,
            "warmupElapsedMs": 3000,
            "warmupRequiredMs": 3000,
            "warmupComplete": True,
            "stepsEnabled": True,
        }
        stream.set_camera_connected(True)
        with patch.object(camera_runner.time, "monotonic", side_effect=(10.0, 10.5, 10.0, 10.501)):
            stream.set_hand_presence(presence)
            self.assertTrue(stream._current_hand_presence_locked()["stepsEnabled"])
            stream.set_hand_presence(presence)
            stale = stream._current_hand_presence_locked()
        self.assertFalse(stale["stepsEnabled"])
        self.assertEqual(0, stale["handsVisible"])

    def test_camera_stream_cannot_be_bound_to_a_network_interface(self):
        with patch.object(camera_runner, "ThreadingHTTPServer") as server:
            with self.assertRaisesRegex(ValueError, "loopback"):
                camera_runner.MjpegFrameServer("0.0.0.0", 8091)
            server.assert_not_called()

    def test_stream_health_cors_accepts_loopback_dashboard_only(self):
        self.assertTrue(camera_runner.is_local_dashboard_origin("http://127.0.0.1:8080"))
        self.assertTrue(camera_runner.is_local_dashboard_origin("http://localhost:5173"))
        self.assertFalse(camera_runner.is_local_dashboard_origin("https://dashboard.example"))
        self.assertFalse(camera_runner.is_local_dashboard_origin("http://localhost.example:8080"))

    def test_dashboard_stream_is_bound_to_the_same_session_as_the_stepper(self):
        stream = camera_runner.MjpegFrameServer("127.0.0.1", 0)
        stream.set_session_id("camera-session")
        stream.set_camera_connected(True)
        stream.set_hand_presence({
            "handsVisible": 2,
            "warmupElapsedMs": 1500,
            "warmupRequiredMs": 3000,
            "warmupComplete": False,
            "stepsEnabled": False,
        })
        stream.start()
        host, port = stream.address
        try:
            health_request = Request(
                f"http://{host}:{port}/health",
                headers={"Origin": "http://127.0.0.1:8080"},
            )
            with urlopen(health_request, timeout=2) as response:
                health = json.loads(response.read())
                self.assertEqual(
                    "http://127.0.0.1:8080",
                    response.headers.get("Access-Control-Allow-Origin"),
                )
            self.assertEqual("camera-session", health["sessionId"])
            self.assertEqual({
                "handsVisible": 2,
                "warmupElapsedMs": 1500,
                "warmupRequiredMs": 3000,
                "warmupComplete": False,
                "stepsEnabled": False,
            }, health["handPresence"])

            stream.set_camera_connected(False)
            with urlopen(f"http://{host}:{port}/health", timeout=2) as response:
                disconnected_health = json.loads(response.read())
            self.assertEqual(0, disconnected_health["handPresence"]["handsVisible"])
            self.assertFalse(disconnected_health["handPresence"]["stepsEnabled"])
            stream.set_camera_connected(True)

            with self.assertRaises(HTTPError) as mismatch:
                urlopen(
                    f"http://{host}:{port}/video.mjpg?sessionId=other-session",
                    timeout=2,
                )
            self.assertEqual(409, mismatch.exception.code)
            mismatch.exception.close()

            with self.assertRaises(HTTPError) as missing_session:
                urlopen(f"http://{host}:{port}/video.mjpg", timeout=2)
            self.assertEqual(409, missing_session.exception.code)
            missing_session.exception.close()

            matching_session = urlopen(
                f"http://{host}:{port}/video.mjpg?sessionId=camera-session",
                timeout=2,
            )
            self.assertEqual(200, matching_session.status)
            matching_session.close()

            with self.assertRaisesRegex(RuntimeError, "otra sesión"):
                stream.set_session_id("other-session")
        finally:
            stream.close()

    def test_dashboard_stream_downscales_only_the_published_jpeg(self):
        with patch.object(camera_runner, "ThreadingHTTPServer"), \
                patch.object(camera_runner.cv2, "imencode", return_value=(True, np.array([1, 2, 3], dtype=np.uint8))) as encode:
            stream = camera_runner.MjpegFrameServer("127.0.0.1", 0, output_width=720)
            stream._clients = 1
            self.assertTrue(stream.publish(np.zeros((540, 960, 3), dtype=np.uint8)))

        self.assertEqual((405, 720, 3), encode.call_args.args[1].shape)
        self.assertEqual(bytes([1, 2, 3]), stream._jpeg)

    def test_stream_configuration_rejects_unusable_sizes_and_quality(self):
        with patch.object(camera_runner, "ThreadingHTTPServer"):
            with self.assertRaises(ValueError):
                camera_runner.MjpegFrameServer("127.0.0.1", 0, output_width=200)
            with self.assertRaises(ValueError):
                camera_runner.MjpegFrameServer("127.0.0.1", 0, jpeg_quality=99)
            with self.assertRaises(ValueError):
                camera_runner.MjpegFrameServer("127.0.0.1", 0, max_clients=0)
            with self.assertRaises(ValueError):
                camera_runner.MjpegFrameServer(
                    "127.0.0.1", 0, client_write_timeout_seconds=float("inf")
                )

    def test_stream_caps_viewers_and_releases_capacity_after_disconnect(self):
        stream = camera_runner.MjpegFrameServer("127.0.0.1", 0, max_clients=1)
        stream.set_session_id("camera-session")
        stream.start()
        host, port = stream.address
        url = f"http://{host}:{port}/video.mjpg?sessionId=camera-session"
        first_client = None
        replacement_client = None
        try:
            first_client = urlopen(url, timeout=2)
            self.assertEqual(200, first_client.status)
            self.assertEqual(1, stream._clients)

            with self.assertRaises(HTTPError) as overloaded:
                urlopen(url, timeout=2)
            self.assertEqual(503, overloaded.exception.code)
            self.assertEqual("2", overloaded.exception.headers.get("Retry-After"))
            self.assertEqual(
                {"error": "STREAM_CAPACITY_REACHED"},
                json.loads(overloaded.exception.read()),
            )
            overloaded.exception.close()

            first_client.close()
            frame = np.zeros((64, 96, 3), dtype=np.uint8)
            deadline = time.monotonic() + 1.5
            while stream._clients and time.monotonic() < deadline:
                stream.publish(frame)
                time.sleep(0.02)
            self.assertEqual(0, stream._clients, "Disconnected viewer kept a stream slot")

            replacement_client = urlopen(url, timeout=2)
            self.assertEqual(200, replacement_client.status)
        finally:
            if first_client is not None:
                first_client.close()
            if replacement_client is not None:
                replacement_client.close()
            stream.close()

    def test_stream_defaults_and_canonical_steps_match_the_model_manifest(self):
        manifest = json.loads((camera_runner.ROOT / "backend/models/model-manifest.json").read_text())
        with patch("sys.argv", ["camera"]):
            options = camera_runner.parse_args()
        self.assertEqual(3000, options.hand_presence_warmup_ms)

        dashboard = manifest["dashboardStream"]
        self.assertEqual(dashboard["outputWidth"], options.stream_width)
        self.assertEqual(dashboard["maxFps"], options.stream_fps)
        self.assertEqual(dashboard["jpegQuality"], options.stream_jpeg_quality)
        self.assertEqual(dashboard["maxConcurrentClients"], camera_runner.DEFAULT_MJPEG_MAX_CLIENTS)
        self.assertEqual(
            dashboard["clientSocketTimeoutSeconds"],
            camera_runner.DEFAULT_MJPEG_CLIENT_TIMEOUT_SECONDS,
        )
        self.assertEqual(set(camera_runner.REQUIRED_STEP_CLASSES), set(manifest["canonicalSteps"]))
        self.assertEqual("backend/models/handwash_yolo26n_7pasos.pt", manifest["active"]["path"])
        self.assertEqual(
            list(camera_runner.REQUIRED_STEP_CLASSES),
            list(manifest["active"]["classNameMapping"].values()),
        )
        self.assertTrue(manifest["active"]["runtime"][
            "explicitBackgroundClassVetoesAtOrAboveStepConfidence"])
        self.assertTrue(manifest["active"]["runtime"][
            "requiresTwoFreshHandPosesForEveryStepInference"])
        self.assertFalse(manifest["active"]["runtime"][
            "fullFrameStepInferenceWhenHandsMissing"])
        self.assertFalse(manifest["partialModeFallback"]["enabled"])

        pose_runtime = next(
            candidate["runtime"] for candidate in manifest["candidates"]
            if candidate["path"] == "backend/models/yolo26s-pose-hands.pt"
        )
        deduplication = pose_runtime["geometricDeduplication"]
        self.assertEqual(
            deduplication["minimumBoxIoU"], camera_runner.HAND_POSE_DEDUP_MIN_BOX_IOU
        )
        self.assertEqual(
            deduplication["maximumCenterShiftFractionOfMeanBoxDiagonal"],
            camera_runner.HAND_POSE_DEDUP_MAX_CENTER_SHIFT_DIAGONALS,
        )
        self.assertEqual(
            deduplication["maximumMedianSharedKeypointShiftFractionOfMeanBoxDiagonal"],
            camera_runner.HAND_POSE_DEDUP_MAX_MEDIAN_KEYPOINT_SHIFT_DIAGONALS,
        )
        self.assertEqual(
            deduplication["minimumSharedKeypoints"], camera_runner.MIN_HAND_KEYPOINTS
        )
        self.assertEqual(3000, pose_runtime["initialBilateralWarmup"]["defaultDurationMs"])
        self.assertTrue(pose_runtime["initialBilateralWarmup"]["stepInferenceSuppressedUntilReady"])
        self.assertTrue(pose_runtime["initialBilateralWarmup"][
            "requiresTwoFreshHandPosesForEveryStepInference"])
        self.assertFalse(pose_runtime["fullFrameFallbackUsesRecentCameraSnapshot"])

    def test_hand_presence_warmup_needs_three_seconds_of_fresh_bilateral_poses(self):
        gate = camera_runner.HandPresenceWarmup(required_ms=3000, max_gap_ms=500)
        state = gate.update(2, 1, 10.0, False)
        self.assertFalse(state["ready"])
        for sequence in range(2, 7):
            state = gate.update(2, sequence, 10.0 + (sequence - 1) * 0.5, False)
            self.assertFalse(state["ready"])
        state = gate.update(2, 7, 13.0, False)
        self.assertTrue(state["ready"])
        self.assertEqual(3000, state["elapsed_ms"])
        lost_hands = gate.update(0, 8, 13.1, True)
        self.assertTrue(lost_hands["ready"])
        self.assertFalse(camera_runner.bilateral_presence_is_fresh(lost_hands, 13.1, 0.5))

    def test_presence_freshness_matches_the_locked_java_station_profiles(self):
        for profile in ("application-station.yml", "application-station-demo.yml"):
            with self.subTest(profile=profile):
                config = yaml.safe_load((camera_runner.ROOT / "backend/src/main/resources" / profile)
                                        .read_text(encoding="utf-8"))
                backend_gap_ms = config["handwash"]["intention"]["hand-presence-max-gap-ms"]
                self.assertEqual(camera_runner.DEFAULT_HAND_PRESENCE_MAX_GAP_MS, backend_gap_ms)

        self.assertEqual(0.5, camera_runner.hand_presence_freshness_window(0.65))
        self.assertEqual(0.25, camera_runner.hand_presence_freshness_window(0.25))
        self.assertEqual(0.0, camera_runner.hand_presence_freshness_window(float("nan")))

    def test_warmup_rearms_after_hand_loss_until_java_accepts_start(self):
        gate = camera_runner.HandPresenceWarmup(required_ms=3000, max_gap_ms=500)
        for sequence in range(7):
            state = gate.update(2, sequence, 20.0 + sequence * 0.5, False)
        self.assertTrue(state["ready"])

        lost = gate.update(1, 7, 23.1, False)
        self.assertFalse(lost["ready"])
        self.assertEqual(0, lost["elapsed_ms"])
        restarted = gate.update(2, 8, 23.2, False)
        self.assertFalse(restarted["ready"])
        self.assertEqual(0, restarted["elapsed_ms"])
        for sequence in range(9, 15):
            state = gate.update(2, sequence, 23.2 + (sequence - 8) * 0.5, False)
        self.assertTrue(state["ready"])

    def test_warmup_stays_open_after_java_start_but_stale_hands_still_block_steps(self):
        gate = camera_runner.HandPresenceWarmup(required_ms=3000, max_gap_ms=500)
        for sequence in range(7):
            state = gate.update(2, sequence, 30.0 + sequence * 0.5, False)
        self.assertTrue(state["ready"])

        stale = gate.update(2, 7, 33.2, True)
        self.assertTrue(stale["ready"])
        self.assertFalse(camera_runner.bilateral_presence_is_fresh(stale, 34.0, 0.5))

    def test_java_start_ack_cancels_a_second_local_warmup_after_polling_race(self):
        gate = camera_runner.HandPresenceWarmup(required_ms=3000, max_gap_ms=500)
        for sequence in range(7):
            state = gate.update(2, sequence, 30.0 + sequence * 0.5, False)
        self.assertTrue(state["ready"])

        lost = gate.update(1, 7, 33.1, False)
        self.assertFalse(lost["ready"], "before Java confirms start, hand loss resets local dwell")

        one_hand = gate.update(1, 8, 33.2, True)
        self.assertTrue(one_hand["ready"], "Java's accepted start is authoritative for initial dwell")
        self.assertFalse(camera_runner.bilateral_presence_is_fresh(one_hand, 33.2, 0.5))

        resumed = gate.update(2, 9, 33.3, True)
        self.assertTrue(resumed["ready"])
        self.assertTrue(camera_runner.bilateral_presence_is_fresh(resumed, 33.3, 0.5))

    def test_ready_warmup_rearms_after_excessive_gap_before_first_java_start(self):
        gate = camera_runner.HandPresenceWarmup(required_ms=3000, max_gap_ms=500)
        for sequence in range(7):
            state = gate.update(2, sequence, 40.0 + sequence * 0.5, False)
        self.assertTrue(state["ready"])

        state = gate.update(2, 7, 43.501, False)
        self.assertFalse(state["ready"])
        self.assertEqual(0, state["elapsed_ms"])
        for sequence in range(8, 16):
            state = gate.update(2, sequence, 43.501 + (sequence - 7) * 0.4, False)
        self.assertTrue(state["ready"])

    def test_partial_step_inference_requires_two_current_hands_after_warmup(self):
        current = {"ready": True, "hands_visible": 2, "observed_at": 10.0}
        gate = camera_runner.should_block_step_inference_for_hands
        self.assertFalse(gate("FRICCION_PARCIAL", True, current, 2, 10.4, 0.5))
        self.assertTrue(gate("FRICCION_PARCIAL", True, current, 1, 10.4, 0.5))
        self.assertTrue(gate(
            "FRICCION_PARCIAL", True,
            {"ready": True, "hands_visible": 0, "observed_at": 10.4},
            0, 10.4, 0.5,
        ))
        self.assertTrue(gate("FRICCION_PARCIAL", True, current, 2, 10.6, 0.5))
        self.assertTrue(gate(
            "FRICCION_PARCIAL", True,
            {"ready": True, "hands_visible": 2, "observed_at": 0.0},
            2, 0.1, 0.5,
        ))
        self.assertTrue(gate(
            "FRICCION_PARCIAL", True,
            {"ready": False, "hands_visible": 2, "observed_at": 10.4},
            2, 10.4, 0.5,
        ))
        self.assertFalse(gate(
            "PROTOCOLO_OMS", True,
            {"ready": False, "hands_visible": 2, "observed_at": 10.4},
            2, 10.4, 0.5,
        ), "OMS keeps only its independent risk-alert inference path open during warmup")
        self.assertFalse(gate("PROTOCOLO_OMS", True, {}, 0, 10.4, 0.5))
        self.assertFalse(gate("FRICCION_PARCIAL", False, {}, 0, 10.4, 0.5))

    def test_oms_limits_pre_warmup_inference_to_risk_class(self):
        select_classes = camera_runner.step_classes_for_presence
        self.assertEqual([11], select_classes("PROTOCOLO_OMS", list(range(12)), 11, False))
        self.assertEqual(list(range(12)), select_classes("PROTOCOLO_OMS", list(range(12)), 11, True))
        self.assertEqual(list(range(7)), select_classes("FRICCION_PARCIAL", list(range(7)), None, False))
        with self.assertRaisesRegex(ValueError, "contacto de riesgo"):
            select_classes("PROTOCOLO_OMS", list(range(11)), 11, False)

    def test_hand_presence_warmup_resets_on_missing_hand_or_excessive_gap(self):
        gate = camera_runner.HandPresenceWarmup(required_ms=3000, max_gap_ms=500)
        gate.update(2, 1, 10.0, False)
        state = gate.update(2, 2, 10.4, False)
        self.assertEqual(400, state["elapsed_ms"])
        state = gate.update(1, 3, 10.5, False)
        self.assertEqual(0, state["elapsed_ms"])
        state = gate.update(2, 4, 10.6, False)
        self.assertEqual(0, state["elapsed_ms"])
        state = gate.update(2, 5, 11.2, False)
        self.assertEqual(0, state["elapsed_ms"])
        self.assertFalse(state["ready"])

    def test_warmup_overlay_hides_progress_when_bilateral_pose_is_stale(self):
        progress = camera_runner.fresh_hand_presence_progress_ms
        max_age = camera_runner.hand_presence_freshness_window(0.65)
        state = {
            "hands_visible": 2, "observed_at": 10.0,
            "elapsed_ms": 1800, "required_ms": 3000,
        }
        self.assertEqual(1800, progress(state, 10.5, max_age))
        self.assertEqual(0, progress(state, 10.501, max_age))
        self.assertEqual(0, progress({**state, "hands_visible": 1}, 10.2, 0.5))

    def test_duplicate_hand_frames_do_not_advance_presence_warmup(self):
        gate = camera_runner.HandPresenceWarmup(required_ms=3000, max_gap_ms=500)
        gate.update(2, 1, 10.0, False)
        state = gate.update(2, 1, 13.0, False)
        self.assertFalse(state["ready"])
        self.assertEqual(0, state["elapsed_ms"])

    def test_session_monitor_latches_java_accepted_start(self):
        states = iter(("ESPERANDO_INICIO", "EN_PROGRESO", "ESPERANDO_INICIO"))
        waits = iter((False, False, False, True))
        stop = SimpleNamespace(wait=lambda _timeout: next(waits))
        session_started = Event()
        session_ended = Event()

        def response_for_next_state(*_args, **_kwargs):
            state = next(states)
            return SimpleNamespace(
                status_code=200,
                ok=True,
                json=lambda: {"estado": state},
            )

        with patch.object(
            camera_runner.requests, "get", side_effect=response_for_next_state
        ) as get:
            camera_runner.monitor_session(
                "http://127.0.0.1:8080", "session", "token", stop,
                session_ended, session_started,
            )

        self.assertEqual(3, get.call_count)
        self.assertTrue(session_started.is_set())
        self.assertFalse(session_ended.is_set())

    def test_presence_warmup_argument_rejects_out_of_range_values(self):
        for value in ("-1", "10001", "1.5"):
            with self.subTest(value=value), patch("sys.argv", ["camera", "--hand-presence-warmup-ms", value]):
                with self.assertRaises(SystemExit):
                    camera_runner.parse_args()

    def test_camera_restart_preserves_iphone_only_avfoundation_source(self):
        with patch.object(camera_runner.subprocess, "Popen") as popen:
            camera_runner.start_camera_process(3, 960, 540)
        command = popen.call_args.args[0]
        self.assertEqual("avfoundation", command[command.index("-f") + 1])
        self.assertEqual("3", command[command.index("-i") + 1])
        self.assertEqual("uyvy422", command[command.index("-pixel_format") + 1])
        self.assertIn("scale=960:540", command)

    def test_camera_reconnect_reenumerates_iphone_when_avfoundation_index_changes(self):
        listing = (
            "AVFoundation video devices:\n"
            "[0] FaceTime HD Camera\n"
            "[3] Jhon's iPhone Camera\n"
            "AVFoundation audio devices:\n"
        )
        with patch.object(camera_runner, "avfoundation_listing", return_value=listing), \
             patch.object(camera_runner.subprocess, "Popen") as popen:
            index, name, _ = camera_runner.reopen_iphone_camera(960, 540)

        self.assertEqual(3, index)
        self.assertEqual("Jhon's iPhone Camera", name)
        command = popen.call_args.args[0]
        self.assertEqual("3", command[command.index("-i") + 1])

    def test_framing_hint_reports_missing_or_edge_clipped_hands(self):
        centered = [((300, 170, 400, 320), 0.8), ((530, 170, 630, 320), 0.9)]
        self.assertIn("Centra ambas", hand_framing_hint([], 960, 540))
        self.assertIn("segunda", hand_framing_hint(centered[:1], 960, 540))
        self.assertIn("borde", hand_framing_hint([((0, 170, 100, 320), 0.8), centered[1]], 960, 540))
        self.assertIn("encuadradas", hand_framing_hint(centered, 960, 540))

    def test_hand_pose_is_enabled_by_default_and_can_be_explicitly_disabled(self):
        with patch.dict("os.environ", {
            "HANDWASH_CLASSIFIER_FALLBACK": "1",
            "HANDWASH_YOLO_CLASSIFIER_MODEL": "",
        }), patch("sys.argv", ["camera"]):
            options = camera_runner.parse_args()
            self.assertTrue(options.hand_pose)
            self.assertEqual(24.0, options.stream_fps)
            self.assertEqual(0.001, options.hand_confidence)
            self.assertEqual(0.90, options.hand_iou)
            self.assertEqual(16, options.hand_max_det)
            self.assertTrue(options.classifier_fallback)
            self.assertTrue(options.classifier_authoritative)
        with patch("sys.argv", ["camera", "--no-classifier-fallback"]):
            self.assertFalse(camera_runner.parse_args().classifier_fallback)
        with patch("sys.argv", ["camera", "--classifier-guarded"]):
            self.assertFalse(camera_runner.parse_args().classifier_authoritative)
        with patch("sys.argv", ["camera", "--no-hand-pose"]):
            self.assertFalse(camera_runner.parse_args().hand_pose)

    def test_derived_classifier_defaults_to_the_packaged_checkpoint(self):
        expected = camera_runner.ROOT / "backend/models/handwash_who_yolo26m_cls.pt"
        with patch.dict("os.environ", {"HANDWASH_YOLO_CLASSIFIER_MODEL": ""}), \
             patch("sys.argv", ["camera"]):
            options = camera_runner.parse_args()
        self.assertEqual(str(expected), options.classifier_model)
        self.assertTrue(expected.is_file())

    def test_documented_classifier_environment_switch_is_honored_and_emergency_off_wins(self):
        with patch.dict("os.environ", {"HANDWASH_CLASSIFIER_FALLBACK": "0"}), \
             patch("sys.argv", ["camera"]):
            self.assertFalse(camera_runner.parse_args().classifier_fallback)
        with patch.dict("os.environ", {"HANDWASH_CLASSIFIER_FALLBACK": "false"}), \
             patch("sys.argv", ["camera", "--classifier-fallback"]):
            self.assertFalse(camera_runner.parse_args().classifier_fallback)
        with patch.dict("os.environ", {"HANDWASH_CLASSIFIER_FALLBACK": "yes"}), \
             patch("sys.argv", ["camera"]):
            self.assertTrue(camera_runner.parse_args().classifier_fallback)

    def test_classifier_model_environment_override_is_used(self):
        configured = str(camera_runner.ROOT / "backend/models/handwash_who_yolo26m_cls.pt")
        with patch.dict("os.environ", {"HANDWASH_YOLO_CLASSIFIER_MODEL": configured}), \
             patch("sys.argv", ["camera"]):
            self.assertEqual(configured, camera_runner.parse_args().classifier_model)

    def test_derived_classifier_maps_only_six_compatible_friction_classes(self):
        valid = SimpleNamespace(task="classify", names=camera_runner.DERIVED_CLASSIFIER_NAMES)
        validate_derived_classifier(valid, "derived.pt")
        for class_id in range(1, 7):
            result = SimpleNamespace(probs=SimpleNamespace(top1=class_id, top1conf=0.9))
            self.assertEqual(camera_runner.REQUIRED_STEP_CLASSES[class_id - 1],
                             compatible_classifier_step(result)[0])
        for class_id in (0, 7, 8):
            result = SimpleNamespace(probs=SimpleNamespace(top1=class_id, top1conf=0.99))
            self.assertEqual((None, None), compatible_classifier_step(result))
        weak = SimpleNamespace(probs=SimpleNamespace(top1=1, top1conf=0.74))
        self.assertEqual((None, None), compatible_classifier_step(weak))
        with self.assertRaisesRegex(RuntimeError, "nueve clases"):
            validate_derived_classifier(SimpleNamespace(task="classify", names={7: "Paso7_Circulares"}),
                                        "wrong.pt")

    def test_classifier_challenges_only_weak_detector_candidates_and_preserves_negatives(self):
        palm = SimpleNamespace(probs=SimpleNamespace(top1=1, top1conf=0.92))
        other_movement = SimpleNamespace(probs=SimpleNamespace(top1=0, top1conf=0.91))
        faucet = SimpleNamespace(probs=SimpleNamespace(top1=7, top1conf=0.95))
        self.assertEqual(("STEP", "Paso1_Palmas", 0.92), derived_classifier_decision(palm))
        self.assertEqual(("NEGATIVE", None, 0.91), derived_classifier_decision(other_movement))
        # Faucet closure is a negative, never project Paso7_Circulares.
        self.assertEqual(("NEGATIVE", None, 0.95), derived_classifier_decision(faucet))

        resolved = arbitrate_uncertain_detection("Paso7_Circulares", 0.67, palm)
        self.assertEqual(("Paso1_Palmas", 0.92, "classifier"), resolved)
        self.assertEqual((None, None, "classifier_veto"),
                         arbitrate_uncertain_detection("Paso7_Circulares", 0.67,
                                                       other_movement))
        self.assertEqual(("Paso7_Circulares", 0.90, "detector"),
                         arbitrate_uncertain_detection("Paso7_Circulares", 0.90, palm))
        self.assertEqual(("Paso1_Palmas", 0.92, "classifier"),
                         arbitrate_uncertain_detection(
                             "Paso7_Circulares", 0.99, palm,
                             classifier_authoritative=True,
                         ))
        self.assertEqual((None, None, "classifier_veto"),
                         arbitrate_uncertain_detection(
                             "Paso7_Circulares", 0.99, faucet,
                             classifier_authoritative=True,
                         ))

    def test_classifier_challenge_requires_fresh_bilateral_partial_pose(self):
        spatial = {"manosVisibles": 2}
        self.assertTrue(classifier_challenge_allowed(
            "Paso7_Circulares", 0.67, "FRICCION_PARCIAL", spatial,
            0.2, 0.5, False,
        ))
        self.assertTrue(classifier_challenge_allowed(
            "Paso7_Circulares", 0.99, "FRICCION_PARCIAL", spatial,
            0.2, 0.5, False, challenge_all=True,
        ))
        self.assertFalse(classifier_challenge_allowed(
            "Paso7_Circulares", 0.67, "FRICCION_PARCIAL",
            {"manosVisibles": 1}, 0.2, 0.5, False,
        ))
        self.assertFalse(classifier_challenge_allowed(
            "Paso1_Palmas", 0.9, "FRICCION_PARCIAL", spatial, 0.2, 0.5, False,
        ))
        self.assertFalse(classifier_challenge_allowed(
            None, None, "PROTOCOLO_OMS", spatial, 0.2, 0.5, False,
        ))

    def test_classifier_fallback_requires_fresh_same_frame_bilateral_pose(self):
        valid = dict(manosVisibles=2, medicionValida=True)
        bilateral_pose_without_motion = dict(manosVisibles=2, medicionValida=False)
        allowed = lambda raw, mode, spatial, age, queued: classifier_fallback_allowed(
            raw, mode, spatial, age, 0.5, queued)
        self.assertTrue(allowed(None, "FRICCION_PARCIAL", valid, 0.2, False))
        # An active phase needs fresh bilateral hands, not a movement threshold.
        # Java separately requires a valid spatial measurement to start the wash.
        self.assertTrue(allowed(None, "FRICCION_PARCIAL",
                                bilateral_pose_without_motion, 0.2, False))
        self.assertFalse(allowed("Paso2_Dorsos", "FRICCION_PARCIAL", valid, 0.2, False))
        self.assertFalse(allowed(None, "PROTOCOLO_OMS", valid, 0.2, False))
        self.assertFalse(allowed(None, "FRICCION_PARCIAL", None, 0.2, False))
        self.assertFalse(allowed(None, "FRICCION_PARCIAL",
                                 dict(manosVisibles=1, medicionValida=True), 0.2, False))
        self.assertFalse(allowed(None, "FRICCION_PARCIAL", valid, 0.6, False))
        self.assertFalse(allowed(None, "FRICCION_PARCIAL", valid, 0.2, True))

    def test_background_veto_uses_relative_confidence_for_final_candidate(self):
        weak_background = frame(("Paso1_Palmas", 0.8), ("Fondo", 0.2))
        self.assertEqual(("Paso1_Palmas", 0.8, {}),
                         best_detection(weak_background, "FRICCION_PARCIAL"))
        self.assertFalse(background_vetoes_detection(weak_background, 0.8))
        self.assertFalse(background_vetoes_detection(weak_background, None))
        self.assertFalse(background_vetoes_detection(weak_background, 0.9))

        strong_background = frame(("Paso1_Palmas", 0.7), ("Fondo", 0.7))
        self.assertEqual((None, None, {}),
                         best_detection(strong_background, "FRICCION_PARCIAL"))
        self.assertTrue(background_vetoes_detection(strong_background, 0.7))
        self.assertFalse(background_vetoes_detection(strong_background, 0.9))

        classification = SimpleNamespace(probs=SimpleNamespace(top1=2, top1conf=0.95))
        self.assertEqual(("Paso2_Dorsos", 0.95, "classifier"),
                         arbitrate_uncertain_detection(
                             "Paso1_Palmas", 0.8, classification,
                             classifier_authoritative=True,
                         ))

    def test_hand_model_requires_one_hand_class_and_twenty_one_keypoints(self):
        valid = SimpleNamespace(
            task="pose",
            names={0: "hand"},
            model=SimpleNamespace(yaml={"kpt_shape": [21, 3]}),
        )
        validate_hand_model(valid, "hands.pt")
        invalid = SimpleNamespace(task="detect", names={0: "hand"})
        with self.assertRaisesRegex(RuntimeError, "no 'pose'"):
            validate_hand_model(invalid, "not-pose.pt")

    def test_pose_localization_and_start_use_their_separate_keypoint_thresholds(self):
        keypoints = np.zeros((2, 21, 3), dtype=float)
        for index, offset in enumerate((0, 100)):
            keypoints[index, :, 0] = np.linspace(offset + 5, offset + 35, 21)
            keypoints[index, :, 1] = np.linspace(10, 40, 21)
            keypoints[index, :, 2] = 0.2
        result = SimpleNamespace(
            boxes=[
                SimpleNamespace(xyxy=np.array([[0, 0, 50, 50]], dtype=float), conf=Scalar(0.9)),
                SimpleNamespace(xyxy=np.array([[100, 0, 150, 50]], dtype=float), conf=Scalar(0.8)),
            ],
            keypoints=SimpleNamespace(data=keypoints),
        )

        evidence = HandMotionEstimator().update(result, 1, 1.0, 0.01)
        self.assertEqual(2, evidence["manosVisibles"])
        self.assertEqual(0, evidence["_manosParaInicio"])
        self.assertFalse(evidence["medicionValida"])
        self.assertEqual(2, len(detected_hands(result, 0.01)))

    def test_near_identical_overlapping_pose_predictions_are_not_two_hands(self):
        keypoints = np.zeros((2, 21, 3), dtype=float)
        for index, offset in enumerate((0, 4)):
            keypoints[index, :, 0] = np.linspace(125 + offset, 165 + offset, 21)
            keypoints[index, :, 1] = np.linspace(65 + offset, 105 + offset, 21)
            keypoints[index, :, 2] = 0.9
        result = SimpleNamespace(
            boxes=[
                SimpleNamespace(xyxy=np.array([[100, 50, 200, 150]], dtype=float), conf=Scalar(0.9)),
                SimpleNamespace(xyxy=np.array([[105, 55, 205, 155]], dtype=float), conf=Scalar(0.8)),
            ],
            keypoints=SimpleNamespace(data=keypoints),
        )

        evidence = HandMotionEstimator().update(result, 1, 1.0, 0.01)
        self.assertEqual(1, evidence["manosVisibles"])
        self.assertEqual(1, evidence["_manosParaInicio"])
        self.assertEqual(1, len(detected_hands(result, 0.01)))

    def test_close_bilateral_poses_are_not_collapsed_as_one_hand(self):
        keypoints = np.zeros((2, 21, 3), dtype=float)
        for index, offset in enumerate((0, 15)):
            keypoints[index, :, 0] = np.linspace(125 + offset, 165 + offset, 21)
            keypoints[index, :, 1] = np.linspace(65, 105, 21)
            keypoints[index, :, 2] = 0.9
        result = SimpleNamespace(
            boxes=[
                SimpleNamespace(xyxy=np.array([[100 + offset, 50, 220 + offset, 180]], dtype=float),
                                conf=Scalar(confidence))
                for offset, confidence in ((0, 0.9), (15, 0.8))
            ],
            keypoints=SimpleNamespace(data=keypoints),
        )

        evidence = HandMotionEstimator().update(result, 1, 1.0, 0.01)

        self.assertEqual(2, evidence["manosVisibles"])
        self.assertEqual(2, len(detected_hands(result, 0.01)))

    def test_pose_diagnostic_separates_raw_boxes_from_distinct_valid_hands(self):
        keypoints = np.zeros((2, 21, 3), dtype=float)
        keypoints[0, :, 0] = np.linspace(125, 165, 21)
        keypoints[1, :, 0] = np.linspace(135, 175, 21)
        keypoints[:, :, 1] = np.linspace(65, 105, 21)
        keypoints[:, :, 2] = 0.9
        result = SimpleNamespace(
            boxes=[
                SimpleNamespace(xyxy=np.array([[100, 50, 220, 180]], dtype=float),
                                conf=Scalar(0.9)),
                SimpleNamespace(xyxy=np.array([[110, 55, 230, 185]], dtype=float),
                                conf=Scalar(0.8)),
            ],
            keypoints=SimpleNamespace(data=keypoints),
        )

        self.assertEqual(2, hand_pose_proposal_count(result))
        self.assertEqual(1, len(detected_hands(result, 0.01)))

    def test_overlapping_but_distinct_hand_skeletons_survive_pose_deduplication(self):
        keypoints = np.zeros((2, 21, 3), dtype=float)
        for index, offset in enumerate((0, 55)):
            keypoints[index, :, 0] = np.linspace(125 + offset, 165 + offset, 21)
            keypoints[index, :, 1] = np.linspace(65, 105, 21)
            keypoints[index, :, 2] = 0.9
        result = SimpleNamespace(
            boxes=[
                SimpleNamespace(xyxy=np.array([[100, 50, 220, 180]], dtype=float), conf=Scalar(0.9)),
                SimpleNamespace(xyxy=np.array([[130, 50, 250, 180]], dtype=float), conf=Scalar(0.8)),
            ],
            keypoints=SimpleNamespace(data=keypoints),
        )
        evidence = HandMotionEstimator().update(result, 1, 1.0, 0.01)
        self.assertEqual(2, evidence["manosVisibles"])

    def test_translated_crop_pose_uses_full_frame_coordinates(self):
        points = np.ones((1, 21, 3), dtype=float)
        result = SimpleNamespace(
            boxes=[SimpleNamespace(
                xyxy=np.array([[10, 20, 30, 40]], dtype=float), conf=Scalar(0.8),
            )],
            keypoints=SimpleNamespace(data=points),
        )
        translated = translate_pose_result(result, 100, 200)
        self.assertEqual((110.0, 220.0, 130.0, 240.0),
                         camera_runner.box_coordinates(translated.boxes[0]))
        np.testing.assert_array_equal([101.0, 201.0, 1.0],
                                      translated.keypoints.data[0, 0])

    def test_hand_recovery_tiles_cover_long_axis_with_overlap_in_both_orientations(self):
        landscape = hand_recovery_tiles(np.zeros((540, 960, 3), dtype=np.uint8))
        self.assertEqual(2, len(landscape))
        self.assertEqual((540, 552, 3), landscape[0][0].shape)
        self.assertEqual((540, 552, 3), landscape[1][0].shape)
        self.assertEqual((0, 0, 0, 0, 480), landscape[0][1:])
        self.assertEqual((408, 0, 0, 1, 480), landscape[1][1:])

        portrait = hand_recovery_tiles(np.zeros((960, 540, 3), dtype=np.uint8))
        self.assertEqual(2, len(portrait))
        self.assertEqual((552, 540, 3), portrait[0][0].shape)
        self.assertEqual((552, 540, 3), portrait[1][0].shape)
        self.assertEqual((0, 0, 1, 0, 480), portrait[0][1:])
        self.assertEqual((0, 408, 1, 1, 480), portrait[1][1:])
        odd_landscape = hand_recovery_tiles(np.zeros((541, 961, 3), dtype=np.uint8))
        self.assertEqual(odd_landscape[0][0].shape, odd_landscape[1][0].shape)
        self.assertEqual([], hand_recovery_tiles(np.zeros((2, 2, 3), dtype=np.uint8)))

    def test_tile_merge_translates_boxes_and_keypoints_to_full_frame(self):
        specs = hand_recovery_tiles(np.zeros((540, 960, 3), dtype=np.uint8))
        merged = merge_hand_pose_tiles([
            hand_pose_result((200, 100, 250, 160)),
            hand_pose_result((152, 100, 202, 160)),
        ], specs)
        hands = detected_hands(merged, min_confidence=0.1)
        self.assertEqual(2, len(hands))
        self.assertEqual([(200.0, 100.0, 250.0, 160.0),
                          (560.0, 100.0, 610.0, 160.0)],
                         sorted(coordinates for coordinates, _ in hands))
        self.assertAlmostEqual(562.0, float(merged.keypoints.data[1, 0, 0]))

    def test_tile_merge_does_not_limit_each_tile_to_one_hand(self):
        specs = hand_recovery_tiles(np.zeros((540, 960, 3), dtype=np.uint8))
        merged = merge_hand_pose_tiles([
            hand_pose_result((100, 100, 150, 160), (300, 220, 350, 280)),
            hand_pose_result(),
        ], specs)
        self.assertEqual(2, len(detected_hands(merged, min_confidence=0.1)))

    def test_tile_merge_uses_owner_side_to_reject_overlap_duplicate(self):
        specs = hand_recovery_tiles(np.zeros((540, 960, 3), dtype=np.uint8))
        merged = merge_hand_pose_tiles([
            hand_pose_result((420, 100, 470, 160)),
            hand_pose_result((12, 100, 62, 160)),
        ], specs)
        self.assertEqual(1, len(detected_hands(merged, min_confidence=0.1)))

    def test_tile_merge_rejects_a_missing_prediction_result(self):
        specs = hand_recovery_tiles(np.zeros((540, 960, 3), dtype=np.uint8))
        with self.assertRaisesRegex(ValueError, "un resultado por cada recorte"):
            merge_hand_pose_tiles([], specs)

    def test_recovery_batches_tiles_only_when_full_frame_misses_a_hand(self):
        class FakeModel:
            def __init__(self, whole, tiles):
                self.whole = whole
                self.tiles = tiles
                self.calls = []

            def predict(self, source, **options):
                self.calls.append((source, options))
                return self.tiles if isinstance(source, list) else [self.whole]

        model = FakeModel(
            hand_pose_result((100, 100, 150, 160)),
            [hand_pose_result((200, 100, 250, 160)),
             hand_pose_result((152, 100, 202, 160))],
        )
        recovered, tile_inferences = recover_hand_pose(
            model, np.zeros((540, 960, 3), dtype=np.uint8),
            {"imgsz": 640, "save": True}, 0.1,
        )

        self.assertEqual(2, len(detected_hands(recovered, min_confidence=0.1)))
        self.assertEqual(2, tile_inferences)
        self.assertEqual(2, len(model.calls))
        self.assertFalse(model.calls[0][1]["save"])
        tile_source, tile_options = model.calls[1]
        self.assertEqual(2, len(tile_source))
        self.assertFalse(tile_options["save"])

    def test_recovery_keeps_full_frame_result_when_tiles_do_not_improve(self):
        class FakeModel:
            def __init__(self, whole, tiles):
                self.whole = whole
                self.tiles = tiles

            def predict(self, source, **options):
                return self.tiles if isinstance(source, list) else [self.whole]

        whole = hand_pose_result((100, 100, 150, 160))
        model = FakeModel(whole, [hand_pose_result(), hand_pose_result()])
        recovered, tile_inferences = recover_hand_pose(
            model, np.zeros((540, 960, 3), dtype=np.uint8),
            {"imgsz": 640}, 0.1,
        )
        self.assertIs(whole, recovered)
        self.assertEqual(2, tile_inferences)

    def test_recovery_skips_tiles_when_full_frame_finds_both_hands(self):
        class FakeModel:
            def __init__(self):
                self.calls = 0

            def predict(self, source, **_options):
                self.calls += 1
                return [hand_pose_result(
                    (100, 100, 150, 160), (600, 100, 650, 160),
                )]

        model = FakeModel()
        _recovered, tile_inferences = recover_hand_pose(
            model, np.zeros((540, 960, 3), dtype=np.uint8),
            {"imgsz": 640}, 0.1,
        )
        self.assertEqual(1, model.calls)
        self.assertEqual(0, tile_inferences)

    def test_recovery_replaces_primary_only_when_pose_evidence_quality_improves(self):
        primary = dict(secuencia=10, manosVisibles=1, _manosParaInicio=1,
                       medicionValida=False, _captured_at=1.0)
        weaker_new_frame = dict(secuencia=11, manosVisibles=0, _manosParaInicio=0,
                                medicionValida=False, _captured_at=1.1)
        better_same_frame = dict(secuencia=10, manosVisibles=2, _manosParaInicio=2,
                                 medicionValida=True, _captured_at=1.0)
        self.assertFalse(prefer_recovered_motion(weaker_new_frame, primary))
        self.assertTrue(prefer_recovered_motion(better_same_frame, primary))

    def test_recovery_crop_boxes_keep_primary_on_tie_and_choose_more_guides(self):
        primary = [((100, 100, 150, 150), 0.5)]
        same_quality = [((101, 100, 151, 150), 0.5)]
        improved_count = [*primary, ((200, 100, 250, 150), 0.15)]
        improved_score = [((100, 100, 150, 150), 0.6)]
        self.assertFalse(camera_runner.prefer_recovered_localization(same_quality, primary))
        self.assertTrue(camera_runner.prefer_recovered_localization(improved_count, primary))
        self.assertTrue(camera_runner.prefer_recovered_localization(improved_score, primary))

    def test_hand_boxes_filter_low_confidence_and_build_padded_crop(self):
        result = SimpleNamespace(boxes=[
            SimpleNamespace(xyxy=np.array([[400, 200, 520, 300]], dtype=float), conf=Scalar(0.91)),
            SimpleNamespace(xyxy=np.array([[20, 40, 70, 90]], dtype=float), conf=Scalar(0.25)),
        ], keypoints=SimpleNamespace(data=np.full((2, 21, 3), 0.5, dtype=float)))
        hands = detected_hands(result, min_confidence=0.35)
        self.assertEqual(1, len(hands))
        self.assertAlmostEqual(0.91, hands[0][1])
        bounds = hand_crop_bounds(hands, (540, 960, 3), padding=0.45)
        self.assertIsNotNone(bounds)
        left, top, right, bottom = bounds
        self.assertLessEqual(left, 400)
        self.assertLessEqual(top, 200)
        self.assertGreaterEqual(right, 520)
        self.assertGreaterEqual(bottom, 300)
        self.assertLess(right - left, 960)
        self.assertIsNone(hand_crop_bounds([], (540, 960, 3)))

    def test_partial_crop_uses_valid_low_box_confidence_pose_without_displaying_it(self):
        points = np.zeros((1, 21, 3), dtype=float)
        points[0, :, 0] = np.linspace(120, 160, 21)
        points[0, :, 1] = np.linspace(80, 120, 21)
        points[0, :, 2] = 0.9
        result = SimpleNamespace(
            boxes=[SimpleNamespace(
                xyxy=np.array([[110, 70, 170, 130]], dtype=float), conf=Scalar(0.02),
            )],
            keypoints=SimpleNamespace(data=points),
        )

        self.assertEqual([], camera_runner.detected_hand_boxes(result, min_confidence=0.15))
        self.assertEqual(1, len(detected_hands(result, min_confidence=0.001)))
        guidance = camera_runner.partial_crop_guidance_hands(result, 0.001, 0.15)
        self.assertEqual(1, len(guidance))
        self.assertEqual((110.0, 70.0, 170.0, 130.0), guidance[0][0])
        evidence = HandMotionEstimator().update(result, 1, 1.0, 0.001)
        self.assertEqual(1, evidence["manosVisibles"])
        self.assertFalse(evidence["medicionValida"])

    def test_partial_crop_accepts_strong_box_only_but_does_not_make_pose_evidence(self):
        points = np.zeros((1, 21, 3), dtype=float)
        points[0, :6, :] = 0.9
        result = SimpleNamespace(
            boxes=[SimpleNamespace(
                xyxy=np.array([[210, 100, 260, 160]], dtype=float), conf=Scalar(0.2),
            )],
            keypoints=SimpleNamespace(data=points),
        )

        self.assertEqual(1, len(camera_runner.partial_crop_guidance_hands(result, 0.001, 0.15)))
        self.assertEqual([], detected_hands(result, min_confidence=0.001))
        evidence = HandMotionEstimator().update(result, 1, 1.0, 0.001)
        self.assertEqual(0, evidence["manosVisibles"])
        self.assertFalse(evidence["medicionValida"])

    def test_partial_crop_unions_pose_and_distinct_box_without_double_counting(self):
        points = np.zeros((3, 21, 3), dtype=float)
        for index, offset in enumerate((0, 0, 100)):
            points[index, :, 0] = np.linspace(120 + offset, 160 + offset, 21)
            points[index, :, 1] = np.linspace(80, 120, 21)
        points[0, :, 2] = 0.9
        points[1, :6, 2] = 0.9
        points[2, :6, 2] = 0.9
        result = SimpleNamespace(
            boxes=[
                SimpleNamespace(xyxy=np.array([[110, 70, 170, 130]], dtype=float), conf=Scalar(0.02)),
                SimpleNamespace(xyxy=np.array([[110, 70, 170, 130]], dtype=float), conf=Scalar(0.85)),
                SimpleNamespace(xyxy=np.array([[210, 70, 270, 130]], dtype=float), conf=Scalar(0.2)),
            ],
            keypoints=SimpleNamespace(data=points),
        )

        guidance = camera_runner.partial_crop_guidance_hands(result, 0.001, 0.15)
        self.assertEqual(2, len(guidance))
        self.assertEqual({(110.0, 70.0, 170.0, 130.0), (210.0, 70.0, 270.0, 130.0)},
                         {item[0] for item in guidance})

    def test_hand_crop_bounds_keep_separated_hands_inside_edge_clipped_frame(self):
        hands = [((0, 0, 60, 60), 0.8), ((100, 10, 160, 70), 0.7)]
        left, top, right, bottom = hand_crop_bounds(hands, (540, 960, 3))
        self.assertEqual((0, 0), (left, top))
        self.assertGreaterEqual(right, 160)
        self.assertGreaterEqual(bottom, 70)
        self.assertLessEqual(right, 960)
        self.assertLessEqual(bottom, 540)

        near_right_edge = [((850, 0, 910, 60), 0.8), ((920, 5, 960, 65), 0.7)]
        bounds = hand_crop_bounds(near_right_edge, (540, 960, 3))
        self.assertIsNotNone(bounds)
        self.assertEqual(960, bounds[2])
        self.assertLessEqual(bounds[3], 540)

    def test_hand_box_without_a_minimum_pose_skeleton_is_rejected(self):
        scores = np.zeros((1, 21, 3), dtype=float)
        scores[0, :6, 2] = 0.9
        result = SimpleNamespace(
            boxes=[SimpleNamespace(xyxy=np.array([[20, 20, 120, 120]]), conf=Scalar(0.9))],
            keypoints=SimpleNamespace(data=scores),
        )
        self.assertEqual([], detected_hands(result, min_confidence=0.01))

    def test_model_contract_accepts_list_form_of_seven_canonical_names(self):
        names = list(camera_runner.REQUIRED_STEP_CLASSES)
        model = SimpleNamespace(task="detect", names=names)
        class_ids, mode = validate_step_model(model, "seven-steps.pt")
        self.assertEqual(list(range(7)), class_ids)
        self.assertEqual("FRICCION_PARCIAL", mode)

    def test_model_contract_maps_sequential_paso_aliases_to_canonical_steps(self):
        model = SimpleNamespace(
            task="detect",
            names={index: f"paso_{index + 1}" for index in range(7)},
        )
        class_ids, mode = validate_step_model(model, "yolo26n_7pasos.pt")
        self.assertEqual(list(range(7)), class_ids)
        self.assertEqual("FRICCION_PARCIAL", mode)

    def test_partial_model_allows_only_one_optional_background_class(self):
        names = [*camera_runner.REQUIRED_STEP_CLASSES, "Fondo"]
        class_ids, mode = validate_step_model(
            SimpleNamespace(task="detect", names=names), "seven-steps-with-background.pt"
        )
        self.assertEqual(list(range(7)), class_ids)
        self.assertEqual("FRICCION_PARCIAL", mode)

    def test_partial_model_rejects_duplicate_semantic_aliases_and_unknown_classes(self):
        steps = list(camera_runner.REQUIRED_STEP_CLASSES)
        with self.assertRaisesRegex(RuntimeError, "Pasos duplicados: .*Paso1_Palmas"):
            validate_step_model(
                SimpleNamespace(task="detect", names=[*steps, "paso_1"]), "duplicate-step.pt"
            )
        with self.assertRaisesRegex(RuntimeError, "clases extra: .*hand"):
            validate_step_model(
                SimpleNamespace(task="detect", names=[*steps, "hand"]), "unknown-class.pt"
            )

    def test_model_contract_rejects_duplicate_label_names(self):
        names = list(camera_runner.REQUIRED_STEP_CLASSES)
        names[-1] = names[0]
        with self.assertRaisesRegex(RuntimeError, "vacíos o duplicados"):
            validate_step_model(SimpleNamespace(task="detect", names=names), "duplicate-labels.pt")

    def test_model_contract_rejects_non_contiguous_class_ids(self):
        names = {index + 1: label for index, label in enumerate(camera_runner.REQUIRED_STEP_CLASSES)}
        with self.assertRaisesRegex(RuntimeError, "contiguos desde cero"):
            validate_step_model(SimpleNamespace(task="detect", names=names), "shifted-ids.pt")

    def test_model_contract_rejects_extra_classes_in_oms_release_detector(self):
        names = {index: label for index, label in enumerate(REQUIRED_OMS_CLASSES)}
        names[len(names)] = "UNREVIEWED_EXTRA_CLASS"
        with self.assertRaisesRegex(RuntimeError, "exactamente las 36 clases aprobadas"):
            validate_step_model(SimpleNamespace(task="detect", names=names), "extra-oms-class.pt")

    def test_model_contract_rejects_permuted_oms_class_order(self):
        names = list(REQUIRED_OMS_CLASSES)
        names[0], names[1] = names[1], names[0]
        with self.assertRaisesRegex(RuntimeError, "orden canónico del checkpoint"):
            validate_step_model(SimpleNamespace(task="detect", names=names), "permuted-oms-classes.pt")

    def test_step_alias_detection_is_converted_before_sending_to_java(self):
        detection = frame(("paso_7", 0.91), ("paso_2", 0.78))
        step, confidence, evidence = best_detection(detection, "FRICCION_PARCIAL")
        self.assertEqual(("Paso7_Circulares", 0.91, {}), (step, confidence, evidence))
        accepted = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"accepted": True})
        with patch.object(camera_runner.HTTP_SESSION, "post", return_value=accepted) as post:
            self.assertTrue(camera_runner.send_detection(
                "http://127.0.0.1:8080", "session", "token", step, confidence
            ))
        self.assertEqual("PASO_7_CIRCULARES", post.call_args.kwargs["json"]["claseDetectada"])

    def test_presence_pulse_has_a_separate_v2_envelope_and_no_step_evidence(self):
        accepted = SimpleNamespace(raise_for_status=lambda: None,
                                   json=lambda: {"accepted": True})
        captured_at = time.monotonic()
        with patch.object(camera_runner.HTTP_SESSION, "post", return_value=accepted) as post:
            self.assertTrue(camera_runner.send_detection(
                "http://127.0.0.1:8080", "session", "token", "PRESENCIA_MANOS", 1.0,
                producer_epoch="epoch", frame_captured_at=captured_at,
                event_type="PRESENCE", control_sequence=4, frame_watermark=12,
                presence_hands_visible=2, require_accepted_ack=False,
            ))

        payload = post.call_args.kwargs["json"]
        self.assertEqual("PRESENCE", payload["eventType"])
        self.assertEqual("PRESENCIA_MANOS", payload["claseDetectada"])
        self.assertEqual(4, payload["controlSequence"])
        self.assertEqual(12, payload["frameWatermark"])
        self.assertEqual(2, payload["presenceHandsVisible"])
        self.assertNotIn("frameSequence", payload)
        self.assertIsNone(payload["evidenciaMovimiento"])
        self.assertEqual({}, payload["evidenciaJabon"])

    def test_presence_pulse_rejects_invalid_counts_and_mixed_step_evidence_locally(self):
        with patch.object(camera_runner.HTTP_SESSION, "post") as post:
            for count in (True, -1, 3, None):
                self.assertFalse(camera_runner.send_detection(
                    "http://127.0.0.1:8080", "session", "token", "PRESENCIA_MANOS", 1.0,
                    producer_epoch="epoch", frame_captured_at=time.monotonic(),
                    event_type="PRESENCE", control_sequence=1, frame_watermark=1,
                    presence_hands_visible=count,
                ))
            self.assertFalse(camera_runner.send_detection(
                "http://127.0.0.1:8080", "session", "token", "PRESENCIA_MANOS", 1.0,
                producer_epoch="epoch", frame_captured_at=time.monotonic(),
                event_type="PRESENCE", control_sequence=1, frame_watermark=1,
                presence_hands_visible=2, motion_evidence={"secuencia": 1},
            ))
        post.assert_not_called()

    def test_non_finite_and_out_of_range_scores_are_abstentions(self):
        malformed = frame(("Paso1_Palmas", float("nan")))
        mixed = frame(("Paso1_Palmas", float("inf")), ("Paso2_Dorsos", 0.82))

        self.assertEqual((None, None, {}), best_detection(malformed, "FRICCION_PARCIAL"))
        self.assertEqual(("Paso2_Dorsos", 0.82, {}),
                         best_detection(mixed, "FRICCION_PARCIAL"))

        accepted = SimpleNamespace(raise_for_status=lambda: None,
                                   json=lambda: {"accepted": True})
        with patch.object(camera_runner.HTTP_SESSION, "post", return_value=accepted) as post:
            for invalid in (float("nan"), float("inf"), float("-inf"), -0.01, 1.01, True):
                self.assertFalse(camera_runner.send_detection(
                    "http://127.0.0.1:8080", "session", "token", "Paso1_Palmas", invalid
                ))
        post.assert_not_called()

    def test_invalid_critical_score_does_not_retry_or_block_sender(self):
        pending = Queue(maxsize=2)
        pending.put_nowait(("OMS_CONTACTO_RIESGO", float("nan"), {}))
        pending.put_nowait(None)

        with patch.object(camera_runner, "send_detection") as send, \
                patch("builtins.print") as warning:
            detection_sender(pending, Event(), "http://127.0.0.1:8080", "session", "token")

        send.assert_not_called()
        warning.assert_called_once()
        pending.join()

    def test_invalid_score_does_not_add_a_temporal_vote_or_bypass_risk_priority(self):
        temporal = TemporalStepFilter(history_size=3, min_votes=2)
        self.assertEqual((None, None), temporal.update("Paso1_Palmas", 0.9))
        self.assertEqual((None, None), temporal.update("Paso1_Palmas", float("nan")))
        self.assertEqual(("Paso1_Palmas", 0.9), temporal.update("Paso1_Palmas", 0.9))

        risk_temporal = TemporalStepFilter(history_size=3, min_votes=2)
        self.assertEqual((None, None), camera_runner.stabilize_detection(
            risk_temporal, "PROTOCOLO_OMS", "OMS_CONTACTO_RIESGO", float("inf")
        ))

    def test_explicit_background_class_vetoes_a_step_at_equal_or_higher_confidence(self):
        tied = frame(("Paso1_Palmas", 0.72), ("Fondo", 0.72))
        padded_label = frame(("Paso1_Palmas", 0.72), (" Fondo ", 0.72))
        stronger = frame(("Paso1_Palmas", 0.72), ("Fondo", 0.73))
        weaker = frame(("Paso1_Palmas", 0.72), ("Fondo", 0.71))

        self.assertEqual((None, None, {}), best_detection(tied, "FRICCION_PARCIAL"))
        self.assertEqual((None, None, {}), best_detection(padded_label, "FRICCION_PARCIAL"))
        self.assertEqual((None, None, {}), best_detection(stronger, "FRICCION_PARCIAL"))
        self.assertEqual(("Paso1_Palmas", 0.72, {}),
                         best_detection(weaker, "FRICCION_PARCIAL"))

    def test_all_seven_model_classes_are_mapped_to_the_backend_vocabulary(self):
        accepted = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"accepted": True})
        with patch.object(camera_runner.HTTP_SESSION, "post", return_value=accepted) as post:
            for model_class in camera_runner.REQUIRED_STEP_CLASSES:
                self.assertTrue(camera_runner.send_detection(
                    "http://127.0.0.1:8080", "session", "token", model_class, 0.9
                ))

        sent_classes = [call.kwargs["json"]["claseDetectada"] for call in post.call_args_list]
        self.assertEqual(
            [camera_runner.STEP_TO_BACKEND[name] for name in camera_runner.REQUIRED_STEP_CLASSES],
            sent_classes,
        )

    def test_camera_can_join_the_dashboard_session_by_pairing_code(self):
        response = SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"sessionId": "dashboard-session", "accessToken": "device-token"},
        )
        with patch.object(camera_runner.HTTP_SESSION, "post", return_value=response) as post:
            credentials = camera_runner.pair_session("http://127.0.0.1:8080", "ABCDE-12345")
        self.assertEqual(("dashboard-session", "device-token"), credentials)
        post.assert_called_once_with(
            "http://127.0.0.1:8080/api/v1/auth/login",
            json={"code": "ABCDE-12345", "producerProtocolVersion": "2"}, timeout=5,
        )

    def test_pairing_code_can_be_supplied_by_supervisor_environment(self):
        with patch("sys.argv", ["camera"]), patch.dict(
            "os.environ", {"HANDWASH_PAIRING_CODE": "ABCDE-12345"}
        ):
            options = camera_runner.parse_args()
        self.assertEqual("ABCDE-12345", options.pairing_code)

    def test_new_session_requests_v2_and_registers_epoch_with_existing_token(self):
        created = SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"sessionId": "new-session", "accessToken": "owner-token",
                          "pairingCode": "ABCDE-12345"},
        )
        registered = SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"protocolVersion": 2, "producerEpoch": "epoch-123"},
        )
        with patch.object(camera_runner.HTTP_SESSION, "post", side_effect=[created, registered]) as post:
            session_id, token = camera_runner.create_session("http://127.0.0.1:8080", "DOMESTICO")
            epoch = camera_runner.register_producer_epoch(
                "http://127.0.0.1:8080", session_id, token)

        self.assertEqual(("new-session", "owner-token", "epoch-123"), (session_id, token, epoch))
        self.assertEqual(
            {"protocolo": "DOMESTICO", "producerProtocolVersion": "2"},
            post.call_args_list[0].kwargs["json"],
        )
        self.assertEqual(
            {"X-Session-Token": "owner-token"},
            post.call_args_list[1].kwargs["headers"],
        )
        self.assertTrue(post.call_args_list[1].args[0].endswith("/api/v1/session/new-session/producer-epoch"))

    def test_each_python_process_registration_receives_a_fresh_epoch(self):
        responses = [
            SimpleNamespace(raise_for_status=lambda: None,
                           json=lambda: {"protocolVersion": 2, "producerEpoch": "epoch-one"}),
            SimpleNamespace(raise_for_status=lambda: None,
                           json=lambda: {"protocolVersion": 2, "producerEpoch": "epoch-two"}),
        ]
        with patch.object(camera_runner.HTTP_SESSION, "post", side_effect=responses) as post:
            first = camera_runner.register_producer_epoch(
                "http://127.0.0.1:8080", "session", "device-token")
            restarted = camera_runner.register_producer_epoch(
                "http://127.0.0.1:8080", "session", "device-token")
        self.assertNotEqual(first, restarted)
        self.assertEqual(2, post.call_count)

    def test_v2_detection_sends_epoch_frame_evidence_and_diagnostic_age(self):
        movement = dict(secuencia=12, manosVisibles=2, movimientoNormalizado=0.2,
                        medicionValida=True, antiguedadMs=0, _captured_at=10.0)
        accepted = SimpleNamespace(raise_for_status=lambda: None,
                                   json=lambda: {"accepted": True, "filtered": False})
        with patch.object(camera_runner.time, "monotonic", return_value=10.125), \
                patch.object(camera_runner.HTTP_SESSION, "post", return_value=accepted) as post:
            self.assertTrue(camera_runner.send_detection(
                "http://127.0.0.1:8080", "session", "token", "Paso1_Palmas", .95,
                {}, movement, producer_epoch="epoch-1", frame_sequence=12,
                frame_captured_at=10.0,
            ))

        payload = post.call_args.kwargs["json"]
        self.assertEqual("epoch-1", payload["producerEpoch"])
        self.assertEqual("DETECTION", payload["eventType"])
        self.assertEqual(12, payload["frameSequence"])
        self.assertEqual(125, payload["captureAgeMs"])
        self.assertEqual(12, payload["evidenciaMovimiento"]["secuencia"])
        self.assertNotIn("_captured_at", payload["evidenciaMovimiento"])

    def test_v2_mismatched_evidence_is_not_sent(self):
        movement = {"secuencia": 7, "_captured_at": 10.0}
        with patch.object(camera_runner.HTTP_SESSION, "post") as post:
            self.assertFalse(camera_runner.send_detection(
                "http://127.0.0.1:8080", "session", "token", "Paso1_Palmas", .95,
                {}, movement, producer_epoch="epoch-1", frame_sequence=8,
                frame_captured_at=10.0,
            ))
        post.assert_not_called()

    def test_boolean_sequence_is_not_coerced_to_frame_one_or_sent_to_java(self):
        movement = {"secuencia": True, "_captured_at": 10.0}
        self.assertFalse(camera_runner.motion_evidence_matches_frame(
            movement, 1, 10.0, 0.5
        ))
        self.assertFalse(camera_runner.motion_evidence_matches_frame(
            {"secuencia": 1, "_captured_at": 10.0}, True, 10.0, 0.5
        ))
        with patch.object(camera_runner.HTTP_SESSION, "post") as post:
            self.assertFalse(camera_runner.send_detection(
                "http://127.0.0.1:8080", "session", "token", "Paso1_Palmas", .95,
                {}, movement, producer_epoch="epoch-1", frame_sequence=1,
                frame_captured_at=10.0,
            ))
        post.assert_not_called()

    def test_hand_motion_estimator_rejects_boolean_frame_sequence(self):
        estimator = HandMotionEstimator()
        evidence = estimator.update(None, True, 10.0)
        self.assertFalse(evidence["medicionValida"])
        self.assertEqual(-1, estimator.current_sequence)

    def test_soap_evidence_is_bound_to_the_same_frame_as_pose_and_detection(self):
        movement = dict(secuencia=12, manosVisibles=2, movimientoNormalizado=0.2,
                        medicionValida=True, antiguedadMs=0, _captured_at=10.0)
        foam = {"PALMA_IZQUIERDA": {"estado": "ESPUMA_VISIBLE", "confianza": 0.96}}
        accepted = SimpleNamespace(raise_for_status=lambda: None,
                                   json=lambda: {"accepted": True, "filtered": False})
        with patch.object(camera_runner.time, "monotonic", return_value=10.125), \
                patch.object(camera_runner.HTTP_SESSION, "post", return_value=accepted) as post:
            self.assertTrue(camera_runner.send_detection(
                "http://127.0.0.1:8080", "session", "token", "OMS_03_FROTAR_PALMAS", .95,
                foam, movement, producer_epoch="epoch-1", frame_sequence=12,
                frame_captured_at=10.0,
            ))
            self.assertFalse(camera_runner.send_detection(
                "http://127.0.0.1:8080", "session", "token", "OMS_03_FROTAR_PALMAS", .95,
                foam, movement, producer_epoch="epoch-1", frame_sequence=13,
                frame_captured_at=10.0,
            ))
            self.assertFalse(camera_runner.send_detection(
                "http://127.0.0.1:8080", "session", "token", "Paso1_Palmas", .95,
                foam,
            ))

        self.assertEqual(1, post.call_count)
        self.assertEqual(12, post.call_args.kwargs["json"]["frameSequence"])
        self.assertEqual(12, post.call_args.kwargs["json"]["evidenciaJabonSecuencia"])

    def test_oms_action_sender_requires_fresh_bilateral_measured_evidence(self):
        valid = dict(secuencia=12, manosVisibles=2, movimientoNormalizado=0.2,
                     medicionValida=True, antiguedadMs=0, _captured_at=10.0)
        cases = [
            (None, 12, "missing evidence"),
            ({**valid, "manosVisibles": 1}, 12, "one visible hand"),
            ({**valid, "medicionValida": False}, 12, "invalid spatial measurement"),
            ({**valid, "_captured_at": 9.49}, 12, "stale evidence for source frame"),
            (valid, 13, "sequence mismatch"),
        ]
        with patch.object(camera_runner.time, "monotonic", return_value=10.125), \
                patch.object(camera_runner.HTTP_SESSION, "post") as post:
            for movement, sequence, _reason in cases:
                self.assertFalse(camera_runner.send_detection(
                    "http://127.0.0.1:8080", "session", "token",
                    "OMS_03_FROTAR_PALMAS", .95, {}, movement,
                    producer_epoch="epoch-1", frame_sequence=sequence,
                    frame_captured_at=10.0,
                ))
            self.assertTrue(camera_runner.send_detection(
                "http://127.0.0.1:8080", "session", "token",
                "OMS_03_FROTAR_PALMAS", .95, {}, valid,
                producer_epoch="epoch-1", frame_sequence=12,
                frame_captured_at=10.0,
            ))
        self.assertEqual(1, post.call_count)

    def test_oms_contact_risk_is_sent_even_when_pose_is_unavailable(self):
        accepted = SimpleNamespace(raise_for_status=lambda: None,
                                   json=lambda: {"accepted": True, "filtered": False})
        with patch.object(camera_runner.time, "monotonic", return_value=10.125), \
                patch.object(camera_runner.HTTP_SESSION, "post", return_value=accepted) as post:
            self.assertTrue(camera_runner.send_detection(
                "http://127.0.0.1:8080", "session", "token",
                "OMS_CONTACTO_RIESGO", .81, {}, None,
                producer_epoch="epoch-1", frame_sequence=13,
                frame_captured_at=10.0,
            ))

        payload = post.call_args.kwargs["json"]
        self.assertEqual("OMS_CONTACTO_RIESGO", payload["claseDetectada"])
        self.assertEqual("DETECTION", payload["eventType"])
        self.assertEqual(13, payload["frameSequence"])
        self.assertIsNone(payload["evidenciaMovimiento"])

    def test_oms_sender_drops_evidence_that_ages_while_waiting_in_queue(self):
        movement = dict(secuencia=12, manosVisibles=2, movimientoNormalizado=0.2,
                        medicionValida=True, antiguedadMs=0, _captured_at=10.0)
        with patch.object(camera_runner.time, "monotonic", return_value=10.501), \
                patch.object(camera_runner.HTTP_SESSION, "post") as post:
            self.assertFalse(camera_runner.send_detection(
                "http://127.0.0.1:8080", "session", "token",
                "OMS_03_FROTAR_PALMAS", .95, {}, movement,
                producer_epoch="epoch-1", frame_sequence=12,
                frame_captured_at=10.0,
            ))
        post.assert_not_called()

    def test_superseded_epoch_header_stops_the_old_sender_without_changing_ack_body(self):
        stale = SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"accepted": False, "filtered": True},
            headers={"X-Producer-Rejection-Reason": "EPOCH_MISMATCH"},
        )
        with patch.object(camera_runner.HTTP_SESSION, "post", return_value=stale):
            with self.assertRaises(camera_runner.PermanentDetectionRejection):
                camera_runner.send_detection(
                    "http://127.0.0.1:8080", "session", "token", "Paso1_Palmas", .95,
                    producer_epoch="old-epoch", frame_sequence=4,
                    frame_captured_at=10.0, require_accepted_ack=False,
                )

    def test_noncanonical_class_header_stops_strict_v2_sender(self):
        rejected = SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"accepted": False, "filtered": True},
            headers={"X-Producer-Rejection-Reason": "NON_CANONICAL_CLASS"},
        )
        with patch.object(camera_runner.HTTP_SESSION, "post", return_value=rejected):
            with self.assertRaises(camera_runner.PermanentDetectionRejection):
                camera_runner.send_detection(
                    "http://127.0.0.1:8080", "session", "token", "Paso1_Palmas", .95,
                    producer_epoch="epoch-1", frame_sequence=9,
                    frame_captured_at=10.0, require_accepted_ack=False,
                )

    def test_control_signal_uses_its_own_sequence_and_frame_watermark(self):
        response = SimpleNamespace(raise_for_status=lambda: None,
                                   json=lambda: {"accepted": False, "filtered": True})
        with patch.object(camera_runner.HTTP_SESSION, "post", return_value=response) as post:
            self.assertTrue(camera_runner.send_detection(
                "http://127.0.0.1:8080", "session", "token", "Fondo", 1.0,
                producer_epoch="epoch-1", frame_captured_at=10.0,
                event_type="CONTROL", control_sequence=2, frame_watermark=21,
                require_accepted_ack=False,
            ))
        payload = post.call_args.kwargs["json"]
        self.assertEqual("CONTROL", payload["eventType"])
        self.assertEqual(2, payload["controlSequence"])
        self.assertEqual(21, payload["frameWatermark"])
        self.assertNotIn("frameSequence", payload)
        self.assertIsNone(payload["evidenciaMovimiento"])

    def test_python_restart_gets_new_epoch_but_ffmpeg_restart_keeps_process_sequence(self):
        first_process = camera_runner.ProducerEpochStream("epoch-before-restart")
        capture_sequence = camera_runner.CameraFrameSequence()
        first_frame = capture_sequence.next()
        self.assertTrue(first_process.reserve_frame(first_frame))

        with patch.object(camera_runner.subprocess, "Popen"):
            camera_runner.start_camera_process(3, 960, 540)
        reconnected_frame = capture_sequence.next()
        self.assertEqual("epoch-before-restart", first_process.producer_epoch)
        self.assertGreater(reconnected_frame, first_frame)
        self.assertTrue(first_process.reserve_frame(reconnected_frame))
        self.assertFalse(first_process.reserve_frame(reconnected_frame))

        restarted_process = camera_runner.ProducerEpochStream("epoch-after-restart")
        self.assertNotEqual(first_process.producer_epoch, restarted_process.producer_epoch)
        self.assertTrue(restarted_process.reserve_frame(1))

    def test_presence_heartbeat_uses_control_sequence_without_consuming_step_frame(self):
        stream = camera_runner.ProducerEpochStream("epoch")
        self.assertEqual(0, stream.reserve_presence(10))
        self.assertFalse(stream.reserve_frame(9), "a detector frame cannot rewind behind presence")
        self.assertTrue(stream.reserve_frame(10))
        self.assertIsNone(stream.reserve_presence(10), "duplicate presence watermarks are not queued")
        self.assertEqual(1, stream.reserve_control(11))
        self.assertIsNone(stream.reserve_presence(10), "presence cannot rewind behind a reset control")

    def test_camera_preflight_rejects_screen_capture_even_with_explicit_index(self):
        with patch.object(camera_runner, "camera_name", return_value="Capture screen 0"):
            with self.assertRaisesRegex(RuntimeError, "no al iPhone"):
                camera_runner.select_iphone_camera(1)

    def test_camera_preflight_does_not_load_yolo_or_start_services(self):
        args = SimpleNamespace(check_camera=True, check_model=False, camera_index=None)
        with patch.object(camera_runner, "parse_args", return_value=args), \
             patch.object(camera_runner, "continuity_camera_index", return_value=2), \
             patch.object(camera_runner, "camera_name", return_value="iPhone de Jhon"), \
             patch.object(camera_runner, "YOLO") as model, \
             patch("builtins.print") as message:
            camera_runner.run()
        model.assert_not_called()
        message.assert_called_once_with(
            "Cámara de Continuidad disponible: [2] iPhone de Jhon", flush=True)

    def test_model_preflight_rejects_partial_oms_weights_before_camera_capture(self):
        args = SimpleNamespace(check_camera=False, check_model=True, model="candidate.pt")
        incomplete = SimpleNamespace(task="detect", names={0: "OMS_01_MOJAR_MANOS"})
        with patch.object(camera_runner, "parse_args", return_value=args), \
             patch.object(camera_runner, "verify_model_artifact", return_value="0" * 64), \
             patch.object(camera_runner, "YOLO", return_value=incomplete), \
             patch.object(camera_runner, "select_iphone_camera") as camera:
            with self.assertRaises(SystemExit) as raised:
                camera_runner.run()
        self.assertIn("no corresponde a un modelo OMS completo", str(raised.exception))
        camera.assert_not_called()

    def test_step_transitions_are_immediate_and_same_step_heartbeat_is_bounded(self):
        self.assertTrue(should_send_step_detection("Paso2_Dorsos", 0.9,
                                                   "Paso1_Palmas", 0.01, 350))
        self.assertFalse(should_send_step_detection("Paso1_Palmas", 0.9,
                                                    "Paso1_Palmas", 0.34, 350))
        self.assertTrue(should_send_step_detection("Paso1_Palmas", 0.9,
                                                   "Paso1_Palmas", 0.35, 350))
        self.assertFalse(should_send_step_detection(None, None,
                                                    "Paso1_Palmas", 2.0, 350))

    def test_idle_background_does_not_advance_watermark_past_first_step_pose(self):
        stream = camera_runner.ProducerEpochStream("epoch")
        for camera_frame, pose_frame in ((100, 99), (110, 109), (120, 119)):
            self.assertFalse(should_publish_visibility_loss(None, 0.0, float(camera_frame), 0.9))
            self.assertTrue(stream.reserve_frame(pose_frame))
        self.assertFalse(should_publish_visibility_loss("Paso1_Palmas", 120.0, 120.8, 0.9))
        self.assertTrue(should_publish_visibility_loss("Paso1_Palmas", 120.0, 120.9, 0.9))
        self.assertEqual(0, stream.reserve_control(121))
        self.assertFalse(stream.reserve_frame(120))

    def test_risk_takes_precedence_over_a_higher_scored_normal_action(self):
        result = frame(
            ("OMS_03_FROTAR_PALMAS", 0.99),
            ("OMS_CONTACTO_RIESGO", 0.81),
            ("ESPUMA_VISIBLE_PALMA_IZQUIERDA", 0.95),
        )
        name, confidence, evidence = best_detection(result, "PROTOCOLO_OMS")
        self.assertEqual("OMS_CONTACTO_RIESGO", name)
        self.assertEqual(0.81, confidence)
        self.assertEqual({}, evidence)

    def test_soap_evidence_is_sent_only_during_matching_rubbing_phase(self):
        foam = ("ESPUMA_VISIBLE_PALMA_IZQUIERDA", 0.95)
        wet = frame(("OMS_01_MOJAR_MANOS", 0.90), foam)
        self.assertEqual({}, best_detection(wet, "PROTOCOLO_OMS")[2])

        soap = frame(("OMS_02_APLICAR_JABON", 0.90), foam)
        self.assertEqual({}, best_detection(soap, "PROTOCOLO_OMS")[2])
        palms = frame(("OMS_03_FROTAR_PALMAS", 0.90), foam)
        self.assertEqual(
            {"PALMA_IZQUIERDA": {"estado": "ESPUMA_VISIBLE", "confianza": 0.95}},
            best_detection(palms, "PROTOCOLO_OMS")[2],
        )
        dorsos = frame(("OMS_04_FROTAR_DORSOS", 0.90), foam)
        self.assertEqual({}, best_detection(dorsos, "PROTOCOLO_OMS")[2])
        rinse = frame(("OMS_09_ENJUAGAR_MANOS", 0.90), foam)
        self.assertEqual({}, best_detection(rinse, "PROTOCOLO_OMS")[2])

    def test_soap_from_outside_the_current_hand_action_is_not_credited(self):
        result = frame(
            ("OMS_03_FROTAR_PALMAS", 0.91, (0, 0, 100, 100)),
            ("ESPUMA_VISIBLE_PALMA_IZQUIERDA", 0.96, (200, 200, 230, 230)),
            ("ESPUMA_VISIBLE_PALMA_DERECHA", 0.96, (40, 40, 70, 70)),
        )
        _, _, evidence = best_detection(result, "PROTOCOLO_OMS")
        self.assertNotIn("PALMA_IZQUIERDA", evidence)
        self.assertIn("PALMA_DERECHA", evidence)

    def test_disjoint_oms_action_boxes_abstain_instead_of_mixing_people(self):
        result = frame(
            ("OMS_03_FROTAR_PALMAS", 0.95, (0, 0, 100, 100)),
            ("OMS_03_FROTAR_PALMAS", 0.90, (200, 200, 300, 300)),
            ("ESPUMA_VISIBLE_PALMA_IZQUIERDA", 0.96, (20, 20, 50, 50)),
        )
        self.assertEqual((None, None, {}), best_detection(result, "PROTOCOLO_OMS"))

    def test_conflicting_soap_predictions_are_not_credited_as_visible_foam(self):
        result = frame(
            ("OMS_03_FROTAR_PALMAS", 0.95, (0, 0, 100, 100)),
            ("ESPUMA_VISIBLE_PALMA_IZQUIERDA", 0.95, (10, 10, 50, 50)),
            ("SIN_ESPUMA_VISIBLE_PALMA_IZQUIERDA", 0.92, (12, 12, 48, 48)),
        )
        _, _, evidence = best_detection(result, "PROTOCOLO_OMS")
        self.assertEqual("NO_VERIFICABLE", evidence["PALMA_IZQUIERDA"]["estado"])

    def test_partial_oms_weights_are_rejected_before_camera_capture(self):
        model = SimpleNamespace(
            task="detect",
            names={index: name for index, name in enumerate(REQUIRED_OMS_CLASSES[:-1])},
        )
        with self.assertRaisesRegex(RuntimeError, "no corresponde a un modelo OMS completo"):
            validate_step_model(model, "incomplete.pt")

    def test_camera_gap_signals_are_sent_in_the_selected_backend_vocabulary(self):
        with patch.object(camera_runner.HTTP_SESSION, "post") as post:
            camera_runner.send_detection("http://127.0.0.1:8080", "session", "token",
                                         "OMS_SIN_EVIDENCIA", 1.0, {})
            self.assertEqual("OMS_SIN_EVIDENCIA", post.call_args.kwargs["json"]["claseDetectada"])
            camera_runner.send_detection("http://127.0.0.1:8080", "session", "token",
                                         "Fondo", 1.0, {})
            self.assertEqual("FONDO", post.call_args.kwargs["json"]["claseDetectada"])

    def test_temporal_filter_does_not_credit_stale_action_or_confidence(self):
        temporal = TemporalStepFilter(history_size=3, min_votes=2)
        self.assertEqual((None, None), temporal.update("OMS_01_MOJAR_MANOS", 0.99))
        self.assertEqual(("OMS_01_MOJAR_MANOS", 0.99),
                         temporal.update("OMS_01_MOJAR_MANOS", 0.99))
        self.assertEqual(("OMS_01_MOJAR_MANOS", 0.61),
                         temporal.update("OMS_01_MOJAR_MANOS", 0.61))
        self.assertEqual((None, None), temporal.update("OMS_02_APLICAR_JABON", 0.9))
        self.assertEqual(("OMS_02_APLICAR_JABON", 0.9),
                         temporal.update("OMS_02_APLICAR_JABON", 0.9))

        temporal.reset()
        self.assertEqual((None, None), temporal.update("OMS_02_APLICAR_JABON", 0.9))

    def test_temporal_votes_never_replay_an_older_higher_confidence(self):
        temporal = TemporalStepFilter(history_size=3, min_votes=2)
        self.assertEqual((None, None), temporal.update("Paso1_Palmas", 0.99))
        self.assertEqual(("Paso1_Palmas", 0.54), temporal.update("Paso1_Palmas", 0.54))
        self.assertEqual((None, None), temporal.update("Paso2_Dorsos", 0.98))
        self.assertEqual(("Paso2_Dorsos", 0.55), temporal.update("Paso2_Dorsos", 0.55))

    def test_temporal_votes_survive_variable_fps_but_expire_after_a_capture_gap(self):
        temporal = TemporalStepFilter(history_size=3, min_votes=2)
        samples = [
            (10.00, "Paso1_Palmas", 0.91),
            (10.14, "Paso1_Palmas", 0.88),
            (10.51, "Paso2_Dorsos", 0.87),
            (10.82, "Paso2_Dorsos", 0.89),
        ]
        previous = 0.0
        stable = []
        for captured_at, label, confidence in samples:
            if camera_runner.temporal_gap_exceeded(previous, captured_at, 0.9):
                temporal.reset()
            stable.append(temporal.update(label, confidence))
            previous = captured_at

        self.assertEqual(("Paso1_Palmas", 0.88), stable[1])
        self.assertEqual(("Paso2_Dorsos", 0.89), stable[3])
        if camera_runner.temporal_gap_exceeded(previous, 11.75, 0.9):
            temporal.reset()
        self.assertEqual((None, None), temporal.update("Paso2_Dorsos", 0.92))

    def test_oms_contact_risk_is_sent_on_first_frame_and_resets_votes(self):
        temporal = TemporalStepFilter(history_size=3, min_votes=2)
        self.assertEqual((None, None), camera_runner.stabilize_detection(
            temporal, "PROTOCOLO_OMS", "OMS_03_FROTAR_PALMAS", 0.90))
        self.assertEqual(("OMS_CONTACTO_RIESGO", 0.82), camera_runner.stabilize_detection(
            temporal, "PROTOCOLO_OMS", "OMS_CONTACTO_RIESGO", 0.82))
        self.assertEqual((None, None), camera_runner.stabilize_detection(
            temporal, "PROTOCOLO_OMS", "OMS_03_FROTAR_PALMAS", 0.91))
        self.assertEqual(("OMS_03_FROTAR_PALMAS", 0.92), camera_runner.stabilize_detection(
            temporal, "PROTOCOLO_OMS", "OMS_03_FROTAR_PALMAS", 0.92))

    def test_risk_signal_preempts_queued_phase_and_survives_newer_normal_frames(self):
        pending = Queue(maxsize=2)
        enqueue_latest_detection(pending, ("OMS_03_FROTAR_PALMAS", 0.9, {}))
        enqueue_latest_detection(pending, ("OMS_CONTACTO_RIESGO", 0.8, {}))
        enqueue_latest_detection(pending, ("OMS_04_FROTAR_DORSOS", 0.9, {}))
        self.assertEqual("OMS_CONTACTO_RIESGO", pending.get_nowait()[0])
        self.assertEqual("OMS_04_FROTAR_DORSOS", pending.get_nowait()[0])

    def test_visibility_loss_preempts_stale_phase(self):
        pending = Queue(maxsize=2)
        enqueue_latest_detection(pending, ("OMS_03_FROTAR_PALMAS", 0.9, {}))
        enqueue_latest_detection(pending, ("OMS_SIN_EVIDENCIA", 1.0, {}))
        self.assertEqual("OMS_SIN_EVIDENCIA", pending.get_nowait()[0])
        self.assertTrue(pending.empty())

    def test_failed_critical_delivery_is_retried_before_any_new_phase(self):
        pending = Queue(maxsize=2)
        stop = Event()
        pending.put_nowait(("OMS_CONTACTO_RIESGO", 0.9, {}))
        attempts = []

        def deliver(*args):
            attempts.append(args[3])
            if len(attempts) == 2:
                stop.set()
                return True
            return False

        with patch.object(camera_runner, "send_detection", side_effect=deliver):
            detection_sender(pending, stop, "http://127.0.0.1:8080", "session", "token")
        self.assertEqual(["OMS_CONTACTO_RIESGO", "OMS_CONTACTO_RIESGO"], attempts)

    def test_v2_filtered_ack_is_not_retried_as_a_transport_failure(self):
        pending = Queue(maxsize=2)
        stop = Event()
        stream = camera_runner.ProducerEpochStream("epoch-1")
        control_sequence = stream.reserve_control(3)
        pending.put_nowait(("Fondo", 1.0, {}, None, None, 10.0,
                            "CONTROL", control_sequence, 3))
        filtered = SimpleNamespace(raise_for_status=lambda: None,
                                   json=lambda: {"accepted": False, "filtered": True})
        with patch.object(camera_runner.HTTP_SESSION, "post", return_value=filtered) as post:
            sender = camera_runner.threading.Thread(
                target=detection_sender,
                args=(pending, stop, "http://127.0.0.1:8080", "session", "token", None, stream),
                daemon=True,
            )
            sender.start()
            pending.join()
            stop.set()
            sender.join(timeout=1)

        self.assertFalse(sender.is_alive())
        post.assert_called_once()

    def test_detection_sender_delivers_presence_with_the_registered_epoch(self):
        pending = Queue(maxsize=2)
        stream = camera_runner.ProducerEpochStream("epoch-1")
        control_sequence = stream.reserve_presence(3)
        pending.put_nowait(("PRESENCIA_MANOS", 1.0, {}, None, None,
                            time.monotonic(), "PRESENCE", control_sequence, 3, 2))
        pending.put_nowait(None)
        accepted = SimpleNamespace(raise_for_status=lambda: None,
                                   json=lambda: {"accepted": True})

        with patch.object(camera_runner.HTTP_SESSION, "post", return_value=accepted) as post:
            detection_sender(
                pending, Event(), "http://127.0.0.1:8080", "session", "token",
                producer_stream=stream,
            )

        self.assertEqual("PRESENCE", post.call_args.kwargs["json"]["eventType"])
        self.assertEqual(2, post.call_args.kwargs["json"]["presenceHandsVisible"])
        pending.join()

    def test_detection_sender_discards_stale_bilateral_presence_before_http_send(self):
        pending = Queue(maxsize=2)
        stream = camera_runner.ProducerEpochStream("epoch-1")
        control_sequence = stream.reserve_presence(3)
        stale_capture_time = time.monotonic() - (
            camera_runner.DEFAULT_HAND_PRESENCE_MAX_GAP_MS / 1000 + 0.001
        )
        pending.put_nowait(("PRESENCIA_MANOS", 1.0, {}, None, None,
                            stale_capture_time, "PRESENCE", control_sequence, 3, 2))
        pending.put_nowait(None)

        with patch.object(camera_runner, "send_detection", return_value=True) as send:
            detection_sender(
                pending, Event(), "http://127.0.0.1:8080", "session", "token",
                producer_stream=stream,
            )

        send.assert_not_called()
        pending.join()

    def test_superseded_epoch_stops_the_sender_thread(self):
        pending = Queue(maxsize=2)
        stop = Event()
        session_ended = Event()
        stream = camera_runner.ProducerEpochStream("old-epoch")
        self.assertTrue(stream.reserve_frame(5))
        pending.put_nowait(("Paso1_Palmas", .95, {}, None, 5, 10.0, "DETECTION"))
        stale = SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"accepted": False, "filtered": True},
            headers={"X-Producer-Rejection-Reason": "EPOCH_MISMATCH"},
        )
        with patch.object(camera_runner.HTTP_SESSION, "post", return_value=stale) as post:
            sender = camera_runner.threading.Thread(
                target=detection_sender,
                args=(pending, stop, "http://127.0.0.1:8080", "session", "token",
                      session_ended, stream),
                daemon=True,
            )
            sender.start()
            pending.join()
            sender.join(timeout=1)
        self.assertTrue(session_ended.is_set())
        self.assertFalse(sender.is_alive())
        post.assert_called_once()

    def test_v2_queue_reorders_retained_priorities_by_frame_watermark(self):
        pending = Queue(maxsize=2)
        enqueue_latest_detection(
            pending, ("Paso1_Palmas", .9, {}, None, 10, 10.0, "DETECTION"))
        enqueue_latest_detection(
            pending, ("OMS_CONTACTO_RIESGO", .8, {}, None, 11, 11.0, "DETECTION"))
        enqueue_latest_detection(
            pending, ("Fondo", 1.0, {}, None, None, 12.0, "CONTROL", 0, 12))
        retained = [pending.get_nowait(), pending.get_nowait()]
        self.assertEqual([11, 12], [item[4] if item[6] == "DETECTION" else item[8]
                                    for item in retained])

    def test_v2_visibility_control_survives_newer_frames_while_queue_is_saturated(self):
        pending = Queue(maxsize=2)
        enqueue_latest_detection(
            pending, ("Paso1_Palmas", .9, {}, None, 10, 10.0, "DETECTION"))
        enqueue_latest_detection(
            pending, ("OMS_CONTACTO_RIESGO", .8, {}, None, 11, 11.0, "DETECTION"))
        enqueue_latest_detection(
            pending, ("Fondo", 1.0, {}, None, None, 12.0, "CONTROL", 0, 12))
        enqueue_latest_detection(
            pending, ("Paso2_Dorsos", .9, {}, None, 13, 13.0, "DETECTION"))

        retained = [pending.get_nowait(), pending.get_nowait()]
        self.assertEqual(["OMS_CONTACTO_RIESGO", "Fondo"], [item[0] for item in retained])
        self.assertEqual([11, 12], [item[4] if item[6] == "DETECTION" else item[8]
                                    for item in retained])

    def test_presence_and_step_coalesce_independently_in_source_sequence_order(self):
        pending = Queue(maxsize=2)
        enqueue_latest_detection(
            pending, ("PRESENCIA_MANOS", 1.0, {}, None, None, 10.0,
                      "PRESENCE", 0, 10, 2))
        enqueue_latest_detection(
            pending, ("Paso1_Palmas", .9, {}, None, 11, 11.0, "DETECTION"))
        retained = [pending.get_nowait(), pending.get_nowait()]
        self.assertEqual(["PRESENCIA_MANOS", "Paso1_Palmas"],
                         [item[0] for item in retained])
        self.assertEqual([10, 11], [item[8] if item[6] == "PRESENCE" else item[4]
                                    for item in retained])

    def test_same_frame_presence_is_sent_before_its_step_candidate(self):
        pending = Queue(maxsize=2)
        enqueue_latest_detection(
            pending, ("PASO_1_PALMAS", .95, {}, None, 10, 10.0, "DETECTION"))
        enqueue_latest_detection(
            pending, ("PRESENCIA_MANOS", 1.0, {}, None, None, 10.0,
                      "PRESENCE", 0, 10, 2))

        retained = [pending.get_nowait(), pending.get_nowait()]
        self.assertEqual(["PRESENCE", "DETECTION"], [item[6] for item in retained])
        self.assertEqual([10, 10], [item[8] if item[6] == "PRESENCE" else item[4]
                                    for item in retained])

    def test_hand_loss_pulse_preempts_queued_step_when_queue_is_full(self):
        pending = Queue(maxsize=2)
        enqueue_latest_detection(
            pending, ("PRESENCIA_MANOS", 1.0, {}, None, None, 10.0,
                      "PRESENCE", 0, 10, 1))
        enqueue_latest_detection(
            pending, ("Paso1_Palmas", .9, {}, None, 11, 11.0, "DETECTION"))
        enqueue_latest_detection(
            pending, ("Paso2_Dorsos", .9, {}, None, 12, 12.0, "DETECTION"))
        retained = [pending.get_nowait(), pending.get_nowait()]
        self.assertEqual(["PRESENCIA_MANOS", "Paso2_Dorsos"],
                         [item[0] for item in retained])


if __name__ == "__main__":
    unittest.main()
