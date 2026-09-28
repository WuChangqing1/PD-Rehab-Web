"""Metric primitive tests.

Covers the V2 test list items "CV calculation" and "left-right difference",
plus the numeric guard rails (no Inf / NaN may ever reach storage).
"""

from __future__ import annotations

import math

import pytest

from app.utils import metrics


# ------------------------------------------------------------------------ CV
def test_cv_matches_manual_computation():
    values = [1.0, 2.0, 3.0, 4.0]
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    expected = math.sqrt(variance) / mean
    assert metrics.coefficient_of_variation(values) == pytest.approx(expected)


def test_cv_uses_population_std():
    """ddof=0, matching the external repository's np.std default."""
    assert metrics.coefficient_of_variation([1.0, 3.0]) == pytest.approx(0.5)


def test_cv_constant_series_is_zero():
    assert metrics.coefficient_of_variation([2.0, 2.0, 2.0]) == 0.0


def test_cv_needs_two_samples():
    assert metrics.coefficient_of_variation([1.0]) is None
    assert metrics.coefficient_of_variation([]) is None
    assert metrics.coefficient_of_variation(None) is None


def test_cv_near_zero_mean_is_undefined_not_infinite():
    """timing_error can average ~0; CV must be None rather than +/-Inf."""
    assert metrics.coefficient_of_variation([1.0, -1.0, 1e-12]) is None
    assert metrics.coefficient_of_variation([0.0, 0.0, 0.0]) is None


def test_cv_ignores_nan_and_inf_inputs():
    assert metrics.coefficient_of_variation([1.0, 2.0, float("nan")]) is not None
    assert metrics.coefficient_of_variation([float("nan"), float("inf")]) is None


def test_cv_never_returns_non_finite():
    for series in ([1e300, -1e300], [1e-300, 1e-300], [1.0, 1e308]):
        result = metrics.coefficient_of_variation(series)
        assert result is None or math.isfinite(result)


# --------------------------------------------------------------------- slope
def test_slope_of_increasing_series():
    assert metrics.linear_slope([1.0, 2.0, 3.0, 4.0]) == pytest.approx(1.0)


def test_slope_of_decreasing_series():
    assert metrics.linear_slope([4.0, 3.0, 2.0, 1.0]) == pytest.approx(-1.0)


def test_slope_of_constant_series_is_zero():
    assert metrics.linear_slope([5.0, 5.0, 5.0]) == pytest.approx(0.0)


def test_slope_needs_two_points():
    assert metrics.linear_slope([1.0]) is None
    assert metrics.linear_slope([]) is None
    assert metrics.linear_slope(None) is None


def test_slope_x_axis_is_cycle_index_not_time():
    """Doubling the sample spacing at a fixed rate doubles the per-step slope."""
    dense = metrics.linear_slope([0.0, 1.0, 2.0, 3.0])
    assert dense == pytest.approx(1.0)


# -------------------------------------------------- left / right difference
def test_absolute_difference_is_left_minus_right():
    assert metrics.absolute_difference(0.8, 0.5) == pytest.approx(0.3)
    assert metrics.absolute_difference(0.5, 0.8) == pytest.approx(-0.3)


def test_absolute_difference_missing_side_is_none_not_zero():
    assert metrics.absolute_difference(None, 0.5) is None
    assert metrics.absolute_difference(0.5, None) is None
    assert metrics.absolute_difference(None, None) is None


def test_absolute_difference_allows_genuine_zero():
    """A real 0.0 difference must stay 0.0, distinct from 'missing'."""
    assert metrics.absolute_difference(0.4, 0.4) == 0.0


def test_asymmetry_ratio():
    assert metrics.asymmetry_ratio(1.0, 0.5) == pytest.approx(0.5 / 0.75)


def test_asymmetry_ratio_zero_mean_is_none():
    assert metrics.asymmetry_ratio(1.0, -1.0) is None
    assert metrics.asymmetry_ratio(0.0, 0.0) is None


# ---------------------------------------------------------------- primitives
def test_mean_and_median():
    assert metrics.mean_or_none([1.0, 2.0, 3.0]) == pytest.approx(2.0)
    assert metrics.median_or_none([1.0, 2.0, 3.0]) == pytest.approx(2.0)
    assert metrics.mean_or_none([]) is None
    assert metrics.median_or_none(None) is None


def test_safe_ratio():
    assert metrics.safe_ratio(1.0, 4.0) == pytest.approx(0.25)
    assert metrics.safe_ratio(1.0, 0.0) is None


# ------------------------------------------------------- finger tapping bits
def test_tapping_frequency():
    # 5 peaks spanning 60 frames at 30 fps -> 4 intervals over 2 s -> 2 Hz
    assert metrics.tapping_frequency([0, 15, 30, 45, 60], 30.0) == pytest.approx(2.0)


def test_tapping_frequency_guards():
    assert metrics.tapping_frequency([10], 30.0) is None
    assert metrics.tapping_frequency([], 30.0) is None
    assert metrics.tapping_frequency([0, 30], 0.0) is None
    assert metrics.tapping_frequency([0, 30], None) is None
    assert metrics.tapping_frequency(None, 30.0) is None


def test_tapping_frequency_unsorted_input():
    assert metrics.tapping_frequency([60, 0, 30], 30.0) == pytest.approx(1.0)


def test_count_interruptions_uses_median_threshold():
    # median = 1.0 -> threshold 1.5; two cycles exceed it
    durations = [1.0, 1.0, 1.0, 2.0, 3.0]
    assert metrics.count_interruptions(durations, factor=1.5) == 2


def test_count_interruptions_none_when_no_cycles():
    assert metrics.count_interruptions([]) is None
    assert metrics.count_interruptions(None) is None


def test_count_interruptions_factor_is_configurable():
    durations = [1.0, 1.0, 2.0]
    assert metrics.count_interruptions(durations, factor=1.5) == 1
    assert metrics.count_interruptions(durations, factor=3.0) == 0
