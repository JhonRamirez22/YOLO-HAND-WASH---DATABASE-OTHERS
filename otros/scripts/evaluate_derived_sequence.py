#!/usr/bin/env python3
"""Replay one held-out 2-fps video through runtime-like crop/fallback filters.

Uses only frames from the test split, keeps pixels in memory, and performs
inference only. It models crop/full-frame inference and capturer temporal votes,
then approximates Java's start evidence; it is not an iPhone/live acceptance test.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
import math
from pathlib import Path

if __package__:  # Keep manifest/timebase validation testable without camera/model dependencies.
    from .dataset_contracts import DERIVED_CLASSIFIER_NAMES
else:  # pragma: no cover - exercised by direct script execution
    from dataset_contracts import DERIVED_CLASSIFIER_NAMES


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "ENTRENAMIENTO/derived_handwash_yolo26_cls_2fps_2026-09-26"
STEP_MODEL = ROOT / "backend/models/handwash_yolo26n_7pasos.pt"
CLASSIFIER_MODEL = ROOT / "backend/models/handwash_who_yolo26m_cls.pt"
POSE_MODEL = ROOT / "backend/models/yolo26s-pose-hands.pt"
DEFAULT_VIDEO = "2020-06-26_23-34-59_camera102.mp4"
WHO_TO_STEP = {
    1: "Paso1_Palmas", 2: "Paso2_Dorsos", 3: "Paso3_Interdigitales",
    4: "Paso4_Nudillos", 5: "Paso5_Pulgar", 6: "Paso6_PuntaDeDedos",
}


def load_test_sequence(
    video_name: str,
    dataset_root: Path = DATASET,
) -> list[tuple[int, int, Path]]:
    """Load a held-out video only after validating split and annotation integrity."""
    root = dataset_root.expanduser().resolve(strict=True)
    manifest_path = (root / "manifest.csv").resolve(strict=True)
    if not manifest_path.is_relative_to(root) or not manifest_path.is_file():
        raise ValueError("manifest.csv debe ser un archivo dentro de la raíz del dataset")

    required_fields = {
        "split", "relative_image", "class_id", "class_name", "video", "source_frame_index",
    }
    video_splits: dict[str, str] = {}
    seen_source_frames: set[tuple[str, int]] = set()
    rows: list[tuple[int, int, Path]] = []
    try:
        with manifest_path.open(newline="", encoding="utf-8-sig") as source:
            reader = csv.DictReader(source)
            if reader.fieldnames is None or not required_fields.issubset(reader.fieldnames):
                raise ValueError(
                    "manifest.csv debe incluir split, relative_image, class_id, class_name, "
                    "video y source_frame_index"
                )
            if len(reader.fieldnames) != len(set(reader.fieldnames)):
                raise ValueError("manifest.csv contiene nombres de columna duplicados")
            for line_number, row in enumerate(reader, start=2):
                if None in row or any(row.get(field) is None for field in required_fields):
                    raise ValueError(f"Fila {line_number} incompleta o con columnas extra en manifest.csv")

                split = row["split"].strip()
                video = row["video"].strip()
                if split not in {"train", "val", "test"} or not video:
                    raise ValueError(f"Fila {line_number}: split o video no válido en manifest.csv")
                previous_split = video_splits.setdefault(video, split)
                if previous_split != split:
                    raise ValueError(
                        f"El video {video!r} aparece en más de un split ({previous_split}, {split})"
                    )

                try:
                    class_id = int(row["class_id"])
                    source_frame_index = int(row["source_frame_index"])
                except ValueError as error:
                    raise ValueError(f"Fila {line_number}: class_id/source_frame_index no entero") from error
                class_name = DERIVED_CLASSIFIER_NAMES.get(class_id)
                if class_name is None or row["class_name"].strip() != class_name:
                    raise ValueError(
                        f"Fila {line_number}: class_id y class_name no coinciden con el mapa del modelo"
                    )
                if source_frame_index < 0:
                    raise ValueError(f"Fila {line_number}: source_frame_index no puede ser negativo")
                source_key = (video, source_frame_index)
                if source_key in seen_source_frames:
                    raise ValueError(
                        f"Fila {line_number}: frame fuente duplicado {source_frame_index} en {video!r}"
                    )
                seen_source_frames.add(source_key)

                relative_value = row["relative_image"].strip()
                relative_image = Path(relative_value)
                if (
                    not relative_value
                    or relative_image.is_absolute()
                    or ".." in relative_image.parts
                    or len(relative_image.parts) < 3
                    or relative_image.parts[0] != split
                    or relative_image.parts[1] != class_name
                ):
                    raise ValueError(f"Fila {line_number}: ruta de imagen no canónica en manifest.csv")
                image = (root / relative_image).resolve(strict=False)
                if not image.is_relative_to(root):
                    raise ValueError(f"Fila {line_number}: ruta de imagen escapa del dataset")

                if split == "test" and video == video_name:
                    try:
                        image = image.resolve(strict=True)
                    except OSError as error:
                        raise ValueError(
                            f"Fila {line_number}: falta una imagen declarada del split test: {relative_value}"
                        ) from error
                    if not image.is_file():
                        raise ValueError(
                            f"Fila {line_number}: la imagen de test no es un archivo: {relative_value}"
                        )
                    rows.append((source_frame_index, class_id, image))
    except csv.Error as error:
        raise ValueError(f"manifest.csv no es un CSV válido: {error}") from error

    sequence = sorted(rows)
    validate_unique_source_frames(sequence)
    return sequence


def validate_unique_source_frames(sequence: list[tuple[int, int, Path]]) -> None:
    """One source frame may contribute only one class vote in a replay."""
    seen: set[int] = set()
    for frame_index, _class_id, _image in sequence:
        if frame_index in seen:
            raise ValueError(
                f"Duplicate source_frame_index {frame_index} in held-out sequence; "
                "deduplicate the annotation manifest before replay."
            )
        seen.add(frame_index)


def source_frame_time_seconds(frame_index: int, source_fps: float) -> float:
    """Convert source frame indices using an explicit/declared source FPS."""
    if not math.isfinite(source_fps) or source_fps <= 0:
        raise ValueError("source_fps must be finite and greater than zero")
    if isinstance(frame_index, bool) or not isinstance(frame_index, int) or frame_index < 0:
        raise ValueError("frame_index must be a non-negative integer")
    return frame_index / source_fps


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", default=DEFAULT_VIDEO)
    parser.add_argument("--step-model", type=Path, default=STEP_MODEL)
    parser.add_argument("--classifier-model", type=Path, default=CLASSIFIER_MODEL)
    parser.add_argument("--pose-model", type=Path, default=POSE_MODEL)
    parser.add_argument("--pose-roi", nargs=4, type=float, default=None,
                        metavar=("X1", "Y1", "X2", "Y2"))
    parser.add_argument("--pose-imgsz", type=int, default=320,
                        help="Tamaño de entrada para la pasada primaria del localizador")
    parser.add_argument("--pose-recovery-imgsz", type=int, default=640)
    parser.add_argument("--pose-box-confidence", type=float, default=0.001,
                        help="Confianza de caja mínima para aceptar propuestas de pose")
    parser.add_argument("--pose-iou", type=float, default=0.90,
                        help="IoU de NMS del detector de pose; valores altos preservan manos solapadas")
    parser.add_argument("--pose-max-det", type=int, default=16,
                        help="Máximo de propuestas de pose antes del deduplicador geométrico")
    parser.add_argument("--pose-recovery-roi", nargs=4, type=float, default=None,
                        metavar=("X1", "Y1", "X2", "Y2"),
                        help="Recorte normalizado usado solo por la recuperación a alta resolución")
    parser.add_argument("--pose-augment", action="store_true",
                        help="Pide TTA al modelo de pose si su arquitectura lo permite")
    parser.add_argument("--source-fps", type=float, required=True,
                        help="FPS real del video original confirmado con ffprobe; no se asume un valor predeterminado")
    parser.add_argument("--trace-class", type=int, choices=range(1, 7), default=None,
                        help="Imprime diagnóstico por frame para una clase anotada 1–6")
    parser.add_argument("--classifier-confidence", type=float, default=0.75)
    parser.add_argument("--detector-challenge-below", type=float, default=0.80)
    parser.add_argument("--classifier-margin", type=float, default=0.10)
    classifier_policy = parser.add_mutually_exclusive_group()
    classifier_policy.add_argument("--classifier-authoritative", dest="classifier_authoritative",
                                   action="store_true")
    classifier_policy.add_argument("--classifier-guarded", dest="classifier_authoritative",
                                   action="store_false")
    parser.set_defaults(classifier_authoritative=True)
    args = parser.parse_args()
    try:
        sequence = load_test_sequence(args.video)
    except (OSError, ValueError) as error:
        parser.error(f"Manifest de evaluación inválido: {error}")
    if not sequence:
        parser.error(f"No held-out frames found for video {args.video!r}")
    if not math.isfinite(args.source_fps) or args.source_fps <= 0:
        parser.error("--source-fps debe ser finito y mayor que cero")
    present_steps = {label for _, label, _ in sequence}
    if not set(range(1, 7)).issubset(present_steps):
        parser.error("Selected test video does not contain all six compatible classes")
    if args.pose_imgsz < 160 or args.pose_imgsz % 32:
        parser.error("--pose-imgsz debe ser >=160 y múltiplo de 32")
    if args.pose_recovery_imgsz and args.pose_recovery_imgsz < args.pose_imgsz:
        parser.error("--pose-recovery-imgsz debe ser 0 o >= --pose-imgsz")
    if not 0.0 < args.pose_box_confidence <= 1.0:
        parser.error("--pose-box-confidence debe estar en (0, 1]")
    if not 0.1 <= args.pose_iou <= 0.95:
        parser.error("--pose-iou debe estar entre 0,1 y 0,95")
    if not 2 <= args.pose_max_det <= 64:
        parser.error("--pose-max-det debe estar entre 2 y 64")
    if args.pose_recovery_roi:
        x1, y1, x2, y2 = args.pose_recovery_roi
        if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
            parser.error("--pose-recovery-roi debe estar dentro de la imagen normalizada")
    if not 0 <= args.classifier_confidence <= 1:
        parser.error("--classifier-confidence debe estar en [0, 1]")
    if not 0 <= args.detector_challenge_below <= 1:
        parser.error("--detector-challenge-below debe estar en [0, 1]")
    if not 0 <= args.classifier_margin <= 1:
        parser.error("--classifier-margin debe estar en [0, 1]")

    import cv2
    from ultralytics import YOLO

    if __package__:
        from .run_yolo26_continuity_camera import (
            HandMotionEstimator, TemporalStepFilter, arbitrate_uncertain_detection,
            best_detection, compatible_classifier_step, derived_classifier_decision,
            detected_hand_boxes, detected_hands, hand_crop_bounds, background_vetoes_detection,
            partial_crop_guidance_hands, prefer_recovered_localization,
            prefer_recovered_motion, temporal_gap_exceeded, validate_derived_classifier,
            validate_hand_model, validate_step_model, translate_pose_result,
        )
    else:  # pragma: no cover - exercised by direct script execution
        from run_yolo26_continuity_camera import (
            HandMotionEstimator, TemporalStepFilter, arbitrate_uncertain_detection,
            best_detection, compatible_classifier_step, derived_classifier_decision,
            detected_hand_boxes, detected_hands, hand_crop_bounds, background_vetoes_detection,
            partial_crop_guidance_hands, prefer_recovered_localization,
            prefer_recovered_motion, temporal_gap_exceeded, validate_derived_classifier,
            validate_hand_model, validate_step_model, translate_pose_result,
        )

    detector = YOLO(str(args.step_model))
    _, mode = validate_step_model(detector, str(args.step_model))
    classifier = YOLO(str(args.classifier_model))
    validate_derived_classifier(classifier, str(args.classifier_model))
    pose_model = YOLO(str(args.pose_model))
    validate_hand_model(pose_model, str(args.pose_model))
    motion_estimator = HandMotionEstimator()
    per_class: dict[int, Counter[str]] = {step: Counter() for step in range(1, 7)}
    classifier_attempts = classifier_successes = paired_pose_frames = motion_frames = 0
    strict_intention_pose_frames = 0
    raw_box_pair_frames = 0
    strict_start_observations: list[tuple[int, float]] = []
    classifier_shadow_correct = classifier_shadow_total = 0
    crop_detector_frames = full_frame_fallback_frames = 0
    primary_filter = TemporalStepFilter(history_size=3, min_votes=2)
    fallback_filter = TemporalStepFilter(history_size=5, min_votes=3)
    previous_source = None
    previous_observation_at = 0.0
    last_start_observation_at = 0.0
    start_candidate_since = 0.0
    start_observations = 0
    start_valid_frames = confirmed_starts = 0

    for frame_index, class_id, image_path in sequence:
        frame = cv2.imread(str(image_path))
        if frame is None:
            raise RuntimeError(f"Unreadable test image: {image_path}")
        classification = classifier.predict(frame, imgsz=320, device="cpu",
                                             verbose=False, save=False)[0]
        classifier_step, _ = compatible_classifier_step(
            classification, args.classifier_confidence
        )
        if 1 <= class_id <= 6:
            classifier_shadow_total += 1
            classifier_shadow_correct += classifier_step == WHO_TO_STEP[class_id]

        pose_frame = frame
        if args.pose_roi:
            height, width = frame.shape[:2]
            x1, y1, x2, y2 = args.pose_roi
            pose_frame = frame[max(0, round(y1 * height)):min(height, round(y2 * height)),
                               max(0, round(x1 * width)):min(width, round(x2 * width))]
            if pose_frame.size == 0:
                parser.error("--pose-roi produced an empty crop")
        capture_time = source_frame_time_seconds(frame_index, args.source_fps)
        pose_result = pose_model.predict(
            pose_frame, imgsz=args.pose_imgsz, conf=args.pose_box_confidence,
            max_det=args.pose_max_det, iou=args.pose_iou,
            device="cpu", augment=args.pose_augment,
            verbose=False, save=False,
        )[0]
        raw_crop_boxes = detected_hand_boxes(pose_result, 0.15)
        raw_pair = len(raw_crop_boxes) >= 2
        raw_box_pair_frames += raw_pair
        crop_hands = partial_crop_guidance_hands(
            pose_result, args.pose_box_confidence, 0.15
        )
        pose_evidence = motion_estimator.update(
            pose_result, frame_index, capture_time, args.pose_box_confidence
        )
        pose_hands = detected_hands(
            pose_result, min_confidence=args.pose_box_confidence
        )
        if len(pose_hands) < 2 and args.pose_recovery_imgsz > args.pose_imgsz:
            recovery_input = pose_frame
            recovery_offset = (0, 0)
            if args.pose_recovery_roi:
                height, width = pose_frame.shape[:2]
                x1, y1, x2, y2 = args.pose_recovery_roi
                left, top = round(x1 * width), round(y1 * height)
                right, bottom = round(x2 * width), round(y2 * height)
                recovery_input = pose_frame[top:bottom, left:right]
                recovery_offset = (left, top)
            recovered_raw = pose_model.predict(
                recovery_input, imgsz=args.pose_recovery_imgsz,
                conf=args.pose_box_confidence, max_det=args.pose_max_det,
                iou=args.pose_iou,
                device="cpu", augment=args.pose_augment,
                verbose=False, save=False,
            )[0]
            recovered = translate_pose_result(recovered_raw, *recovery_offset)
            recovered_evidence = motion_estimator.update(
                recovered, frame_index, capture_time, args.pose_box_confidence
            )
            recovered_hands = detected_hands(
                recovered, min_confidence=args.pose_box_confidence
            )
            recovered_raw_boxes = detected_hand_boxes(recovered, 0.15)
            raw_box_pair_frames += (len(recovered_raw_boxes) >= 2 and not raw_pair)
            recovered_crop_hands = partial_crop_guidance_hands(
                recovered, args.pose_box_confidence, 0.15
            )
            if prefer_recovered_localization(recovered_crop_hands, crop_hands):
                crop_hands = recovered_crop_hands
            recovery_improves_pose = prefer_recovered_motion(
                recovered_evidence, pose_evidence
            )
            if recovery_improves_pose:
                pose_result, pose_evidence, pose_hands = recovered, recovered_evidence, recovered_hands
        has_pair = pose_evidence["manosVisibles"] >= 2
        paired_pose_frames += has_pair
        if 1 <= class_id <= 6:
            per_class[class_id]["bilateral_pose_frames"] += has_pair
        strict_start_pose = pose_evidence["_manosParaInicio"] >= 2
        strict_intention_pose_frames += strict_start_pose
        if strict_start_pose:
            strict_start_observations.append((frame_index, capture_time))
        has_motion = has_pair and bool(pose_evidence.get("medicionValida"))
        motion_frames += has_motion
        if 1 <= class_id <= 6:
            per_class[class_id]["strict_start_pose_frames"] += strict_start_pose
            per_class[class_id]["valid_motion_frames"] += has_motion

        crop_bounds = hand_crop_bounds(crop_hands, pose_frame.shape) if crop_hands else None
        full_frame_fallback = crop_bounds is None
        if full_frame_fallback:
            full_frame_fallback_frames += 1
            detector_result = detector.predict(
                frame, imgsz=640, conf=0.75, max_det=24,
                device="cpu", verbose=False, save=False,
            )[0]
        else:
            crop_detector_frames += 1
            left, top, right, bottom = crop_bounds
            detector_result = detector.predict(
                pose_frame[top:bottom, left:right].copy(),
                imgsz=416, conf=0.35, device="cpu", verbose=False, save=False,
            )[0]
        detector_step, detector_confidence, _ = best_detection(detector_result, mode)

        final_step = detector_step
        final_confidence = detector_confidence
        # During an active session Java accepts a trusted class with fresh
        # bilateral hand poses; only initial intent confirmation requires a
        # valid two-frame spatial measurement. This counts classifier proposals,
        # not proof that the first Palmas observation can start the session.
        if (has_pair
            and (args.classifier_authoritative or detector_step is None
                 or detector_confidence is None
                 or detector_confidence < args.detector_challenge_below)):
            classifier_attempts += 1
        if has_pair:
            final_step, final_confidence, challenge_source = arbitrate_uncertain_detection(
                detector_step, detector_confidence, classification,
                args.classifier_confidence, args.detector_challenge_below,
                args.classifier_margin, args.classifier_authoritative,
            )
            if background_vetoes_detection(detector_result, final_confidence):
                final_step, final_confidence, challenge_source = None, None, "background_veto"
            if challenge_source == "classifier":
                classifier_successes += 1

        if temporal_gap_exceeded(previous_observation_at, capture_time, 0.9):
            primary_filter.reset()
            fallback_filter.reset()
            previous_source = None
        source = "full-frame-fallback" if full_frame_fallback else "hand-crop"
        if source == "full-frame-fallback":
            primary_filter.reset()
            if previous_source != source:
                fallback_filter.reset()
            active_filter = fallback_filter
        else:
            fallback_filter.reset()
            if previous_source != source:
                primary_filter.reset()
            active_filter = primary_filter
        stable_step, stable_confidence = active_filter.update(final_step, final_confidence)
        previous_source = source
        previous_observation_at = capture_time

        if (stable_step == "Paso1_Palmas" and stable_confidence is not None
            and stable_confidence >= 0.75 and has_pair and has_motion):
            start_valid_frames += 1
            interval = capture_time - last_start_observation_at
            if last_start_observation_at and 0 < interval <= 0.65:
                start_observations += 1
            else:
                start_observations = 1
                start_candidate_since = capture_time
            last_start_observation_at = capture_time
            if (start_observations >= 3
                and capture_time - start_candidate_since >= 0.65):
                confirmed_starts += 1
        elif stable_step is not None:
            start_observations = 0
            last_start_observation_at = 0.0
            start_candidate_since = 0.0

        if 1 <= class_id <= 6:
            expected = WHO_TO_STEP[class_id]
            per_class[class_id]["detector_ok"] += detector_step == expected
            per_class[class_id]["roi_crop_frames"] += crop_bounds is not None
            per_class[class_id]["combined_ok"] += final_step == expected
            per_class[class_id]["temporal_ok"] += stable_step == expected
            # This is a pre-Java bilateral pose gate only; this offline replay
            # does not execute the Java session state machine or its transitions.
            per_class[class_id]["bilateral_gated_ok"] += (
                stable_step == expected and has_pair
            )
            per_class[class_id]["classifier_ok"] += classifier_step == expected
            per_class[class_id]["frames"] += 1
            if args.trace_class == class_id:
                classifier_kind, classifier_name, classifier_confidence = (
                    derived_classifier_decision(classification, args.classifier_confidence)
                )
                top1_id = int(classification.probs.top1)
                top1_name = classifier.names[top1_id]
                detected = (f"{detector_step}:{detector_confidence:.2f}"
                            if detector_step is not None and detector_confidence is not None
                            else "SIN_PASO")
                classified = (f"{top1_name}:{float(classification.probs.top1conf):.2f}"
                              if classification.probs is not None else "SIN_CLASIFICACION")
                selected = (f"{final_step}:{final_confidence:.2f}"
                            if final_step is not None and final_confidence is not None
                            else "ABSTENCION")
                print(
                    f"TRACE frame={frame_index} t={capture_time:.3f}s "
                    f"pose={pose_evidence['manosVisibles']} "
                    f"pose_inicio={pose_evidence['_manosParaInicio']} "
                    f"medicion={bool(pose_evidence.get('medicionValida'))} "
                    f"roi={'manos' if crop_bounds is not None else 'cuadro_completo'} "
                    f"detector={detected} clasificador={classified} "
                    f"decision_clasificador={classifier_kind}:{classifier_name or '-'}"
                    f"{'' if classifier_confidence is None else f'/{classifier_confidence:.2f}'} "
                    f"seleccion={selected} temporal={stable_step or 'PENDIENTE'}",
                    flush=True,
                )

    print(f"Held-out video: {args.video}; frames: {len(sequence)}")
    print(f"Replay timebase: source_frame_index / {args.source_fps:g} FPS "
          "(verify this against the original video metadata)")
    print(f"Detector agreement steps 1-6: "
          f"{sum(c['detector_ok'] for c in per_class.values())}/"
          f"{sum(c['frames'] for c in per_class.values())}")
    print(f"Per-frame detector/fallback proposals steps 1-6 (before Java evidence): "
          f"{sum(c['combined_ok'] for c in per_class.values())}/"
          f"{sum(c['frames'] for c in per_class.values())}")
    print(f"After capturer temporal filter (before Java session state): "
          f"{sum(c['temporal_ok'] for c in per_class.values())}/"
          f"{sum(c['frames'] for c in per_class.values())}")
    print(f"After capturer temporal filter plus bilateral pose gate (before Java state machine): "
          f"{sum(c['bilateral_gated_ok'] for c in per_class.values())}/"
          f"{sum(c['frames'] for c in per_class.values())}")
    print(f"Classifier shadow agreement steps 1-6 (ungated): "
          f"{classifier_shadow_correct}/{classifier_shadow_total}")
    print(f"Frames with two poses: {paired_pose_frames}/{len(sequence)}; "
          f"strict start poses: {strict_intention_pose_frames}/{len(sequence)}; "
          f"same-frame valid motion measurements: {motion_frames}/{len(sequence)}; "
          f"two raw boxes (no pose validation): {raw_box_pair_frames}/{len(sequence)}")
    strict_gaps = [
        (current_index - previous_index, current_time - previous_time)
        for (previous_index, previous_time), (current_index, current_time)
        in zip(strict_start_observations, strict_start_observations[1:])
    ]
    consecutive_strict_pairs = sum(0 < gap_seconds <= 0.65 for _, gap_seconds in strict_gaps)
    print(f"Strict two-hand pose pairs within Java's 650 ms freshness window: "
          f"{consecutive_strict_pairs} among {len(strict_start_observations)} strict observations; "
          f"source-frame/time gaps={[(frames, round(seconds, 3)) for frames, seconds in strict_gaps]}")
    print(f"Classifier ran {classifier_attempts} times; "
          f"produced a compatible step {classifier_successes} times")
    print(f"Detector used hand crops on {crop_detector_frames} frames and full-frame "
          f"fallback on {full_frame_fallback_frames}; replay start-gate Palmas observations: "
          f"{start_valid_frames}; starts confirmed by the replay approximation: {confirmed_starts}")
    for step, counts in per_class.items():
        print(f"Step {step}: detector {counts['detector_ok']}/{counts['frames']}; "
              f"classifier {counts['classifier_ok']}/{counts['frames']}; "
              f"two poses {counts['bilateral_pose_frames']}/{counts['frames']}; "
              f"hand ROI {counts['roi_crop_frames']}/{counts['frames']}; "
              f"strict start poses {counts['strict_start_pose_frames']}/{counts['frames']}; "
              f"valid motion {counts['valid_motion_frames']}/{counts['frames']}; "
              f"combined {counts['combined_ok']}/{counts['frames']}; "
              f"temporal {counts['temporal_ok']}/{counts['frames']}; "
              f"bilateral-gated {counts['bilateral_gated_ok']}/{counts['frames']}")
    print("Inference-only replay; no frames were written and no model was trained.")


if __name__ == "__main__":
    main()
