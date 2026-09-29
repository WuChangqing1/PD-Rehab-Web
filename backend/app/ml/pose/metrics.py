"""Raw pose metrics (spec V2 section 28).

Every function here is a pure function over a `PoseSeries`, so the arithmetic can
be tested without running a model, and every value traces back to landmarks.

WHAT IS DELIBERATELY NOT HERE
=============================
No display scores. The specification lists completion / ROM / symmetry /
stability as 0-100 values but never defines their formulas, and the numbers in
the source documents (82 / 88 / 79) are illustrative. Inventing a formula would
put a made-up number in front of a clinician, so `pose_sessions.completion_score`
and friends stay NULL and only the raw metrics below are produced.

DATA-DERIVED THRESHOLDS
=======================
Where a decision needs a threshold (what counts as a repetition, what counts as
holding a position) it is derived from the patient's own range of motion in this
recording rather than from an external clinical constant, and the derivation is
recorded in `ANALYSIS_CONFIG` so a result can be reproduced.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.ml.pose.landmarks import (
    LEFT_ELBOW,
    LEFT_HIP,
    LEFT_SHOULDER,
    LEFT_WRIST,
    MIN_LANDMARK_VISIBILITY,
    PoseSeries,
    RIGHT_ELBOW,
    RIGHT_HIP,
    RIGHT_SHOULDER,
    RIGHT_WRIST,
)

# Versioned so a change in any derivation below invalidates the cache of
# interpretation rather than silently shifting a trend line.
POSE_METRICS_ALGORITHM_VERSION = "pose-metrics-v1.0.0"

ANALYSIS_CONFIG: dict[str, object] = {
    "smoothing_window_frames": 5,
    "repetition_high_fraction": 0.75,
    "repetition_low_fraction": 0.35,
    "repetition_percentile": 95.0,
    "hold_band_fraction": 0.90,
    "min_repetition_interval_frames": 5,
    # Hold time is measured on the smoothed series. A centred moving average
    # trims (window - 1) / 2 frames from each end of a plateau, so with the
    # default window of 5 a 2.00 s hold is reported as about 1.87 s at 30 fps.
    # The bias is a known, reproducible property of the derivation, not noise.
    "hold_time_smoothing_bias_frames": 2,
    "min_landmark_visibility": MIN_LANDMARK_VISIBILITY,
    "min_valid_frame_ratio": 0.5,
    "min_duration_sec": 2.0,
    "min_movement_range_deg": 10.0,
    "trunk_rotation_is_monocular_proxy": True,
    "algorithm_version": POSE_METRICS_ALGORITHM_VERSION,
}


# --------------------------------------------------------------------------- #
# geometry
# --------------------------------------------------------------------------- #
def angle_deg(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
    """Angle at `b` formed by `a-b-c`, in degrees (0-180)."""
    bax, bay = a[0] - b[0], a[1] - b[1]
    bcx, bcy = c[0] - b[0], c[1] - b[1]
    na = math.hypot(bax, bay)
    nc = math.hypot(bcx, bcy)
    if na < 1e-9 or nc < 1e-9:
        return float("nan")
    cos = (bax * bcx + bay * bcy) / (na * nc)
    return math.degrees(math.acos(max(-1.0, min(1.0, cos))))


def midpoint(a: tuple[float, float], b: tuple[float, float]) -> tuple[float, float]:
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)


def tilt_from_vertical_deg(lower: tuple[float, float], upper: tuple[float, float]) -> float:
    """Signed angle of the lower->upper vector from vertical, in degrees.

    Positive means the upper point is to the patient's left in the image, i.e.
    the image's +x direction. The image is mirrored for a front camera, so this
    is a screen-relative sign, and is reported as such.
    """
    dx = upper[0] - lower[0]
    dy = upper[1] - lower[1]
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return float("nan")
    # atan2(dx, -dy): straight up in image coordinates is -y.
    return math.degrees(math.atan2(dx, -dy))


def _clean(values: list[float]) -> list[float]:
    return [v for v in values if v is not None and not math.isnan(v)]


def percentile(values: list[float], fraction: float) -> float:
    """Linear-interpolated percentile; avoids a numpy dependency for one call."""
    ordered = sorted(values)
    if not ordered:
        return float("nan")
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[int(position)]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def moving_average(values: list[float], window: int) -> list[float]:
    """Centred moving average, ignoring NaN entries."""
    if window <= 1 or not values:
        return list(values)
    half = window // 2
    out: list[float] = []
    for i in range(len(values)):
        lo = max(0, i - half)
        hi = min(len(values), i + half + 1)
        chunk = _clean(values[lo:hi])
        out.append(sum(chunk) / len(chunk) if chunk else float("nan"))
    return out


# --------------------------------------------------------------------------- #
# per-frame joint angles
# --------------------------------------------------------------------------- #
def _series(series: PoseSeries, compute) -> list[float]:
    """Run `compute(frame_index)` per frame, yielding NaN where it is undefined."""
    return [compute(i) for i in range(len(series.frames))]


def _elbow_angle(series: PoseSeries, frame: int, side: str) -> float:
    """Angle at the elbow: shoulder-elbow-wrist."""
    shoulder = series.pixel_xy(frame, LEFT_SHOULDER if side == "left" else RIGHT_SHOULDER)
    elbow = series.pixel_xy(frame, LEFT_ELBOW if side == "left" else RIGHT_ELBOW)
    wrist = series.pixel_xy(frame, LEFT_WRIST if side == "left" else RIGHT_WRIST)
    if shoulder is None or elbow is None or wrist is None:
        return float("nan")
    return angle_deg(shoulder, elbow, wrist)


def _shoulder_abduction(series: PoseSeries, frame: int, side: str) -> float:
    """Angle at the shoulder: hip-shoulder-elbow.

    Straight down at the side is near 0 degrees, arms horizontal is near 90, and
    arms overhead approaches 180.
    """
    hip = series.pixel_xy(frame, LEFT_HIP if side == "left" else RIGHT_HIP)
    shoulder = series.pixel_xy(frame, LEFT_SHOULDER if side == "left" else RIGHT_SHOULDER)
    elbow = series.pixel_xy(frame, LEFT_ELBOW if side == "left" else RIGHT_ELBOW)
    if hip is None or shoulder is None or elbow is None:
        return float("nan")
    return angle_deg(hip, shoulder, elbow)


def _trunk_tilt(series: PoseSeries, frame: int) -> float:
    """Signed lateral lean of the torso, in degrees."""
    left_hip = series.pixel_xy(frame, LEFT_HIP)
    right_hip = series.pixel_xy(frame, RIGHT_HIP)
    left_shoulder = series.pixel_xy(frame, LEFT_SHOULDER)
    right_shoulder = series.pixel_xy(frame, RIGHT_SHOULDER)
    if None in (left_hip, right_hip, left_shoulder, right_shoulder):
        return float("nan")
    return tilt_from_vertical_deg(
        midpoint(left_hip, right_hip), midpoint(left_shoulder, right_shoulder)
    )


def _shoulder_line_depth_deg(series: PoseSeries, frame: int) -> float:
    """Trunk rotation proxy from the depth difference across the shoulders.

    MONOCULAR PROXY, and the weakest metric in this module. A rotation about the
    vertical axis is mostly a depth change, and MediaPipe's z is relative and
    unscaled; the value is normalised by the apparent shoulder width, which
    itself shrinks as the person turns. Treat it as a direction, not a number.
    """
    left = series.point(frame, LEFT_SHOULDER)
    right = series.point(frame, RIGHT_SHOULDER)
    if left is None or right is None:
        return float("nan")
    width = abs(left.x - right.x)
    if width < 1e-6:
        return float("nan")
    ratio = max(-1.0, min(1.0, (left.z - right.z) / width))
    return math.degrees(math.asin(ratio))


def elbow_series(series: PoseSeries, side: str) -> list[float]:
    return _series(series, lambda i: _elbow_angle(series, i, side))


def abduction_series(series: PoseSeries, side: str) -> list[float]:
    return _series(series, lambda i: _shoulder_abduction(series, i, side))


def trunk_tilt_series(series: PoseSeries) -> list[float]:
    return _series(series, lambda i: _trunk_tilt(series, i))


def trunk_rotation_series(series: PoseSeries) -> list[float]:
    return _series(series, lambda i: _shoulder_line_depth_deg(series, i))


# --------------------------------------------------------------------------- #
# series-level metrics
# --------------------------------------------------------------------------- #
@dataclass
class MovementStats:
    """Metrics derived from one angle series."""

    peak_deg: float | None
    min_deg: float | None
    range_deg: float | None
    hold_time_sec: float | None
    repetition_count: int
    repetition_interval_ms: float | None
    movement_speed_deg_per_sec: float | None
    angle_std_deg: float | None
    valid_sample_ratio: float


def analyse_series(
    values: list[float],
    fps: float,
    *,
    smoothing_window: int | None = None,
    high_fraction: float | None = None,
    low_fraction: float | None = None,
) -> MovementStats:
    """Turn one raw angle series into the metrics the exercises report."""
    window = smoothing_window or int(ANALYSIS_CONFIG["smoothing_window_frames"])
    high_fraction = (
        high_fraction if high_fraction is not None else float(ANALYSIS_CONFIG["repetition_high_fraction"])
    )
    low_fraction = (
        low_fraction if low_fraction is not None else float(ANALYSIS_CONFIG["repetition_low_fraction"])
    )

    total = len(values)
    clean = _clean(values)
    sample_ratio = (len(clean) / total) if total else 0.0
    if not clean:
        return MovementStats(None, None, None, None, 0, None, None, None, sample_ratio)

    smoothed = moving_average(values, window)
    smooth_clean = _clean(smoothed)

    peak = percentile(smooth_clean, float(ANALYSIS_CONFIG["repetition_percentile"]) / 100.0)
    minimum = min(smooth_clean)
    span = peak - minimum

    reps, intervals = count_repetitions(
        smoothed,
        low=minimum + low_fraction * span,
        high=minimum + high_fraction * span,
        fps=fps,
    )
    hold = hold_time_sec(smoothed, peak=peak, fps=fps)
    speed = movement_speed_deg_per_sec(smoothed, fps=fps)
    # Steadiness is measured where the patient is trying to hold still: the
    # samples inside the hold band. Including the moving part would just measure
    # how fast they moved.
    band = [v for v in smooth_clean if peak - v <= (1 - float(ANALYSIS_CONFIG["hold_band_fraction"])) * span + 1e-9]
    std = _std(band) if len(band) >= 2 else None

    return MovementStats(
        peak_deg=peak,
        min_deg=minimum,
        range_deg=span,
        hold_time_sec=hold,
        repetition_count=reps,
        repetition_interval_ms=(
            sum(intervals) / len(intervals) * 1000.0 / fps if intervals and fps > 0 else None
        ),
        movement_speed_deg_per_sec=speed,
        angle_std_deg=std,
        valid_sample_ratio=sample_ratio,
    )


def _std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(max(0.0, variance))


def count_repetitions(
    values: list[float],
    *,
    low: float,
    high: float,
    fps: float,
) -> tuple[int, list[int]]:
    """Count movement cycles with hysteresis.

    A repetition is a rise from below `low` to above `high`. Requiring both
    thresholds stops a signal hovering around a single level from being counted
    as a burst of repetitions.
    """
    if not values or high <= low:
        return 0, []

    min_interval = int(ANALYSIS_CONFIG["min_repetition_interval_frames"])
    peaks: list[int] = []
    armed = False
    for index, value in enumerate(values):
        if math.isnan(value):
            continue
        if not armed and value <= low:
            armed = True
        elif armed and value >= high:
            if not peaks or index - peaks[-1] >= min_interval:
                peaks.append(index)
            armed = False

    intervals = [peaks[i + 1] - peaks[i] for i in range(len(peaks) - 1)]
    return len(peaks), intervals


def hold_time_sec(values: list[float], *, peak: float, fps: float) -> float | None:
    """Longest continuous time spent within the hold band below the peak.

    The band is a fraction of the patient's own range of motion in this
    recording, not an absolute clinical angle, and the fraction is versioned in
    ANALYSIS_CONFIG.
    """
    clean = _clean(values)
    if not clean or fps <= 0:
        return None
    band = (1 - float(ANALYSIS_CONFIG["hold_band_fraction"])) * (peak - min(clean))
    longest = 0
    current = 0
    for value in values:
        inside = not math.isnan(value) and peak - value <= band + 1e-9
        current = current + 1 if inside else 0
        longest = max(longest, current)
    return longest / fps


def movement_speed_deg_per_sec(values: list[float], *, fps: float) -> float | None:
    """Mean absolute angular rate over the frames where movement is happening."""
    if fps <= 0 or len(values) < 2:
        return None
    deltas: list[float] = []
    for i in range(1, len(values)):
        a, b = values[i - 1], values[i]
        if math.isnan(a) or math.isnan(b):
            continue
        deltas.append(abs(b - a))
    if not deltas:
        return None
    # The 60th percentile of frame-to-frame change separates moving from holding
    # without assuming a movement velocity in advance.
    moving = [d for d in deltas if d >= percentile(deltas, 0.6)]
    if not moving:
        moving = deltas
    return (sum(moving) / len(moving)) * fps


def left_right_difference_deg(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return abs(left - right)


def overall_valid_frame_ratio(series: PoseSeries) -> float:
    return series.valid_frame_ratio
