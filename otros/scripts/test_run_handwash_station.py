import json
import argparse
import contextlib
import hashlib
import io
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

import run_handwash_station as station


def ready_station_manifest():
    model_hash = "a" * 64
    data_config_path = station.ROOT / "scripts/testdata/station-release-data.yaml"
    movement_report = station.ROOT / "scripts/testdata/movement-intent-validation.fixture.txt"
    return {
        "schemaVersion": 1,
        "washingIntent": {
            "startMinimumNormalizedMovement": 1e-8,
            "stepMinimumNormalizedMovement": 1e-8,
            "startUsesMovementMagnitudeThreshold": True,
            "startUsesClinicallyCalibratedMovementMagnitudeThreshold": True,
            "stepCreditUsesMovementMagnitudeThreshold": True,
            "stepCreditUsesClinicallyCalibratedMovementMagnitudeThreshold": True,
            "validationEvidence": {
                "status": "VALIDATED_FOR_HOSPITAL_PILOT",
                "startIntentIndependentlyValidated": True,
                "reportPath": "scripts/testdata/movement-intent-validation.fixture.txt",
                "reportSha256": hashlib.sha256(movement_report.read_bytes()).hexdigest(),
            },
        },
        "deploymentReadiness": {
            "status": "READY_FOR_HOSPITAL_PILOT",
            "hospitalUseAllowed": True,
            "stepTaxonomyVerified": True,
            "independentVideoValidationPassed": True,
            "continuityCameraPilotPassed": True,
            "clinicalSafetyReviewPassed": True,
            "blockers": [],
        },
        "active": {
            "task": "detect",
            "sha256": model_hash,
            "modelClassNames": list(station.WHO_REQUIRED_MODEL_CLASSES),
            "trainingRun": {
                "task": "detect",
                "trainingDataConfigIncluded": True,
                "trainingDataConfigPath": "scripts/testdata/station-release-data.yaml",
                "trainingDataConfigSha256": hashlib.sha256(data_config_path.read_bytes()).hexdigest(),
                "identicalToActiveCheckpoint": True,
                "checkpointSha256": model_hash,
            },
            "validatedAgainst": {"independentValidationEligible": True},
        },
        "whoProcedure": {
            "status": "VALIDATED_FOR_HOSPITAL_PILOT",
            "approvalAllowed": True,
            "requiredPhases": list(station.WHO_REQUIRED_PHASES),
        },
        "stationArtifacts": {
            "javaJarSha256": "0" * 64,
            "javaSbomSha256": "4" * 64,
            "cameraPythonSbomSha256": "5" * 64,
            "sbomGeneratorLockSha256": "6" * 64,
            "stationSupervisorSha256": "1" * 64,
            "cameraProducerSha256": "2" * 64,
            "cameraRequirementsLockSha256": "3" * 64,
        },
    }


class StationSupervisorPolicyTest(unittest.TestCase):
    def test_bounded_release_reader_rejects_oversize_and_symlink_inputs(self):
        with tempfile.TemporaryDirectory(prefix="handwash-bounded-read-") as temp_dir:
            root = Path(temp_dir)
            artifact = root / "artifact.json"
            artifact.write_bytes(b"reviewed")

            self.assertEqual(b"reviewed", station._read_bounded_regular_file(artifact, 16))
            self.assertEqual(hashlib.sha256(b"reviewed").hexdigest(),
                             station._sha256_regular_file(artifact, 16))
            with self.assertRaises(OSError):
                station._read_bounded_regular_file(artifact, 4)
            with self.assertRaises(OSError):
                station._sha256_regular_file(artifact, 4)

            alias = root / "artifact-alias.json"
            alias.symlink_to(artifact)
            with self.assertRaises(OSError):
                station._read_bounded_regular_file(alias, 16)
            with self.assertRaises(OSError):
                station._sha256_regular_file(alias, 16)

    def test_current_model_manifest_blocks_hospital_station_readiness(self):
        manifest = json.loads(
            (station.ROOT / "backend/models/model-manifest.json").read_text(encoding="utf-8")
        )
        intent = manifest["washingIntent"]
        self.assertIs(intent["startUsesMovementMagnitudeThreshold"], True)
        self.assertIs(intent["stepCreditUsesMovementMagnitudeThreshold"], True)
        self.assertIs(intent["startUsesClinicallyCalibratedMovementMagnitudeThreshold"], False)
        self.assertIs(intent["stepCreditUsesClinicallyCalibratedMovementMagnitudeThreshold"], False)
        self.assertEqual("NOT_VALIDATED", intent["validationEvidence"]["status"])
        blockers = station.hospital_readiness_blockers(manifest)
        self.assertGreaterEqual(len(blockers), 7)
        self.assertTrue(any("data.yaml" in blocker for blocker in blockers))
        self.assertTrue(any("Continuity Camera" in blocker for blocker in blockers))
        self.assertTrue(any("real rubbing intent is not independently validated" in blocker
                            for blocker in blockers))

    def test_hospital_readiness_requires_every_explicit_evidence_gate(self):
        manifest = ready_station_manifest()
        self.assertTrue(any(
            "firma Ed25519" in blocker
            for blocker in station.hospital_readiness_blockers(manifest)
        ), "los booleanos no deben habilitar el release si no hay firma verificada")
        self.assertEqual([], station.hospital_readiness_blockers(manifest, signature_error=None))

        manifest["deploymentReadiness"]["clinicalSafetyReviewPassed"] = False
        self.assertTrue(station.hospital_readiness_blockers(manifest, signature_error=None))

    def test_hospital_readiness_requires_movement_calibration_evidence(self):
        manifest = ready_station_manifest()
        manifest.pop("washingIntent", None)
        blockers = station.hospital_readiness_blockers(manifest, signature_error=None)
        self.assertTrue(any("umbrales de movimiento" in blocker for blocker in blockers))

    def test_movement_calibration_rejects_false_flags_wrong_hash_and_symlinks(self):
        manifest = ready_station_manifest()
        manifest["washingIntent"]["startUsesClinicallyCalibratedMovementMagnitudeThreshold"] = False
        self.assertFalse(station.verify_movement_intent_evidence(manifest["washingIntent"]))

        manifest = ready_station_manifest()
        manifest["washingIntent"]["validationEvidence"]["reportSha256"] = "0" * 64
        self.assertFalse(station.verify_movement_intent_evidence(manifest["washingIntent"]))

        for invalid_threshold in (True, 0, -0.1, 1.01, float("nan")):
            with self.subTest(invalid_threshold=invalid_threshold):
                manifest = ready_station_manifest()
                manifest["washingIntent"]["startMinimumNormalizedMovement"] = invalid_threshold
                self.assertFalse(station.verify_movement_intent_evidence(manifest["washingIntent"]))

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            report = root / "report.txt"
            report.write_text("synthetic evidence", encoding="utf-8")
            alias = root / "alias.txt"
            alias.symlink_to(report)
            evidence = {
                "startUsesMovementMagnitudeThreshold": True,
                "startUsesClinicallyCalibratedMovementMagnitudeThreshold": True,
                "stepCreditUsesMovementMagnitudeThreshold": True,
                "stepCreditUsesClinicallyCalibratedMovementMagnitudeThreshold": True,
                "validationEvidence": {
                    "status": "VALIDATED_FOR_HOSPITAL_PILOT",
                    "startIntentIndependentlyValidated": True,
                    "reportPath": "alias.txt",
                    "reportSha256": hashlib.sha256(report.read_bytes()).hexdigest(),
                },
            }
            self.assertFalse(station.verify_movement_intent_evidence(evidence, root))

    def test_hospital_readiness_requires_schema_version_as_exact_json_integer_one(self):
        for invalid_version in (True, 1.0, "1", 2, 4_294_967_297):
            with self.subTest(schema_version=invalid_version):
                manifest = ready_station_manifest()
                manifest["schemaVersion"] = invalid_version
                blockers = station.hospital_readiness_blockers(manifest, signature_error=None)
                self.assertTrue(any("schemaVersion 1" in blocker for blocker in blockers))

    def test_hospital_readiness_rejects_noncanonical_who_phase_order_and_classes(self):
        manifest = ready_station_manifest()
        manifest["whoProcedure"]["requiredPhases"][0] = "APLICAR_JABON"
        blockers = station.hospital_readiness_blockers(manifest, signature_error=None)
        self.assertTrue(any("orden canónico" in blocker for blocker in blockers))

        manifest = ready_station_manifest()
        manifest["active"]["modelClassNames"].remove("SIN_ESPUMA_VISIBLE_PALMA_IZQUIERDA")
        blockers = station.hospital_readiness_blockers(manifest, signature_error=None)
        self.assertTrue(any("36 clases OMS" in blocker for blocker in blockers))

        manifest = ready_station_manifest()
        manifest["active"]["modelClassNames"][0:2] = reversed(
            manifest["active"]["modelClassNames"][0:2])
        blockers = station.hospital_readiness_blockers(manifest, signature_error=None)
        self.assertTrue(any("orden canónico" in blocker for blocker in blockers))

    def test_hospital_readiness_requires_checkpoint_and_training_run_identity(self):
        manifest = ready_station_manifest()
        manifest["active"]["trainingRun"]["checkpointSha256"] = "f" * 64
        blockers = station.hospital_readiness_blockers(manifest, signature_error=None)
        self.assertTrue(any("tarea o SHA-256" in blocker for blocker in blockers))

    def test_hospital_readiness_requires_hash_bound_training_yaml_inside_project(self):
        manifest = ready_station_manifest()
        manifest["active"]["trainingRun"]["trainingDataConfigSha256"] = "f" * 64
        blockers = station.hospital_readiness_blockers(manifest, signature_error=None)
        self.assertTrue(any("data.yaml exacto" in blocker for blocker in blockers))

        manifest = ready_station_manifest()
        manifest["active"]["trainingRun"]["trainingDataConfigPath"] = "../README.md"
        blockers = station.hospital_readiness_blockers(manifest, signature_error=None)
        self.assertTrue(any("fuera del proyecto" in blocker for blocker in blockers))

        manifest = ready_station_manifest()
        manifest["active"]["trainingRun"].pop("trainingDataConfigSha256")
        blockers = station.hospital_readiness_blockers(manifest, signature_error=None)
        self.assertTrue(any("SHA-256" in blocker for blocker in blockers))

    def test_training_yaml_hash_is_not_enough_without_exact_class_order(self):
        canonical_yaml = (station.ROOT / "scripts/testdata/station-release-data.yaml").read_text(
            encoding="utf-8")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            yaml_path = root / "data.yaml"

            def verifies(content: str) -> bool:
                encoded = content.encode("utf-8")
                yaml_path.write_bytes(encoded)
                training = {
                    "trainingDataConfigPath": "data.yaml",
                    "trainingDataConfigSha256": hashlib.sha256(encoded).hexdigest(),
                }
                return station.verify_training_data_config(training, root)

            self.assertTrue(verifies(canonical_yaml))
            list_yaml = "names:\n" + "".join(
                f"  - {name}\n" for name in station.WHO_REQUIRED_MODEL_CLASSES)
            self.assertTrue(verifies(list_yaml))
            self.assertFalse(verifies(canonical_yaml.replace(
                "0: OMS_01_MOJAR_MANOS", "0: OMS_02_APLICAR_JABON")))
            self.assertFalse(verifies(canonical_yaml.replace(
                "  1: OMS_02_APLICAR_JABON", "  0: OMS_02_APLICAR_JABON")))
            self.assertFalse(verifies(canonical_yaml + "duplicate: true\nduplicate: false\n"))

    def test_release_json_parser_rejects_duplicate_keys(self):
        with self.assertRaisesRegex(ValueError, "clave JSON duplicada"):
            json.loads(
                '{"schemaVersion":1,"schemaVersion":2}',
                object_pairs_hook=station._reject_duplicate_json_keys,
            )

    def test_hospital_readiness_requires_explicit_well_formed_empty_blocker_list(self):
        manifest = ready_station_manifest()
        self.assertEqual([], station.hospital_readiness_blockers(manifest, signature_error=None))
        del manifest["deploymentReadiness"]["blockers"]
        self.assertTrue(any("lista explícita" in blocker for blocker in
                            station.hospital_readiness_blockers(manifest, signature_error=None)))
        manifest["deploymentReadiness"]["blockers"] = [None]
        self.assertTrue(any("entrada inválida" in blocker for blocker in
                            station.hospital_readiness_blockers(manifest, signature_error=None)))
        manifest["deploymentReadiness"]["blockers"] = ["   "]
        self.assertTrue(any("entrada inválida" in blocker for blocker in
                            station.hospital_readiness_blockers(manifest, signature_error=None)))

    def test_hospital_readiness_requires_hashes_for_station_runtime_artifacts(self):
        manifest = ready_station_manifest()
        self.assertEqual([], station.hospital_readiness_blockers(manifest, signature_error=None))
        del manifest["stationArtifacts"]["javaJarSha256"]
        self.assertTrue(any("javaJarSha256" in blocker for blocker in
                            station.hospital_readiness_blockers(manifest, signature_error=None)))
        manifest["stationArtifacts"]["javaJarSha256"] = "0" * 64
        del manifest["stationArtifacts"]["javaSbomSha256"]
        self.assertTrue(any("javaSbomSha256" in blocker for blocker in
                            station.hospital_readiness_blockers(manifest, signature_error=None)))
        manifest["stationArtifacts"]["javaSbomSha256"] = "4" * 64
        del manifest["stationArtifacts"]["cameraPythonSbomSha256"]
        self.assertTrue(any("cameraPythonSbomSha256" in blocker for blocker in
                            station.hospital_readiness_blockers(manifest, signature_error=None)))
        manifest["stationArtifacts"]["cameraPythonSbomSha256"] = "5" * 64
        del manifest["stationArtifacts"]["sbomGeneratorLockSha256"]
        self.assertTrue(any("sbomGeneratorLockSha256" in blocker for blocker in
                            station.hospital_readiness_blockers(manifest, signature_error=None)))
        manifest["stationArtifacts"]["sbomGeneratorLockSha256"] = "6" * 64
        del manifest["stationArtifacts"]["cameraRequirementsLockSha256"]
        self.assertTrue(any("cameraRequirementsLockSha256" in blocker for blocker in
                            station.hospital_readiness_blockers(manifest, signature_error=None)))

    def test_runtime_artifact_hashes_detect_jar_drift(self):
        with tempfile.TemporaryDirectory(prefix="handwash-station-artifacts-") as temp_dir:
            temp = Path(temp_dir)
            jar = temp / "station.jar"
            supervisor = temp / "supervisor.py"
            camera = temp / "camera.py"
            lock = temp / "requirements.lock"
            sbom = temp / "handwash-java-sbom.json"
            camera_sbom = temp / "handwash-camera-python-sbom.json"
            generator_lock = temp / "requirements-sbom-generator.lock"
            jar.write_bytes(b"jar-release")
            supervisor.write_bytes(b"supervisor-release")
            camera.write_bytes(b"camera-release")
            lock.write_text("# Interpreter baseline: CPython 3.14.4\n"
                            "# Platform baseline: macOS arm64\n"
                            "opencv-python==5.0.0.93\n", encoding="utf-8")
            sbom.write_text(
                '{"bomFormat":"CycloneDX","specVersion":"1.6","version":1,'
                '"metadata":{"component":{"type":"application","name":"test"}},'
                '"components":[{"type":"library","name":"test-dependency","version":"1.0"}]}',
                encoding="utf-8",
            )
            camera_sbom.write_text(
                '{"bomFormat":"CycloneDX","specVersion":"1.6","version":1,'
                '"components":[{"type":"library","name":"opencv-python",'
                '"version":"5.0.0.93"}]}', encoding="utf-8")
            generator_lock.write_text("cyclonedx-bom==7.5.0\n", encoding="utf-8")
            manifest = {"stationArtifacts": {
                "javaJarSha256": hashlib.sha256(jar.read_bytes()).hexdigest(),
                "javaSbomSha256": hashlib.sha256(sbom.read_bytes()).hexdigest(),
                "cameraPythonSbomSha256": hashlib.sha256(camera_sbom.read_bytes()).hexdigest(),
                "sbomGeneratorLockSha256": hashlib.sha256(generator_lock.read_bytes()).hexdigest(),
                "stationSupervisorSha256": hashlib.sha256(supervisor.read_bytes()).hexdigest(),
                "cameraProducerSha256": hashlib.sha256(camera.read_bytes()).hexdigest(),
                "cameraRequirementsLockSha256": hashlib.sha256(lock.read_bytes()).hexdigest(),
            }}
            self.assertEqual([], station.verify_station_artifact_hashes(
                manifest, java_jar=jar, java_sbom=sbom, camera_python_sbom=camera_sbom,
                supervisor=supervisor, camera_producer=camera,
                requirements_lock=lock, sbom_generator_lock=generator_lock))
            generator_lock.write_text("changed generator dependency lock\n", encoding="utf-8")
            generator_errors = station.verify_station_artifact_hashes(
                manifest, java_jar=jar, java_sbom=sbom, camera_python_sbom=camera_sbom,
                supervisor=supervisor, camera_producer=camera, requirements_lock=lock,
                sbom_generator_lock=generator_lock)
            self.assertTrue(any("sbomGeneratorLockSha256" in error for error in generator_errors))
            generator_lock.write_text("cyclonedx-bom==7.5.0\n", encoding="utf-8")
            camera_sbom.write_text(camera_sbom.read_text(encoding="utf-8").replace(
                "opencv-python", "different-package"), encoding="utf-8")
            manifest["stationArtifacts"]["cameraPythonSbomSha256"] = hashlib.sha256(
                camera_sbom.read_bytes()).hexdigest()
            camera_errors = station.verify_station_artifact_hashes(
                manifest, java_jar=jar, java_sbom=sbom, camera_python_sbom=camera_sbom,
                supervisor=supervisor, camera_producer=camera, requirements_lock=lock,
                sbom_generator_lock=generator_lock)
            self.assertTrue(any("no coincide exactamente" in error for error in camera_errors))
            camera_sbom.write_text(
                '{"bomFormat":"CycloneDX","specVersion":"1.6","version":1,'
                '"components":[{"type":"library","name":"opencv-python",'
                '"version":"5.0.0.93"}]}', encoding="utf-8")
            camera_sbom.write_text(camera_sbom.read_text(encoding="utf-8").replace(
                '"version":1', f'"version":{2**63}'), encoding="utf-8")
            manifest["stationArtifacts"]["cameraPythonSbomSha256"] = hashlib.sha256(
                camera_sbom.read_bytes()).hexdigest()
            camera_version_errors = station.verify_station_artifact_hashes(
                manifest, java_jar=jar, java_sbom=sbom, camera_python_sbom=camera_sbom,
                supervisor=supervisor, camera_producer=camera, requirements_lock=lock,
                sbom_generator_lock=generator_lock)
            self.assertTrue(any("CycloneDX 1.6 válido/no vacío" in error
                                for error in camera_version_errors))
            camera_sbom.write_text(
                '{"bomFormat":"CycloneDX","specVersion":"1.6","version":1,'
                '"components":[{"type":"library","name":"opencv-python",'
                '"version":"5.0.0.93"}]}', encoding="utf-8")
            sbom.write_text(sbom.read_text(encoding="utf-8").replace("CycloneDX", "Other"),
                            encoding="utf-8")
            manifest["stationArtifacts"]["javaSbomSha256"] = hashlib.sha256(
                sbom.read_bytes()).hexdigest()
            sbom_errors = station.verify_station_artifact_hashes(
                manifest, java_jar=jar, java_sbom=sbom, camera_python_sbom=camera_sbom,
                supervisor=supervisor,
                camera_producer=camera, requirements_lock=lock, sbom_generator_lock=generator_lock)
            self.assertTrue(any("CycloneDX 1.6" in error for error in sbom_errors))
            sbom.write_text(
                '{"bomFormat":"CycloneDX","specVersion":"1.6","version":1,'
                '"metadata":{"component":{"type":"application","name":"test"}},'
                '"components":[{"type":"library","name":"test-dependency","version":"1.0"}]}',
                encoding="utf-8",
            )
            sbom.write_text(sbom.read_text(encoding="utf-8").replace(
                '"version":1', f'"version":{2**63}'), encoding="utf-8")
            manifest["stationArtifacts"]["javaSbomSha256"] = hashlib.sha256(
                sbom.read_bytes()).hexdigest()
            java_version_errors = station.verify_station_artifact_hashes(
                manifest, java_jar=jar, java_sbom=sbom, camera_python_sbom=camera_sbom,
                supervisor=supervisor, camera_producer=camera, requirements_lock=lock,
                sbom_generator_lock=generator_lock)
            self.assertTrue(any("SBOM Java" in error for error in java_version_errors))
            sbom.write_text(
                '{"bomFormat":"CycloneDX","specVersion":"1.6","version":1,'
                '"metadata":{"component":{"type":"application","name":"test"}},'
                '"components":[{"type":"library","name":"test-dependency","version":"1.0"}]}',
                encoding="utf-8",
            )
            jar.write_bytes(b"tampered jar")
            errors = station.verify_station_artifact_hashes(
                manifest, java_jar=jar, java_sbom=sbom, camera_python_sbom=camera_sbom,
                supervisor=supervisor, camera_producer=camera,
                requirements_lock=lock, sbom_generator_lock=generator_lock)
            self.assertTrue(any("javaJarSha256" in error for error in errors))

    def test_signed_station_release_rechecks_camera_script_before_launch(self):
        with tempfile.TemporaryDirectory(prefix="handwash-release-recheck-") as temp_dir:
            temp = Path(temp_dir)
            manifest_path = temp / "model-manifest.json"
            jar = temp / "station.jar"
            supervisor = temp / "supervisor.py"
            camera = temp / "camera.py"
            lock = temp / "requirements-camera-macos-arm64.lock"
            sbom = temp / "handwash-java-sbom.json"
            camera_sbom = temp / "handwash-camera-python-sbom.json"
            generator_lock = temp / "requirements-sbom-generator.lock"
            jar.write_bytes(b"jar-release")
            supervisor.write_bytes(b"supervisor-release")
            camera.write_bytes(b"camera-release")
            lock.write_text("# Interpreter baseline: CPython 3.14.4\n"
                            "# Platform baseline: macOS arm64\n"
                            "opencv-python==5.0.0.93\n", encoding="utf-8")
            sbom.write_text(
                '{"bomFormat":"CycloneDX","specVersion":"1.6","version":1,'
                '"metadata":{"component":{"type":"application","name":"test"}},'
                '"components":[{"type":"library","name":"test-dependency","version":"1.0"}]}',
                encoding="utf-8",
            )
            camera_sbom.write_text(
                '{"bomFormat":"CycloneDX","specVersion":"1.6","version":1,'
                '"components":[{"type":"library","name":"opencv-python",'
                '"version":"5.0.0.93"}]}', encoding="utf-8")
            generator_lock.write_text("cyclonedx-bom==7.5.0\n", encoding="utf-8")
            manifest = ready_station_manifest()
            manifest["stationArtifacts"] = {
                "javaJarSha256": hashlib.sha256(jar.read_bytes()).hexdigest(),
                "javaSbomSha256": hashlib.sha256(sbom.read_bytes()).hexdigest(),
                "cameraPythonSbomSha256": hashlib.sha256(camera_sbom.read_bytes()).hexdigest(),
                "sbomGeneratorLockSha256": hashlib.sha256(generator_lock.read_bytes()).hexdigest(),
                "stationSupervisorSha256": hashlib.sha256(supervisor.read_bytes()).hexdigest(),
                "cameraProducerSha256": hashlib.sha256(camera.read_bytes()).hexdigest(),
                "cameraRequirementsLockSha256": hashlib.sha256(lock.read_bytes()).hexdigest(),
            }
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with patch.object(station, "verify_release_manifest_signature", return_value=None):
                self.assertEqual([], station.verify_signed_station_release(
                    manifest_path,
                    java_jar=jar,
                    java_sbom=sbom,
                    camera_python_sbom=camera_sbom,
                    supervisor=supervisor,
                    camera_producer=camera,
                    requirements_lock=lock,
                    sbom_generator_lock=generator_lock,
                ))
                camera.write_bytes(b"changed while Java was starting")
                blockers = station.verify_signed_station_release(
                    manifest_path,
                    java_jar=jar,
                    java_sbom=sbom,
                    camera_python_sbom=camera_sbom,
                    supervisor=supervisor,
                    camera_producer=camera,
                    requirements_lock=lock,
                    sbom_generator_lock=generator_lock,
                )

            self.assertTrue(any("cameraProducerSha256" in blocker for blocker in blockers))

    def test_camera_runtime_lock_requires_exact_versions_and_platform_metadata(self):
        with tempfile.TemporaryDirectory(prefix="handwash-runtime-lock-") as temp_dir:
            lock = Path(temp_dir) / "requirements.lock"
            lock.write_text(
                "# Interpreter baseline: CPython 3.14.4\n"
                "# Platform baseline: macOS arm64\n"
                "opencv_python==5.0.0.93\nTorch==2.14.0\n",
                encoding="utf-8",
            )
            requirements, python_version, platform_name = station.parse_camera_runtime_lock(lock)
            self.assertEqual({"opencv-python": "5.0.0.93", "torch": "2.14.0"}, requirements)
            self.assertEqual("3.14.4", python_version)
            self.assertEqual("arm64", platform_name)

            lock.write_text("opencv-python>=5.0\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "solo requisitos exactos"):
                station.parse_camera_runtime_lock(lock)

    def test_camera_runtime_verification_uses_isolated_python_and_reports_drift(self):
        with tempfile.TemporaryDirectory(prefix="handwash-runtime-check-") as temp_dir:
            lock = Path(temp_dir) / "requirements.lock"
            lock.write_text(
                "# Interpreter baseline: CPython 3.14.4\n"
                "# Platform baseline: macOS arm64\n"
                "opencv-python==5.0.0.93\n",
                encoding="utf-8",
            )
            completed = SimpleNamespace(returncode=0, stdout='["Python runtime diferente"]')
            with patch.object(station.subprocess, "run", return_value=completed) as run:
                errors = station.verify_camera_runtime(Path(sys.executable), lock)
            self.assertEqual(["Python runtime diferente"], errors)
            command = run.call_args.args[0]
            self.assertIn("-I", command)
            self.assertEqual("1", run.call_args.kwargs["env"]["PYTHONNOUSERSITE"])
            self.assertNotIn("PYTHONPATH", run.call_args.kwargs["env"])

    @unittest.skipUnless(shutil.which("openssl"), "OpenSSL requerido para probar firmas Ed25519")
    def test_release_manifest_signature_detects_manual_edits(self):
        with tempfile.TemporaryDirectory(prefix="handwash-release-signature-") as temp_dir:
            temp = Path(temp_dir)
            manifest = temp / "model-manifest.json"
            private_key = temp / "release-private.pem"
            public_key = temp / "release-public.pem"
            signature = temp / "model-manifest.json.sig"
            manifest_bytes = b'{"schemaVersion":1,"deploymentReadiness":{"status":"READY_FOR_HOSPITAL_PILOT"}}\n'
            manifest.write_bytes(manifest_bytes)

            subprocess.run(
                [shutil.which("openssl"), "genpkey", "-algorithm", "Ed25519", "-out", str(private_key)],
                check=True, capture_output=True, timeout=5,
            )
            subprocess.run(
                [shutil.which("openssl"), "pkey", "-in", str(private_key), "-pubout", "-out", str(public_key)],
                check=True, capture_output=True, timeout=5,
            )
            subprocess.run(
                [shutil.which("openssl"), "pkeyutl", "-sign", "-inkey", str(private_key),
                 "-rawin", "-in", str(manifest), "-out", str(signature)],
                check=True, capture_output=True, timeout=5,
            )

            self.assertIsNone(station.verify_release_manifest_signature(manifest, public_key, signature))

            manifest.write_bytes(manifest_bytes + b" ")
            self.assertIn("no es válida", station.verify_release_manifest_signature(
                manifest, public_key, signature
            ))
            self.assertIsNone(station.verify_release_manifest_signature(
                manifest, public_key, signature, manifest_bytes=manifest_bytes
            ), "el supervisor debe verificar los bytes ya cargados, no releer el manifiesto modificado")

    def test_release_signature_fails_closed_when_trust_key_is_not_configured(self):
        with patch.dict("os.environ", {"HANDWASH_RELEASE_PUBLIC_KEY_PATH": ""}):
            message = station.verify_release_manifest_signature(Path("model-manifest.json"))
        self.assertIn("HANDWASH_RELEASE_PUBLIC_KEY_PATH", message)

    def test_release_trust_key_must_be_outside_repository(self):
        message = station.verify_release_manifest_signature(
            Path("model-manifest.json"), station.ROOT / "README.md"
        )
        self.assertIn("fuera del repositorio", message)

    def test_supervisor_does_not_start_java_for_unsigned_ready_boolean_manifest(self):
        manifest = ready_station_manifest()
        with tempfile.TemporaryDirectory(prefix="handwash-unsigned-release-") as temp_dir:
            root = Path(temp_dir)
            manifest_path = root / "backend" / "models" / "model-manifest.json"
            manifest_path.parent.mkdir(parents=True)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            supervisor = station.StationSupervisor(station.parse_args([]))

            with patch.object(station, "ROOT", root), \
                 patch.dict("os.environ", {"HANDWASH_RELEASE_PUBLIC_KEY_PATH": ""}), \
                 patch.object(supervisor, "_start_backend") as start_backend, \
                 contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(3, supervisor.run())

            start_backend.assert_not_called()

    def test_demo_supervisor_rejects_symlinked_manifest_before_starting_processes(self):
        with tempfile.TemporaryDirectory(prefix="handwash-demo-manifest-link-") as temp_dir:
            root = Path(temp_dir)
            model_directory = root / "backend/models"
            model_directory.mkdir(parents=True)
            trusted_manifest = root / "trusted-model-manifest.json"
            trusted_manifest.write_text(json.dumps(ready_station_manifest()), encoding="utf-8")
            (model_directory / "model-manifest.json").symlink_to(trusted_manifest)

            jar = root / "station.jar"
            jar.write_bytes(b"test")
            python = root / "python"
            python.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            python.chmod(0o755)
            camera_script = root / "camera.py"
            camera_script.write_text("pass\n", encoding="utf-8")

            supervisor = station.StationSupervisor(
                station.parse_args(["--unvalidated-demo"])
            )
            supervisor.args.jar = jar
            supervisor.args.python = python
            supervisor.args.camera_script = camera_script

            with patch.object(station, "ROOT", root), \
                 patch.object(station, "verify_camera_runtime", return_value=[]), \
                 patch.object(station.shutil, "which", return_value="/usr/bin/java"), \
                 patch.object(station, "port_is_in_use", return_value=False), \
                 patch.object(supervisor, "_start_backend") as start_backend, \
                 contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(2, supervisor.run())

            start_backend.assert_not_called()

    def test_supervisor_uses_nonclinical_profile_only_for_explicit_demo(self):
        for arguments, expected_profile in (
            ([], "station"),
            (["--unvalidated-demo"], "station-demo"),
        ):
            supervisor = station.StationSupervisor(station.parse_args(arguments))
            with patch.object(station.subprocess, "Popen", return_value=Mock()) as popen, \
                 contextlib.redirect_stdout(io.StringIO()):
                supervisor._start_backend()
            self.assertEqual(expected_profile, popen.call_args.kwargs["env"]["SPRING_PROFILES_ACTIVE"])

    def test_station_backend_environment_discards_unreviewed_spring_overrides(self):
        inherited = {
            "PATH": "/usr/bin",
            "HOME": "/tmp/test-home",
            "HANDWASH_RELEASE_PUBLIC_KEY_PATH": "/etc/handwash/release-public.pem",
            "HANDWASH_OMS_INPUT_ENABLED": "true",
            "HANDWASH_RECEPTOR_CONFIDENCE_THRESHOLD": "0.0",
            "HANDWASH_SESSION_MAX_ACTIVE_SESSIONS": "128",
            "SPRING_APPLICATION_JSON": '{"server":{"address":"0.0.0.0"}}',
            "SERVER_ADDRESS": "0.0.0.0",
            "JAVA_TOOL_OPTIONS": "-javaagent:/tmp/unknown-agent.jar",
        }

        env = station.station_backend_environment(False, inherited)

        self.assertEqual("station", env["SPRING_PROFILES_ACTIVE"])
        self.assertEqual("127.0.0.1", env["SERVER_ADDRESS"])
        self.assertEqual("false", env["HANDWASH_OMS_INPUT_ENABLED"])
        self.assertEqual("true", env["HANDWASH_PRODUCER_REQUIRE_V2"])
        self.assertEqual("1", env["HANDWASH_SESSION_MAX_ACTIVE_SESSIONS"])
        self.assertEqual(inherited["HANDWASH_RELEASE_PUBLIC_KEY_PATH"],
                         env["HANDWASH_RELEASE_PUBLIC_KEY_PATH"])
        self.assertNotIn("HANDWASH_RECEPTOR_CONFIDENCE_THRESHOLD", env)
        self.assertNotIn("SPRING_APPLICATION_JSON", env)
        self.assertNotIn("JAVA_TOOL_OPTIONS", env)

    def test_supervisor_keeps_oms_disabled_in_both_station_profiles(self):
        inherited = {
            "HANDWASH_OMS_MODEL_READY": "true",
            "HANDWASH_OMS_INPUT_ENABLED": "true",
        }
        for demo, expected_profile in ((False, "station"), (True, "station-demo")):
            with self.subTest(profile=expected_profile):
                env = station.station_backend_environment(demo, inherited)
                self.assertEqual(expected_profile, env["SPRING_PROFILES_ACTIVE"])
                self.assertEqual("false", env["HANDWASH_OMS_MODEL_READY"])
                self.assertEqual("false", env["HANDWASH_OMS_INPUT_ENABLED"])

    def test_only_verified_hospital_release_enables_oms_in_child_environment(self):
        env = station.station_backend_environment(False, {}, release_verified=True)
        self.assertEqual("station", env["SPRING_PROFILES_ACTIVE"])
        self.assertEqual("true", env["HANDWASH_OMS_MODEL_READY"])
        self.assertEqual("true", env["HANDWASH_OMS_INPUT_ENABLED"])
        with self.assertRaisesRegex(ValueError, "demo no clínica"):
            station.station_backend_environment(True, {}, release_verified=True)

    def test_camera_environment_discards_session_model_threshold_and_proxy_overrides(self):
        inherited = {
            "PATH": "/usr/bin",
            "PYTHONHOME": "/tmp/foreign-python",
            "PYTHONPATH": "/tmp/injected-modules",
            "PYTHONUSERBASE": "/tmp/user-site",
            "HANDWASH_SESSION_TOKEN": "must-not-be-inherited",
            "HANDWASH_CLASSIFIER_FALLBACK": "0",
            "HANDWASH_YOLO_CLASSIFIER_MODEL": "/tmp/unreviewed.pt",
            "HANDWASH_YOLO_HAND_CROP_CONFIDENCE": "0.0",
            "HANDWASH_MAX_DETECTION_GAP_MS": "60000",
            "HTTP_PROXY": "http://proxy.invalid:3128",
            "https_proxy": "http://proxy.invalid:3128",
        }

        env = station.camera_child_environment("ABCDE-12345", inherited)

        self.assertEqual("/usr/bin", env["PATH"])
        self.assertEqual("1", env["PYTHONNOUSERSITE"])
        self.assertEqual("1", env["PYTHONUNBUFFERED"])
        self.assertEqual("127.0.0.1", env["HANDWASH_CAMERA_STREAM_HOST"])
        self.assertEqual("8091", env["HANDWASH_CAMERA_STREAM_PORT"])
        self.assertEqual("ABCDE-12345", env["HANDWASH_PAIRING_CODE"])
        self.assertEqual("127.0.0.1,localhost,::1", env["NO_PROXY"])
        self.assertNotIn("PYTHONHOME", env)
        self.assertNotIn("PYTHONPATH", env)
        self.assertNotIn("HANDWASH_SESSION_TOKEN", env)
        self.assertEqual("0", env["HANDWASH_CLASSIFIER_FALLBACK"])
        self.assertNotIn("HANDWASH_YOLO_CLASSIFIER_MODEL", env)
        self.assertNotIn("HANDWASH_YOLO_HAND_CROP_CONFIDENCE", env)
        self.assertNotIn("HANDWASH_MAX_DETECTION_GAP_MS", env)
        self.assertNotIn("HTTP_PROXY", env)
        self.assertNotIn("https_proxy", env)

    def test_camera_environment_cannot_force_enable_classifier_or_override_protocol(self):
        env = station.camera_child_environment(None, {
            "HANDWASH_CLASSIFIER_FALLBACK": "true",
            "HANDWASH_PROTOCOL": "DOMESTICO",
            "HANDWASH_PAIRING_CODE": "INJECTED-CODE",
        })
        self.assertNotIn("HANDWASH_CLASSIFIER_FALLBACK", env)
        self.assertNotIn("HANDWASH_PROTOCOL", env)
        self.assertNotIn("HANDWASH_PAIRING_CODE", env)

    def test_runtime_paths_are_normalized_before_child_working_directory_changes(self):
        args = station.parse_args([
            "--jar", "./relative station.jar",
            "--python", "./relative python",
            "--camera-script", "./relative camera.py",
        ])

        self.assertEqual(Path("./relative station.jar").resolve(), args.jar)
        self.assertEqual(Path("./relative python").absolute(), args.python)
        self.assertEqual(Path("./relative camera.py").resolve(), args.camera_script)
        self.assertTrue(args.jar.is_absolute())
        self.assertTrue(args.python.is_absolute())
        self.assertTrue(args.camera_script.is_absolute())

    @unittest.skipUnless((station.ROOT / ".venv/bin/python").is_symlink(), "venv local no disponible")
    def test_supervisor_preserves_virtualenv_python_symlink(self):
        args = station.parse_args([])
        expected = station.ROOT / ".venv/bin/python"
        self.assertEqual(expected, args.python)
        self.assertTrue(args.python.is_symlink())

    def test_extracts_pairing_code_from_camera_startup_line(self):
        self.assertEqual(
            "AB234-CDEFG",
            station.pairing_code_from_output("Código para vincular el dashboard: AB234-CDEFG\n"),
        )
        self.assertIsNone(station.pairing_code_from_output("inferencia YOLO lista"))

    def test_camera_output_pipe_keeps_draining_after_terminal_sink_breaks(self):
        supervisor = station.StationSupervisor(station.parse_args([]))
        camera_output = io.StringIO(
            "inferencia YOLO lista\n"
            "Código para vincular el dashboard: AB234-CDEFG\n"
            "continuación del proceso\n"
        )

        with patch("builtins.print", side_effect=BrokenPipeError):
            supervisor._camera_output(camera_output)

        self.assertEqual("AB234-CDEFG", supervisor._get_pairing_code())
        self.assertTrue(camera_output.closed)

    def test_camera_normal_exit_starts_a_new_session(self):
        self.assertEqual(
            station.RestartDecision.NEW_SESSION,
            station.camera_exit_decision(
                0, java_alive=True, pairing_code_available=True, retries_used=0, retry_limit=3
            ),
        )

    def test_camera_crash_retries_only_with_live_java_and_pairing_code(self):
        retry = station.camera_exit_decision(
            1, java_alive=True, pairing_code_available=True, retries_used=1, retry_limit=3
        )
        no_code = station.camera_exit_decision(
            1, java_alive=True, pairing_code_available=False, retries_used=0, retry_limit=3
        )
        java_down = station.camera_exit_decision(
            0, java_alive=False, pairing_code_available=True, retries_used=0, retry_limit=3
        )
        exhausted = station.camera_exit_decision(
            1, java_alive=True, pairing_code_available=True, retries_used=3, retry_limit=3
        )
        self.assertEqual(station.RestartDecision.RETRY_SAME_SESSION, retry)
        self.assertEqual(station.RestartDecision.STOP, no_code)
        self.assertEqual(station.RestartDecision.STOP, java_down)
        self.assertEqual(station.RestartDecision.STOP, exhausted)

    def test_backend_exit_during_retry_backoff_cancels_camera_restart(self):
        supervisor = station.StationSupervisor(station.parse_args([]))
        java_process = SimpleNamespace(poll=Mock(side_effect=[None, 1]))
        supervisor._java_process = java_process
        with patch.object(supervisor.stop_requested, "wait", return_value=False) as wait:
            self.assertFalse(supervisor._wait_while_backend_alive(60.0))
        wait.assert_called_once()
        self.assertEqual(2, java_process.poll.call_count)

    def test_backend_must_still_be_alive_at_the_end_of_restart_delay(self):
        supervisor = station.StationSupervisor(station.parse_args([]))
        java_process = SimpleNamespace(poll=Mock(return_value=None))
        supervisor._java_process = java_process
        self.assertTrue(supervisor._wait_while_backend_alive(0.0))

        supervisor.stop_requested.set()
        self.assertFalse(supervisor._wait_while_backend_alive(0.0))

    def test_retry_delay_parser_checks_bounds(self):
        self.assertEqual((2.0, 5.0, 15.0), station.parse_retry_delays("2,5,15"))
        with self.assertRaises(argparse.ArgumentTypeError):
            station.parse_retry_delays("-1,2")
        with self.assertRaises(argparse.ArgumentTypeError):
            station.parse_retry_delays("nan,2")

    def test_completed_session_clears_old_pairing_code(self):
        supervisor = station.StationSupervisor(station.parse_args([]))
        supervisor._set_pairing_code("ABCDE-12345")
        supervisor._clear_pairing_code()
        self.assertIsNone(supervisor._get_pairing_code())

    def test_station_identity_requires_expected_protocol_dto_shape(self):
        step_times = {
            "PASO_1_PALMAS": 5_000,
            "PASO_2_DORSOS": 5_000,
            "PASO_3_INTERDIGITALES": 5_000,
            "PASO_4_NUDILLOS": 5_000,
            "PASO_5_PULGAR": 5_000,
            "PASO_6_PUNTA_DE_DEDOS": 5_000,
            "PASO_7_CIRCULARES": 5_000,
        }

        def protocol(name, total_ms):
            return {
                "nombre": name,
                "duracion_total_ms": total_ms,
                "tiempos_por_paso": dict(step_times),
                "origen_tiempos_por_paso": "REGLA_DEL_PROYECTO_NO_UMBRAL_OMS",
                "metodo_objetivo": "duracion_por_paso",
                "alcance_evaluacion": "friccion_parcial",
                "procedimiento_completo_validado": False,
                "acciones_no_detectadas": ["Mojar manos", "Aplicar jabón"],
            }

        station_json = json.dumps({
            "CLINICO_QUIRURGICO": protocol("Clínico", 60_000),
            "DOMESTICO": protocol("Doméstico", 40_000),
        }).encode()
        other_json = json.dumps({"status": "ok"}).encode()
        camel_case_json = json.dumps({
            "CLINICO_QUIRURGICO": {
                "procedimientoCompletoValidado": False,
                "tiempos_por_paso": step_times,
            },
            "DOMESTICO": protocol("Doméstico", 40_000),
        }).encode()
        incomplete_json = json.dumps({
            "CLINICO_QUIRURGICO": protocol("Clínico", 60_000),
        }).encode()

        class Response:
            def __init__(self, payload, status=200):
                self.payload = payload
                self.status = status

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self, _limit):
                return self.payload

        health_json = json.dumps({"status": "UP"}).encode()
        pilot_status_json = json.dumps({
            "mode": "HOSPITAL_PILOT",
            "clinicalDecisionAllowed": False,
            "notice": "Piloto supervisado; no es producción clínica.",
        }).encode()
        with patch.object(
            station, "urlopen", side_effect=[
                Response(health_json), Response(pilot_status_json), Response(station_json)
            ]
        ):
            self.assertTrue(station.backend_matches_station("http://127.0.0.1:8080"))

        demo_status_json = json.dumps({
            "mode": "NON_CLINICAL_DEMO",
            "clinicalDecisionAllowed": False,
            "notice": "Uso interno; no clínico.",
        }).encode()
        with patch.object(
            station, "urlopen", side_effect=[
                Response(health_json), Response(demo_status_json), Response(station_json)
            ]
        ):
            self.assertFalse(
                station.backend_matches_station("http://127.0.0.1:8080"),
                "el modo demo no debe pasar por el preflight hospitalario",
            )
        with patch.object(
            station, "urlopen", side_effect=[
                Response(health_json), Response(demo_status_json), Response(station_json)
            ]
        ):
            self.assertTrue(station.backend_matches_station(
                "http://127.0.0.1:8080", expected_mode="NON_CLINICAL_DEMO"
            ))

        for unsafe_status in (
            {"mode": "DEVELOPMENT", "clinicalDecisionAllowed": False, "notice": "dev"},
            {"mode": "HOSPITAL_PILOT", "clinicalDecisionAllowed": True, "notice": "approved"},
            {"mode": "HOSPITAL_PILOT", "clinicalDecisionAllowed": False, "notice": "  "},
        ):
            with self.subTest(deployment_status=unsafe_status), patch.object(
                station, "urlopen", side_effect=[
                    Response(health_json),
                    Response(json.dumps(unsafe_status).encode()),
                ]
            ):
                self.assertFalse(station.backend_matches_station("http://127.0.0.1:8080"))

        with patch.object(
            station, "urlopen", side_effect=[
                Response(health_json), Response(pilot_status_json), Response(other_json)
            ]
        ):
            self.assertFalse(station.backend_matches_station("http://127.0.0.1:8080"))
        with patch.object(
            station, "urlopen", side_effect=[
                Response(health_json), Response(pilot_status_json), Response(camel_case_json)
            ]
        ):
            self.assertFalse(station.backend_matches_station("http://127.0.0.1:8080"))
        with patch.object(
            station, "urlopen", side_effect=[
                Response(health_json), Response(pilot_status_json), Response(incomplete_json)
            ]
        ):
            self.assertFalse(station.backend_matches_station("http://127.0.0.1:8080"))

        malformed_steps = json.loads(station_json)
        del malformed_steps["DOMESTICO"]["tiempos_por_paso"]["PASO_7_CIRCULARES"]
        with patch.object(
            station,
            "urlopen",
            side_effect=[
                Response(health_json), Response(pilot_status_json),
                Response(json.dumps(malformed_steps).encode()),
            ],
        ):
            self.assertFalse(station.backend_matches_station("http://127.0.0.1:8080"))

        with patch.object(
            station, "urlopen", return_value=Response(json.dumps({"status": "DOWN"}).encode())
        ) as health_down:
            self.assertFalse(station.backend_matches_station("http://127.0.0.1:8080"))
            health_down.assert_called_once_with(
                "http://127.0.0.1:8080/actuator/health", timeout=0.7
            )

        with patch.object(station, "urlopen", return_value=Response(b"not-json")):
            self.assertFalse(station.backend_matches_station("http://127.0.0.1:8080"))

        with patch.object(
            station, "urlopen", return_value=Response(health_json, status=503)
        ):
            self.assertFalse(station.backend_matches_station("http://127.0.0.1:8080"))

    def test_supervisor_rejects_stream_exposure_and_session_override(self):
        for args in (
            ["--camera-arg=--stream-host=0.0.0.0"],
            ["--camera-arg=--pairing-code=ABCDE-12345"],
            ["--camera-arg=--no-hand-pose"],
            ["--camera-arg=--hand-presence-warmup-ms=0"],
        ):
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    station.parse_args(args)

    def test_supervisor_accepts_limited_hardware_and_display_tuning(self):
        args = station.parse_args([
            "--camera-arg=--device=mps",
            "--camera-arg=--stream-fps=20",
        ])
        self.assertEqual(["--device=mps", "--stream-fps=20"], args.camera_arg)

    def test_supervisor_locks_three_second_hand_presence_warmup(self):
        supervisor = station.StationSupervisor(station.parse_args([
            "--unvalidated-demo", "--camera-arg=--stream-fps=20",
        ]))
        supervisor._get_pairing_code = Mock(return_value=None)
        with patch.object(station, "camera_child_environment", return_value={"PATH": "/usr/bin"}), \
             patch.object(station.subprocess, "Popen", return_value=Mock(stdout=io.StringIO(""))) as start_camera, \
             contextlib.redirect_stdout(io.StringIO()):
            supervisor._start_camera()

        command = start_camera.call_args.args[0]
        warmup_index = command.index("--hand-presence-warmup-ms")
        self.assertEqual(
            ["--hand-presence-warmup-ms", "3000"],
            command[warmup_index:warmup_index + 2],
        )
        self.assertIn("--stream-fps=20", command)

    def test_supervisor_rejects_resource_values_outside_safe_ranges(self):
        for camera_arg in (
            "--stream-width=100000",
            "--stream-fps=nan",
            "--stream-jpeg-quality=100",
            "--device=invalid",
        ):
            with self.subTest(camera_arg=camera_arg), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    station.parse_args([f"--camera-arg={camera_arg}"])

    def test_camera_group_cleanup_still_targets_descendants_after_worker_exit(self):
        process = SimpleNamespace(pid=12345, poll=lambda: 1, wait=Mock())
        with patch.object(station.os, "killpg", side_effect=ProcessLookupError) as kill_group:
            station.StationSupervisor._terminate_group(
                process, graceful_signal=station.signal.SIGTERM, timeout=0.1
            )
        kill_group.assert_called_once_with(12345, station.signal.SIGTERM)


if __name__ == "__main__":
    unittest.main()
