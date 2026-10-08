import unittest
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi import HTTPException
from fastapi.testclient import TestClient

from archive.experimental_fastapi_yolo import yolo26_camera_service as gateway


class GatewaySecurityTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(gateway.app)

    def test_default_gateway_uses_the_active_seven_step_detector(self):
        self.assertEqual(
            gateway.ROOT / "backend/models/handwash_yolo26n_7pasos.pt",
            gateway.DEFAULT_MODEL_PATH,
        )
        self.assertEqual(list(range(7)), gateway.STEP_CLASS_IDS)
        self.assertEqual(
            "Paso7_Circulares",
            gateway.classifier_step_name("paso_7"),
        )

    def test_anonymous_upload_never_reaches_inference(self):
        with patch.object(gateway, "infer_frame") as predict:
            response = self.client.post("/infer", files={"file": ("frame.jpg", b"image", "image/jpeg")})
        self.assertEqual(422, response.status_code)
        predict.assert_not_called()

    def test_invalid_session_token_never_reaches_inference(self):
        unauthorized = SimpleNamespace(status_code=401)
        with patch.object(gateway.requests, "get", return_value=unauthorized), \
             patch.object(gateway, "infer_frame") as predict:
            response = self.client.post(
                "/infer", data={"session_id": "session", "access_token": "wrong"},
                files={"file": ("frame.jpg", b"image", "image/jpeg")},
            )
        self.assertEqual(401, response.status_code)
        predict.assert_not_called()

    def test_oversized_upload_is_rejected_before_inference(self):
        authorized = SimpleNamespace(status_code=200, json=lambda: {"estado": "EN_PROGRESO"})
        with patch.object(gateway.requests, "get", return_value=authorized), \
             patch.object(gateway, "MAX_UPLOAD_BYTES", 64), \
             patch.object(gateway, "infer_frame") as predict:
            response = self.client.post(
                "/infer", data={"session_id": "session", "access_token": "valid"},
                files={"file": ("frame.jpg", b"x" * 65, "image/jpeg")},
            )
        self.assertEqual(413, response.status_code)
        predict.assert_not_called()

    def test_busy_model_drops_the_new_upload_without_queueing_it(self):
        authorized = SimpleNamespace(status_code=200, json=lambda: {"estado": "EN_PROGRESO"})
        gateway.INFERENCE_LOCK.acquire()
        try:
            with patch.object(gateway.requests, "get", return_value=authorized), \
                 patch.object(gateway, "infer_frame") as predict:
                response = self.client.post(
                    "/infer", data={"session_id": "session", "access_token": "valid"},
                    files={"file": ("frame.jpg", b"image", "image/jpeg")},
                )
            self.assertEqual(429, response.status_code)
            predict.assert_not_called()
        finally:
            gateway.INFERENCE_LOCK.release()

    def test_cors_does_not_allow_unrelated_websites(self):
        response = self.client.options("/infer", headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "POST",
        })
        self.assertNotIn("access-control-allow-origin", response.headers)

    def test_highly_compressed_oversized_image_is_rejected_before_decode(self):
        class LargeImage:
            width = 5000
            height = 4000

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                return False

            def convert(self, mode):
                raise AssertionError("Large image must not be decoded")

        with patch.object(gateway.Image, "open", return_value=LargeImage()):
            with self.assertRaises(HTTPException) as raised:
                gateway.infer_frame(b"small compressed image", session_id="session")
        self.assertEqual(413, raised.exception.status_code)


class GatewayTemporalFilterTest(unittest.TestCase):
    @staticmethod
    def step(name, confidence):
        return {"className": name, "confidence": confidence}

    def test_conflicting_frame_abstains_and_old_confidence_is_not_replayed(self):
        selected = gateway.TemporalStepFilter(history_size=3, min_votes=2)
        palms = self.step("Paso1_Palmas", 0.99)
        dorsos = self.step("Paso2_Dorsos", 0.98)
        self.assertIsNone(selected.update("session", palms))
        self.assertEqual("Paso1_Palmas", selected.update("session", palms)["className"])
        self.assertIsNone(selected.update("session", dorsos))
        self.assertEqual("Paso2_Dorsos", selected.update("session", dorsos)["className"])
        self.assertEqual(0.65, selected.update("session", self.step("Paso2_Dorsos", 0.65))["confidence"])

        selected.update("session", None)
        self.assertIsNone(selected.update("session", palms))

    def test_old_session_histories_are_bounded(self):
        selected = gateway.TemporalStepFilter(max_sessions=2)
        selected.update("first", self.step("Paso1_Palmas", 0.9))
        selected.update("second", self.step("Paso1_Palmas", 0.9))
        selected.update("third", self.step("Paso1_Palmas", 0.9))
        self.assertNotIn("first", selected._history)
        self.assertLessEqual(len(selected._history), 2)

    def test_confirmation_uses_current_frame_score_not_old_high_score(self):
        selected = gateway.TemporalStepFilter(history_size=3, min_votes=2)
        self.assertIsNone(selected.update("session", self.step("Paso1_Palmas", 0.99)))
        self.assertEqual(0.54, selected.update("session", self.step("Paso1_Palmas", 0.54))["confidence"])
        self.assertIsNone(selected.update("session", self.step("Paso2_Dorsos", 0.98)))
        self.assertEqual(0.55, selected.update("session", self.step("Paso2_Dorsos", 0.55))["confidence"])


if __name__ == "__main__":
    unittest.main()
