"""Finger Tapping motor feature extraction.

All formulas follow docs/metric_definitions.md section 1, which in turn follows
the external repository (VideoBased-PD-Biomarkers, Apache-2.0) wherever it has
an implementation. Deviations are deliberate and listed below.

Recorded deviations from upstream
================================
D1  `cov_percycle_max_speed` -- upstream computes
        std_amp / mean_percycle_max_speed
    using the *amplitude* standard deviation in the numerator, which is a bug
    (the correct numerator is the standard deviation of the per-cycle maximum
    speeds). This implementation uses the corrected formula. Upstream is NOT
    modified; the difference is documented rather than silently copied.

D2  The low-pass filter uses the video's real fps instead of a hardcoded 30.0.

D3  `tapping_frequency` does not exist upstream at all. It is NEW_DERIVED here
    and computed two ways, because the two definitions differ at the boundaries
    (the first and last half-cycles):
        - tapping_frequency             = (n_peaks - 1) / span_seconds
        - tapping_frequency_cycle_based = 1 / mean_cycle_duration
    Both are reported so the values can be compared on real recordings before
    either is treated as canonical.

D4  Missing input yields None, never NaN or Infinity, and never 0. A mean near
    zero makes CV undefined rather than exploding.

D5  `median_cycle_duration` is computed and reported; upstream calculates it but
    drops it from the feature dictionary.

Peak detection uses `find_peaks` with distance=5, height=mean/2 and
prominence=mean/2, exactly as upstream.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
from scipy.signal import find_peaks

from app.ml.finger_tapping.signal import DistanceSignal, speed_signal
from app.utils.metrics import (
    EPS,
    clean_float,
    coefficient_of_variation,
    linear_slope,
)

# Peak detection parameters (upstream values for the 'ft' test type).
PEAK_DISTANCE = 5
PEAK_HEIGHT_FACTOR = 0.5
PEAK_PROMINENCE_FACTOR = 0.5

# Interruption rule (upstream): a cycle longer than 1.5 x the median cycle.
INTERRUPTION_THRESHOLD_FACTOR = 1.5


@dataclass
class PeakTroughResult:
    peaks: np.ndarray
    troughs: np.ndarray
    alignment_note: str | None = None


@dataclass
class FeatureSet:
    """The 12 motor features plus the intermediate series they came from."""

    # --- P0 motor features (FingerTappingResult columns) ---
    tapping_frequency: float | None = None
    avg_amplitude: float | None = None
    avg_speed: float | None = None
    avg_cycle_duration: float | None = None
    amplitude_cv: float | None = None
    speed_cv: float | None = None
    cycle_cv: float | None = None
    amplitude_slope: float | None = None
    speed_slope: float | None = None
    cycle_slope: float | None = None
    interruptions: int | None = None

    # --- intermediate / supplementary values (raw_features_json) ---
    tapping_frequency_cycle_based: float | None = None
    median_cycle_duration: float | None = None
    avg_percycle_max_speed: float | None = None
    avg_percycle_avg_speed: float | None = None
    cov_percycle_max_speed: float | None = None
    cov_percycle_avg_speed: float | None = None
    amplitudes: list[float] = field(default_factory=list)
    cycle_durations: list[float] = field(default_factory=list)
    per_cycle_avg_speed: list[float] = field(default_factory=list)
    per_cycle_max_speed: list[float] = field(default_factory=list)
    peak_frames: list[int] = field(default_factory=list)
    trough_frames: list[int] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_features(self) -> dict[str, Any]:
        """The subset persisted as finger_tapping_results columns."""
        return {
            "tapping_frequency": self.tapping_frequency,
            "avg_amplitude": self.avg_amplitude,
            "avg_speed": self.avg_speed,
            "avg_cycle_duration": self.avg_cycle_duration,
            "amplitude_cv": self.amplitude_cv,
            "speed_cv": self.speed_cv,
            "cycle_cv": self.cycle_cv,
            "amplitude_slope": self.amplitude_slope,
            "speed_slope": self.speed_slope,
            "cycle_slope": self.cycle_slope,
            "interruptions": self.interruptions,
        }

    def to_raw(self, *, include_series: bool = True) -> dict[str, Any]:
        d = asdict(self)
        if not include_series:
            for key in (
                "amplitudes",
                "cycle_durations",
                "per_cycle_avg_speed",
                "per_cycle_max_speed",
                "peak_frames",
                "trough_frames",
            ):
                d.pop(key, None)
        return d


def detect_peaks_and_troughs(values: np.ndarray) -> PeakTroughResult:
    """Peaks = maximal aperture (fingers fully open), troughs = closed."""
    if values.size == 0:
        return PeakTroughResult(np.empty(0, dtype=int), np.empty(0, dtype=int))

    mean = float(np.mean(values))
    height = mean * PEAK_HEIGHT_FACTOR
    prominence = mean * PEAK_PROMINENCE_FACTOR

    peaks, _ = find_peaks(
        values, distance=PEAK_DISTANCE, height=height, prominence=prominence
    )
    troughs, _ = find_peaks(
        -values,
        distance=PEAK_DISTANCE,
        height=-mean,
        prominence=prominence,
    )

    note = None
    # Upstream drops leading peaks that precede the first trough, so the first
    # amplitude is measured from a real closed position.
    if peaks.size and troughs.size and troughs[0] > peaks[0]:
        peaks = peaks[1:]
        note = "dropped_leading_peak_before_first_trough"

    return PeakTroughResult(peaks, troughs, note)


def compute_amplitudes(
    values: np.ndarray, peaks: np.ndarray, troughs: np.ndarray
) -> tuple[list[float], list[int]]:
    """Per-cycle amplitude = |value at peak - value at the nearest earlier trough|."""
    amplitudes: list[float] = []
    frames: list[int] = []
    for peak in peaks:
        earlier = troughs[troughs < peak]
        if earlier.size == 0:
            continue
        last_trough = int(earlier[-1])
        amplitudes.append(abs(float(values[peak]) - float(values[last_trough])))
        frames.append(int(peak))
    return amplitudes, frames


def compute_per_cycle_speeds(
    speed: np.ndarray, peaks: np.ndarray
) -> tuple[list[float], list[float], list[int]]:
    """Per-cycle mean and 95th-percentile absolute speed, over peak-to-peak windows."""
    means: list[float] = []
    maxima: list[float] = []
    midframes: list[int] = []
    for i in range(len(peaks) - 1):
        start = int(peaks[i])
        end = int(peaks[i + 1])
        window = speed[start:end] if start < speed.size else np.empty(0)
        if window.size == 0:
            continue
        absolute = np.abs(window)
        means.append(float(np.mean(absolute)))
        maxima.append(float(np.percentile(absolute, 95)))
        midframes.append((start + end) // 2)
    return means, maxima, midframes


def extract_features(signal: DistanceSignal, fps: float) -> FeatureSet:
    """Compute the full feature set from a filtered aperture series."""
    features = FeatureSet()
    values = np.asarray(signal.values, dtype=float)

    if values.size == 0:
        features.notes.append("empty_signal")
        return features

    # ---------------------------------------------------------- peaks/troughs
    detected = detect_peaks_and_troughs(values)
    peaks, troughs = detected.peaks, detected.troughs
    if detected.alignment_note:
        features.notes.append(detected.alignment_note)
    features.peak_frames = [int(p) for p in peaks]
    features.trough_frames = [int(t) for t in troughs]

    if peaks.size < 2:
        features.notes.append("fewer_than_two_peaks")
        return features

    # -------------------------------------------------------------- amplitude
    amplitudes, _amp_frames = compute_amplitudes(values, peaks, troughs)
    if not amplitudes:
        features.notes.append("no_valid_peak_trough_pair")
        return features

    features.amplitudes = amplitudes
    features.avg_amplitude = float(np.mean(amplitudes))
    features.amplitude_cv = coefficient_of_variation(amplitudes)
    features.amplitude_slope = linear_slope(amplitudes)

    # ------------------------------------------------------------------ speed
    speed = speed_signal(signal, fps)
    if speed.size:
        means, maxima, _mid = compute_per_cycle_speeds(speed, peaks)
        features.per_cycle_avg_speed = means
        features.per_cycle_max_speed = maxima
        if means:
            features.avg_percycle_avg_speed = float(np.mean(means))
            features.avg_speed = features.avg_percycle_avg_speed
            features.cov_percycle_avg_speed = coefficient_of_variation(means)
            features.speed_cv = features.cov_percycle_avg_speed
            features.speed_slope = linear_slope(means)
        if maxima:
            features.avg_percycle_max_speed = float(np.mean(maxima))
            # D1: corrected numerator (std of the maxima, not of the amplitudes).
            features.cov_percycle_max_speed = coefficient_of_variation(maxima)

    # ------------------------------------------------------------------ cycle
    if fps and fps > 0:
        cycle_durations = np.diff(peaks) / float(fps)
        durations = [float(c) for c in cycle_durations]
        features.cycle_durations = durations
        if durations:
            mean_duration = float(np.mean(durations))
            features.avg_cycle_duration = mean_duration
            features.median_cycle_duration = float(np.median(durations))
            features.cycle_cv = coefficient_of_variation(durations)
            features.cycle_slope = linear_slope(durations)
            if abs(mean_duration) > EPS:
                features.tapping_frequency_cycle_based = 1.0 / mean_duration
            features.interruptions = count_interruptions(durations)

    # -------------------------------------------------------------- frequency
    # D3: NEW_DERIVED, does not exist upstream.
    if fps and fps > 0 and peaks.size >= 2:
        span_seconds = (int(peaks[-1]) - int(peaks[0])) / float(fps)
        if span_seconds > 0:
            features.tapping_frequency = clean_float((peaks.size - 1) / span_seconds)
        else:
            features.notes.append("zero_peak_span")

    return features


def count_interruptions(
    cycle_durations: list[float], factor: float = INTERRUPTION_THRESHOLD_FACTOR
) -> int | None:
    """Cycles longer than `factor` x the median cycle duration (upstream rule).

    The factor and the median basis are configurable and recorded in
    analysis_config_json so a single analysis stays reproducible.
    """
    if not cycle_durations:
        return None
    arr = np.asarray(cycle_durations, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return None
    median = float(np.median(arr))
    if abs(median) < EPS:
        return None
    return int(np.sum(arr > factor * median))
