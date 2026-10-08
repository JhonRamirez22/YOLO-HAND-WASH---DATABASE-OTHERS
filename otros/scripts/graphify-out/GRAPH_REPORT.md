# Graph Report - scripts  (2026-10-07)

## Corpus Check
- 33 files · ~44,646 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 598 nodes · 1204 edges · 34 communities (23 shown, 11 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 38 edges (avg confidence: 0.7)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `bebe2e09`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- run_handwash_station.py
- prepare_grouped_yolo_dataset.py
- train_handwash_who.py
- test_run_yolo26_continuity_camera.py
- StationSupervisorPolicyTest
- ContinuityCameraDetectionTest
- train_handwash_robust.py
- HandMotionEstimator
- MotionTest
- DerivedSequenceEvaluationTest
- MjpegFrameServer
- Any
- prepare_dataset5.py
- Queue
- run_yolo26_continuity_camera.py
- run
- verify_model_artifact
- train_handwash_mfh.py
- TemporalStepFilter
- best_detection
- validate_active_step_manifest
- validate_step_model
- train_hand_hygiene_transfer.py
- rebalance_dataset.py
- main
- start_handwash.sh
- ProducerEpochStream
- CameraFrameSequence
- hand_framing_hint
- audit_dependencies.sh
- build_handwash_station.sh
- run_backend_yolo_foreground.sh
- verify_handwash_project.sh

## God Nodes (most connected - your core abstractions)
1. `ContinuityCameraDetectionTest` - 94 edges
2. `StationSupervisorPolicyTest` - 42 edges
3. `run()` - 32 edges
4. `main()` - 24 edges
5. `validate_step_model()` - 21 edges
6. `best_detection()` - 20 edges
7. `TemporalStepFilter` - 17 edges
8. `StationSupervisor` - 16 edges
9. `HandMotionEstimator` - 16 edges
10. `find_duplicate_candidates()` - 15 edges

## Surprising Connections (you probably didn't know these)
- `main()` --uses--> `HandMotionEstimator`  [INFERRED]
  scripts/evaluate_derived_detector.py → scripts/run_yolo26_continuity_camera.py
- `main()` --uses--> `HandMotionEstimator`  [INFERRED]
  scripts/evaluate_derived_sequence.py → scripts/run_yolo26_continuity_camera.py
- `main()` --uses--> `TemporalStepFilter`  [INFERRED]
  scripts/evaluate_derived_sequence.py → scripts/run_yolo26_continuity_camera.py
- `ContinuityCameraDetectionTest` --uses--> `HandMotionEstimator`  [INFERRED]
  scripts/test_run_yolo26_continuity_camera.py → scripts/run_yolo26_continuity_camera.py
- `ContinuityCameraDetectionTest` --uses--> `TemporalStepFilter`  [INFERRED]
  scripts/test_run_yolo26_continuity_camera.py → scripts/run_yolo26_continuity_camera.py

## Import Cycles
- None detected.

## Communities (34 total, 11 thin omitted)

### Community 0 - "run_handwash_station.py"
Cohesion: 0.06
Nodes (46): backend_matches_station(), camera_child_environment(), camera_exit_decision(), _file_identity_unchanged(), hospital_readiness_blockers(), main(), _open_regular_file_no_follow(), pairing_code_from_output() (+38 more)

### Community 1 - "prepare_grouped_yolo_dataset.py"
Cohesion: 0.08
Nodes (34): _dataset_split_paths(), DuplicateCandidate, find_duplicate_candidates(), _image_paths(), ImageSignature, main(), parse_args(), Namespace (+26 more)

### Community 2 - "train_handwash_who.py"
Cohesion: 0.10
Nodes (25): extract_video(), load_manifest(), main(), prepare(), Path, VideoEntry, PrepareOmsReviewFramesTest, TrainHandwashWhoValidationTest (+17 more)

### Community 3 - "test_run_yolo26_continuity_camera.py"
Cohesion: 0.09
Nodes (36): Shared, lightweight dataset taxonomy contracts used by runtime and audits., main(), main(), arbitrate_uncertain_detection(), box_coordinates(), classifier_fallback_allowed(), compatible_classifier_step(), derived_classifier_decision() (+28 more)

### Community 4 - "StationSupervisorPolicyTest"
Cohesion: 0.06
Nodes (3): skipUnless, ready_station_manifest(), StationSupervisorPolicyTest

### Community 6 - "train_handwash_robust.py"
Cohesion: 0.14
Nodes (20): ndarray, Path, RobustTrainingSplitGateTest, audit_prepared_splits(), download_dataset(), ensure_fresh_run_paths(), main(), merge_split() (+12 more)

### Community 7 - "HandMotionEstimator"
Cohesion: 0.12
Nodes (10): detected_hands(), hand_pose_candidates(), hand_pose_proposal_count(), HandMotionEstimator, Count raw pose boxes before keypoint validation and duplicate suppression., Return distinct hand poses; overlapping duplicate predictions are not two hands., Compare adjacent usable hand snapshots without re-counting frame retries.…, Keep the best keypoint result for this capture, without retaining frames. (+2 more)

### Community 8 - "MotionTest"
Cohesion: 0.14
Nodes (4): MotionTest, poses(), Synthetic keypoint checks only; no camera access or image recording., Tensor

### Community 9 - "DerivedSequenceEvaluationTest"
Cohesion: 0.19
Nodes (10): load_test_sequence(), Path, One source frame may contribute only one class vote in a replay., Convert source frame indices using an explicit/declared source FPS., Load a held-out video only after validating split and annotation integrity., source_frame_time_seconds(), validate_unique_source_frames(), DerivedSequenceEvaluationTest (+2 more)

### Community 10 - "MjpegFrameServer"
Cohesion: 0.11
Nodes (11): draw_hand_boxes(), draw_hand_focus_inset(), draw_step_boxes(), is_local_dashboard_origin(), MjpegFrameServer, ndarray, Overlay the pre-trained hand detector boxes without retaining video., Show the live hand-focused crop; the main-frame border marks the last analyzed… (+3 more)

### Community 11 - "Any"
Cohesion: 0.16
Nodes (15): Exception, classifier_challenge_allowed(), motion_evidence_matches_frame(), normalized_confidence(), oms_spatial_evidence_is_valid(), PermanentDetectionRejection, Any, The Java API rejected a request that retrying cannot repair. (+7 more)

### Community 12 - "prepare_dataset5.py"
Cohesion: 0.19
Nodes (14): balance_classes(), consensus_annotation(), copy_existing_dataset(), create_yaml(), extract_frames_and_annotate(), load_annotations(), main(), DataSet5 Dataset Preparation Pipeline =====================================… (+6 more)

### Community 13 - "Queue"
Cohesion: 0.31
Nodes (5): Event, Queue, detection_sender(), enqueue_latest_detection(), Send detections off the video thread; bounded queue favors fresh state.

### Community 14 - "run_yolo26_continuity_camera.py"
Cohesion: 0.22
Nodes (12): avfoundation_listing(), camera_name(), continuity_camera_index(), overlap_fraction(), Popen, Geometrically deduplicate pose-valid and box-only views of one hand., Fraction of inner box covered by outer box, independent of box size., Open the currently enumerated iPhone only; no desktop/webcam fallback. (+4 more)

### Community 15 - "run"
Cohesion: 0.15
Nodes (12): create_session(), monitor_session(), pair_session(), parse_args(), Namespace, Only retain temporal votes across a bounded interval of real camera time., Publish transitions immediately; keep same-step traffic bounded., Stop local camera capture when Java deletes or finishes its session. (+4 more)

### Community 16 - "verify_model_artifact"
Cohesion: 0.18
Nodes (5): Fail closed when a runtime weight is missing or differs from its recorded…, Explain that generic ordinal labels are structural aliases, not verified…, sequential_label_taxonomy_warning(), verify_model_artifact(), main()

### Community 17 - "train_handwash_mfh.py"
Cohesion: 0.35
Nodes (11): label_for_path(), link_or_copy(), main(), parse_args(), prepare_dataset(), Namespace, Path, Find Step1..Step7 in any ancestor; tolerate left/right suffixes. (+3 more)

### Community 20 - "validate_active_step_manifest"
Cohesion: 0.22
Nodes (6): canonical_step_name(), Path, Keep the active checkpoint's real class-ID order aligned with its signed…, Normalize only the explicitly supported canonical and paso_1..paso_7 labels., _reject_duplicate_manifest_keys(), validate_active_step_manifest()

### Community 22 - "train_hand_hygiene_transfer.py"
Cohesion: 0.42
Nodes (8): choose_device(), class_names(), main(), Any, Path, validate_inputs(), validate_split(), write_dataset_yaml()

### Community 23 - "rebalance_dataset.py"
Cohesion: 0.38
Nodes (6): count_classes(), main(), Aggressive Dataset Rebalancing ============================== - Cap Fondo class…, Count instances per class across all label files., Rebalance a split (train or val) to target_count per class., rebalance_split()

### Community 24 - "main"
Cohesion: 0.47
Nodes (5): labeled_crop(), main(), parse_args(), Namespace, Path

### Community 25 - "start_handwash.sh"
Cohesion: 0.53
Nodes (4): require_command(), start_handwash.sh script, start_if_missing(), wait_for_http()

## Knowledge Gaps
- **5 isolated node(s):** `audit_dependencies.sh script`, `build_handwash_station.sh script`, `run_backend_yolo_foreground.sh script`, `RestartDecision`, `verify_handwash_project.sh script`
  These have ≤1 connection - possible missing edges or undocumented components.
- **11 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `train()` connect `train_handwash_robust.py` to `test_run_yolo26_continuity_camera.py`?**
  _High betweenness centrality (0.188) - this node is a cross-community bridge._
- **Why does `ContinuityCameraDetectionTest` connect `ContinuityCameraDetectionTest` to `test_run_yolo26_continuity_camera.py`, `HandMotionEstimator`, `Queue`, `run`, `verify_model_artifact`, `TemporalStepFilter`, `best_detection`, `validate_active_step_manifest`, `validate_step_model`, `hand_framing_hint`?**
  _High betweenness centrality (0.110) - this node is a cross-community bridge._
- **Why does `main()` connect `train_handwash_who.py` to `test_run_yolo26_continuity_camera.py`?**
  _High betweenness centrality (0.107) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `ContinuityCameraDetectionTest` (e.g. with `HandMotionEstimator` and `TemporalStepFilter`) actually correct?**
  _`ContinuityCameraDetectionTest` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `run()` (e.g. with `detection_sender()` and `monitor_session()`) actually correct?**
  _`run()` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `main()` (e.g. with `HandMotionEstimator` and `TemporalStepFilter`) actually correct?**
  _`main()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `audit_dependencies.sh script`, `build_handwash_station.sh script`, `run_backend_yolo_foreground.sh script` to the rest of the system?**
  _5 weakly-connected nodes found - possible documentation gaps or missing edges._