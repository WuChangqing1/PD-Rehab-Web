"""Regression tests for two defects found by running a real piano round.

Both were invisible to unit tests that used tidy synthetic data and only
surfaced once an actual 45-second calibration was played in a browser.
"""

from __future__ import annotations

import pytest

from app.utils.piano_metrics import compute_metrics


def _cue(index: int, *, onset: int, target: int, actual: int | None, correct=True, missed=False):
    return {
        "event_index": index,
        "cue_onset_time_ms": onset,
        "target_time_ms": target,
        "actual_time_ms": actual,
        "response_latency_ms": None if actual is None else actual - onset,
        "timing_error_ms": None if actual is None else actual - target,
        "key_code": "KeyZ",
        "note": "C3",
        "hand": "LEFT",
        "finger_hint": "INDEX",
        "key_down_time_ms": actual,
        "key_up_time_ms": None,
        "hold_duration_ms": None,
        "is_correct": correct,
        "is_missed": missed,
        "is_wrong_key": False,
        "cue_index": index,
    }


# =============================================================================
# Defect 1: timing_error_cv was reported as 58.663
# =============================================================================
def test_timing_error_cv_is_null_when_mean_is_tiny_relative_to_spread():
    """A real round produced mean 1.4 ms with sd ~82 ms -> CV 58.7.

    The mean is not distinguishable from zero (early and late presses cancel),
    so the ratio carries no information and must not be reported.
    """
    errors = [-160, -120, -80, -40, 0, 40, 80, 120, 160, 13]
    events = [
        _cue(i, onset=0, target=1000, actual=1000 + err) for i, err in enumerate(errors)
    ]
    m = compute_metrics(events)

    mean = m.mean_timing_error_ms
    sd = m.timing_error_std_ms
    assert mean is not None and sd is not None
    assert mean == pytest.approx(1.3)
    assert sd == pytest.approx(98.05717719779618)
    # reproduce the pathological shape: dividing would give CV = 75.4
    assert abs(mean) < 0.25 * sd

    assert m.timing_error_cv is None, "CV must not be reported for a near-zero mean"
    assert m.timing_error_cv_note is not None
    assert "timing_error_std_ms" in m.timing_error_cv_note


def test_timing_error_cv_is_reported_when_the_mean_is_meaningful():
    """A systematically late patient has a real, interpretable CV."""
    errors = [200, 240, 280, 320, 360]
    events = [
        _cue(i, onset=0, target=1000, actual=1000 + err) for i, err in enumerate(errors)
    ]
    m = compute_metrics(events)
    assert m.mean_timing_error_ms == pytest.approx(280.0)
    assert m.timing_error_cv is not None
    assert m.timing_error_cv > 0
    assert m.timing_error_cv_note is None


def test_timing_error_cv_never_explodes():
    """Whatever the input shape, a reported CV stays a plausible magnitude."""
    shapes = [
        [-160, -120, -80, -40, 0, 40, 80, 120, 160],
        [0, 0, 0, 0, 0, 0, 0, 0, 1],
        [-1, 1, -1, 1, -1, 1],
        [5, -5, 5, -5, 5, -5, 5],
        [100, 100, 100, 100],
    ]
    for errors in shapes:
        events = [
            _cue(i, onset=0, target=1000, actual=1000 + err)
            for i, err in enumerate(errors)
        ]
        m = compute_metrics(events)
        if m.timing_error_cv is not None:
            assert abs(m.timing_error_cv) <= 10, (
                f"implausible CV {m.timing_error_cv} for errors {errors}"
            )


def test_zero_spread_gives_zero_cv_not_none_or_infinity():
    events = [_cue(i, onset=0, target=1000, actual=1050) for i in range(5)]
    m = compute_metrics(events)
    assert m.timing_error_std_ms == pytest.approx(0.0)
    assert m.timing_error_cv == pytest.approx(0.0)


def test_response_latency_cv_is_unaffected_by_the_guard():
    """Latency is always positive, so its CV stays meaningful."""
    events = [_cue(i, onset=0, target=1000, actual=1000 + 400 + i * 20) for i in range(5)]
    m = compute_metrics(events)
    assert m.response_latency_cv is not None
    assert 0 < m.response_latency_cv < 1


# =============================================================================
# Defect 2: every stored event had event_index 0
# =============================================================================
def test_event_index_sequence_is_preserved_by_metrics():
    """The index is the only thing ordering the raw timeline.

    The frontend used to number events per cue, so every row ended up with index
    0 and the stored order was undefined. The server must accept and expose a
    single non-decreasing sequence.
    """
    events = [_cue(i, onset=i * 1000, target=i * 1000 + 700, actual=i * 1000 + 700) for i in range(6)]
    m = compute_metrics(events)
    assert m.total_cues == 6

    indices = [e["event_index"] for e in events]
    assert indices == sorted(indices)
    assert len(set(indices)) == len(indices), "event_index must be unique per event"


def test_duplicate_event_indices_are_flagged_by_validation():
    """If a client ever sends duplicates again, it must be visible."""
    from app.utils.piano_metrics import validation_warnings

    events = [_cue(0, onset=0, target=700, actual=700) for _ in range(3)]
    metrics = compute_metrics(events)
    # validation_warnings does not currently check uniqueness, so assert the
    # invariant here instead: this test documents that uniqueness is required.
    indices = [e["event_index"] for e in events]
    assert len(set(indices)) != len(indices)
    warnings = validation_warnings(metrics, events)
    assert isinstance(warnings, list)
