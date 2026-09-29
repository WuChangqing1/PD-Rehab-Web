"""Per-exercise pose analysis.

Takes a landmark series and produces the raw metrics each exercise reports, plus
the quality gates that decide whether a recording is usable at all. When a gate
fails the analysis is refused with the measured reason instead of returning a
number computed from a video that does not show the movement.

The drive series per exercise is chosen from the movement the exercise actually
asks for (spec V2 section 27), not from whatever is easiest to compute.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from app.ml.pose.exercises import EXERCISE_BY_KEY, ExerciseDefinition
from app.ml.pose.landmarks import CORE_JOINTS, PoseSeries
from app.ml.pose.metrics import (
    ANALYSIS_CONFIG,
    POSE_METRICS_ALGORITHM_VERSION,
    MovementStats,
    abduction_series,
    analyse_series,
    elbow_series,
    left_right_difference_deg,
    trunk_rotation_series,
    trunk_tilt_series,
)
from app.utils.metrics import clean_float

# Quality gate identifiers. Same shape as the finger tapping gates so the UI can
# treat "refused because of the recording" the same way in both modules.
GATE_NO_POSE_DETECTED = "NO_POSE_DETECTED"
GATE_LOW_VALID_FRAME_RATIO = "LOW_VALID_FRAME_RATIO"
GATE_VIDEO_TOO_SHORT = "VIDEO_TOO_SHORT"
GATE_LOW_LANDMARK_VISIBILITY = "LOW_LANDMARK_VISIBILITY"
GATE_NO_MOVEMENT_DETECTED = "NO_MOVEMENT_DETECTED"
GATE_INSUFFICIENT_REPETITIONS = "INSUFFICIENT_REPETITIONS"

# Which joint series drives each exercise.
DRIVE_SERIES = {
    "MOUNTAIN_ARMS_UP": "shoulder_abduction",
    "ARMS_LATERAL_RAISE": "shoulder_abduction",
    "SIDE_BEND_STRETCH": "trunk_tilt",
    "SEATED_TRUNK_ROTATION": "trunk_rotation",
    "SEATED_ALTERNATING_ARM_RAISE": "shoulder_abduction",
}

# Exercises whose trunk must be visible for the metric to mean anything.
REQUIRES_TRUNK = {"SIDE_BEND_STRETCH", "SEATED_TRUNK_ROTATION"}

TRUNK_JOINTS = (11, 12, 23, 24)


@dataclass
class PoseOutcome:
    """Result of analysing one recording."""

    exercise_key: str
    metrics: dict[str, Any]
    quality: dict[str, Any]
    warnings: list[str] = field(default_factory=list)
    gate_failures: list[str] = field(default_factory=list)
    algorithm_version: str = POSE_METRICS_ALGORITHM_VERSION

    @property
    def accepted(self) -> bool:
        return not self.gate_failures


def _pick(value: float | None) -> float | None:
    """Round for storage and drop non-finite values, which must never leak."""
    if value is None:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return clean_float(float(value))


def _stats_fields(stats: MovementStats) -> dict[str, Any]:
    return {
        "max_angle_deg": _pick(stats.peak_deg),
        "min_angle_deg": _pick(stats.min_deg),
        "range_deg": _pick(stats.range_deg),
        "hold_time_sec": _pick(stats.hold_time_sec),
        "repetition_count": stats.repetition_count,
        "repetition_interval_ms": _pick(stats.repetition_interval_ms),
        "movement_speed_deg_per_sec": _pick(stats.movement_speed_deg_per_sec),
        "angle_std_deg": _pick(stats.angle_std_deg),
        "sample_ratio": _pick(stats.valid_sample_ratio),
    }


def _gate_failures(series: PoseSeries, exercise: ExerciseDefinition, stats: MovementStats) -> list[str]:
    """Decide whether this recording can be measured at all."""
    failures: list[str] = []

    if series.valid_frame_count == 0:
        failures.append(GATE_NO_POSE_DETECTED)
        # Everything below needs at least one frame with a person in it.
        return failures

    if series.duration_sec < float(ANALYSIS_CONFIG["min_duration_sec"]):
        failures.append(GATE_VIDEO_TOO_SHORT)

    if series.valid_frame_ratio < float(ANALYSIS_CONFIG["min_valid_frame_ratio"]):
        failures.append(GATE_LOW_VALID_FRAME_RATIO)

    joints = TRUNK_JOINTS if exercise.key in REQUIRES_TRUNK else CORE_JOINTS
    visibility = series.mean_visibility(joints)
    # None means the model reported no visibility at all: that is "not measured",
    # not "measured and bad", so it must not fail the gate.
    if visibility is not None and visibility < float(ANALYSIS_CONFIG["min_landmark_visibility"]):
        failures.append(GATE_LOW_LANDMARK_VISIBILITY)

    if stats.range_deg is None or stats.range_deg < float(ANALYSIS_CONFIG["min_movement_range_deg"]):
        failures.append(GATE_NO_MOVEMENT_DETECTED)

    if stats.repetition_count < 1:
        failures.append(GATE_INSUFFICIENT_REPETITIONS)

    return failures


def analyse(series: PoseSeries, exercise_key: str) -> PoseOutcome:
    """Analyse one recording for one exercise."""
    exercise = EXERCISE_BY_KEY.get(exercise_key)
    if exercise is None:
        raise KeyError(exercise_key)

    drive = DRIVE_SERIES[exercise_key]
    fps = series.fps

    left_abduction = abduction_series(series, "left")
    right_abduction = abduction_series(series, "right")
    left_elbow = elbow_series(series, "left")
    right_elbow = elbow_series(series, "right")
    tilt = trunk_tilt_series(series)
    rotation = trunk_rotation_series(series)

    left_stats = analyse_series(left_abduction, fps)
    right_stats = analyse_series(right_abduction, fps)
    elbow_left_stats = analyse_series(left_elbow, fps)
    elbow_right_stats = analyse_series(right_elbow, fps)
    tilt_stats = analyse_series(tilt, fps)
    rotation_stats = analyse_series(rotation, fps)

    if drive == "shoulder_abduction":
        driving = analyse_series(
            [
                (a + b) / 2 if not (math.isnan(a) or math.isnan(b)) else float("nan")
                for a, b in zip(left_abduction, right_abduction)
            ],
            fps,
        )
    elif drive == "trunk_tilt":
        driving = analyse_series([abs(v) if not math.isnan(v) else float("nan") for v in tilt], fps)
    elif drive == "trunk_rotation":
        driving = analyse_series(
            [abs(v) if not math.isnan(v) else float("nan") for v in rotation], fps
        )
    else:  # pragma: no cover - DRIVE_SERIES is exhaustive
        raise KeyError(drive)

    gate_failures = _gate_failures(series, exercise, driving)

    metrics: dict[str, Any] = {
        # ---- the ten raw metrics from spec V2 section 28 ----
        "left_shoulder_max_angle_deg": _pick(left_stats.peak_deg),
        "right_shoulder_max_angle_deg": _pick(right_stats.peak_deg),
        "left_right_angle_difference_deg": _pick(
            left_right_difference_deg(left_stats.peak_deg, right_stats.peak_deg)
        ),
        "trunk_angle_deg": _pick(tilt_stats.peak_deg if drive == "trunk_tilt" else None),
        "hold_time_sec": _pick(driving.hold_time_sec),
        "repetition_count": driving.repetition_count,
        "repetition_interval_ms": _pick(driving.repetition_interval_ms),
        "movement_speed_deg_per_sec": _pick(driving.movement_speed_deg_per_sec),
        "angle_std_deg": _pick(driving.angle_std_deg),
        "valid_pose_frame_ratio": _pick(series.valid_frame_ratio),
        # ---- per-side and secondary series, stored raw ----
        "left_shoulder": _stats_fields(left_stats),
        "right_shoulder": _stats_fields(right_stats),
        "left_elbow": _stats_fields(elbow_left_stats),
        "right_elbow": _stats_fields(elbow_right_stats),
        "trunk_tilt": {
            **_stats_fields(tilt_stats),
            # Signed extremes keep the direction: which way the patient leaned.
            "positive_peak_deg": _pick(max((v for v in tilt if not math.isnan(v)), default=None)),
            "negative_peak_deg": _pick(min((v for v in tilt if not math.isnan(v)), default=None)),
        },
        "trunk_rotation": {
            **_stats_fields(rotation_stats),
            "is_monocular_proxy": True,
        },
        "left_repetition_count": left_stats.repetition_count,
        "right_repetition_count": right_stats.repetition_count,
        "drive_series": drive,
        "exercise_target_repetitions": exercise.target_repetitions,
        "exercise_target_hold_sec": exercise.hold_time_sec,
    }

    warnings: list[str] = []
    if series.truncated:
        warnings.append(
            f"录制超出分析上限：只分析了前 {series.duration_sec:.0f} 秒"
            + (
                f"（整段约 {series.source_duration_sec:.0f} 秒）"
                if series.source_duration_sec > 0
                else ""
            )
            + "。下面的指标只描述已分析的部分，请缩短录制后重测。"
        )
    if exercise.key in REQUIRES_TRUNK:
        warnings.append(
            "躯干角度由单目关键点推算；拍摄时请让髋部完整入镜，并尽量正对或侧对镜头。"
        )
    if exercise.key == "SEATED_TRUNK_ROTATION":
        warnings.append(
            "trunk_rotation 为单目深度代理量，只反映旋转方向与相对大小，不是角度真值。"
        )
    if driving.valid_sample_ratio < 1.0:
        warnings.append(
            f"仅 {driving.valid_sample_ratio * 100:.0f}% 的帧可计算该动作角度，"
            "其余帧未检出人体或关键点被遮挡。"
        )

    quality = {
        "fps": _pick(fps),
        "width": series.width,
        "height": series.height,
        "frame_count": series.frame_count,
        "valid_frame_count": series.valid_frame_count,
        "valid_pose_frame_ratio": _pick(series.valid_frame_ratio),
        "duration_sec": _pick(series.duration_sec),
        "source_duration_sec": _pick(series.source_duration_sec) or None,
        "truncated": series.truncated,
        "mean_visibility_core_joints": _pick(series.mean_visibility(CORE_JOINTS)),
        "mean_visibility_trunk_joints": _pick(series.mean_visibility(TRUNK_JOINTS)),
        "visibility_measured": series.mean_visibility(CORE_JOINTS) is not None,
        "gate_failures": gate_failures,
        "analysis_config": dict(ANALYSIS_CONFIG),
    }

    return PoseOutcome(
        exercise_key=exercise_key,
        metrics=metrics,
        quality=quality,
        warnings=warnings,
        gate_failures=gate_failures,
    )


def describe_thresholds() -> dict[str, Any]:
    """The derivations behind the gates, for the UI to explain a refusal."""
    return {
        "min_valid_frame_ratio": ANALYSIS_CONFIG["min_valid_frame_ratio"],
        "min_duration_sec": ANALYSIS_CONFIG["min_duration_sec"],
        "min_landmark_visibility": ANALYSIS_CONFIG["min_landmark_visibility"],
        "min_movement_range_deg": ANALYSIS_CONFIG["min_movement_range_deg"],
        "algorithm_version": POSE_METRICS_ALGORITHM_VERSION,
    }
