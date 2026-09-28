"""Finger Tapping analysis pipeline.

    video -> OpenCV -> MediaPipe HandLandmarker -> 21 keypoints -> target hand
          -> PALM_REFERENCE normalization -> thumb/index aperture series
          -> Butterworth low-pass -> peaks/troughs -> cycles -> 12 features
          -> quality gates

Algorithm semantics come from the external repository
D:\\CodingData\\Github\\VideoBased-PD-Biomarkers (Apache-2.0, unmodified) and are
documented, with deviations, in docs/metric_definitions.md section 1 and in the
module docstrings of signal.py / features.py.

Design notes
============
* The pipeline is a pure function of (video bytes, hand). It never invents a
  value: anything unmeasurable is None.
* `severity_score` and `severity_label` are always None. The upstream repository
  ships no trained severity model and no inference entry point (verified in
  Phase 0), so producing such a number would be fabrication.
* MediaPipe's handedness follows the mirrored/webcam convention. The external
  repository compares it directly against the requested hand without
  correction. That is preserved here, but flagged in analysis_config as
  "TBD" because it has not been validated against real recordings with a known
  hand. A `handedness_note` is included in the result so a reviewer can see it.
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from app.core.config import settings
from app.core.errors import APIError, ErrorCode
from app.core.logging import get_logger
from app.ml.finger_tapping import features as feature_module
from app.ml.finger_tapping import quality as qc
from app.ml.finger_tapping.signal import (
    DEFAULT_FILTER_CUTOFF_HZ,
    DEFAULT_FILTER_ORDER,
    HandObservation,
    aperture_from_normalized,
    lowpass_filter,
    normalize_landmarks,
    observations_to_signal,
)

logger = get_logger(__name__)

# MediaPipe emits a fair amount of C++ logging at INFO/WARNING level.
for _noisy in ("mediapipe", "absl"):
    logging.getLogger(_noisy).setLevel(logging.ERROR)

TARGET_HAND = {"LEFT": "Left", "RIGHT": "Right"}


@dataclass
class AnalysisOutcome:
    """Everything one analysis produced."""

    hand: str
    features: dict[str, Any]
    quality: dict[str, Any]
    analysis_config: dict[str, Any]
    raw_features: dict[str, Any]
    timeseries: dict[str, list[float]] = field(default_factory=dict)
    # Always None -- see module docstring.
    severity_score: float | None = None
    severity_label: str | None = None
    analyzer_version: str = settings.ft_feature_algorithm_version
    qc_version: str = settings.ft_qc_algorithm_version
    feature_schema_version: str = settings.feature_schema_version
    inference_time_ms: int | None = None
    handedness_note: str = ""


def resolve_landmarker_path() -> Path:
    path = settings.mediapipe_model_path
    if not path.is_file():
        raise APIError(
            503,
            ErrorCode.MODEL_UNAVAILABLE,
            "未找到 MediaPipe Hand Landmarker 模型文件，无法进行 Finger Tapping 分析。",
            {
                "expected_path": str(path),
                "hint": (
                    "把 hand_landmarker.task 放到 models/mediapipe/ 下，"
                    "或设置 HAND_LANDMARKER_PATH，"
                    "也可从外部仓库 src/demo/ 复制。"
                ),
                "expected_sha256": settings.hand_landmarker_sha256,
            },
        )
    return path


def _import_cv2_and_mediapipe():
    """Import heavy CV dependencies lazily so the app starts without them."""
    try:
        import cv2  # noqa: PLC0415
        import mediapipe as mp  # noqa: PLC0415
    except ImportError as exc:
        raise APIError(
            503,
            ErrorCode.MODEL_UNAVAILABLE,
            "Finger Tapping 分析依赖未安装（需要 opencv-contrib-python 与 mediapipe）。",
            {"missing": str(exc)},
        ) from exc
    return cv2, mp


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def analyze_video(video_path: str, hand: str) -> AnalysisOutcome:
    """Analyse one hand in one video.

    Raises APIError with a specific code when the input cannot support the
    analysis (see app/ml/finger_tapping/quality.py).
    """
    hand = (hand or "").upper()
    if hand not in TARGET_HAND:
        raise APIError(
            422,
            ErrorCode.VALIDATION_ERROR,
            "hand 必须是 LEFT 或 RIGHT。",
            {"hand": hand},
        )

    video = Path(video_path)
    if not video.is_file():
        raise APIError(
            400, ErrorCode.VIDEO_UNREADABLE, "视频文件不存在或不可读。",
            {"path": video_path},
        )

    cv2, mp = _import_cv2_and_mediapipe()
    landmarker_path = resolve_landmarker_path()

    started = time.perf_counter()

    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        # Report through the same quality envelope as every other rejection, so
        # the caller always has one shape to handle.
        report = qc.QualityReport()
        report.error_code = "VIDEO_UNREADABLE"
        report.error_message = (
            "OpenCV 无法打开该视频文件，请确认文件未损坏且格式为 mp4 / mov / avi。"
        )
        _fail(report, hand, started)

    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        report = qc.evaluate_video_metadata(
            fps=fps, frame_count=frame_count, width=width or None, height=height or None
        )
        if report.error_code:
            return _fail(report, hand, started)

        observations, detected_flags, handedness_scores = _decode(
            cap, cv2, mp, landmarker_path, hand
        )
    finally:
        cap.release()

    report = qc.evaluate_detection(
        report,
        detected_flags=detected_flags,
        handedness_scores=handedness_scores,
        filter_fs_hz=fps,
        filter_order=DEFAULT_FILTER_ORDER,
        filter_cutoff_hz=DEFAULT_FILTER_CUTOFF_HZ,
    )
    if report.error_code:
        return _fail(report, hand, started)

    # ------------------------------------------------------------- time series
    raw_signal = observations_to_signal(observations)
    filtered = lowpass_filter(
        raw_signal, fps=fps, order=DEFAULT_FILTER_ORDER, cutoff_hz=DEFAULT_FILTER_CUTOFF_HZ
    )
    report.notes.extend(n for n in filtered.notes if n not in report.notes)
    report.analyzed_samples = len(filtered)
    report.feature_schema_version = settings.feature_schema_version

    # ---------------------------------------------------------------- features
    feature_set = feature_module.extract_features(filtered, fps)
    report.notes.extend(n for n in feature_set.notes if n not in report.notes)

    report = qc.evaluate_cycles(report, len(feature_set.cycle_durations) or None)
    if not report.passed:
        return _fail(report, hand, started, feature_set=feature_set, signal=filtered)

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "finger tapping analysed: hand=%s frames=%d cycles=%d freq=%s elapsed=%dms",
        hand,
        report.frame_count,
        len(feature_set.cycle_durations),
        feature_set.tapping_frequency,
        elapsed_ms,
    )

    raw_features = feature_set.to_raw(include_series=True)
    raw_features["signal_sample_count"] = len(filtered)
    raw_features["handedness_labels_seen"] = sorted(
        {label for label in raw_signal.handedness_labels if label}
    )
    raw_features["landmarker_sha256"] = _sha256_of(landmarker_path)
    raw_features["mean_palm_reference"] = (
        float(np.mean(raw_signal.palm_references)) if raw_signal.palm_references else None
    )

    timeseries = {
        "frame_index": [int(f) for f in filtered.frame_indices],
        "timestamp_ms": [int(t) for t in filtered.timestamps_ms],
        "aperture_raw": [float(v) for v in raw_signal.values],
        "aperture_filtered": [float(v) for v in filtered.values],
    }

    return AnalysisOutcome(
        hand=hand,
        features=feature_set.to_features(),
        quality=report.to_dict(),
        analysis_config=report.analysis_config,
        raw_features=raw_features,
        timeseries=timeseries,
        inference_time_ms=elapsed_ms,
        handedness_note=(
            "MediaPipe 手别按镜像（前置摄像头）约定输出，外部算法仓库直接比对未做纠正。"
            "本系统沿用该行为，但该约定尚未用已知手别的真实录制验证，"
            "因此 analysis_config.handedness_convention 标记为 TBD。"
        ),
    )


def _decode(cap, cv2, mp, landmarker_path: Path, hand: str):
    """Read every frame, keep the frames where the target hand is present."""
    target_label = TARGET_HAND[hand]

    options = mp.tasks.vision.HandLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_buffer=landmarker_path.read_bytes()),
        num_hands=2,
        running_mode=mp.tasks.vision.RunningMode.VIDEO,
    )
    landmarker = mp.tasks.vision.HandLandmarker.create_from_options(options)

    observations: list[HandObservation] = []
    detected_flags: list[bool] = []
    handedness_scores: list[float | None] = []
    frame_index = 0

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            timestamp_ms = int(cap.get(cv2.CAP_PROP_POS_MSEC))
            result = landmarker.detect_for_video(
                mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), timestamp_ms
            )

            matched_landmarks = None
            matched_label = None
            matched_score = None
            for idx, handedness in enumerate(result.handedness or []):
                if handedness and handedness[0].category_name == target_label:
                    matched_landmarks = result.hand_landmarks[idx]
                    matched_label = handedness[0].category_name
                    matched_score = float(handedness[0].score)
                    break

            if matched_landmarks:
                normalized, palm_reference = normalize_landmarks(matched_landmarks)
                observations.append(
                    HandObservation(
                        frame_index=frame_index,
                        timestamp_ms=timestamp_ms,
                        handedness_label=matched_label,
                        handedness_score=matched_score,
                        normalized=normalized,
                        raw=[(lm.x, lm.y, lm.z) for lm in matched_landmarks],
                        palm_reference=palm_reference,
                    )
                )
                detected_flags.append(True)
                handedness_scores.append(matched_score)
            else:
                detected_flags.append(False)
                handedness_scores.append(None)

            frame_index += 1
    finally:
        landmarker.close()

    return observations, detected_flags, handedness_scores


def _fail(report, hand: str, started: float, *, feature_set=None, signal=None) -> AnalysisOutcome:
    """Build a failed outcome and raise the matching APIError.

    `quality` is attached to the error detail so the caller sees *why* the
    recording was rejected (which ratio failed, how many cycles were found).
    """
    detail: dict[str, Any] = {"quality": report.to_dict()}
    if feature_set is not None:
        detail["partial_features"] = feature_set.to_features()

    raise APIError(
        422,
        report.error_code or ErrorCode.INFERENCE_FAILED,
        report.error_message or "视频质量不足，无法完成分析。",
        detail,
    )


def analyze_bytes(content: bytes, hand: str, *, suffix: str = ".mp4") -> AnalysisOutcome:
    """Convenience wrapper writing bytes to a temporary file first."""
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
        tmp.write(content)
        tmp.flush()
        return analyze_video(tmp.name, hand)


__all__ = [
    "AnalysisOutcome",
    "analyze_video",
    "analyze_bytes",
    "resolve_landmarker_path",
    "aperture_from_normalized",
]
