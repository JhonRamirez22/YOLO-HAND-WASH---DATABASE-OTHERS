#!/usr/bin/env python3
"""Check the active detector on the supplied classifier's held-out test frames.

This is inference only; it does not train or write images. Whole-frame class
agreement is a domain-transfer diagnostic, not detection mAP or clinical proof.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
import re
import time

import cv2
from ultralytics import YOLO

from run_yolo26_continuity_camera import (
    DEFAULT_HAND_POSE_CONFIDENCE, DEFAULT_HAND_POSE_IMAGE_SIZE,
    DERIVED_CLASSIFIER_NAMES, HandMotionEstimator, best_detection,
    arbitrate_uncertain_detection, compatible_classifier_step,
    derived_classifier_decision,
    hand_crop_bounds, partial_crop_guidance_hands,
    background_vetoes_detection, prefer_recovered_localization, prefer_recovered_motion,
    recover_hand_pose, validate_derived_classifier, validate_hand_model,
    validate_step_model,
)


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "ENTRENAMIENTO/derived_handwash_yolo26_cls_2fps_2026-09-26"
MODEL = ROOT / "backend/models/handwash_yolo26n_7pasos.pt"
CLASSIFIER = ROOT / "backend/models/handwash_who_yolo26m_cls.pt"
POSE_MODEL = ROOT / "backend/models/yolo26s-pose-hands.pt"
CAMERA_ID_PATTERN = re.compile(r"_camera(\d+)_")


def camera_id_from_path(path: Path) -> str:
    match = CAMERA_ID_PATTERN.search(path.name)
    return match.group(1) if match else "unknown"


def matches_expected_class(expected_prefix: str | None, prediction: str | None) -> bool:
    if expected_prefix is None:
        return prediction is None
    return prediction is not None and prediction.startswith(expected_prefix)


def recover_pose_for_diagnostic(model, frame, pose_result, pose, crop_hands,
                                predict_options, confidence):
    """Use the live capturer's high-resolution and tiled recovery for one frame."""
    if pose["manosVisibles"] >= 2:
        return pose_result, pose, crop_hands, 0

    recovered_result, tile_inferences = recover_hand_pose(
        model, frame, predict_options, confidence
    )
    recovered_pose = HandMotionEstimator().update(
        recovered_result, 1, 1.0, confidence
    )
    recovered_crop_hands = partial_crop_guidance_hands(
        recovered_result, confidence, 0.15
    )
    if prefer_recovered_motion(recovered_pose, pose):
        pose_result, pose = recovered_result, recovered_pose
    if prefer_recovered_localization(recovered_crop_hands, crop_hands):
        crop_hands = recovered_crop_hands
    # recover_hand_pose always performs one high-resolution full-frame pass;
    # tile_inferences counts the optional pair of overlapping crop inferences.
    return pose_result, pose, crop_hands, 1 + tile_inferences


def sample_class_paths(paths: list[Path], per_class: int,
                       per_camera: int = 0) -> list[Path]:
    ordered = sorted(paths)
    if not ordered:
        return []
    if per_camera == 0:
        count = min(per_class, len(ordered))
        indexes = [((2 * index + 1) * len(ordered)) // (2 * count)
                   for index in range(count)]
        return [ordered[index] for index in indexes]

    by_camera: dict[str, list[Path]] = defaultdict(list)
    for path in ordered:
        by_camera[camera_id_from_path(path)].append(path)
    samples = []
    for camera in sorted(by_camera):
        camera_paths = by_camera[camera]
        count = min(per_camera, len(camera_paths))
        indexes = [((2 * index + 1) * len(camera_paths)) // (2 * count)
                   for index in range(count)]
        samples.extend(camera_paths[index] for index in indexes)
    return samples


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--model", type=Path, default=MODEL)
    parser.add_argument("--classifier", type=Path, default=CLASSIFIER)
    parser.add_argument("--pose-model", type=Path, default=POSE_MODEL)
    parser.add_argument("--with-pose", action="store_true",
                        help="Count frames with two confident hand poses (upper bound for live fallback)")
    parser.add_argument("--pose-imgsz", type=int, default=DEFAULT_HAND_POSE_IMAGE_SIZE,
                        help="Resolución primaria de pose; por defecto coincide con el capturador")
    parser.add_argument("--pose-recovery-imgsz", type=int, default=640)
    parser.add_argument("--pose-box-confidence", type=float, default=DEFAULT_HAND_POSE_CONFIDENCE,
                        help="Confianza de caja mínima para aceptar propuestas de pose")
    parser.add_argument("--pose-iou", type=float, default=0.90)
    parser.add_argument("--pose-max-det", type=int, default=16)
    parser.add_argument("--classifier-confidence", type=float, default=0.75)
    parser.add_argument("--detector-challenge-below", type=float, default=0.80,
                        help="Simula challenge si el detector queda por debajo de este score")
    parser.add_argument("--classifier-margin", type=float, default=0.10)
    classifier_policy = parser.add_mutually_exclusive_group()
    classifier_policy.add_argument("--classifier-authoritative", dest="classifier_authoritative",
                                   action="store_true")
    classifier_policy.add_argument("--classifier-guarded", dest="classifier_authoritative",
                                   action="store_false")
    parser.set_defaults(classifier_authoritative=True)
    parser.add_argument("--pose-roi", nargs=4, type=float, default=None,
                        metavar=("X1", "Y1", "X2", "Y2"),
                        help="Optional normalized x1 y1 x2 y2 region to enlarge for hand pose")
    parser.add_argument("--per-class", type=int, default=20)
    parser.add_argument("--per-camera", type=int, default=0,
                        help="Sample up to N frames per camera and class; 0 keeps --per-class sampling")
    args = parser.parse_args()
    if args.per_class <= 0:
        parser.error("--per-class must be positive")
    if args.per_camera < 0:
        parser.error("--per-camera cannot be negative")
    if args.pose_imgsz < 160 or args.pose_imgsz % 32 != 0:
        parser.error("--pose-imgsz debe ser múltiplo de 32 y no menor que 160")
    if args.pose_recovery_imgsz < args.pose_imgsz or args.pose_recovery_imgsz % 32 != 0:
        parser.error("--pose-recovery-imgsz debe ser múltiplo de 32 y no menor que --pose-imgsz")
    if not 0.0 < args.pose_box_confidence <= 1.0:
        parser.error("--pose-box-confidence debe estar en (0, 1]")
    if not 0.1 <= args.pose_iou <= 0.95:
        parser.error("--pose-iou debe estar entre 0,1 y 0,95")
    if not 2 <= args.pose_max_det <= 64:
        parser.error("--pose-max-det debe estar entre 2 y 64")
    if not 0 <= args.classifier_confidence <= 1:
        parser.error("--classifier-confidence debe estar en [0, 1]")
    if not 0 <= args.detector_challenge_below <= 1:
        parser.error("--detector-challenge-below debe estar en [0, 1]")
    if not 0 <= args.classifier_margin <= 1:
        parser.error("--classifier-margin debe estar en [0, 1]")
    model = YOLO(str(args.model))
    _, mode = validate_step_model(model, str(args.model))
    if mode != "FRICCION_PARCIAL":
        parser.error("Expected a seven-step partial-friction detector")
    classifier = YOLO(str(args.classifier))
    validate_derived_classifier(classifier, str(args.classifier))
    pose_model = YOLO(str(args.pose_model)) if args.with_pose else None
    if pose_model is not None:
        validate_hand_model(pose_model, str(args.pose_model))
    pose_predict_options = {
        "imgsz": args.pose_imgsz,
        "conf": args.pose_box_confidence,
        "max_det": args.pose_max_det,
        "iou": args.pose_iou,
        "device": "cpu",
        "verbose": False,
        "save": False,
    }
    pose_recovery_options = {
        **pose_predict_options,
        "imgsz": args.pose_recovery_imgsz,
    }
    fallback_latencies = []
    challenge_correct_total = challenge_sample_total = challenge_false_step_negatives = 0
    classifier_correct_total = classifier_sample_total = classifier_false_step_negatives = 0
    all_challenge_sources: Counter[str] = Counter()
    two_hand_pose_correct_total = two_hand_pose_frame_total = 0
    two_hand_pose_false_step_total = single_frame_motion_valid_total = 0
    pose_recovery_inferences_total = 0
    camera_totals: dict[str, Counter[str]] = defaultdict(Counter)

    # Include all three non-step classes: other washing, faucet closure, and
    # not washing. They must all remain negative for the six-step fallback.
    for class_id in range(len(DERIVED_CLASSIFIER_NAMES)):
        folder = args.dataset / "test" / DERIVED_CLASSIFIER_NAMES[class_id]
        paths = sorted(folder.glob("*.jpg"))
        if not paths:
            parser.error(f"No held-out frames in {folder}")
        # Deterministically sample held-out frames; camera mode balances each
        # available camera within every action class for view diagnostics.
        samples = sample_class_paths(paths, args.per_class, args.per_camera)
        predicted: Counter[str] = Counter()
        classifier_predictions: Counter[str] = Counter()
        with_fallback: Counter[str] = Counter()
        challenged: Counter[str] = Counter()
        challenge_sources: Counter[str] = Counter()
        two_hand_pose = 0
        pose_crop_frames = 0
        fallback_eligible_frames = 0
        two_hand_pose_frames = two_hand_pose_correct = two_hand_pose_false_steps = 0
        single_frame_motion_valid = 0
        expected = f"Paso{class_id}_" if 1 <= class_id <= 6 else None
        for path in samples:
            frame = cv2.imread(str(path))
            if frame is None:
                raise RuntimeError(f"Unreadable frame: {path}")
            detector_name = None
            name = None
            has_two_hands = False
            crop_hands = []
            pose_recovery_inferences = 0
            pose_frame = frame
            if pose_model is not None:
                if args.pose_roi:
                    frame_h, frame_w = frame.shape[:2]
                    x1, y1, x2, y2 = args.pose_roi
                    pose_frame = frame[
                        max(0, round(y1 * frame_h)):min(frame_h, round(y2 * frame_h)),
                        max(0, round(x1 * frame_w)):min(frame_w, round(x2 * frame_w)),
                    ]
                    if pose_frame.size == 0:
                        parser.error("--pose-roi produced an empty crop")
                pose_result = pose_model.predict(
                    pose_frame, **pose_predict_options
                )[0]
                # Per-frame count only. An isolated photo cannot establish the
                # inter-frame motion measurement required by the live system.
                pose = HandMotionEstimator().update(
                    pose_result, 1, 1.0, args.pose_box_confidence
                )
                crop_hands = partial_crop_guidance_hands(
                    pose_result, args.pose_box_confidence, 0.15
                )
                pose_result, pose, crop_hands, pose_recovery_inferences = (
                    recover_pose_for_diagnostic(
                        pose_model, pose_frame, pose_result, pose, crop_hands,
                        pose_recovery_options, args.pose_box_confidence,
                    )
                )
                pose_recovery_inferences_total += pose_recovery_inferences
                has_two_hands = pose["manosVisibles"] >= 2
                two_hand_pose += has_two_hands
                single_frame_motion_valid += bool(pose["medicionValida"])
                fresh_hand_crop = bool(crop_hands)
                pose_crop_frames += fresh_hand_crop
                crop_bounds = (
                    hand_crop_bounds(crop_hands, pose_frame.shape)
                    if crop_hands else None
                )
                if crop_bounds is None:
                    fresh_hand_crop = False
            else:
                fresh_hand_crop = False

            # Match the runtime's spatial detector path: use the hand crop at
            # 416px when available; otherwise use the conservative 640px full-
            # frame fallback. The classifier shadow below is only diagnostic.
            if fresh_hand_crop:
                left, top, right, bottom = crop_bounds
                step_frame = pose_frame[top:bottom, left:right].copy()
                result = model.predict(step_frame, imgsz=416, conf=0.35,
                                       device="cpu", verbose=False, save=False)[0]
            elif pose_model is not None:
                result = model.predict(frame, imgsz=640, conf=0.75, max_det=24,
                                       device="cpu", verbose=False, save=False)[0]
            else:
                result = model.predict(frame, imgsz=416, conf=0.35,
                                       device="cpu", verbose=False, save=False)[0]
            detector_name, detector_confidence, _ = best_detection(result, mode)
            name = detector_name
            predicted[name or "SIN_PASO"] += 1
            fallback_eligible_frames += (
                detector_name is None and has_two_hands
            ) if pose_model is not None else 0
            started = time.monotonic()
            classification = classifier.predict(frame, imgsz=320, device="cpu",
                                                verbose=False, save=False)[0]
            classifier_latency = time.monotonic() - started
            classifier_kind, classifier_step, _ = derived_classifier_decision(
                classification, args.classifier_confidence
            )
            classifier_label = classifier_step if classifier_kind == "STEP" else None
            classifier_predictions[classifier_label or "SIN_PASO"] += 1
            if pose_model is not None and has_two_hands:
                fallback_latencies.append(classifier_latency)
                challenge_name, challenge_confidence, challenge_source = (
                    arbitrate_uncertain_detection(
                        detector_name, detector_confidence, classification,
                        args.classifier_confidence, args.detector_challenge_below,
                        args.classifier_margin, args.classifier_authoritative,
                    )
                )
            else:
                challenge_name, challenge_confidence, challenge_source = (
                    detector_name, detector_confidence, "detector"
                )
            if background_vetoes_detection(result, challenge_confidence):
                challenge_name, challenge_confidence, challenge_source = None, None, "background_veto"
            challenged[challenge_name or "SIN_PASO"] += 1
            challenge_sources[challenge_source] += 1
            all_challenge_sources[challenge_source] += 1
            camera_stats = camera_totals[camera_id_from_path(path)]
            camera_stats["samples"] += 1
            camera_stats["positive_samples"] += int(expected is not None)
            camera_stats["negative_samples"] += int(expected is None)
            camera_stats["detector_correct"] += int(
                matches_expected_class(expected, detector_name))
            camera_stats["classifier_correct"] += int(
                matches_expected_class(expected, classifier_label))
            camera_stats["combined_correct"] += int(
                matches_expected_class(expected, challenge_name))
            camera_stats["negative_false_steps"] += int(
                expected is None and challenge_name is not None)
            camera_stats["two_hand_pose_frames"] += int(has_two_hands)
            camera_stats["pose_recovery_inferences"] += pose_recovery_inferences
            if name is None:
                fallback_name, fallback_confidence = compatible_classifier_step(
                    classification, args.classifier_confidence
                )
                if not background_vetoes_detection(result, fallback_confidence):
                    name = fallback_name
            with_fallback[name or "SIN_PASO"] += 1
            if pose_model is not None:
                # This is only a two-hand-pose proxy. Each image gets a fresh
                # estimator, so it cannot prove the motion evidence Java needs.
                if has_two_hands:
                    gated_name = challenge_name
                    two_hand_pose_frames += 1
                    if expected is not None:
                        two_hand_pose_correct += bool(
                            gated_name is not None and gated_name.startswith(expected)
                        )
                    else:
                        two_hand_pose_correct += gated_name is None
                        two_hand_pose_false_steps += gated_name is not None
                else:
                    gated_name = None
        two_hand_pose_correct_total += two_hand_pose_correct
        two_hand_pose_frame_total += two_hand_pose_frames
        two_hand_pose_false_step_total += two_hand_pose_false_steps
        single_frame_motion_valid_total += single_frame_motion_valid
        correct = (sum(count for name, count in predicted.items()
                       if name.startswith(expected)) if expected is not None
                   else predicted["SIN_PASO"])
        fallback_correct = (sum(count for name, count in with_fallback.items()
                                if name.startswith(expected)) if expected is not None
                            else with_fallback["SIN_PASO"])
        challenge_correct = (sum(count for name, count in challenged.items()
                                 if name.startswith(expected)) if expected is not None
                             else challenged["SIN_PASO"])
        challenge_correct_total += challenge_correct
        challenge_sample_total += len(samples)
        classifier_correct = (
            sum(count for name, count in classifier_predictions.items()
                if name.startswith(expected)) if expected is not None
            else classifier_predictions["SIN_PASO"]
        )
        classifier_correct_total += classifier_correct
        classifier_sample_total += len(samples)
        if expected is None:
            classifier_false_step_negatives += sum(
                count for name, count in classifier_predictions.items()
                if name != "SIN_PASO"
            )
        if expected is None:
            challenge_false_step_negatives += sum(
                count for name, count in challenged.items()
                if name != "SIN_PASO"
            )
        print(f"{DERIVED_CLASSIFIER_NAMES[class_id]}: detector {correct}/{len(samples)}, "
              f"classifier {classifier_correct}/{len(samples)}, "
              f"ungated classifier-on-miss {fallback_correct}/{len(samples)}; "
              f"detector predictions {dict(predicted)}; "
              f"combined predictions {dict(with_fallback)}; "
              f"pre-pose-gate candidates {dict(challenged)}", flush=True)
        if pose_model is not None:
            print(f"  two-hand-pose proxy only (not Java-eligible): "
                  f"{two_hand_pose_correct}/{two_hand_pose_frames} matches; "
                  f"two-hand poses {two_hand_pose}/{len(samples)}; "
                  f"single-frame motion measurements marked valid "
                  f"{single_frame_motion_valid}/{len(samples)}; "
                  f"fresh crop {pose_crop_frames}/{len(samples)}; "
                  f"fallback eligible {fallback_eligible_frames}/{len(samples)}", flush=True)
    if fallback_latencies:
        print(f"Classifier mean latency CPU on eligible frames: "
              f"{1000 * sum(fallback_latencies) / len(fallback_latencies):.1f} ms "
              f"over {len(fallback_latencies)} frames")
    print(f"Pre-pose-gate challenge decisions: {dict(all_challenge_sources)}; this is a sampled "
          "diagnostic, not full-session or iPhone validation.")
    print(f"Pre-gate challenge agreement: {challenge_correct_total}/{challenge_sample_total}; "
          f"unfiltered false step proposals on negative classes: "
          f"{challenge_false_step_negatives} (sampled).")
    print(f"Standalone classifier agreement: {classifier_correct_total}/{classifier_sample_total}; "
          f"false step proposals on the three negative classes: "
          f"{classifier_false_step_negatives} (sampled).")
    if pose_model is not None:
        print(f"Two-hand-pose proxy only: {two_hand_pose_correct_total}/"
              f"{two_hand_pose_frame_total} matches on frames with two poses; "
              f"{two_hand_pose_false_step_total} negative-class candidates on that proxy. "
              f"Single-frame motion evidence valid: {single_frame_motion_valid_total}; "
              "Java motion/intent/temporal/sequence acceptance was not evaluated.")
        print(f"Additional pose-recovery inferences (high-res full frame plus any tiles): "
              f"{pose_recovery_inferences_total}; inference count, not latency or FPS.")
    sample_mode = "balanced per camera/class" if args.per_camera else "global per-class sample"
    print(f"Per-camera diagnostic ({sample_mode}; not angle holdout or clinical validation):")
    for camera_id, stats in sorted(camera_totals.items()):
        total = stats["samples"]
        summary = (
            f"camera {camera_id}: {total} frames "
            f"({stats['positive_samples']} positive, {stats['negative_samples']} negative), "
            f"detector {stats['detector_correct']}/{total}, "
            f"classifier {stats['classifier_correct']}/{total}, "
            f"combined {stats['combined_correct']}/{total}, "
            f"false steps on negative classes {stats['negative_false_steps']}"
        )
        if pose_model is not None:
            summary += (f", two-hand poses {stats['two_hand_pose_frames']}/{total}, "
                        f"recovery inferences {stats['pose_recovery_inferences']}")
        print(summary)
    print("Diagnostic only: no box labels or iPhone-domain validation are supplied.")


if __name__ == "__main__":
    main()
