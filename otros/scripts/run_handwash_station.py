#!/usr/bin/env python3
"""Supervise the single-Mac hand-wash station without resuming lost sessions.

Java owns session state. A failed YOLO process may re-pair to its existing
session while Java is alive; a Java restart is terminal because it loses that
in-memory session. Normal camera completion starts a fresh session for the next
wash. No credentials or media are written to disk by this supervisor.
"""

from __future__ import annotations

import argparse
import errno
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
from typing import TextIO
from urllib.error import URLError
from urllib.request import urlopen

import yaml
from yaml.events import AliasEvent


ROOT = Path(__file__).resolve().parents[1]
PAIRING_CODE_PATTERN = re.compile(r"Código para vincular el dashboard:\s*([A-Z0-9]{5}-[A-Z0-9]{5})", re.I)
EXPECTED_STATION_PROTOCOLS = {"CLINICO_QUIRURGICO", "DOMESTICO"}
EXPECTED_STATION_STEPS = {
    "PASO_1_PALMAS",
    "PASO_2_DORSOS",
    "PASO_3_INTERDIGITALES",
    "PASO_4_NUDILLOS",
    "PASO_5_PULGAR",
    "PASO_6_PUNTA_DE_DEDOS",
    "PASO_7_CIRCULARES",
}
WHO_REQUIRED_PHASES = (
    "MOJAR_MANOS",
    "APLICAR_JABON",
    "FROTAR_PALMAS",
    "FROTAR_DORSOS",
    "FROTAR_ENTRE_DEDOS",
    "FROTAR_DORSO_DE_DEDOS",
    "FROTAR_PULGARES",
    "FROTAR_PUNTAS_DE_DEDOS",
    "ENJUAGAR_MANOS",
    "SECAR_TOALLA_DESECHABLE",
    "CERRAR_GRIFO_CON_TOALLA",
)
WHO_SOAP_REGIONS = (
    "PALMA_IZQUIERDA", "PALMA_DERECHA", "DORSO_IZQUIERDO", "DORSO_DERECHO",
    "INTERDIGITALES_IZQUIERDA", "INTERDIGITALES_DERECHA", "DORSO_DE_DEDOS_IZQUIERDO",
    "DORSO_DE_DEDOS_DERECHO", "PULGAR_IZQUIERDO", "PULGAR_DERECHO",
    "PUNTAS_DE_DEDOS_IZQUIERDA", "PUNTAS_DE_DEDOS_DERECHA",
)
WHO_REQUIRED_MODEL_CLASSES = (
    *(f"OMS_{index:02d}_{phase}" for index, phase in enumerate(WHO_REQUIRED_PHASES, start=1)),
    "OMS_CONTACTO_RIESGO",
    *(f"{prefix}_{region}" for region in WHO_SOAP_REGIONS
      for prefix in ("ESPUMA_VISIBLE", "SIN_ESPUMA_VISIBLE")),
)
CAMERA_RUNTIME_LOCK = ROOT / "requirements-camera-macos-arm64.lock"
PROTOCOL_RESPONSE_FIELDS = {
    "nombre",
    "duracion_total_ms",
    "tiempos_por_paso",
    "origen_tiempos_por_paso",
    "metodo_objetivo",
    "alcance_evaluacion",
    "procedimiento_completo_validado",
    "acciones_no_detectadas",
}
SAFE_CAMERA_OPTIONS = {
    "--camera-index", "--device", "--precision", "--stream-width",
    "--stream-fps", "--stream-jpeg-quality",
}
LOCKED_HAND_PRESENCE_WARMUP_MS = 3000
STATION_ARTIFACT_HASH_FIELDS = (
    "javaJarSha256",
    "javaSbomSha256",
    "cameraPythonSbomSha256",
    "sbomGeneratorLockSha256",
    "stationSupervisorSha256",
    "cameraProducerSha256",
    "cameraRequirementsLockSha256",
)
SHA256_PATTERN = re.compile(r"[0-9a-fA-F]{64}\Z")
MAX_RELEASE_TRAINING_CONFIG_BYTES = 2 * 1024 * 1024
MAX_MOVEMENT_INTENT_EVIDENCE_BYTES = 2 * 1024 * 1024
MAX_RELEASE_JAVA_SBOM_BYTES = 32 * 1024 * 1024
MAX_RELEASE_CAMERA_PYTHON_SBOM_BYTES = 32 * 1024 * 1024
LOCKED_REQUIREMENT_PATTERN = re.compile(r"([A-Za-z0-9][A-Za-z0-9_.-]*)==([A-Za-z0-9][A-Za-z0-9.+!-]*)\Z")
PYTHON_BASELINE_PATTERN = re.compile(r"# Interpreter baseline: CPython ([0-9]+\.[0-9]+\.[0-9]+)\Z")
PLATFORM_BASELINE = "# Platform baseline: macOS arm64"
SAFE_CHILD_ENVIRONMENT_KEYS = ("PATH", "HOME", "TMPDIR", "TEMP", "LANG", "LC_ALL", "TZ")


class _ReleaseYamlLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects aliases and duplicate keys in signed configs."""

    def compose_node(self, parent, index):
        if self.check_event(AliasEvent):
            raise yaml.YAMLError("No se permiten aliases en el data.yaml de release.")
        return super().compose_node(parent, index)


def _construct_unique_yaml_mapping(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as error:
            raise yaml.YAMLError("El data.yaml contiene una clave no válida.") from error
        if duplicate:
            raise yaml.YAMLError("El data.yaml contiene una clave duplicada.")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_ReleaseYamlLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_yaml_mapping
)


def parse_retry_delays(value: str) -> tuple[float, ...]:
    try:
        delays = tuple(float(item.strip()) for item in value.split(","))
    except ValueError as error:
        raise argparse.ArgumentTypeError("usa segundos separados por coma, por ejemplo 2,5,15") from error
    if not delays or any(not math.isfinite(delay) or delay < 0 or delay > 300 for delay in delays):
        raise argparse.ArgumentTypeError("cada espera debe estar entre 0 y 300 segundos")
    return delays


def _reject_duplicate_json_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    parsed: dict[str, object] = {}
    for key, value in pairs:
        if key in parsed:
            raise ValueError(f"El manifiesto contiene la clave JSON duplicada: {key}.")
        parsed[key] = value
    return parsed


def _open_regular_file_no_follow(path: Path, maximum_bytes: int) -> tuple[int, os.stat_result]:
    """Open a bounded regular file without following a last-component symlink."""
    if maximum_bytes < 1:
        raise ValueError("El límite de lectura debe ser positivo.")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    descriptor = os.open(path, flags)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size <= 0:
            raise OSError("El artefacto no es un archivo regular no vacío.")
        if metadata.st_size > maximum_bytes:
            raise OSError("El artefacto excede el tamaño permitido.")
        return descriptor, metadata
    except BaseException:
        os.close(descriptor)
        raise


def _file_identity_unchanged(before: os.stat_result, after: os.stat_result) -> bool:
    return (before.st_dev == after.st_dev and before.st_ino == after.st_ino
            and before.st_size == after.st_size
            and getattr(before, "st_mtime_ns", None) == getattr(after, "st_mtime_ns", None)
            and getattr(before, "st_ctime_ns", None) == getattr(after, "st_ctime_ns", None))


def _read_bounded_regular_file(path: Path, maximum_bytes: int) -> bytes:
    """Read one stable, bounded regular file without a size-check/read race."""
    descriptor, before = _open_regular_file_no_follow(path, maximum_bytes)
    try:
        content = bytearray()
        while len(content) <= maximum_bytes:
            chunk = os.read(descriptor, min(64 * 1024, maximum_bytes + 1 - len(content)))
            if not chunk:
                break
            content.extend(chunk)
        after = os.fstat(descriptor)
        if (len(content) > maximum_bytes or len(content) != before.st_size
            or not _file_identity_unchanged(before, after)):
            raise OSError("El archivo cambió o excedió el límite durante la lectura.")
        return bytes(content)
    finally:
        os.close(descriptor)


def _sha256_regular_file(path: Path, maximum_bytes: int) -> str:
    """Hash a stable bounded regular file without following a replacement symlink."""
    descriptor, before = _open_regular_file_no_follow(path, maximum_bytes)
    try:
        digest = hashlib.sha256()
        total_bytes = 0
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            total_bytes += len(chunk)
            if total_bytes > maximum_bytes:
                raise OSError("El artefacto creció más allá del límite durante el hash.")
            digest.update(chunk)
        after = os.fstat(descriptor)
        if (total_bytes != before.st_size or not _file_identity_unchanged(before, after)):
            raise OSError("El artefacto cambió durante el cálculo de SHA-256.")
        return digest.hexdigest()
    finally:
        os.close(descriptor)


def parse_camera_runtime_lock(lock_path: Path = CAMERA_RUNTIME_LOCK) -> tuple[dict[str, str], str, str]:
    """Parse the small, exact dependency lock and its target interpreter/platform."""
    try:
        lock_bytes = _read_bounded_regular_file(lock_path, 128 * 1024)
        content = lock_bytes.decode("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ValueError(f"No se pudo leer el lock de cámara: {error}") from error

    requirements: dict[str, str] = {}
    python_version: str | None = None
    platform_name: str | None = None
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            match = PYTHON_BASELINE_PATTERN.fullmatch(line)
            if match:
                python_version = match.group(1)
            if line == PLATFORM_BASELINE:
                platform_name = "arm64"
            continue
        match = LOCKED_REQUIREMENT_PATTERN.fullmatch(line)
        if not match:
            raise ValueError("El lock debe contener solo requisitos exactos name==version.")
        name = re.sub(r"[-_.]+", "-", match.group(1)).lower()
        if name in requirements:
            raise ValueError(f"El lock contiene una dependencia duplicada: {name}.")
        requirements[name] = match.group(2)

    if not requirements or python_version is None or platform_name is None:
        raise ValueError("El lock debe declarar dependencias, versión de Python y plataforma.")
    return requirements, python_version, platform_name


def verify_camera_runtime(python_executable: Path,
                          lock_path: Path = CAMERA_RUNTIME_LOCK) -> list[str]:
    """Fail closed if the selected interpreter or any locked package drifted."""
    try:
        requirements, python_version, platform_name = parse_camera_runtime_lock(lock_path)
    except ValueError as error:
        return [str(error)]

    checker = (
        "import importlib.metadata as metadata, json, platform, sys\n"
        "expected=json.loads(sys.argv[1]); target=json.loads(sys.argv[2]); errors=[]\n"
        "if platform.python_version() != target['python']:\n"
        " errors.append(f\"Python {platform.python_version()} != {target['python']}\")\n"
        "if platform.system() != 'Darwin' or platform.machine() != target['machine']:\n"
        " errors.append(f\"Plataforma {platform.system()} {platform.machine()} != macOS {target['machine']}\")\n"
        "for name, version in expected.items():\n"
        " try: actual=metadata.version(name)\n"
        " except metadata.PackageNotFoundError: actual=None\n"
        " if actual != version: errors.append(f\"{name} {actual or 'ausente'} != {version}\")\n"
        "print(json.dumps(errors, ensure_ascii=False))\n"
    )
    try:
        result = subprocess.run(
            [str(python_executable), "-I", "-c", checker,
             json.dumps(requirements, separators=(",", ":")),
             json.dumps({"python": python_version, "machine": platform_name})],
            cwd=ROOT,
            env={"PATH": os.environ.get("PATH", ""), "PYTHONNOUSERSITE": "1"},
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except FileNotFoundError:
        return ["No se encontró el intérprete Python seleccionado."]
    except subprocess.TimeoutExpired:
        return ["La comprobación de versiones del runtime superó 15 segundos."]
    except OSError:
        return ["No se pudo iniciar el intérprete Python seleccionado."]
    if result.returncode != 0:
        detail = result.stderr.strip()[-500:] if result.stderr else "sin diagnóstico del intérprete"
        return [f"Falló la verificación del runtime Python de la cámara: {detail}"]
    try:
        errors = json.loads(result.stdout)
    except json.JSONDecodeError:
        return ["El verificador del runtime devolvió una respuesta inválida."]
    if not isinstance(errors, list) or any(not isinstance(error, str) for error in errors):
        return ["El verificador del runtime devolvió una respuesta inválida."]
    return errors


def station_backend_environment(unvalidated_demo: bool,
                                inherited: dict[str, str] | None = None,
                                *, release_verified: bool = False) -> dict[str, str]:
    """Give Spring only host basics, its external trust key, and fixed station policy."""
    if unvalidated_demo and release_verified:
        raise ValueError("Una demo no clínica no puede recibir autorización hospitalaria.")
    source = os.environ if inherited is None else inherited
    env = {key: source[key] for key in SAFE_CHILD_ENVIRONMENT_KEYS if key in source}
    release_key = source.get("HANDWASH_RELEASE_PUBLIC_KEY_PATH")
    if release_key:
        env["HANDWASH_RELEASE_PUBLIC_KEY_PATH"] = release_key
    env.update({
        "SPRING_PROFILES_ACTIVE": "station-demo" if unvalidated_demo else "station",
        "SERVER_PORT": "8080",
        "SERVER_ADDRESS": "127.0.0.1",
        "HANDWASH_CORS_ALLOWED_ORIGINS": "http://127.0.0.1:8080,http://localhost:8080",
        # Only run() may pass true, after the signed readiness gate succeeds.
        "HANDWASH_OMS_MODEL_READY": str(release_verified).lower(),
        "HANDWASH_OMS_INPUT_ENABLED": str(release_verified).lower(),
        "HANDWASH_INFERENCE_API_ENABLED": "false",
        "HANDWASH_PRODUCER_REQUIRE_V2": "true",
        "HANDWASH_SESSION_ACCESS_REQUIRED": "true",
        "HANDWASH_SESSION_MAX_ACTIVE_SESSIONS": "1",
    })
    return env


def camera_child_environment(pairing_code: str | None,
                             inherited: dict[str, str] | None = None) -> dict[str, str]:
    """Start camera with no inherited model/threshold/session/proxy overrides."""
    source = os.environ if inherited is None else inherited
    env = {key: source[key] for key in SAFE_CHILD_ENVIRONMENT_KEYS if key in source}
    env.update({
        "PYTHONNOUSERSITE": "1",
        "PYTHONUNBUFFERED": "1",
        "HANDWASH_CAMERA_STREAM_HOST": "127.0.0.1",
        "HANDWASH_CAMERA_STREAM_PORT": "8091",
        # Both requests and urllib must keep device credentials on loopback.
        "NO_PROXY": "127.0.0.1,localhost,::1",
        "no_proxy": "127.0.0.1,localhost,::1",
    })
    if pairing_code:
        env["HANDWASH_PAIRING_CODE"] = pairing_code
    # This documented one-way emergency switch may disable the auxiliary
    # classifier, but an inherited environment can never force-enable it.
    fallback = source.get("HANDWASH_CLASSIFIER_FALLBACK", "").strip().casefold()
    if fallback in {"0", "false", "no", "off"}:
        env["HANDWASH_CLASSIFIER_FALLBACK"] = "0"
    return env


def validate_camera_option(option: str, value: str) -> bool:
    try:
        if option == "--camera-index":
            return 0 <= int(value) <= 64
        if option == "--device":
            return value in {"auto", "cpu", "mps", "cuda"}
        if option == "--precision":
            return value in {"fp16", "fp32"}
        if option == "--stream-width":
            return 320 <= int(value) <= 1920
        if option == "--stream-fps":
            fps = float(value)
            return math.isfinite(fps) and 5 <= fps <= 30
        if option == "--stream-jpeg-quality":
            return 50 <= int(value) <= 95
    except ValueError:
        return False
    return False


def pairing_code_from_output(line: str) -> str | None:
    match = PAIRING_CODE_PATTERN.search(line)
    return match.group(1).upper() if match else None


def port_is_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        result = listener.connect_ex((host, port))
    if result == 0:
        return True
    if result in {errno.ECONNREFUSED, errno.EHOSTUNREACH, errno.ENETUNREACH, errno.ETIMEDOUT}:
        return False
    raise OSError(result, f"No se pudo comprobar el puerto {host}:{port}")


def backend_matches_station(
    url: str,
    timeout: float = 0.7,
    expected_mode: str = "HOSPITAL_PILOT",
) -> bool:
    """Require healthy dependencies, the expected runtime mode and protocol catalog.

    The response is the public ProtocolResponse DTO. In particular, Jackson
    serializes ``procedimientoCompletoValidado`` as the explicit wire name
    ``procedimiento_completo_validado``; accepting a camelCase lookalike would
    let a stale or unrelated API appear ready while the real station always
    timed out. Actuator health is checked first so a database or other critical
    dependency failure cannot be hidden by an otherwise responsive API. The
    runtime-mode endpoint also prevents starting camera inference against a
    development/demo backend when the selected station profile is different.
    """
    try:
        base_url = url.rstrip("/")
        with urlopen(f"{base_url}/actuator/health", timeout=timeout) as response:
            if response.status != 200:
                return False
            health_payload = response.read(4_096).decode("utf-8")
        health = json.loads(health_payload)
        if not isinstance(health, dict) or health.get("status") != "UP":
            return False

        with urlopen(f"{base_url}/api/v1/deployment/status", timeout=timeout) as response:
            if response.status != 200:
                return False
            deployment_payload = response.read(4_096).decode("utf-8")
        deployment = json.loads(deployment_payload)
        if (not isinstance(deployment, dict)
            or deployment.get("mode") != expected_mode
            or deployment.get("clinicalDecisionAllowed") is not False
            or not isinstance(deployment.get("notice"), str)
            or not deployment["notice"].strip()):
            return False

        with urlopen(f"{base_url}/api/v1/protocols", timeout=timeout) as response:
            if response.status != 200:
                return False
            payload = response.read(256_000).decode("utf-8")
        catalog = json.loads(payload)
        if not isinstance(catalog, dict):
            return False
        for protocol_name in EXPECTED_STATION_PROTOCOLS:
            protocol = catalog.get(protocol_name)
            if not isinstance(protocol, dict) or not PROTOCOL_RESPONSE_FIELDS.issubset(protocol):
                return False
            if not isinstance(protocol["nombre"], str) or not protocol["nombre"].strip():
                return False
            if (not isinstance(protocol["origen_tiempos_por_paso"], str)
                or not protocol["origen_tiempos_por_paso"].strip()
                or not isinstance(protocol["metodo_objetivo"], str)
                or not protocol["metodo_objetivo"].strip()
                or not isinstance(protocol["alcance_evaluacion"], str)
                or not protocol["alcance_evaluacion"].strip()):
                return False
            total_ms = protocol["duracion_total_ms"]
            if isinstance(total_ms, bool) or not isinstance(total_ms, int) or total_ms <= 0:
                return False
            if not isinstance(protocol["procedimiento_completo_validado"], bool):
                return False
            actions = protocol["acciones_no_detectadas"]
            if not isinstance(actions, list) or any(not isinstance(action, str) for action in actions):
                return False
            step_times = protocol["tiempos_por_paso"]
            if not isinstance(step_times, dict) or set(step_times) != EXPECTED_STATION_STEPS:
                return False
            if any(
                isinstance(duration, bool) or not isinstance(duration, int) or duration <= 0
                for duration in step_times.values()
            ):
                return False
        return True
    except (OSError, URLError, ValueError, UnicodeDecodeError):
        return False


class RestartDecision:
    NEW_SESSION = "new_session"
    RETRY_SAME_SESSION = "retry_same_session"
    STOP = "stop"


def camera_exit_decision(
    return_code: int,
    *,
    java_alive: bool,
    pairing_code_available: bool,
    retries_used: int,
    retry_limit: int,
) -> str:
    if not java_alive:
        return RestartDecision.STOP
    if return_code == 0:
        return RestartDecision.NEW_SESSION
    if not pairing_code_available or retries_used >= retry_limit:
        return RestartDecision.STOP
    return RestartDecision.RETRY_SAME_SESSION


def verify_training_data_config(training: object, project_root: Path | None = None) -> bool:
    """Require a bounded, hash-matching YAML whose class IDs match release taxonomy."""
    if not isinstance(training, dict):
        return False
    relative_value = training.get("trainingDataConfigPath")
    expected_digest = training.get("trainingDataConfigSha256")
    if (not isinstance(relative_value, str) or not relative_value.strip()
        or not isinstance(expected_digest, str)
        or not SHA256_PATTERN.fullmatch(expected_digest)):
        return False
    try:
        relative_path = Path(relative_value)
        if relative_path.is_absolute():
            return False
        root = (ROOT if project_root is None else project_root).resolve(strict=True)
        artifact = (root / relative_path).resolve(strict=True)
        if not artifact.is_relative_to(root) or not artifact.is_file():
            return False
        config_bytes = _read_bounded_regular_file(artifact, MAX_RELEASE_TRAINING_CONFIG_BYTES)
        if hashlib.sha256(config_bytes).hexdigest().lower() != expected_digest.lower():
            return False
        config = yaml.load(config_bytes.decode("utf-8"), Loader=_ReleaseYamlLoader)
        if not isinstance(config, dict):
            return False
        names = config.get("names")
        if isinstance(names, list):
            ordered_names = names
        elif isinstance(names, dict):
            indexed_names: dict[int, str] = {}
            for raw_index, name in names.items():
                if type(raw_index) is int:
                    index = raw_index
                elif isinstance(raw_index, str) and re.fullmatch(r"(?:0|[1-9][0-9]*)", raw_index):
                    index = int(raw_index)
                else:
                    return False
                if index in indexed_names or not isinstance(name, str):
                    return False
                indexed_names[index] = name
            if set(indexed_names) != set(range(len(WHO_REQUIRED_MODEL_CLASSES))):
                return False
            ordered_names = [indexed_names[index] for index in range(len(WHO_REQUIRED_MODEL_CLASSES))]
        else:
            return False
        return ordered_names == list(WHO_REQUIRED_MODEL_CLASSES)
    except (OSError, RuntimeError, ValueError, TypeError, UnicodeDecodeError, yaml.YAMLError):
        return False


def verify_movement_intent_evidence(
    washing_intent: object, project_root: Path | None = None
) -> bool:
    """Require calibrated start/step thresholds backed by a bounded report hash."""
    if not isinstance(washing_intent, dict):
        return False
    for field in ("startMinimumNormalizedMovement", "stepMinimumNormalizedMovement"):
        threshold = washing_intent.get(field)
        if (type(threshold) not in (int, float) or not math.isfinite(threshold)
            or threshold <= 0.0 or threshold > 1.0):
            return False
    required_flags = (
        "startUsesMovementMagnitudeThreshold",
        "startUsesClinicallyCalibratedMovementMagnitudeThreshold",
        "stepCreditUsesMovementMagnitudeThreshold",
        "stepCreditUsesClinicallyCalibratedMovementMagnitudeThreshold",
    )
    if any(washing_intent.get(field) is not True for field in required_flags):
        return False

    evidence = washing_intent.get("validationEvidence")
    if (not isinstance(evidence, dict)
        or evidence.get("status") != "VALIDATED_FOR_HOSPITAL_PILOT"
        or evidence.get("startIntentIndependentlyValidated") is not True):
        return False
    relative_value = evidence.get("reportPath")
    expected_digest = evidence.get("reportSha256")
    if (not isinstance(relative_value, str) or not relative_value.strip()
        or not isinstance(expected_digest, str)
        or not SHA256_PATTERN.fullmatch(expected_digest)):
        return False

    try:
        relative_path = Path(relative_value)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            return False
        root = (ROOT if project_root is None else project_root).resolve(strict=True)
        artifact = root
        for part in relative_path.parts:
            if part in ("", "."):
                continue
            artifact = artifact / part
            if artifact.is_symlink():
                return False
        if not artifact.is_relative_to(root) or not artifact.is_file():
            return False
        report = _read_bounded_regular_file(artifact, MAX_MOVEMENT_INTENT_EVIDENCE_BYTES)
        return bool(report) and hashlib.sha256(report).hexdigest().lower() == expected_digest.lower()
    except (OSError, RuntimeError, ValueError, TypeError):
        return False


def hospital_readiness_blockers(
    manifest: dict,
    *,
    signature_error: str | None = "No se ha verificado la firma Ed25519 del manifiesto de release.",
) -> list[str]:
    """Return missing release evidence; generic labels must not be silently trusted."""
    blockers: list[str] = []
    if type(manifest.get("schemaVersion")) is not int or manifest.get("schemaVersion") != 1:
        blockers.append("El manifiesto debe declarar schemaVersion 1.")
    readiness = manifest.get("deploymentReadiness")
    if not isinstance(readiness, dict):
        return ["El manifiesto no contiene deploymentReadiness; falta una evaluación de release."]

    if readiness.get("status") != "READY_FOR_HOSPITAL_PILOT":
        blockers.append("El estado de release no es READY_FOR_HOSPITAL_PILOT.")
    if readiness.get("hospitalUseAllowed") is not True:
        blockers.append("El manifiesto no autoriza uso hospitalario.")
    evidence_fields = (
        ("stepTaxonomyVerified", "La semántica y rúbrica de las clases no están verificadas."),
        ("independentVideoValidationPassed", "Falta validación independiente con videos separados por fuente."),
        ("continuityCameraPilotPassed", "Falta un piloto documentado con Continuity Camera en el puesto objetivo."),
        ("clinicalSafetyReviewPassed", "Falta revisión clínica/de seguridad y aprobación documentada."),
    )
    for field, message in evidence_fields:
        if readiness.get(field) is not True:
            blockers.append(message)
    if not verify_movement_intent_evidence(manifest.get("washingIntent")):
        blockers.append(
            "Falta calibración independiente de los umbrales de movimiento/intención y un "
            "reporte acotado con SHA-256 verificado."
        )

    active = manifest.get("active")
    if not isinstance(active, dict):
        blockers.append("El manifiesto no identifica un detector activo.")
    else:
        training = active.get("trainingRun")
        active_digest = active.get("sha256")
        checkpoint_digest = training.get("checkpointSha256") if isinstance(training, dict) else None
        if (not isinstance(training, dict)
            or training.get("trainingDataConfigIncluded") is not True
            or not verify_training_data_config(training)):
            blockers.append(
                "El data.yaml exacto falta, está fuera del proyecto, no coincide con su SHA-256 "
                "o declara nombres/índices de clase distintos a la taxonomía firmada."
            )
        if not isinstance(training, dict) or (
            active.get("task") != "detect"
            or training.get("task") != "detect"
            or training.get("identicalToActiveCheckpoint") is not True
            or not isinstance(active_digest, str)
            or not SHA256_PATTERN.fullmatch(active_digest)
            or not isinstance(checkpoint_digest, str)
            or not SHA256_PATTERN.fullmatch(checkpoint_digest)
            or checkpoint_digest.lower() != active_digest.lower()
        ):
            blockers.append("El checkpoint activo y el run firmado no coinciden en tarea o SHA-256.")

        model_classes = active.get("modelClassNames")
        if (not isinstance(model_classes, list)
            or any(not isinstance(label, str) for label in model_classes)
            or model_classes != list(WHO_REQUIRED_MODEL_CLASSES)):
            blockers.append(
                "El detector activo no declara las 36 clases OMS en el orden canónico del checkpoint.")
        evaluation = active.get("validatedAgainst")
        if not isinstance(evaluation, dict) or evaluation.get("independentValidationEligible") is not True:
            blockers.append("La evaluación registrada no es elegible como validación independiente.")

    who = manifest.get("whoProcedure")
    if (not isinstance(who, dict)
        or who.get("status") != "VALIDATED_FOR_HOSPITAL_PILOT"
        or who.get("approvalAllowed") is not True):
        blockers.append("El modelo/protocolo no valida el procedimiento completo de agua y jabón objetivo.")
    elif who.get("requiredPhases") != list(WHO_REQUIRED_PHASES):
        blockers.append("Las fases OMS del manifiesto no coinciden con el orden canónico del backend Java.")

    artifacts = manifest.get("stationArtifacts")
    if not isinstance(artifacts, dict):
        blockers.append("Faltan las huellas firmadas de los artefactos ejecutables de la estación.")
    else:
        for field in STATION_ARTIFACT_HASH_FIELDS:
            digest = artifacts.get(field)
            if not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest):
                blockers.append(f"Falta una huella SHA-256 válida en stationArtifacts.{field}.")

    listed = readiness.get("blockers")
    if not isinstance(listed, list):
        blockers.append("El manifiesto debe declarar una lista explícita de blockers (vacía para liberar).")
    else:
        for item in listed:
            if not isinstance(item, str) or not item.strip():
                blockers.append("La lista blockers del manifiesto contiene una entrada inválida.")
            else:
                blockers.append(item)
    if signature_error is not None:
        blockers.append(signature_error)
    return list(dict.fromkeys(blockers))


def verify_station_artifact_hashes(
    manifest: dict,
    *,
    java_jar: Path,
    java_sbom: Path | None = None,
    camera_python_sbom: Path | None = None,
    supervisor: Path | None = None,
    camera_producer: Path | None = None,
    requirements_lock: Path | None = None,
    sbom_generator_lock: Path | None = None,
) -> list[str]:
    """Verify executable station artifacts against the signed manifest metadata."""
    artifacts = manifest.get("stationArtifacts")
    if not isinstance(artifacts, dict):
        return ["Faltan las huellas firmadas de los artefactos ejecutables de la estación."]
    actual_paths = {
        "javaJarSha256": java_jar,
        "javaSbomSha256": java_sbom or ROOT / "backend/target/handwash-java-sbom.json",
        "cameraPythonSbomSha256": camera_python_sbom
            or ROOT / "backend/target/handwash-camera-python-sbom.json",
        "sbomGeneratorLockSha256": sbom_generator_lock
            or ROOT / "requirements-sbom-generator-macos-arm64.lock",
        "stationSupervisorSha256": supervisor or Path(__file__).resolve(),
        "cameraProducerSha256": camera_producer or ROOT / "scripts/run_yolo26_continuity_camera.py",
        "cameraRequirementsLockSha256": requirements_lock or CAMERA_RUNTIME_LOCK,
    }
    maximum_sizes = {
        "javaJarSha256": 1024 * 1024 * 1024,
        "javaSbomSha256": MAX_RELEASE_JAVA_SBOM_BYTES,
        "cameraPythonSbomSha256": MAX_RELEASE_CAMERA_PYTHON_SBOM_BYTES,
        "sbomGeneratorLockSha256": 128 * 1024,
        "stationSupervisorSha256": 10 * 1024 * 1024,
        "cameraProducerSha256": 10 * 1024 * 1024,
        "cameraRequirementsLockSha256": 128 * 1024,
    }
    errors: list[str] = []
    for field, path in actual_paths.items():
        expected = artifacts.get(field)
        if not isinstance(expected, str) or not SHA256_PATTERN.fullmatch(expected):
            errors.append(f"stationArtifacts.{field} no contiene una huella SHA-256 válida.")
            continue
        try:
            resolved = path.expanduser().resolve(strict=True)
            if field == "javaSbomSha256":
                content = _read_bounded_regular_file(resolved, maximum_sizes[field])
                digest_value = hashlib.sha256(content).hexdigest()
                bom = json.loads(content, object_pairs_hook=_reject_duplicate_json_keys)
                metadata_component = bom.get("metadata", {}).get("component", {})
                components = bom.get("components")
                if (not isinstance(bom, dict)
                    or bom.get("bomFormat") != "CycloneDX"
                    or bom.get("specVersion") != "1.6"
                    or type(bom.get("version")) is not int or not 1 <= bom["version"] <= 2**63 - 1
                    or not isinstance(metadata_component, dict)
                    or metadata_component.get("type") != "application"
                    or not isinstance(metadata_component.get("name"), str)
                    or not metadata_component["name"].strip()
                    or not isinstance(components, list) or not components
                    or any(not isinstance(component, dict) for component in components)):
                    errors.append("El SBOM Java no es un CycloneDX 1.6 de aplicación válido/no vacío.")
                    continue
            elif field == "cameraPythonSbomSha256":
                content = _read_bounded_regular_file(resolved, maximum_sizes[field])
                digest_value = hashlib.sha256(content).hexdigest()
                bom = json.loads(content, object_pairs_hook=_reject_duplicate_json_keys)
                components = bom.get("components") if isinstance(bom, dict) else None
                actual_dependencies: dict[str, str] = {}
                valid_bom = (
                    isinstance(bom, dict)
                    and bom.get("bomFormat") == "CycloneDX"
                    and bom.get("specVersion") == "1.6"
                    and type(bom.get("version")) is int
                    and 1 <= bom["version"] <= 2**63 - 1
                    and isinstance(components, list)
                    and bool(components)
                )
                if valid_bom:
                    for component in components:
                        if not isinstance(component, dict):
                            valid_bom = False
                            break
                        name, version = component.get("name"), component.get("version")
                        if not isinstance(name, str) or not name.strip() or not isinstance(version, str):
                            valid_bom = False
                            break
                        normalized_name = re.sub(r"[-_.]+", "-", name).lower()
                        if normalized_name in actual_dependencies:
                            valid_bom = False
                            break
                        actual_dependencies[normalized_name] = version
                try:
                    expected_dependencies, _, _ = parse_camera_runtime_lock(
                        requirements_lock or CAMERA_RUNTIME_LOCK)
                except ValueError:
                    valid_bom = False
                    expected_dependencies = {}
                if not valid_bom:
                    errors.append("El SBOM Python de cámara no es un CycloneDX 1.6 válido/no vacío.")
                    continue
                if actual_dependencies != expected_dependencies:
                    errors.append(
                        "El SBOM Python de cámara no coincide exactamente con las dependencias/versiones del lock.")
                    continue
            else:
                digest_value = _sha256_regular_file(resolved, maximum_sizes[field])
        except (OSError, UnicodeDecodeError, ValueError, AttributeError, TypeError):
            errors.append(f"No se pudo verificar el artefacto de estación: {path}.")
            continue
        if digest_value.lower() != expected.lower():
            errors.append(f"La huella del artefacto no coincide con stationArtifacts.{field}.")
    return errors


def verify_signed_station_release(
    manifest_path: Path,
    *,
    java_jar: Path,
    java_sbom: Path | None = None,
    camera_python_sbom: Path | None = None,
    supervisor: Path | None = None,
    camera_producer: Path | None = None,
    requirements_lock: Path | None = None,
    sbom_generator_lock: Path | None = None,
) -> list[str]:
    """Revalidate the signed release and its runtime files immediately before use."""
    try:
        manifest_bytes = _read_bounded_regular_file(manifest_path, 2 * 1024 * 1024)
        manifest = json.loads(manifest_bytes, object_pairs_hook=_reject_duplicate_json_keys)
    except (OSError, UnicodeDecodeError, ValueError):
        return ["No se pudo leer un manifiesto de release válido antes de iniciar YOLO."]
    if not isinstance(manifest, dict):
        return ["El manifiesto de release debe ser un objeto JSON."]

    signature_error = verify_release_manifest_signature(
        manifest_path, manifest_bytes=manifest_bytes
    )
    blockers = hospital_readiness_blockers(manifest, signature_error=signature_error)
    blockers.extend(verify_station_artifact_hashes(
        manifest,
        java_jar=java_jar,
        java_sbom=java_sbom,
        camera_python_sbom=camera_python_sbom,
        supervisor=supervisor,
        camera_producer=camera_producer,
        requirements_lock=requirements_lock,
        sbom_generator_lock=sbom_generator_lock,
    ))
    return list(dict.fromkeys(blockers))


def verify_release_manifest_signature(
    manifest_path: Path,
    public_key_path: Path | None = None,
    signature_path: Path | None = None,
    *,
    manifest_bytes: bytes | None = None,
) -> str | None:
    """Verify a detached Ed25519 signature over the exact release manifest bytes.

    The verification key is provisioned outside the repository by the station
    administrator. A signature protects the reviewed release decision from
    accidental or manual edits; it does not establish that the evidence itself
    is clinically valid.
    """
    if public_key_path is None:
        configured_path = os.environ.get("HANDWASH_RELEASE_PUBLIC_KEY_PATH")
        if not configured_path:
            return "No se configuró HANDWASH_RELEASE_PUBLIC_KEY_PATH (clave pública de release confiable)."
        public_key_path = Path(configured_path).expanduser()
    if not public_key_path.is_absolute():
        return "La clave pública de release debe configurarse con una ruta absoluta y administrada externamente."
    try:
        public_key_path = public_key_path.resolve(strict=False)
        if public_key_path.is_relative_to(ROOT.resolve()):
            return "La clave pública de confianza debe residir fuera del repositorio del proyecto."
    except OSError:
        return "No se pudo resolver la ruta externa de la clave pública de release."

    signature_path = signature_path or manifest_path.with_name(manifest_path.name + ".sig")
    for path, description, max_bytes in (
        (manifest_path, "manifiesto", 2 * 1024 * 1024),
        (signature_path, "firma", 16 * 1024),
        (public_key_path, "clave pública", 64 * 1024),
    ):
        try:
            if not path.is_file():
                return f"No existe el archivo de {description} requerido para verificar el release."
            if path.stat().st_size > max_bytes:
                return f"El archivo de {description} excede el tamaño permitido para verificar el release."
        except OSError:
            return f"No se pudo leer el archivo de {description} para verificar el release."

    try:
        signed_bytes = (manifest_bytes if manifest_bytes is not None else
                        _read_bounded_regular_file(manifest_path, 2 * 1024 * 1024))
        signature_bytes = _read_bounded_regular_file(signature_path, 16 * 1024)
        public_key_bytes = _read_bounded_regular_file(public_key_path, 64 * 1024)
    except OSError:
        return "No se pudo leer de forma segura el manifiesto, la firma o la clave pública de release."
    if len(signed_bytes) > 2 * 1024 * 1024:
        return "El manifiesto excede el tamaño permitido para verificar el release."

    openssl = shutil.which("openssl")
    if openssl is None:
        return "No se encontró OpenSSL; no se puede verificar la firma Ed25519 del manifiesto."
    try:
        # Ed25519 verification is one-shot: OpenSSL sizes an input buffer from
        # file metadata. On macOS, /dev/stdin points at a pipe reporting a
        # zero-byte size, which makes OpenSSL 3.6 intermittently reject valid
        # signatures after stream tests have run. Give it a short-lived regular
        # file containing the exact bytes already read above; this preserves
        # the no-TOCTOU guarantee without retaining release data.
        with tempfile.TemporaryDirectory(prefix="handwash-release-verification-") as temp_directory:
            exact_directory = Path(temp_directory)
            exact_input = exact_directory / "manifest.json"
            exact_signature = exact_directory / "manifest.sig"
            exact_public_key = exact_directory / "public.pem"
            exact_input.write_bytes(signed_bytes)
            exact_signature.write_bytes(signature_bytes)
            exact_public_key.write_bytes(public_key_bytes)
            result = subprocess.run(
                [
                    openssl, "pkeyutl", "-verify", "-pubin", "-inkey", str(exact_public_key),
                    "-sigfile", str(exact_signature), "-rawin", "-in", str(exact_input),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=5,
            )
    except (OSError, subprocess.TimeoutExpired):
        return "Falló la verificación criptográfica del manifiesto de release."
    if result.returncode != 0:
        return "La firma Ed25519 del manifiesto no es válida para la clave pública configurada."
    return None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inicia y supervisa Java + YOLO en una estación local de un lavamanos."
    )
    parser.add_argument("--jar", type=Path,
                        default=ROOT / "backend/target/hand-wash-compliance-1.0.0.jar")
    parser.add_argument("--java", default="java", help="Ejecutable Java (por defecto, java del PATH)")
    parser.add_argument("--python", type=Path, default=ROOT / ".venv/bin/python")
    parser.add_argument("--camera-script", type=Path,
                        default=ROOT / "scripts/run_yolo26_continuity_camera.py")
    parser.add_argument("--startup-timeout", type=float, default=60.0)
    parser.add_argument("--retry-limit", type=int, default=3,
                        help="Reintentos máximos por fallos consecutivos de YOLO")
    parser.add_argument("--retry-delays", type=parse_retry_delays, default=(2.0, 5.0, 15.0))
    parser.add_argument("--unvalidated-demo", action="store_true",
                        help="Solo para demostración interna; nunca habilita ni representa uso hospitalario")
    parser.add_argument("--camera-arg", action="append", default=[], metavar="ARG",
                        help="Argumento de cámara adicional; repetir la opción si hace falta")
    args = parser.parse_args(argv)
    # Child processes use ROOT as cwd; normalize user-supplied paths now so
    # validation and execution cannot resolve the same relative path differently.
    args.jar = args.jar.expanduser().resolve()
    # Keep the lexical path: resolving .venv/bin/python follows its symlink to
    # Homebrew's base interpreter and silently discards the virtualenv context.
    args.python = Path(os.path.abspath(args.python.expanduser()))
    args.camera_script = args.camera_script.expanduser().resolve()
    if not math.isfinite(args.startup_timeout) or args.startup_timeout <= 0 or args.startup_timeout > 300:
        parser.error("--startup-timeout debe estar entre 0 y 300 segundos")
    if args.retry_limit < 0 or args.retry_limit > 20:
        parser.error("--retry-limit debe estar entre 0 y 20")
    index = 0
    while index < len(args.camera_arg):
        argument = args.camera_arg[index]
        option, separator, inline_value = argument.partition("=")
        if option not in SAFE_CAMERA_OPTIONS:
            parser.error(f"opción de cámara no permitida por el supervisor: {option}")
        if separator:
            if not validate_camera_option(option, inline_value):
                parser.error(f"valor fuera de rango/no válido para {option}: {inline_value!r}")
            index += 1
            continue
        if index + 1 >= len(args.camera_arg) or args.camera_arg[index + 1].startswith("--"):
            parser.error(f"falta el valor de {option}; usa --camera-arg={option}=VALOR")
        if not validate_camera_option(option, args.camera_arg[index + 1]):
            parser.error(f"valor fuera de rango/no válido para {option}: {args.camera_arg[index + 1]!r}")
        index += 2
    return args


class StationSupervisor:
    """Own exactly the Java and camera child processes started by this run."""

    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.stop_requested = threading.Event()
        self._pairing_lock = threading.Lock()
        self._pairing_code = os.environ.get("HANDWASH_PAIRING_CODE", "").strip() or None
        self._camera_process: subprocess.Popen[str] | None = None
        self._camera_reader: threading.Thread | None = None
        self._java_process: subprocess.Popen[bytes] | None = None

    def _set_pairing_code(self, candidate: str | None) -> None:
        if candidate:
            with self._pairing_lock:
                self._pairing_code = candidate

    def _clear_pairing_code(self) -> None:
        with self._pairing_lock:
            self._pairing_code = None

    def _get_pairing_code(self) -> str | None:
        with self._pairing_lock:
            return self._pairing_code

    def _camera_output(self, output: TextIO) -> None:
        forward_to_terminal = True
        try:
            for line in output:
                code = pairing_code_from_output(line)
                self._set_pairing_code(code)
                # Output remains in the terminal only; no log file can retain a code/token.
                if forward_to_terminal:
                    try:
                        print(line, end="", flush=True)
                    except (BrokenPipeError, OSError):
                        # Keep draining the child pipe so a closed log sink
                        # cannot backpressure and freeze the camera process.
                        forward_to_terminal = False
        finally:
            output.close()

    @staticmethod
    def _terminate_group(process: subprocess.Popen, *, graceful_signal: int, timeout: float) -> None:
        group_id = process.pid
        try:
            os.killpg(group_id, graceful_signal)
        except ProcessLookupError:
            return

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if process.poll() is None:
                try:
                    process.wait(timeout=0.05)
                except subprocess.TimeoutExpired:
                    pass
            try:
                os.killpg(group_id, 0)
            except ProcessLookupError:
                return
            except PermissionError:
                # A group we created should remain signalable; fail closed if not.
                break
            time.sleep(0.05)
        try:
            os.killpg(group_id, signal.SIGKILL)
        except ProcessLookupError:
            pass
        if process.poll() is None:
            process.wait()

    def _start_backend(self, *, release_verified: bool = False) -> subprocess.Popen[bytes]:
        env = station_backend_environment(
            self.args.unvalidated_demo, release_verified=release_verified)
        print("[estación] Iniciando backend Java en 127.0.0.1:8080…", flush=True)
        return subprocess.Popen(
            [self.args.java, "-jar", str(self.args.jar)],
            cwd=ROOT,
            env=env,
            start_new_session=True,
        )

    def _wait_backend(self, process: subprocess.Popen[bytes]) -> bool:
        deadline = time.monotonic() + self.args.startup_timeout
        while not self.stop_requested.is_set() and time.monotonic() < deadline:
            if process.poll() is not None:
                print("[estación] Java terminó antes de estar disponible.", file=sys.stderr, flush=True)
                return False
            expected_mode = (
                "NON_CLINICAL_DEMO" if self.args.unvalidated_demo else "HOSPITAL_PILOT"
            )
            if backend_matches_station(
                "http://127.0.0.1:8080", expected_mode=expected_mode
            ):
                print("[estación] Backend Java listo; dashboard: http://127.0.0.1:8080/", flush=True)
                return True
            self.stop_requested.wait(0.25)
        print("[estación] Tiempo agotado esperando el backend Java.", file=sys.stderr, flush=True)
        return False

    def _backend_alive(self) -> bool:
        return self._java_process is not None and self._java_process.poll() is None

    def _wait_while_backend_alive(self, delay: float) -> bool:
        """Wait interruptibly, but never keep a camera retry alive after Java exits."""
        deadline = time.monotonic() + max(0.0, delay)
        while not self.stop_requested.is_set():
            if not self._backend_alive():
                return False
            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                return True
            self.stop_requested.wait(min(0.2, remaining))
        return False

    def _start_camera(self) -> subprocess.Popen[str]:
        pairing_code = self._get_pairing_code()
        env = camera_child_environment(pairing_code)
        command = [
            str(self.args.python), str(self.args.camera_script),
            "--java-url", "http://127.0.0.1:8080",
            "--hand-presence-warmup-ms", str(LOCKED_HAND_PRESENCE_WARMUP_MS),
            *self.args.camera_arg,
        ]
        print("[estación] Iniciando YOLO/Cámara de Continuidad…", flush=True)
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            start_new_session=True,
        )
        self._camera_process = process
        if process.stdout is None:
            raise RuntimeError("No se pudo abrir la salida del proceso de cámara")
        self._camera_reader = threading.Thread(
            target=self._camera_output,
            args=(process.stdout,),
            name="station-camera-output",
            daemon=True,
        )
        self._camera_reader.start()
        return process

    def run(self) -> int:
        manifest_path = ROOT / "backend/models/model-manifest.json"
        try:
            manifest_bytes = _read_bounded_regular_file(manifest_path, 2 * 1024 * 1024)
            manifest = json.loads(manifest_bytes, object_pairs_hook=_reject_duplicate_json_keys)
        except (OSError, UnicodeDecodeError, ValueError) as error:
            print(f"No se puede leer el manifiesto de modelos {manifest_path}: {error}",
                  file=sys.stderr)
            return 2
        if not isinstance(manifest, dict):
            print("El manifiesto de modelos debe ser un objeto JSON.", file=sys.stderr)
            return 2
        if self.args.unvalidated_demo:
            blockers = hospital_readiness_blockers(
                manifest,
                signature_error="Se solicitó --unvalidated-demo; este arranque no tiene autorización clínica.",
            )
        else:
            blockers = verify_signed_station_release(
                manifest_path,
                java_jar=self.args.jar,
                supervisor=Path(__file__),
                camera_producer=self.args.camera_script,
            )
        if blockers and not self.args.unvalidated_demo:
            print("[bloqueo de release] La estación no se inicia para uso hospitalario:",
                  file=sys.stderr)
            for blocker in blockers:
                print(f"  - {blocker}", file=sys.stderr)
            print("Para pruebas internas sin valor clínico, usa --unvalidated-demo.", file=sys.stderr)
            return 3
        release_verified = not self.args.unvalidated_demo and not blockers
        if blockers:
            print("[DEMO NO CLÍNICA] Modelo sin validación de release hospitalario; "
                  "no usar para decisiones ni registros clínicos.", file=sys.stderr, flush=True)

        if not self.args.jar.is_file():
            print(f"No existe el JAR de estación: {self.args.jar}. Ejecuta scripts/build_handwash_station.sh.",
                  file=sys.stderr)
            return 2
        if not self.args.python.is_file() or not os.access(self.args.python, os.X_OK):
            print(f"No existe un Python ejecutable: {self.args.python}", file=sys.stderr)
            return 2
        runtime_errors = verify_camera_runtime(self.args.python)
        if runtime_errors:
            print("[bloqueo de runtime] El entorno de cámara no coincide con "
                  "requirements-camera-macos-arm64.lock:", file=sys.stderr)
            for error in runtime_errors:
                print(f"  - {error}", file=sys.stderr)
            return 2
        if not self.args.camera_script.is_file():
            print(f"No existe el capturador YOLO: {self.args.camera_script}", file=sys.stderr)
            return 2
        if shutil.which(self.args.java) is None:
            print(f"No se encontró Java en PATH: {self.args.java}", file=sys.stderr)
            return 2
        for port in (8080, 8091):
            if port_is_in_use("127.0.0.1", port):
                print(f"El puerto local {port} ya está ocupado; no reutilizaré ni cerraré ese proceso.",
                      file=sys.stderr)
                return 2

        self._java_process = self._start_backend(release_verified=release_verified)
        if not self._wait_backend(self._java_process):
            return 1

        retries_used = 0
        while not self.stop_requested.is_set():
            if not self._backend_alive():
                print("[estación] Java terminó antes de iniciar/reintentar YOLO; "
                      "la sesión en memoria ya no se puede reanudar.",
                      file=sys.stderr, flush=True)
                return 1
            # The station may have spent time starting Java or waiting between retries.
            # Recheck the signature and every executable before launching Python again.
            runtime_errors = verify_camera_runtime(self.args.python)
            if runtime_errors:
                print("[bloqueo de runtime] El entorno Python cambió antes de iniciar YOLO:",
                      file=sys.stderr)
                for error in runtime_errors:
                    print(f"  - {error}", file=sys.stderr)
                return 2
            if not self.args.unvalidated_demo:
                blockers = verify_signed_station_release(
                    manifest_path,
                    java_jar=self.args.jar,
                    supervisor=Path(__file__),
                    camera_producer=self.args.camera_script,
                )
                if blockers:
                    print("[bloqueo de release] Artefactos/manifiesto cambiaron antes de YOLO:",
                          file=sys.stderr)
                    for blocker in blockers:
                        print(f"  - {blocker}", file=sys.stderr)
                    return 3
            if self.stop_requested.is_set():
                return 130
            if not self._backend_alive():
                print("[estación] Java terminó durante las verificaciones previas; "
                      "no se iniciará YOLO.",
                      file=sys.stderr, flush=True)
                return 1
            camera = self._start_camera()
            while camera.poll() is None and not self.stop_requested.is_set():
                if self._java_process.poll() is not None:
                    print("[estación] Java cayó; la sesión activa se perdió. Se exige un lavado nuevo.",
                          file=sys.stderr, flush=True)
                    self._terminate_group(camera, graceful_signal=signal.SIGINT, timeout=8.0)
                    return 1
                self.stop_requested.wait(0.2)
            if self.stop_requested.is_set():
                self._terminate_group(camera, graceful_signal=signal.SIGINT, timeout=8.0)
                return 130

            return_code = camera.wait()
            # Also reap FFmpeg/preview descendants if the Python worker crashed.
            self._terminate_group(camera, graceful_signal=signal.SIGTERM, timeout=2.0)
            if self._camera_reader is not None:
                self._camera_reader.join(timeout=2.0)
            code = self._get_pairing_code()
            decision = camera_exit_decision(
                return_code,
                java_alive=self._java_process.poll() is None,
                pairing_code_available=code is not None,
                retries_used=retries_used,
                retry_limit=self.args.retry_limit,
            )
            if decision == RestartDecision.NEW_SESSION:
                # A completed/expired session cannot be reused. Start a clean one.
                self._clear_pairing_code()
                retries_used = 0
                if not self._wait_while_backend_alive(1.0):
                    if self.stop_requested.is_set():
                        return 130
                    print("[estación] Java terminó antes de preparar una sesión nueva.",
                          file=sys.stderr, flush=True)
                    return 1
                print("[estación] El intento terminó; preparando una sesión nueva.", flush=True)
                continue
            if decision == RestartDecision.RETRY_SAME_SESSION:
                delay_index = min(retries_used, len(self.args.retry_delays) - 1)
                delay = self.args.retry_delays[delay_index]
                retries_used += 1
                print(
                    f"[estación] YOLO terminó con error ({return_code}); reintento "
                    f"{retries_used}/{self.args.retry_limit} en {delay:g} s, "
                    "con la misma sesión y un epoch nuevo.",
                    file=sys.stderr,
                    flush=True,
                )
                if not self._wait_while_backend_alive(delay):
                    if self.stop_requested.is_set():
                        return 130
                    print("[estación] Java terminó durante la espera; no se reiniciará YOLO.",
                          file=sys.stderr, flush=True)
                    return 1
                continue
            print(
                "[estación] No es seguro reanudar YOLO (sin código de sesión, límite de reintentos "
                "alcanzado o Java detenido). La estación queda cerrada; no se crea una sesión "
                "que parezca continuar el lavado anterior.",
                file=sys.stderr,
                flush=True,
            )
            return 1
        return 130

    def stop(self) -> None:
        self.stop_requested.set()
        if self._camera_process is not None and self._camera_process.poll() is None:
            self._terminate_group(self._camera_process, graceful_signal=signal.SIGINT, timeout=8.0)
        if self._java_process is not None and self._java_process.poll() is None:
            self._terminate_group(self._java_process, graceful_signal=signal.SIGTERM, timeout=10.0)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    supervisor = StationSupervisor(args)
    previous_handlers: dict[int, object] = {}

    def request_shutdown(_signum: int, _frame: object) -> None:
        supervisor.stop_requested.set()

    for signum in (signal.SIGINT, signal.SIGTERM):
        previous_handlers[signum] = signal.signal(signum, request_shutdown)
    try:
        return supervisor.run()
    except KeyboardInterrupt:
        return 130
    except (OSError, RuntimeError) as error:
        print(f"[estación] No se pudo mantener la estación: {error}", file=sys.stderr, flush=True)
        return 1
    finally:
        supervisor.stop()
        for signum, previous in previous_handlers.items():
            signal.signal(signum, previous)


if __name__ == "__main__":
    raise SystemExit(main())
