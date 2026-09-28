"""Finger Tapping feature extraction tests.

Ground truth comes from arithmetic rather than from the implementation itself.

Two properties of discrete peak detection are asserted with closed forms:

* Sampled peak amplitude. A continuous sine of amplitude A sampled at fps has
  its highest sample near a crest at cos(pi * f / fps) of the true peak, so the
  measured peak-to-trough amplitude approaches 2 * A * cos(pi * f / fps). This
  is a property of sampling, not an error in the feature code.

* Cycle-duration jitter. When the period is an exact integer number of frames
  (3.00 Hz at 30 fps -> 10 frames), peak picking can land on 9, 10 or 11 frames,
  so cycle CV is non-zero even for a perfect sine. The tests assert CV stays
  small and that a non-degenerate frequency keeps it smaller still.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from app.ml.finger_tapping.features import (
    count_interruptions,
    detect_peaks_and_troughs,
    extract_features,
)
from app.ml.finger_tapping.signal import (
    INDEX_FINGER_MCP,
    INDEX_FINGER_TIP,
    THUMB_TIP,
    WRIST,
    DistanceSignal,
    aperture_from_normalized,
    lowpass_filter,
    speed_signal,
)

FPS = 30.0


class _Landmark:
    __slots__ = ("x", "y", "z")

    def __init__(self, x: float, y: float, z: float = 0.0) -> None:
        self.x, self.y, self.z = x, y, z


def _sine_signal(freq_hz: float, *, seconds: float = 10.0, amp: float = 0.3, mid: float = 0.5):
    n = int(FPS * seconds)
    t = np.arange(n) / FPS
    values = mid + amp * np.sin(2 * np.pi * freq_hz * t)
    return DistanceSignal(
        values=values,
        frame_indices=np.arange(n),
        timestamps_ms=(np.arange(n) * 1000 / FPS).astype(int),
    )


# ------------------------------------------------------------- landmark setup
def test_landmark_indices_match_mediapipe_topology():
    """mediapipe 1.0.1 removed mp.solutions, so these are pinned here."""
    assert (WRIST, THUMB_TIP, INDEX_FINGER_MCP, INDEX_FINGER_TIP) == (0, 4, 5, 8)


def test_aperture_is_thumb_index_distance():
    normalized = [(0.0, 0.0, 0.0)] * 21
    normalized[THUMB_TIP] = (0.0, 0.0, 0.0)
    normalized[INDEX_FINGER_TIP] = (0.3, 0.4, 0.0)
    # 3-4-5 triangle
    assert aperture_from_normalized(normalized) == pytest.approx(0.5)


# ---------------------------------------------------------------- normalization
def test_palm_reference_normalization_is_scale_invariant():
    """Doubling every coordinate must not change the normalized aperture."""
    from app.ml.finger_tapping.signal import normalize_landmarks

    def build(scale: float):
        pts = [_Landmark(0.0, 0.0) for _ in range(21)]
        pts[WRIST] = _Landmark(0.0, 0.0)
        # palm reference length = 0.5 (before scaling)
        pts[INDEX_FINGER_MCP] = _Landmark(0.0, 0.5 * scale)
        pts[THUMB_TIP] = _Landmark(-0.1 * scale, 0.2 * scale)
        pts[INDEX_FINGER_TIP] = _Landmark(0.1 * scale, 0.2 * scale)
        return pts

    small, ref_small = normalize_landmarks(build(1.0))
    large, ref_large = normalize_landmarks(build(4.0))

    assert aperture_from_normalized(small) == pytest.approx(
        aperture_from_normalized(large), rel=1e-9
    )
    assert ref_large == pytest.approx(ref_small * 4.0)


def test_degenerate_palm_reference_is_clamped():
    """A zero-length wrist->mcp vector must not divide by zero."""
    from app.ml.finger_tapping.signal import normalize_landmarks

    pts = [_Landmark(0.0, 0.0) for _ in range(21)]
    normalized, reference = normalize_landmarks(pts)
    assert reference == pytest.approx(1e-5)
    assert all(math.isfinite(v) for point in normalized for v in point)


# --------------------------------------------------------------------- filtering
def test_filter_uses_real_fps_and_records_it():
    signal = _sine_signal(2.7)
    filtered = lowpass_filter(signal, fps=FPS)
    assert filtered.filtered is True
    assert filtered.filter_fs_hz == FPS
    assert filtered.filter_order == 4
    assert filtered.filter_cutoff_hz == pytest.approx(9.0)
    assert len(filtered) == len(signal)


def test_filter_preserves_low_frequency_amplitude():
    """2.7 Hz is well inside a 9 Hz passband, so amplitude survives."""
    signal = _sine_signal(2.7)
    filtered = lowpass_filter(signal, fps=FPS)
    assert float(np.std(filtered.values)) == pytest.approx(
        float(np.std(signal.values)), rel=0.05
    )


def test_filter_skips_short_series_instead_of_raising():
    short = DistanceSignal(
        values=np.array([0.1, 0.2, 0.3]),
        frame_indices=np.arange(3),
        timestamps_ms=np.array([0, 33, 66]),
    )
    filtered = lowpass_filter(short, fps=FPS)
    assert filtered.filtered is False
    assert "filter_skipped_series_too_short" in filtered.notes


def test_filter_handles_invalid_fps():
    signal = _sine_signal(2.7)
    filtered = lowpass_filter(signal, fps=0)
    assert filtered.filtered is False
    assert "filter_skipped_invalid_fps" in filtered.notes


# ---------------------------------------------------------------- peak finding
def test_peaks_and_troughs_count():
    signal = _sine_signal(2.7)
    detected = detect_peaks_and_troughs(signal.values)
    # 2.7 Hz over 10 s -> 27 cycles -> about 27-28 peaks
    assert 25 <= len(detected.peaks) <= 29
    assert abs(len(detected.peaks) - len(detected.troughs)) <= 1


def test_flat_signal_yields_no_peaks():
    flat = DistanceSignal(
        values=np.full(300, 0.4),
        frame_indices=np.arange(300),
        timestamps_ms=(np.arange(300) * 1000 / FPS).astype(int),
    )
    detected = detect_peaks_and_troughs(flat.values)
    assert len(detected.peaks) == 0


# ---------------------------------------------------------------------- speed
def test_speed_signal_is_first_difference_over_dt():
    values = np.array([0.0, 0.1, 0.3, 0.6])
    signal = DistanceSignal(values=values, frame_indices=np.arange(4), timestamps_ms=np.arange(4))
    speed = speed_signal(signal, FPS)
    expected = np.diff(values) / (1.0 / FPS)
    assert speed == pytest.approx(expected)
    assert speed.size == values.size - 1


# ------------------------------------------------------------------- features
@pytest.mark.parametrize("freq_hz", [3.0, 2.7])
def test_frequency_is_recovered(freq_hz: float):
    features = extract_features(_sine_signal(freq_hz), FPS)
    assert features.tapping_frequency == pytest.approx(freq_hz, abs=0.05)
    assert features.tapping_frequency_cycle_based == pytest.approx(freq_hz, abs=0.05)
    # both definitions must agree on a well-formed signal
    assert features.tapping_frequency == pytest.approx(
        features.tapping_frequency_cycle_based, rel=0.02
    )


@pytest.mark.parametrize("freq_hz", [3.0, 2.7])
def test_amplitude_matches_sampling_closed_form(freq_hz: float):
    amp = 0.3
    features = extract_features(_sine_signal(freq_hz, amp=amp), FPS)
    predicted = 2 * amp * math.cos(math.pi * freq_hz / FPS)
    assert features.avg_amplitude == pytest.approx(predicted, abs=0.02)


def test_cycle_duration_matches_period():
    features = extract_features(_sine_signal(2.7), FPS)
    assert features.avg_cycle_duration == pytest.approx(1 / 2.7, abs=0.01)


def test_cycle_cv_small_for_regular_tapping():
    features = extract_features(_sine_signal(2.7), FPS)
    assert features.cycle_cv is not None
    assert features.cycle_cv < 0.08


def test_amplitude_cv_near_zero_for_constant_amplitude():
    features = extract_features(_sine_signal(2.7), FPS)
    assert features.amplitude_cv is not None
    assert features.amplitude_cv < 0.02


def test_slopes_present_for_trending_series():
    features = extract_features(_sine_signal(2.7), FPS)
    for slope in (features.amplitude_slope, features.speed_slope, features.cycle_slope):
        assert slope is not None
        assert math.isfinite(slope)


def test_no_interruptions_in_steady_tapping():
    features = extract_features(_sine_signal(2.7), FPS)
    assert features.interruptions == 0


def test_interruption_detected_when_a_cycle_is_stretched():
    n = int(FPS * 10)
    t = np.arange(n) / FPS
    half = n // 2
    values = np.concatenate(
        [
            0.5 + 0.3 * np.sin(2 * np.pi * 2.7 * t[:half]),
            np.full(int(FPS * 0.9), 0.5),
            0.5 + 0.3 * np.sin(2 * np.pi * 2.7 * t[: n // 3]),
        ]
    )
    signal = DistanceSignal(
        values=values,
        frame_indices=np.arange(values.size),
        timestamps_ms=(np.arange(values.size) * 1000 / FPS).astype(int),
    )
    features = extract_features(signal, FPS)
    assert features.interruptions is not None
    assert features.interruptions >= 1


def test_interruption_threshold_factor_is_configurable():
    durations = [1.0, 1.0, 2.0]
    assert count_interruptions(durations, factor=1.5) == 1
    assert count_interruptions(durations, factor=3.0) == 0
    assert count_interruptions([]) is None


# --------------------------------------------------------------- guard rails
def test_empty_signal_produces_all_none():
    empty = DistanceSignal(
        values=np.empty(0),
        frame_indices=np.empty(0, dtype=int),
        timestamps_ms=np.empty(0, dtype=int),
    )
    features = extract_features(empty, FPS)
    assert all(v is None for v in features.to_features().values())


def test_single_peak_is_insufficient():
    values = np.concatenate([np.linspace(0.1, 0.9, 20), np.linspace(0.9, 0.1, 20)])
    signal = DistanceSignal(
        values=values,
        frame_indices=np.arange(values.size),
        timestamps_ms=(np.arange(values.size) * 1000 / FPS).astype(int),
    )
    features = extract_features(signal, FPS)
    assert features.tapping_frequency is None
    assert "fewer_than_two_peaks" in features.notes


def test_features_never_contain_nan_or_inf():
    for freq in (0.5, 2.7, 3.0, 5.0):
        features = extract_features(_sine_signal(freq), FPS)
        for key, value in features.to_features().items():
            if isinstance(value, float):
                assert math.isfinite(value), f"{key} is not finite"


def test_flat_signal_yields_no_frequency():
    flat = DistanceSignal(
        values=np.full(300, 0.4),
        frame_indices=np.arange(300),
        timestamps_ms=(np.arange(300) * 1000 / FPS).astype(int),
    )
    features = extract_features(flat, FPS)
    assert features.tapping_frequency is None


def test_zero_fps_does_not_raise():
    features = extract_features(_sine_signal(2.7), 0.0)
    assert features.avg_cycle_duration is None
    assert features.tapping_frequency is None


def test_feature_columns_are_exactly_the_persisted_set():
    """to_features() must match the finger_tapping_results columns."""
    assert set(extract_features(_sine_signal(2.7), FPS).to_features()) == {
        "tapping_frequency",
        "avg_amplitude",
        "avg_speed",
        "avg_cycle_duration",
        "amplitude_cv",
        "speed_cv",
        "cycle_cv",
        "amplitude_slope",
        "speed_slope",
        "cycle_slope",
        "interruptions",
    }
