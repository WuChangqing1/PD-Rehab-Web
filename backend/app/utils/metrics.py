"""Metric computation helpers shared by later phases.

Only the pieces required for verification now live here. The full Finger
Tapping pipeline (OpenCV -> MediaPipe -> features) lands in Phase 4; the
definitions implemented below come from docs/metric_definitions.md.

Guard rails:
  * Never emit Inf or NaN. Undefined results are None.
  * CV = std / mean with a safe guard when the mean is near zero.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

# Below this magnitude a mean is treated as zero, so CV is undefined.
EPS = 1e-9


def _clean(value: float | None) -> float | None:
    """Reject NaN / Inf so they can never reach the database or the API."""
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if math.isnan(float(value)) or math.isinf(float(value)):
            return None
    return value


def coefficient_of_variation(values: Sequence[float] | None) -> float | None:
    """CV = std / mean, population standard deviation (ddof=0).

    Returns None when there are fewer than two samples or when the mean is
    effectively zero, which is the documented behaviour in
    docs/metric_definitions.md section 1.3.
    """
    if values is None:
        return None
    arr = np.asarray(list(values), dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size < 2:
        return None
    mean = float(np.mean(arr))
    if abs(mean) < EPS:
        return None
    return _clean(float(np.std(arr) / mean))


def linear_slope(values: Sequence[float] | None) -> float | None:
    """Least-squares slope against the cycle index (0, 1, 2, ...).

    The independent variable is the cycle index, not time, so the unit is
    "change per cycle" (docs/metric_definitions.md section 1.3.8).
    """
    if values is None:
        return None
    arr = np.asarray(list(values), dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size < 2:
        return None
    x = np.arange(arr.size, dtype=float)
    slope, _intercept = np.polyfit(x, arr, 1)
    return _clean(float(slope))


def mean_or_none(values: Sequence[float] | None) -> float | None:
    if values is None:
        return None
    arr = np.asarray(list(values), dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return None
    return _clean(float(np.mean(arr)))


def median_or_none(values: Sequence[float] | None) -> float | None:
    if values is None:
        return None
    arr = np.asarray(list(values), dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return None
    return _clean(float(np.median(arr)))


def absolute_difference(left: float | None, right: float | None) -> float | None:
    """left - right. None if either side is missing; missing is never 0."""
    if left is None or right is None:
        return None
    return _clean(left - right)


def asymmetry_ratio(left: float | None, right: float | None) -> float | None:
    """(left - right) / mean(left, right). None when the mean is ~0."""
    if left is None or right is None:
        return None
    denom = (left + right) / 2.0
    if abs(denom) < EPS:
        return None
    return _clean((left - right) / denom)


def safe_ratio(numerator: float, denominator: float) -> float | None:
    """numerator / denominator, or None when the denominator is ~0."""
    if abs(denominator) < EPS:
        return None
    return _clean(numerator / denominator)


def tapping_frequency(
    peak_frames: Sequence[int] | None, fps: float | None
) -> float | None:
    """(number of peaks - 1) / span in seconds.

    Marked NEW_DERIVED in docs/metric_definitions.md: the external repository
    has no frequency field. Phase 4 cross-checks this against
    1 / avg_cycle_duration before either is treated as canonical.
    """
    if not peak_frames or fps is None or fps <= 0:
        return None
    frames = sorted(int(f) for f in peak_frames)
    if len(frames) < 2:
        return None
    span_sec = (frames[-1] - frames[0]) / fps
    if span_sec <= 0:
        return None
    return _clean((len(frames) - 1) / span_sec)


def count_interruptions(
    cycle_durations: Sequence[float] | None, factor: float = 1.5
) -> int | None:
    """Number of cycles longer than factor * median(cycle duration).

    Threshold and basis are configurable and recorded in
    analysis_config_json so a run stays reproducible
    (docs/metric_definitions.md section 1.3.9).
    """
    if not cycle_durations:
        return None
    arr = np.asarray(list(cycle_durations), dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return None
    median = float(np.median(arr))
    if abs(median) < EPS:
        return None
    return int(np.sum(arr > factor * median))
